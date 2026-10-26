import traceback

import frappe
import requests
from frappe.utils import add_to_date, nowdate

DATE_BASED_EVENTS = ("Days Before", "Days After")

METHOD_TO_EVENT = {
	"after_insert": "New",
	"on_submit": "Submit",
	"on_cancel": "Cancel",
	"on_update": "Update",
	"on_change": "Value Change",
}


def handle_event(doc, method, *args, context=None, **kwargs):
	"""Send the Teams Alerts that match a document event.

	Standard hooks map to their event name. Any other method name is a
	"Method" event, like in Notification. Such a method reaches this handler
	only when an app routes it here in its doc_events, and it can pass
	`context` through doc.run_method(method, context={...}).
	"""
	send_alert_on = METHOD_TO_EVENT.get(method, "Method")

	# Skip internal Teams Alert / Teams Webhook saves to avoid infinite loops
	if doc.doctype in ("Teams Alert", "Teams Webhook"):
		return

	# Guard: table may not exist during initial install / migrate
	if not frappe.db.table_exists("Teams Alert"):
		return

	filters = {
		"enabled": 1,
		"document_type": doc.doctype,
		"send_alert_on": send_alert_on,
	}
	if send_alert_on == "Method":
		filters["method"] = method

	alerts = frappe.get_all("Teams Alert", filters=filters, pluck="name")

	if not alerts:
		return

	for alert_name in alerts:
		alert = frappe.get_doc("Teams Alert", alert_name)
		if _evaluate_condition(alert, doc, context):
			_enqueue_send_alert(alert_name, doc.doctype, doc.name, context)


def trigger_daily_alerts():
	"""Send "Days Before" / "Days After" alerts. Same as Notification's daily trigger."""
	if not frappe.db.table_exists("Teams Alert"):
		return

	alerts = frappe.get_all(
		"Teams Alert",
		filters={"enabled": 1, "send_alert_on": ("in", DATE_BASED_EVENTS)},
		pluck="name",
	)
	for alert_name in alerts:
		try:
			alert = frappe.get_doc("Teams Alert", alert_name)
			for docname in _get_documents_for_today(alert):
				_enqueue_send_alert(alert_name, alert.document_type, docname)
		except Exception:
			frappe.log_error(
				title=f"Teams Alert Daily Trigger Error: {alert_name}",
				message=traceback.format_exc(),
			)


def _get_documents_for_today(alert):
	"""Names of documents whose reference date is today ± days_in_advance.

	Mirrors Notification.get_documents_for_today.
	"""
	diff_days = alert.days_in_advance or 0
	if alert.send_alert_on == "Days After":
		diff_days = -diff_days

	reference_date = add_to_date(nowdate(), days=diff_days)
	docnames = frappe.get_all(
		alert.document_type,
		filters=[
			[alert.date_changed, ">=", reference_date + " 00:00:00.000000"],
			[alert.date_changed, "<=", reference_date + " 23:59:59.000000"],
		],
		pluck="name",
	)

	return [
		docname
		for docname in docnames
		if _evaluate_condition(alert, frappe.get_doc(alert.document_type, docname))
	]


def _enqueue_send_alert(alert_name, doctype, docname, context=None):
	frappe.enqueue(
		"teams_alert.teams_alert.teams_alert_engine.send_alert",
		alert_name=alert_name,
		doctype=doctype,
		docname=docname,
		context=context,
		queue="default",
		now=frappe.flags.in_test,
		enqueue_after_commit=True,
	)


def get_context(doc, context=None):
	"""Condition context: `doc` and `nowdate` like Notification, plus `context`.

	`frappe` comes from the safe_eval globals, which already include
	frappe.utils (the only part Notification exposes).
	"""
	return {**(context or {}), "doc": doc, "nowdate": nowdate}


def _evaluate_condition(alert, doc, context=None):
	if not alert.condition:
		return True
	try:
		return bool(frappe.safe_eval(alert.condition.strip(), None, get_context(doc, context)))
	except Exception:
		frappe.log_error(
			title=f"Teams Alert Condition Error: {alert.name}",
			message=traceback.format_exc(),
		)
		return False


def send_alert(alert_name, doctype, docname, context=None):
	try:
		if not frappe.db.exists("Teams Alert", alert_name):
			return
		alert = frappe.get_doc("Teams Alert", alert_name)

		if not frappe.db.exists(doctype, docname):
			return
		doc = frappe.get_doc(doctype, docname)

		webhook = frappe.get_doc("Teams Webhook", alert.teams_webhook)

		if not webhook.enabled:
			return

		context = {**(context or {}), "doc": doc, "alert": alert}
		subject = frappe.render_template(alert.subject or "", context)
		# Keep rendered HTML — card builder will parse it into paragraphs
		message_html = frappe.render_template(alert.message or "", context)

		payload = _build_adaptive_card(subject, message_html, doctype, docname)

		response = requests.post(
			webhook.webhook_url.strip(),
			json=payload,
			headers={"Content-Type": "application/json"},
			timeout=15,
		)
		response.raise_for_status()

		_set_alert_status(alert_name, "OK", None)

	except Exception:
		error_msg = traceback.format_exc()
		frappe.log_error(
			title=f"Teams Alert Send Error: {alert_name}",
			message=error_msg,
		)
		_set_alert_status(alert_name, "Failed", error_msg[:500])


def _html_to_paragraphs(html):
	"""Parse Quill/Text Editor HTML into a list of plain-text lines.

	Each <p> or <div> becomes one entry; empty tags become empty strings
	so the caller can insert spacing between real paragraphs.
	"""
	from html.parser import HTMLParser

	class _Parser(HTMLParser):
		def __init__(self):
			super().__init__()
			self.lines = []
			self._buf = []

		def _flush(self):
			self.lines.append("".join(self._buf).strip())
			self._buf = []

		def handle_starttag(self, tag, attrs):
			if tag == "br":
				self._flush()

		def handle_endtag(self, tag):
			if tag in ("p", "div", "li"):
				self._flush()

		def handle_data(self, data):
			self._buf.append(data)

	try:
		p = _Parser()
		p.feed(html or "")
		if p._buf:
			p._flush()
		return p.lines
	except Exception:
		import re

		text = re.sub(r"<[^>]+>", " ", html or "")
		return [re.sub(r"\s+", " ", text).strip()]


def _build_adaptive_card(subject, message_html, doctype, docname):
	site_url = frappe.utils.get_url()
	doctype_slug = doctype.lower().replace(" ", "-")
	doc_url = f"{site_url}/app/{doctype_slug}/{docname}"

	body = [
		{
			"type": "Container",
			"style": "accent",
			"bleed": True,
			"items": [
				{
					"type": "TextBlock",
					"text": subject or "(no subject)",
					"weight": "Bolder",
					"size": "Medium",
					"color": "Dark",
					"wrap": True,
				},
				{
					"type": "TextBlock",
					"text": f"{doctype}  ·  {docname}",
					"size": "Small",
					"color": "Dark",
					"isSubtle": True,
					"spacing": "None",
					"wrap": True,
				},
			],
		},
	]

	if message_html:
		lines = _html_to_paragraphs(message_html)
		first = True
		for line in lines:
			if not line:
				continue
			block = {
				"type": "TextBlock",
				"text": line,
				"wrap": True,
				"spacing": "Medium" if first else "None",
			}
			body.append(block)
			first = False

	return {
		"type": "message",
		"attachments": [
			{
				"contentType": "application/vnd.microsoft.card.adaptive",
				"content": {
					"$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
					"type": "AdaptiveCard",
					"version": "1.4",
					"body": body,
					"actions": [
						{
							"type": "Action.OpenUrl",
							"title": "Open in ERPNext",
							"url": doc_url,
						}
					],
				},
			}
		],
	}


def _set_alert_status(alert_name, status, error_msg):
	try:
		update = {"last_status": status, "last_error": error_msg or ""}
		if status == "OK":
			update["last_sent"] = frappe.utils.now()
		frappe.db.set_value("Teams Alert", alert_name, update)
	except Exception:
		pass

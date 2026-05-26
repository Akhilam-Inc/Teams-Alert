import traceback

import frappe
import requests

METHOD_TO_EVENT = {
	"after_insert": "New",
	"on_submit": "Submit",
	"on_cancel": "Cancel",
	"on_update": "Update",
	"on_change": "Value Change",
}


def handle_event(doc, method):
	send_alert_on = METHOD_TO_EVENT.get(method)
	if not send_alert_on:
		return

	# Skip internal Teams Alert / Teams Webhook saves to avoid infinite loops
	if doc.doctype in ("Teams Alert", "Teams Webhook"):
		return

	# Guard: table may not exist during initial install / migrate
	if not frappe.db.table_exists("Teams Alert"):
		return

	alerts = frappe.get_all(
		"Teams Alert",
		filters={
			"enabled": 1,
			"document_type": doc.doctype,
			"send_alert_on": send_alert_on,
		},
		pluck="name",
	)

	if not alerts:
		return

	for alert_name in alerts:
		alert = frappe.get_doc("Teams Alert", alert_name)
		if _evaluate_condition(alert, doc):
			frappe.enqueue(
				"teams_alert.teams_alert.teams_alert_engine.send_alert",
				alert_name=alert_name,
				doctype=doc.doctype,
				docname=doc.name,
				queue="default",
				now=frappe.flags.in_test,
				enqueue_after_commit=True,
			)


def _evaluate_condition(alert, doc):
	if not alert.condition:
		return True
	try:
		return bool(frappe.safe_eval(alert.condition.strip(), eval_globals=None, eval_locals={"doc": doc}))
	except Exception:
		frappe.log_error(
			title=f"Teams Alert Condition Error: {alert.name}",
			message=traceback.format_exc(),
		)
		return False


def send_alert(alert_name, doctype, docname):
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

		context = {"doc": doc, "alert": alert}
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

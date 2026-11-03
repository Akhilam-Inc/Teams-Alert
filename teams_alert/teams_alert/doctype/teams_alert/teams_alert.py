import frappe
from frappe.model.document import Document

from teams_alert.teams_alert.teams_alert_engine import DATE_BASED_EVENTS


class TeamsAlert(Document):
	def validate(self):
		self.validate_event_fields()
		self.validate_personal_chat()

		if self.condition:
			try:
				compile(self.condition.strip(), "<condition>", "eval")
			except SyntaxError as e:
				frappe.throw(f"Condition has a syntax error: {e}")

		if self.subject:
			try:
				frappe.render_template(self.subject, {"doc": frappe._dict()})
			except Exception as e:
				frappe.throw(f"Subject template error: {e}")

	def validate_event_fields(self):
		if self.send_alert_on == "Method" and not self.method:
			frappe.throw("Please specify which method to trigger")

		if self.send_alert_on in DATE_BASED_EVENTS:
			if not self.date_changed:
				frappe.throw("Please specify which date field must be checked")
			if self.date_changed not in _date_fields(self.document_type):
				frappe.throw(f"{self.date_changed} is not a Date or Datetime field of {self.document_type}")

	def validate_personal_chat(self):
		if not self.send_to_personal_chat:
			if not self.teams_webhook:
				frappe.throw("Teams Webhook is required unless Send to Employee's Personal Chat is ticked")
			return
		if self.document_type != "Employee" and not frappe.get_meta(self.document_type).has_field("employee"):
			frappe.throw(
				"Send to Employee's Personal Chat needs Document Type Employee or a document type with an employee field"
			)


def _date_fields(doctype):
	meta = frappe.get_meta(doctype)
	fields = [df.fieldname for df in meta.fields if df.fieldtype in ("Date", "Datetime")]
	return [*fields, "creation", "modified"]

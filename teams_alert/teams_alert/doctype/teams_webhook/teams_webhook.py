import frappe
import requests
from frappe.model.document import Document
from frappe.utils import now

from teams_alert.teams_alert.teams_alert_engine import _post_to_webhook


class TeamsWebhook(Document):
	def validate(self):
		if self.webhook_url and not self.webhook_url.strip().startswith("https://"):
			frappe.throw("Webhook URL must start with https://")
		self.validate_personal_webhook()

	def validate_personal_webhook(self):
		"""At most one enabled personal webhook per employee."""
		if not (self.employee and self.enabled):
			return
		existing = frappe.db.get_value(
			"Teams Webhook",
			{"employee": self.employee, "enabled": 1, "name": ("!=", self.name)},
		)
		if existing:
			frappe.throw(f"Employee {self.employee} already has an enabled personal webhook: {existing}")

	@frappe.whitelist()
	def send_test_message(self):
		site = frappe.local.site
		timestamp = now()

		payload = {
			"type": "message",
			"attachments": [
				{
					"contentType": "application/vnd.microsoft.card.adaptive",
					"content": {
						"$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
						"type": "AdaptiveCard",
						"version": "1.4",
						"body": [
							{
								"type": "TextBlock",
								"text": "Test Message from ERPNext",
								"weight": "Bolder",
								"size": "Medium",
								"wrap": True,
							},
							{
								"type": "TextBlock",
								"text": f"Site: {site} — {timestamp}",
								"wrap": True,
							},
						],
					},
				}
			],
		}

		try:
			_post_to_webhook(self.webhook_url, payload)
			if frappe.conf.get("teams_alert_dry_run"):
				frappe.msgprint("Dry run is on: the test message was logged, not sent.", alert=True)
			else:
				frappe.msgprint("Test message sent successfully to Teams!", alert=True)
		except requests.exceptions.RequestException as e:
			frappe.throw(f"Failed to send test message: {e}")

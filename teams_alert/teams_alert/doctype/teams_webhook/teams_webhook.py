import frappe
import requests
from frappe.model.document import Document
from frappe.utils import now


class TeamsWebhook(Document):
	def validate(self):
		if self.webhook_url and not self.webhook_url.strip().startswith("https://"):
			frappe.throw("Webhook URL must start with https://")
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
			response = requests.post(
				self.webhook_url.strip(),
				json=payload,
				headers={"Content-Type": "application/json"},
				timeout=15,
			)
			response.raise_for_status()
			frappe.msgprint("Test message sent successfully to Teams!", alert=True)
		except requests.exceptions.RequestException as e:
			frappe.throw(f"Failed to send test message: {e}")

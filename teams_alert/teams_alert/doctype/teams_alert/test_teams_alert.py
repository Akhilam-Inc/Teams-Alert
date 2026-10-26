# Copyright (c) 2026, Raj Tailor and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from teams_alert.teams_alert.teams_alert_engine import handle_event, trigger_daily_alerts

WEBHOOK = "_Test Teams Webhook"


class TestTeamsAlert(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Teams Webhook", WEBHOOK):
			frappe.get_doc(
				{
					"doctype": "Teams Webhook",
					"label": WEBHOOK,
					"enabled": 1,
					"webhook_url": "https://example.com/teams-webhook",
				}
			).insert()

	def setUp(self):
		# Records of earlier tests in this class are not rolled back yet.
		frappe.db.delete("Teams Alert", {"title": ("like", "_Test Alert %")})
		frappe.db.delete("ToDo", {"description": "_Test Teams Alert"})
		self.post = patch("teams_alert.teams_alert.teams_alert_engine.requests.post").start()
		self.addCleanup(patch.stopall)

	def _alert(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Teams Alert",
				"title": f"_Test Alert {frappe.generate_hash(length=6)}",
				"document_type": "ToDo",
				"teams_webhook": WEBHOOK,
				"enabled": 1,
				**values,
			}
		).insert()

	def _posted_subjects(self):
		return [
			call.kwargs["json"]["attachments"][0]["content"]["body"][0]["items"][0]["text"]
			for call in self.post.call_args_list
		]

	def _todo(self, **values):
		return frappe.get_doc({"doctype": "ToDo", "description": "_Test Teams Alert", **values}).insert()

	# --- Method event ---

	def test_method_event_sends_matching_alert_with_context(self):
		self._alert(
			send_alert_on="Method",
			method="custom_reminder",
			condition="count > 1",
			subject="Reminder {{ count }} for {{ doc.description }}",
		)
		self._alert(send_alert_on="Method", method="other_method", subject="Other")
		todo = self._todo()

		handle_event(todo, "custom_reminder", context={"count": 2})

		self.assertEqual(self._posted_subjects(), ["Reminder 2 for _Test Teams Alert"])

	def test_method_event_condition_uses_context(self):
		self._alert(send_alert_on="Method", method="custom_reminder", condition="count > 1", subject="X")

		handle_event(self._todo(), "custom_reminder", context={"count": 1})

		self.post.assert_not_called()

	def test_run_method_reaches_method_alert(self):
		# send_payment_reminder is routed to Teams Alert in hooks.py.
		self._alert(
			send_alert_on="Method",
			method="send_payment_reminder",
			subject="Reminder {{ reminder_count }} sent",
		)

		self._todo().run_method("send_payment_reminder", context={"reminder_count": 3})

		self.assertEqual(self._posted_subjects(), ["Reminder 3 sent"])
		self.assertIn("/app/todo/", self.post.call_args.kwargs["json"]["attachments"][0]["content"]["actions"][0]["url"])

	def test_method_requires_method_name(self):
		with self.assertRaises(frappe.ValidationError):
			self._alert(send_alert_on="Method", subject="X")

	# --- Days Before / Days After ---

	def test_days_after_sends_for_matching_date(self):
		self._alert(
			send_alert_on="Days After",
			date_changed="date",
			days_in_advance=1,
			condition="doc.priority == 'High'",
			subject="Late: {{ doc.priority }}",
		)
		self._todo(date=add_days(today(), -1), priority="High")
		self._todo(date=add_days(today(), -1), priority="Low")
		self._todo(date=add_days(today(), -2), priority="High")

		trigger_daily_alerts()

		self.assertEqual(self._posted_subjects(), ["Late: High"])

	def test_days_before_sends_for_matching_date(self):
		self._alert(send_alert_on="Days Before", date_changed="date", days_in_advance=2, subject="Soon")
		self._todo(date=add_days(today(), 2))
		self._todo(date=add_days(today(), 1))

		trigger_daily_alerts()

		self.assertEqual(self._posted_subjects(), ["Soon"])

	def test_date_event_requires_date_field(self):
		with self.assertRaises(frappe.ValidationError):
			self._alert(send_alert_on="Days After", subject="X")
		with self.assertRaises(frappe.ValidationError):
			self._alert(send_alert_on="Days After", date_changed="description", subject="X")

	# --- existing events ---

	def test_document_event_still_works_without_context(self):
		self._alert(send_alert_on="New", condition="doc.priority == 'High'", subject="New {{ doc.priority }}")

		self._todo(priority="High")
		self._todo(priority="Low")

		self.assertEqual(self._posted_subjects(), ["New High"])

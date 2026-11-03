import frappe

# Default Teams Alerts fired by teams_alert.timesheet_alerts. Created once if missing;
# after that, subject, message, condition and enabled are edited in the Teams Alert UI.
DEFAULT_ALERTS = [
	{
		"title": "Timesheet Reminder",
		"method": "send_timesheet_reminder",
		"subject": "Timesheet reminder",
		"message": (
			"<p>Hi {{ doc.employee_name }}, you have not filed your timesheet for: {{ missed_dates_text }}.</p>"
			"<p>Please fill it in today.</p>"
		),
	},
	{
		"title": "Timesheet Final Reminder",
		"method": "send_timesheet_final_reminder",
		"subject": "Final timesheet reminder for this week",
		"message": (
			"<p>Hi {{ doc.employee_name }},</p>"
			"{% if missed_dates %}<p>Your timesheet is still missing for: {{ missed_dates_text }}.</p>{% endif %}"
			"{% if deduction_days %}<p>Salary deduction days so far in {{ month_label }}: "
			"{{ total_deduction_days }}</p>"
			"{% for d in deduction_days %}<p>{{ frappe.utils.formatdate(d.date) }}: {{ d.reason }} "
			"({{ d.value }})</p>{% endfor %}{% endif %}"
		),
	},
	{
		"title": "Salary Deduction Alert",
		"method": "send_salary_deduction_alert",
		"subject": "Salary deduction days for {{ month_label }}",
		"message": (
			"<p>Hi {{ doc.employee_name }}, you have {{ total_deduction_days }} salary deduction day(s) "
			"in {{ month_label }}:</p>"
			"{% for d in deduction_days %}<p>{{ frappe.utils.formatdate(d.date) }}: {{ d.reason }} "
			"({{ d.value }})</p>{% endfor %}"
			"<p>Please contact HR if this is not correct.</p>"
		),
	},
]


def execute():
	for alert in DEFAULT_ALERTS:
		if frappe.db.exists("Teams Alert", alert["title"]):
			continue
		frappe.get_doc(
			{
				"doctype": "Teams Alert",
				"document_type": "Employee",
				"send_alert_on": "Method",
				"send_to_personal_chat": 1,
				"enabled": 1,
				**alert,
			}
		).insert(ignore_permissions=True)

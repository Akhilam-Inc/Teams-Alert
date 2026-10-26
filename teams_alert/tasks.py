import traceback
import datetime
import requests
import frappe
from frappe.utils import today, get_datetime
from teams_alert.teams_alert.teams_alert_engine import (
	_set_alert_status,
	_build_adaptive_card,
)
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday


def send_missing_checkin_alert():
	try:
		alerts = frappe.get_all(
			"Teams Alert",
			filters={
				"enabled": 1,
				"document_type": "Employee Checkin",
				"send_alert_on": "Daily Attendance Check",
			},
			pluck="name",
		)
		for alert_name in alerts:
			try:
				run_attendance_check_for_alert(alert_name)
			except Exception:
				error_msg = traceback.format_exc()
				frappe.log_error(
					title=f"Attendance Check Alert Failed: {alert_name}",
					message=error_msg,
				)
				_set_alert_status(alert_name, "Failed", error_msg[:500])
	except Exception:
		frappe.log_error(
			title="Attendance Check Scheduler Job Failed",
			message=traceback.format_exc(),
		)


def run_attendance_check_for_alert(alert_name):
	alert = frappe.get_doc("Teams Alert", alert_name)
	today_date = today()

	# Idempotency Check
	if alert.last_sent:
		last_sent_date = get_datetime(alert.last_sent).strftime("%Y-%m-%d")
		if last_sent_date == today_date:
			frappe.logger().info(
				f"Teams Alert {alert_name} was already sent today. Skipping."
			)
			return

	# Working Day Check
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		companies = frappe.get_all("Company", limit=1, pluck="name")
		if companies:
			company = companies[0]

	holiday_list = None
	if company:
		holiday_list = frappe.get_cached_value(
			"Company", company, "default_holiday_list"
		)

	is_today_holiday = False

	if holiday_list:
		is_today_holiday = is_holiday(holiday_list, today_date)
	else:
		# Sunday is the only weekly non-working day.
		date_obj = datetime.datetime.strptime(today_date, "%Y-%m-%d").date()

		if date_obj.weekday() == 6:
			is_today_holiday = True

	if is_today_holiday:
		frappe.logger().info(
			f"Today ({today_date}) is a holiday or Sunday. Skipping Teams Alert."
		)
		return

	# Fetch Active Employees
	employees = frappe.get_all(
		"Employee", filters={"status": "Active"}, fields=["name", "employee_name"]
	)
	if not employees:
		frappe.logger().info("No active employees found to monitor.")
		return

	employee_ids = [emp.name for emp in employees]

	# Query today's check-ins in a single batch (avoid N+1)
	checkins = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": ["in", employee_ids],
			"time": ["between", [f"{today_date} 00:00:00", f"{today_date} 23:59:59"]],
		},
		fields=["employee"],
	)
	checked_in_employees = {c.employee for c in checkins}

	# Query today's approved leave applications in a single batch (avoid N+1)
	leaves = frappe.get_all(
		"Leave Application",
		filters={
			"employee": ["in", employee_ids],
			"status": "Approved",
			"docstatus": 1,
			"from_date": ["<=", today_date],
			"to_date": [">=", today_date],
		},
		fields=["employee"],
	)
	on_leave_employees = {l.employee for l in leaves}

	# Identify employees missing check-in
	missing_employees = []
	for emp in employees:
		if emp.name not in checked_in_employees and emp.name not in on_leave_employees:
			missing_employees.append(emp.employee_name or emp.name)

	if not missing_employees:
		frappe.logger().info(f"No employees missing check-in today ({today_date}).")
		return

	# Retrieve Webhook configuration
	webhook = frappe.get_doc("Teams Webhook", alert.teams_webhook)
	if not webhook.enabled:
		frappe.logger().info(
			f"Teams Webhook {alert.teams_webhook} is disabled. Skipping."
		)
		return

	# Format the Teams notification message
	employee_bullets = "\n".join([f"• {name}" for name in missing_employees])

	context = {
		"alert": alert,
		"missing_employees": missing_employees,
		"date": today_date,
		"employee_bullets": employee_bullets,
	}

	subject = alert.subject or "⚠️ Missing Check-in Alert"
	try:
		subject = frappe.render_template(subject, context)
	except Exception:
		pass

	default_message = (
		"The following employees have not checked in today and are not on approved leave:\n\n"
		f"{employee_bullets}\n\n"
		f"Date: {today_date}\n"
		"Time checked: 10:45 AM"
	)

	message = alert.message or default_message
	try:
		message = frappe.render_template(message, context)
	except Exception:
		pass

	# Reuse existing adaptive card layout and sending mechanism
	payload = _build_adaptive_card(subject, message, "Employee Checkin", "")

	response = requests.post(
		webhook.webhook_url.strip(),
		json=payload,
		headers={"Content-Type": "application/json"},
		timeout=15,
	)
	response.raise_for_status()

	_set_alert_status(alert_name, "OK", None)

"""Scheduled timesheet / salary-deduction alerts to employees' personal Teams chats.

The jobs fire Method events on Employee (`doc.run_method(method, context=...)`);
the Teams Alert records for those methods decide subject, message and condition.
The timesheet, attendance and holiday logic lives in Akhilam Project Management.
"""

import traceback

import frappe
from frappe.utils import add_days, add_months, formatdate, get_first_day, get_last_day, getdate, today

from teams_alert.teams_alert.teams_alert_engine import get_personal_webhooks

DAILY_METHOD = "send_timesheet_reminder"
FINAL_METHOD = "send_timesheet_final_reminder"
MONTHLY_METHOD = "send_salary_deduction_alert"

AKHILAM_UTILS = "akhilam_project_management.utils"
SENT_MARKER = "Teams Alert {method} sent for {month}"


def send_daily_timesheet_reminders():
	"""Mon-Fri: remind about a missing timesheet on each employee's previous working day."""
	_run_job(DAILY_METHOD, _build_daily_contexts)


def send_saturday_final_reminders():
	"""Saturday: this week's (Mon-Fri) missed timesheets and month-to-date deduction days."""
	_run_job(FINAL_METHOD, _build_final_contexts)


def send_monthly_deduction_alerts():
	"""Days 1-7: previous month's deduction days, on each employee's first working day of the month."""
	_run_job(MONTHLY_METHOD, _build_monthly_contexts)


def _run_job(method, build_contexts):
	try:
		if not frappe.get_all(
			"Teams Alert",
			filters={
				"enabled": 1,
				"send_alert_on": "Method",
				"method": method,
				"document_type": "Employee",
			},
			limit=1,
		):
			return

		employees = _get_employees_with_personal_webhook()
		if not employees:
			return

		helpers = _load_akhilam_helpers()
		if not helpers:
			return

		run_date = getdate(today())
		holidays_today = helpers["get_holiday_dates"](employees, run_date, run_date)
		employees = [emp for emp in employees if str(run_date) not in holidays_today.get(emp, set())]
		if not employees:
			return

		contexts = build_contexts(employees, run_date, helpers)
	except Exception:
		frappe.log_error(title=f"Timesheet Alert Job Failed: {method}", message=traceback.format_exc())
		return

	for employee, context in contexts.items():
		try:
			frappe.get_doc("Employee", employee).run_method(method, context=context)
			if method == MONTHLY_METHOD:
				_mark_monthly_sent(employee, context["month_label"])
		except Exception:
			frappe.log_error(title=f"Timesheet Alert Failed: {employee}", message=traceback.format_exc())


def _get_employees_with_personal_webhook():
	active = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")
	webhooks = get_personal_webhooks(active)
	return [emp for emp in active if emp in webhooks]


def _load_akhilam_helpers():
	try:
		return {
			"get_holiday_dates": frappe.get_attr(f"{AKHILAM_UTILS}.holidays.get_holiday_dates"),
			"get_missed_timesheet_dates": frappe.get_attr(
				f"{AKHILAM_UTILS}.timesheet.get_missed_timesheet_dates"
			),
			"get_previous_working_days": frappe.get_attr(
				f"{AKHILAM_UTILS}.timesheet.get_previous_working_days"
			),
			"get_deduction_days": frappe.get_attr(f"{AKHILAM_UTILS}.attendance.get_deduction_days"),
		}
	except Exception:
		frappe.log_error(
			title="Timesheet Alert: Akhilam Project Management helpers unavailable",
			message=traceback.format_exc(),
		)
		return None


def _build_daily_contexts(employees, run_date, helpers):
	targets = helpers["get_previous_working_days"](employees, run_date)
	targets = {emp: day for emp, day in targets.items() if day}
	if not targets:
		return {}

	missed = helpers["get_missed_timesheet_dates"](
		list(targets), min(targets.values()), max(targets.values())
	)
	contexts = {}
	for emp, target in targets.items():
		missed_dates = [day for day in missed.get(emp, []) if day == target]
		if missed_dates:
			contexts[emp] = {
				"missed_dates": missed_dates,
				"missed_dates_text": _dates_text(missed_dates),
				"target_date": target,
			}
	return contexts


def _build_final_contexts(employees, run_date, helpers):
	week_start = add_days(run_date, -(run_date.weekday()))
	week_end = add_days(week_start, 4)  # Friday
	if week_end >= run_date:
		week_end = add_days(run_date, -1)
	month_start = get_first_day(run_date)
	yesterday = add_days(run_date, -1)

	missed = helpers["get_missed_timesheet_dates"](employees, week_start, week_end)
	deductions = (
		helpers["get_deduction_days"](employees, month_start, yesterday) if yesterday >= month_start else {}
	)

	contexts = {}
	for emp in employees:
		missed_dates = missed.get(emp, [])
		deduction_days = deductions.get(emp, [])
		if missed_dates or deduction_days:
			contexts[emp] = {
				"missed_dates": missed_dates,
				"missed_dates_text": _dates_text(missed_dates),
				"deduction_days": deduction_days,
				"total_deduction_days": _total(deduction_days),
				"month_label": _month_label(run_date),
			}
	return contexts


def _build_monthly_contexts(employees, run_date, helpers):
	month_start = get_first_day(run_date)
	first_week = helpers["get_holiday_dates"](employees, month_start, add_days(month_start, 6))
	already_sent = _get_monthly_sent(employees, _month_label(add_months(month_start, -1)))
	due = [
		emp
		for emp in employees
		if emp not in already_sent and _first_working_day(first_week.get(emp, set()), month_start) == run_date
	]
	if not due:
		return {}

	from_date = add_months(month_start, -1)
	to_date = get_last_day(from_date)
	deductions = helpers["get_deduction_days"](due, from_date, to_date)

	contexts = {}
	for emp in due:
		deduction_days = deductions.get(emp, [])
		total = _total(deduction_days)
		if total > 0:
			contexts[emp] = {
				"deduction_days": deduction_days,
				"total_deduction_days": total,
				"month_label": _month_label(from_date),
				"from_date": str(from_date),
				"to_date": str(to_date),
			}
	return contexts


def _first_working_day(holidays, month_start):
	for i in range(7):
		day = add_days(month_start, i)
		if str(day) not in holidays:
			return getdate(day)
	return None


def _get_monthly_sent(employees, month_label):
	"""Employees for whom the monthly alert was already fired for `month_label`."""
	return set(
		frappe.get_all(
			"Comment",
			filters={
				"comment_type": "Info",
				"reference_doctype": "Employee",
				"reference_name": ("in", employees),
				"content": SENT_MARKER.format(method=MONTHLY_METHOD, month=month_label),
			},
			pluck="reference_name",
		)
	)


def _mark_monthly_sent(employee, month_label):
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Employee",
			"reference_name": employee,
			"content": SENT_MARKER.format(method=MONTHLY_METHOD, month=month_label),
		}
	).insert(ignore_permissions=True)


def _dates_text(dates):
	return ", ".join(f"{formatdate(day)} ({getdate(day).strftime('%a')})" for day in dates)


def _month_label(date):
	return getdate(date).strftime("%B %Y")


def _total(deduction_days):
	return float(sum(day["value"] for day in deduction_days))

app_name = "teams_alert"
app_title = "Teams Alert"
app_publisher = "Raj Tailor"
app_description = "Frappe alert to Microsoft Team"
app_email = "raaj@akhilaminc.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "teams_alert",
# 		"logo": "/assets/teams_alert/logo.png",
# 		"title": "Teams Alert",
# 		"route": "/teams_alert",
# 		"has_permission": "teams_alert.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/teams_alert/css/teams_alert.css"
# app_include_js = "/assets/teams_alert/js/teams_alert.js"

# include js, css files in header of web template
# web_include_css = "/assets/teams_alert/css/teams_alert.css"
# web_include_js = "/assets/teams_alert/js/teams_alert.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "teams_alert/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "teams_alert/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "teams_alert.utils.jinja_methods",
# 	"filters": "teams_alert.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "teams_alert.install.before_install"
# after_install = "teams_alert.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "teams_alert.uninstall.before_uninstall"
# after_uninstall = "teams_alert.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "teams_alert.utils.before_app_install"
# after_app_install = "teams_alert.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "teams_alert.utils.before_app_uninstall"
# after_app_uninstall = "teams_alert.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "teams_alert.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "*": {
        "after_insert": "teams_alert.teams_alert.teams_alert_engine.handle_event",
        "on_submit": "teams_alert.teams_alert.teams_alert_engine.handle_event",
        "on_cancel": "teams_alert.teams_alert.teams_alert_engine.handle_event",
        "on_update": "teams_alert.teams_alert.teams_alert_engine.handle_event",
        "on_change": "teams_alert.teams_alert.teams_alert_engine.handle_event",
        # Methods for the "Method" event. Frappe passes a doc.run_method call
        # to doc_events only for the method names listed here.
        "send_payment_reminder": "teams_alert.teams_alert.teams_alert_engine.handle_event",
    }
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": ["teams_alert.teams_alert.teams_alert_engine.trigger_daily_alerts"],
    "cron": {"45 10 * * *": ["teams_alert.tasks.send_missing_checkin_alert"]},
}

# Testing
# -------

# before_tests = "teams_alert.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teams_alert.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "teams_alert.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["teams_alert.utils.before_request"]
# after_request = ["teams_alert.utils.after_request"]

# Job Events
# ----------
# before_job = ["teams_alert.utils.before_job"]
# after_job = ["teams_alert.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"teams_alert.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

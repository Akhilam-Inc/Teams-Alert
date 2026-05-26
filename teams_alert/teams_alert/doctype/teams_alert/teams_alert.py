import frappe
from frappe.model.document import Document


class TeamsAlert(Document):
	def validate(self):
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

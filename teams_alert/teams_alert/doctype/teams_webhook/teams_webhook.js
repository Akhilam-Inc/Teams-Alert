frappe.ui.form.on("Teams Webhook", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Send Test Message"), () => {
				frappe.call({
					doc: frm.doc,
					method: "send_test_message",
					freeze: true,
					freeze_message: __("Sending test message…"),
				});
			});
		}
	},
});

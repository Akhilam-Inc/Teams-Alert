frappe.ui.form.on("Teams Alert", {
	refresh(frm) {
		if (frm.doc.last_status) {
			const color = frm.doc.last_status === "OK" ? "green" : "red";
			frm.dashboard.set_headline(
				`<span style="color:${color}">Last status: ${frm.doc.last_status}</span>`
			);
		}
		frm.trigger("set_date_options");
	},

	document_type(frm) {
		frm.trigger("set_date_options");
	},

	// Same options as Notification's "Reference Date" field.
	set_date_options(frm) {
		if (!frm.doc.document_type) return;
		frappe.model.with_doctype(frm.doc.document_type, () => {
			const date_fields = frappe.get_meta(frm.doc.document_type).fields
				.filter((df) => ["Date", "Datetime"].includes(df.fieldtype))
				.map((df) => ({ label: `${__(df.label)} (${df.fieldname})`, value: df.fieldname }));
			const options = [
				{ label: __("Created On"), value: "creation" },
				{ label: __("Last Modified"), value: "modified" },
				...date_fields,
			];
			frm.set_df_property("date_changed", "options", [""].concat(options));
		});
	},
});

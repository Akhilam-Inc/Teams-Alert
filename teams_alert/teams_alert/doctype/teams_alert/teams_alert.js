frappe.ui.form.on("Teams Alert", {
	refresh(frm) {
		if (frm.doc.last_status) {
			const color = frm.doc.last_status === "OK" ? "green" : "red";
			frm.dashboard.set_headline(
				`<span style="color:${color}">Last status: ${frm.doc.last_status}</span>`
			);
		}
	},
});

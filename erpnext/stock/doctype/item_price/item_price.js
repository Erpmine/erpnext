// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Item Price", {
	onload: function (frm) {
		// Fetch price list details
		frm.add_fetch("price_list", "buying", "buying");
		frm.add_fetch("price_list", "selling", "selling");
		frm.add_fetch("price_list", "currency", "currency");

		// Fetch item details
		frm.add_fetch("item_code", "item_name", "item_name");
		frm.add_fetch("item_code", "item_group", "item_group");
		frm.add_fetch("item_code", "brand", "brand");
		frm.add_fetch("item_code", "description", "item_description");

		frm.set_df_property("bulk_import_help", "options",
			'<a href="#data-import-tool/Item Price">' + __("Import in Bulk") + '</a>');
	}
});

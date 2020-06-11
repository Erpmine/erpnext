# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint, today
from erpnext.stock.utils import update_included_uom_in_list_report

def execute(filters=None):
	filters = frappe._dict(filters or {})
	include_uom = filters.get("include_uom")
	columns = get_columns(filters)
	bin_list = get_bin_list(filters)
	item_map = get_item_map(filters.get("item_code"), include_uom)

	warehouse_company = {}
	data = []
	conversion_factors = []

	filtered_item_groups = []
	if filters.item_group:
		item_group_lft_rgt = frappe.db.get_value("Item Group", filters.item_group, fieldname=['lft', 'rgt'])
		if item_group_lft_rgt:
			filtered_item_groups = frappe.db.sql_list("select name from `tabItem Group` where lft >= %s and rgt <= %s",
				item_group_lft_rgt)

	for bin in bin_list:
		item = item_map.get(bin.item_code)

		if not item:
			# likely an item that has reached its end of life
			continue

		# item = item_map.setdefault(bin.item_code, get_item(bin.item_code))
		company = warehouse_company.setdefault(bin.warehouse,
			frappe.db.get_value("Warehouse", bin.warehouse, "company"))

		if filters.brand and filters.brand != item.brand:
			continue
			
		elif filters.item_group and item.item_group not in filtered_item_groups:
			continue

		elif filters.company and filters.company != company:
			continue

		alt_uom_size = item.alt_uom_size if filters.qty_field == "Contents Qty" and item.alt_uom else 1.0

		re_order_level = re_order_qty = 0

		for d in item.get("reorder_levels"):
			if d.warehouse == bin.warehouse:
				re_order_level = d.warehouse_reorder_level
				re_order_qty = d.warehouse_reorder_qty

		shortage_qty = re_order_level - flt(bin.projected_qty) if (re_order_level or re_order_qty) else 0

		row = [item.name, item.item_group, item.brand]

		if not cint(filters.get('consolidated')):
			row.append(bin.warehouse)

		row += [
			item.alt_uom or item.stock_uom if filters.qty_field == "Contents Qty" else item.stock_uom,
			bin.actual_qty * alt_uom_size,
			bin.planned_qty * alt_uom_size,
			bin.indented_qty * alt_uom_size,
			bin.ordered_qty * alt_uom_size,
			bin.reserved_qty * alt_uom_size,
			bin.reserved_qty_for_production * alt_uom_size,
			bin.reserved_qty_for_sub_contract * alt_uom_size,
			bin.projected_qty * alt_uom_size,
			re_order_level * alt_uom_size,
			re_order_qty * alt_uom_size,
			shortage_qty * alt_uom_size
		]
		data.append(row)

		if include_uom:
			conversion_factors.append(item.conversion_factor)

	update_included_uom_in_list_report(columns, data, include_uom, conversion_factors)
	return columns, data

def get_columns(filters):
	columns = [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 100},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 100},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 120},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		{"label": _("Actual Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Planned Qty"), "fieldname": "planned_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Requested Qty"), "fieldname": "indented_qty", "fieldtype": "Float", "width": 110, "convertible": "qty"},
		{"label": _("Ordered Qty"), "fieldname": "ordered_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Reserved Qty"), "fieldname": "reserved_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Reserved Qty for Production"), "fieldname": "reserved_qty_for_production", "fieldtype": "Float",
			"width": 100, "convertible": "qty"},
		{"label": _("Reserved for sub contracting"), "fieldname": "reserved_qty_for_sub_contract", "fieldtype": "Float",
			"width": 100, "convertible": "qty"},
		{"label": _("Projected Qty"), "fieldname": "projected_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Reorder Level"), "fieldname": "re_order_level", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Reorder Qty"), "fieldname": "re_order_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Shortage Qty"), "fieldname": "shortage_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"}
	]

	if cint(filters.get('consolidated')):
		columns = list(filter(lambda d: d.get('fieldname') != 'warehouse', columns))

	return columns

def get_bin_list(filters):
	conditions = []
	
	if filters.item_code:
		conditions.append("item_code = '%s' "%filters.item_code)
		
	if filters.warehouse:
		warehouse_details = frappe.db.get_value("Warehouse", filters.warehouse, ["lft", "rgt"], as_dict=1)

		if warehouse_details:
			conditions.append(" exists (select name from `tabWarehouse` wh \
				where wh.lft >= %s and wh.rgt <= %s and bin.warehouse = wh.name)"%(warehouse_details.lft,
				warehouse_details.rgt))

	if cint(filters.get('consolidated')):
		group_fields = "item_code"
	else:
		group_fields = "item_code, warehouse"

	bin_list = frappe.db.sql("""
		select 
			item_code, warehouse,
			sum(actual_qty) as actual_qty, sum(planned_qty) as planned_qty, sum(indented_qty) as indented_qty,
			sum(ordered_qty) as ordered_qty, sum(reserved_qty) as reserved_qty,
			sum(reserved_qty_for_production) as reserved_qty_for_production,
			sum(reserved_qty_for_sub_contract) as reserved_qty_for_sub_contract,
			sum(projected_qty) as projected_qty
		from tabBin bin
		{conditions}
		group by {group_fields}
		order by {group_fields}
	""".format(conditions=" where " + " and ".join(conditions) if conditions else "", group_fields=group_fields), as_dict=1)

	return bin_list

def get_item_map(item_code, include_uom):
	"""Optimization: get only the item doc and re_order_levels table"""

	condition = ""
	if item_code:
		condition = 'and item_code = "{0}"'.format(frappe.db.escape(item_code, percent=False))

	cf_field = cf_join = ""
	if include_uom:
		cf_field = ", ucd.conversion_factor"
		cf_join = "left join `tabUOM Conversion Detail` ucd on ucd.parent=item.name and ucd.uom=%(include_uom)s"

	items = frappe.db.sql("""
		select item.name, item.item_name, item.description, item.item_group, item.brand,
		item.stock_uom, item.alt_uom, item.alt_uom_size {cf_field}
		from `tabItem` item
		{cf_join}
		where item.is_stock_item = 1
		and item.disabled=0
		{condition}
		and (item.end_of_life > %(today)s or item.end_of_life is null or item.end_of_life='0000-00-00')
		and exists (select name from `tabBin` bin where bin.item_code=item.name)"""\
		.format(cf_field=cf_field, cf_join=cf_join, condition=condition),
		{"today": today(), "include_uom": include_uom}, as_dict=True)

	condition = ""
	if item_code:
		condition = 'where parent="{0}"'.format(frappe.db.escape(item_code, percent=False))

	reorder_levels = frappe._dict()
	for ir in frappe.db.sql("""select * from `tabItem Reorder` {condition}""".format(condition=condition), as_dict=1):
		if ir.parent not in reorder_levels:
			reorder_levels[ir.parent] = []

		reorder_levels[ir.parent].append(ir)

	item_map = frappe._dict()
	for item in items:
		item["reorder_levels"] = reorder_levels.get(item.name) or []
		item_map[item.name] = item

	return item_map

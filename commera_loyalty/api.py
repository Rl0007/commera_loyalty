import frappe
from frappe import _
from frappe.utils.data import cint, cstr

from commera_loyalty.loyalty import MANUAL_ADJUSTMENT, get_points


@frappe.whitelist(methods=["GET"])
def get_ledger(customer: str | None = None, start: int = 0, page_length: int = 20) -> dict:
	filters = {"customer": customer} if customer else {}
	rows = frappe.get_list(
		"Loyalty Ledger Entry",
		filters=filters,
		fields=["name", "creation", "customer", "sales_order", "reason", "points"],
		order_by="creation desc",
		start=cint(start),
		page_length=cint(page_length),
	)
	totals_by_reason = frappe.get_list(
		"Loyalty Ledger Entry",
		filters=filters,
		fields=["reason", {"SUM": "points", "as": "points"}, {"COUNT": "*", "as": "count"}],
		group_by="reason",
		order_by="reason asc",
	)
	customers = frappe.get_list(
		"Loyalty Ledger Entry",
		fields=["customer"],
		group_by="customer",
		order_by="customer asc",
		pluck="customer",
	)
	return {
		"rows": rows,
		"total": sum(cint(row.count) for row in totals_by_reason),
		"issued": sum(cint(row.points) for row in totals_by_reason if cint(row.points) > 0),
		"reversed": -sum(cint(row.points) for row in totals_by_reason if cint(row.points) < 0),
		"balance": get_points(customer) if customer else None,
		"customers": customers,
	}


@frappe.whitelist(methods=["GET"])
def get_top_customers(start: int = 0, page_length: int = 20) -> dict:
	rows = frappe.get_list(
		"Loyalty Ledger Entry",
		fields=[
			"customer",
			{"SUM": "points", "as": "balance"},
			{"COUNT": "*", "as": "entries"},
			{"MAX": "creation", "as": "last_activity"},
		],
		group_by="customer",
		order_by="balance desc",
		start=cint(start),
		page_length=cint(page_length),
	)
	customer_names = dict(
		frappe.get_all(
			"Customer",
			filters={"name": ["in", [row.customer for row in rows]]},
			fields=["name", "customer_name"],
			as_list=True,
		)
	)
	for row in rows:
		row.customer_name = customer_names.get(row.customer) or row.customer
	customers = frappe.get_list(
		"Loyalty Ledger Entry", fields=["customer"], group_by="customer", pluck="customer"
	)
	return {"rows": rows, "total": len(customers)}


@frappe.whitelist(methods=["GET"])
def get_order_points(sales_order: str) -> dict:
	frappe.has_permission("Sales Order", "read", sales_order, throw=True)
	rows = frappe.get_list(
		"Loyalty Ledger Entry",
		filters={"sales_order": sales_order},
		fields=["name", "creation", "reason", "note", "points"],
		order_by="creation asc",
	)
	return {
		"rows": rows,
		"earned": sum(cint(row.points) for row in rows if cint(row.points) > 0),
		"reversed": -sum(cint(row.points) for row in rows if cint(row.points) < 0),
	}


@frappe.whitelist(methods=["POST"])
def adjust_points(sales_order: str, points: int, note: str) -> dict:
	frappe.has_permission("Sales Order", "read", sales_order, throw=True)
	points = cint(points)
	note = cstr(note).strip()
	if not points:
		frappe.throw(_("Enter the points to add, or a negative number to take away."))
	if not note:
		frappe.throw(_("Say why the points are changing."))

	customer = frappe.db.get_value("Sales Order", sales_order, "customer")
	balance = get_points(customer)
	if balance + points < 0:
		frappe.throw(_("{0} only has {1} points.").format(customer, balance))

	ledger_entry = frappe.new_doc("Loyalty Ledger Entry")
	ledger_entry.update(
		{
			"customer": customer,
			"sales_order": sales_order,
			"points": points,
			"reason": MANUAL_ADJUSTMENT,
			"note": note,
		}
	)
	ledger_entry.insert()
	return {"name": ledger_entry.name, "points": points, "balance": balance + points}

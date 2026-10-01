import frappe
from commera.core import get_customer_contact
from commera.sdk.events import CommeraEvent
from erpnext.controllers.website_list_for_contact import get_parents_for_user
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Sum
from frappe.utils.data import cint, flt

CURRENCY_UNITS_PER_POINT = 10


def on_order_paid(event: CommeraEvent):
	if is_event_recorded(event.id):
		return

	order = frappe.db.get_value("Sales Order", event.sales_order, ["customer", "net_total"], as_dict=True)
	points = int(flt(order.net_total) // CURRENCY_UNITS_PER_POINT)
	if points > 0:
		save_ledger_entry(event, order.customer, points, "Order Paid")


def on_order_refunded(event: CommeraEvent):
	if is_event_recorded(event.id):
		return

	order = frappe.db.get_value(
		"Sales Order",
		event.sales_order,
		["customer", "currency", "rounded_total", "grand_total", "base_rounded_total", "base_grand_total"],
		as_dict=True,
	)
	ledger_entries = get_order_ledger_entries(event.sales_order)
	awarded_points = sum(entry.points for entry in ledger_entries if entry.points > 0)
	reversed_points = -sum(entry.points for entry in ledger_entries if entry.points < 0)
	refund_amount = flt(event.data.get("amount"))
	refunded_amount = sum(flt(entry.refunded_amount) for entry in ledger_entries) + refund_amount

	order_total = get_order_total(order, event.data.get("currency"))
	refunded_share = min(refunded_amount / order_total, 1) if order_total else 1
	# Cumulative, so two partial refunds that add up to the whole order reverse every awarded point.
	points_to_reverse = int(flt(awarded_points * refunded_share, 6)) - reversed_points
	points_to_reverse = max(min(points_to_reverse, awarded_points - reversed_points), 0)
	save_ledger_entry(event, order.customer, -points_to_reverse, "Order Refunded", refund_amount)


def on_order_cancelled(event: CommeraEvent):
	if is_event_recorded(event.id):
		return

	points_left = sum(entry.points for entry in get_order_ledger_entries(event.sales_order))
	if points_left > 0:
		customer = frappe.db.get_value("Sales Order", event.sales_order, "customer")
		save_ledger_entry(event, customer, -points_left, "Order Cancelled")


def get_order_total(order, refund_currency: str | None) -> float:
	if not refund_currency or refund_currency == order.currency:
		return flt(order.rounded_total) or flt(order.grand_total)
	return flt(order.base_rounded_total) or flt(order.base_grand_total)


def is_event_recorded(event_id: str) -> bool:
	return bool(frappe.db.exists("Loyalty Ledger Entry", {"event_id": event_id}))


def get_order_ledger_entries(sales_order: str) -> list:
	return frappe.get_all(
		"Loyalty Ledger Entry",
		filters={"sales_order": sales_order},
		fields=["points", "refunded_amount"],
	)


def save_ledger_entry(
	event: CommeraEvent, customer: str, points: int, reason: str, refunded_amount: float = 0
):
	frappe.get_doc(
		{
			"doctype": "Loyalty Ledger Entry",
			"customer": customer,
			"sales_order": event.sales_order,
			"points": points,
			"reason": reason,
			"refunded_amount": refunded_amount,
			"event_id": event.id,
		}
	).insert()


@frappe.whitelist(methods=["GET"])
def get_points(customer: str) -> int:
	if not can_read_points(customer):
		frappe.throw(_("Not permitted to read this customer's points"), frappe.PermissionError)

	ledger_entry = DocType("Loyalty Ledger Entry")
	total = (
		frappe.qb.from_(ledger_entry)
		.select(Sum(ledger_entry.points))
		.where(ledger_entry.customer == customer)
		.run()
	)
	return cint(total[0][0])


def can_read_points(customer: str) -> bool:
	if frappe.session.user == "Guest":
		return False
	if frappe.has_permission("Loyalty Ledger Entry", "read"):
		return True

	customer_contact = get_customer_contact(frappe.session.user)
	if customer_contact and customer_contact[0] == customer:
		return True
	return customer in get_parents_for_user("Customer")

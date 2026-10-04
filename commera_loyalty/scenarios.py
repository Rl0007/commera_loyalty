import time

import frappe
from commera.api.orders import cancel_order, create_refund_payment_entry
from commera.api.payments import create_payment_entry, get_charge_amount, make_sales_invoice, place_cod_order
from commera.plugin_events import fire_event, run_app_deliveries
from erpnext.accounts.party import get_party_account
from frappe.utils import flt, nowdate

from commera_loyalty.loyalty import get_points

APP = "commera_loyalty"
COMPANY = "Lifestyle Demo"
CASH_ACCOUNT = "Cash - LSD"
PRICE_LIST = "Standard Selling"
ITEM = "ZZ-LOYALTY-TEE"
ITEM_RATE = 437
CUSTOMER = "ZZ Loyalty Customer"
SHOPPER = "loyalty.shopper@example.com"
OTHER_CUSTOMER = "ZZ Loyalty Other Customer"
OTHER_SHOPPER = "loyalty.other@example.com"
GATEWAY = "Loyalty Test Pay"


def run():
	add_fixtures()
	cod_order = run_cod_payment()
	gateway_order = run_gateway_order()
	run_partial_refunds(gateway_order)
	run_cancel()
	run_duplicate_delivery(cod_order)
	run_desk_refund()
	run_get_points()


def add_fixtures():
	add_customer(CUSTOMER, SHOPPER)
	add_customer(OTHER_CUSTOMER, OTHER_SHOPPER)
	if not frappe.db.exists("Item", ITEM):
		item = frappe.new_doc("Item")
		item.update(
			{
				"item_code": ITEM,
				"item_name": "Loyalty Tee",
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		)
		item.insert()
	if not frappe.db.exists("Item Price", {"item_code": ITEM, "price_list": PRICE_LIST}):
		item_price = frappe.new_doc("Item Price")
		item_price.update({"item_code": ITEM, "price_list": PRICE_LIST, "price_list_rate": ITEM_RATE})
		item_price.insert()

	if not frappe.db.exists("Mode of Payment", GATEWAY):
		mode_of_payment = frappe.new_doc("Mode of Payment")
		mode_of_payment.mode_of_payment = GATEWAY
		mode_of_payment.type = "Cash"
		mode_of_payment.append("accounts", {"company": COMPANY, "default_account": CASH_ACCOUNT})
		mode_of_payment.insert()
	if not frappe.db.exists("Payment Gateway Profile", GATEWAY):
		profile = frappe.new_doc("Payment Gateway Profile")
		profile.name = GATEWAY
		profile.gateway_settings = "Loyalty Test Gateway Settings"
		# Disabled, so the fake gateway is never offered at the real storefront checkout.
		profile.enabled = 0
		profile.insert(set_name=GATEWAY)
	frappe.db.set_single_value("Loyalty Test Gateway Settings", "fail_refunds", 0)
	frappe.db.commit()
	print("fixtures ready; COD enabled:", frappe.db.get_single_value("Commera Settings", "cod_enabled"))


def add_customer(customer_name: str, email: str):
	if not frappe.db.exists("Customer", customer_name):
		customer = frappe.new_doc("Customer")
		customer.update({"customer_name": customer_name, "customer_type": "Individual"})
		customer.insert()
	if not frappe.db.get_value("Contact Email", {"email_id": email, "parenttype": "Contact"}, "parent"):
		contact = frappe.new_doc("Contact")
		contact.first_name = customer_name
		contact.append("email_ids", {"email_id": email, "is_primary": 1})
		contact.append("links", {"link_doctype": "Customer", "link_name": customer_name})
		contact.insert()
	if not frappe.db.exists("User", email):
		user = frappe.new_doc("User")
		user.update({"email": email, "first_name": customer_name, "send_welcome_email": 0})
		user.insert()


def new_cart():
	contact = frappe.db.get_value("Contact Email", {"email_id": SHOPPER, "parenttype": "Contact"}, "parent")
	quotation = frappe.new_doc("Quotation")
	quotation.update(
		{
			"quotation_to": "Customer",
			"party_name": CUSTOMER,
			"company": COMPANY,
			"order_type": "Shopping Cart",
			"contact_person": contact,
			"contact_email": SHOPPER,
			"currency": "INR",
			"conversion_rate": 1,
			"selling_price_list": PRICE_LIST,
			"price_list_currency": "INR",
			"plc_conversion_rate": 1,
			"items": [{"item_code": ITEM, "qty": 3}],
		}
	)
	quotation.flags.ignore_permissions = True
	quotation.insert()
	return quotation


def place_gateway_order() -> str:
	"""Pay a cart through the real Gateway Payment Request webhook path, against the fake gateway."""
	quotation = new_cart()
	payment_request = frappe.get_doc(
		{
			"doctype": "Gateway Payment Request",
			"gateway": GATEWAY,
			"amount": get_charge_amount(quotation),
			"currency_code": quotation.currency,
			"company": COMPANY,
			"ref_doctype": "Quotation",
			"ref_docname": quotation.name,
			"customer_ref": quotation.party_name,
			"customer_email": SHOPPER,
		}
	).insert(ignore_permissions=True)
	payment_request.apply_webhook_status("Paid", f"evt_{frappe.generate_hash(length=8)}")
	frappe.db.commit()
	return frappe.db.get_value("Gateway Payment Request", payment_request.name, "ref_docname")


def run_cod_payment() -> str:
	print("\n== 1. COD order, partial then full payment")
	sales_order_name = place_cod_order(new_cart().name).name
	frappe.db.commit()
	sales_order = frappe.get_doc("Sales Order", sales_order_name)
	sales_order.flags.ignore_permissions = True
	sales_order.submit()
	sales_invoice = make_sales_invoice(sales_order_name, ignore_permissions=True)
	sales_invoice.flags.ignore_permissions = True
	sales_invoice.insert()
	sales_invoice.submit()
	frappe.db.commit()
	print(
		"order",
		sales_order_name,
		"net_total",
		sales_order.net_total,
		"invoice",
		sales_invoice.name,
		"grand_total",
		sales_invoice.grand_total,
	)

	create_payment_entry(sales_invoice, "Cash", 100, None)
	frappe.db.commit()
	ledger = wait_for(lambda: get_ledger(sales_order_name), lambda rows: rows, timeout=15)
	print("after partial payment of 100: ledger", ledger, "events", get_events(sales_order_name))

	sales_invoice.reload()
	create_payment_entry(sales_invoice, "Cash", flt(sales_invoice.outstanding_amount), None)
	frappe.db.commit()
	ledger = wait_for(lambda: get_ledger(sales_order_name), lambda rows: rows)
	print("after full payment: ledger", ledger)
	print("events", get_events(sales_order_name))
	return sales_order_name


def run_gateway_order() -> str:
	print("\n== 2. Gateway order through Gateway Payment Request -> place_order")
	sales_order_name = place_gateway_order()
	ledger = wait_for(lambda: get_ledger(sales_order_name), lambda rows: rows)
	net_total, rounded_total = frappe.db.get_value(
		"Sales Order", sales_order_name, ["net_total", "rounded_total"]
	)
	print("order", sales_order_name, "net_total", net_total, "rounded_total", rounded_total)
	print("ledger", ledger)
	print("events", get_events(sales_order_name))
	return sales_order_name


def run_partial_refunds(sales_order_name: str):
	print("\n== 3. Refunds through create_refund_payment_entry on", sales_order_name)
	frappe.db.set_single_value("Loyalty Test Gateway Settings", "fail_refunds", 1)
	frappe.db.commit()
	try:
		create_refund_payment_entry(sales_order_name, 200)
		print("unexpected: refused gateway refund went through")
	except frappe.ValidationError as error:
		frappe.db.rollback()
		print("gateway refused refund:", error)
	frappe.db.set_single_value("Loyalty Test Gateway Settings", "fail_refunds", 0)
	frappe.db.commit()

	for amount in (300, 400, None):
		payment_entry = create_refund_payment_entry(sales_order_name, amount)
		frappe.db.commit()
		expected_rows = 2 + (amount is None) + (amount in (400, None))
		ledger = wait_for(
			lambda: get_ledger(sales_order_name), lambda rows, count=expected_rows: len(rows) >= count
		)
		print(f"refund {amount or 'balance'} as {payment_entry}: ledger", ledger)
	print("events", get_events(sales_order_name))
	print("order points left:", sum(row[1] for row in get_ledger(sales_order_name)))


def run_cancel():
	print("\n== 4. Cancel a paid gateway order, and a paid COD order")
	sales_order_name = place_gateway_order()
	wait_for(lambda: get_ledger(sales_order_name), lambda rows: rows)
	create_refund_payment_entry(sales_order_name, 500)
	frappe.db.commit()
	wait_for(lambda: get_ledger(sales_order_name), lambda rows: len(rows) >= 2)
	cancel_order(sales_order_name)
	frappe.db.commit()
	ledger = wait_for(lambda: get_ledger(sales_order_name), lambda rows: len(rows) >= 3)
	print("gateway order", sales_order_name, "ledger", ledger)
	print("events", get_events(sales_order_name))
	refunds = frappe.get_all(
		"Payment Entry",
		filters={
			"payment_type": "Pay",
			"remarks": f"Refund for Sales Order {sales_order_name}",
			"docstatus": 1,
		},
		fields=["name", "paid_amount", "reference_no"],
	)
	print("refund payment entries", refunds)

	sales_order_name = place_cod_order(new_cart().name).name
	frappe.db.commit()
	cancel_order(sales_order_name)
	frappe.db.commit()
	time.sleep(8)
	print(
		"unpaid COD order",
		sales_order_name,
		"ledger",
		get_ledger(sales_order_name),
		"events",
		get_events(sales_order_name),
	)


def run_duplicate_delivery(sales_order_name: str):
	print("\n== 5. Duplicate deliveries on", sales_order_name)
	event_key = f"{sales_order_name}-order_paid"
	fire_event("order_paid", "Sales Order", sales_order_name)
	frappe.db.commit()
	print("refire order_paid: events with that key", frappe.db.count("Commera Event", {"name": event_key}))

	run_app_deliveries(APP, "Sales Order", sales_order_name)
	run_app_deliveries(APP, "Sales Order", sales_order_name)
	frappe.set_user("Administrator")
	delivery = frappe.db.get_value("Commera Event Delivery", {"parent": event_key, "app": APP}, "name")
	# Simulates a worker that ran the handler but died before marking the delivery Done.
	frappe.db.set_value("Commera Event Delivery", delivery, {"status": "Queued", "finished_at": None})
	frappe.db.commit()
	run_app_deliveries(APP, "Sales Order", sales_order_name)
	run_app_deliveries(APP, "Sales Order", sales_order_name)
	frappe.set_user("Administrator")
	print(
		"delivery after forced redelivery",
		frappe.db.get_value("Commera Event Delivery", delivery, ["status", "attempts"], as_dict=True),
	)
	print("ledger", get_ledger(sales_order_name))


def run_desk_refund():
	print("\n== 6. Refunds made directly in Desk (Payment Entry, type Pay)")
	sales_order_name = place_gateway_order()
	wait_for(lambda: get_ledger(sales_order_name), lambda rows: rows)
	capture_reference = frappe.db.get_value(
		"Payment Entry Reference",
		{"reference_doctype": "Sales Invoice", "reference_name": get_order_invoice(sales_order_name)},
		"parent",
	)
	capture_reference_no = frappe.db.get_value("Payment Entry", capture_reference, "reference_no")

	submit_desk_refund(250, None)
	time.sleep(8)
	print(
		"Pay entry without reference_no: ledger",
		get_ledger(sales_order_name),
		"events",
		get_events(sales_order_name),
	)

	submit_desk_refund(250, capture_reference_no)
	ledger = wait_for(lambda: get_ledger(sales_order_name), lambda rows: len(rows) >= 2)
	print("Pay entry with the capture's reference_no: ledger", ledger, "events", get_events(sales_order_name))


def submit_desk_refund(amount: float, reference_no: str | None):
	payment_entry = frappe.new_doc("Payment Entry")
	payment_entry.update(
		{
			"payment_type": "Pay",
			"company": COMPANY,
			"mode_of_payment": "Cash",
			"party_type": "Customer",
			"party": CUSTOMER,
			"paid_from": CASH_ACCOUNT,
			"paid_to": get_party_account("Customer", CUSTOMER, COMPANY),
			"paid_amount": amount,
			"received_amount": amount,
			"reference_no": reference_no,
			"reference_date": nowdate(),
		}
	)
	payment_entry.insert()
	payment_entry.submit()
	frappe.db.commit()
	return payment_entry.name


def run_get_points():
	print("\n== 7. get_points permissions")
	for user in ("Administrator", SHOPPER, OTHER_SHOPPER, "Guest"):
		frappe.set_user(user)
		try:
			print(user, "->", get_points(CUSTOMER))
		except frappe.PermissionError:
			print(user, "-> PermissionError")
		finally:
			frappe.local.message_log = []
	frappe.set_user("Administrator")


def get_order_invoice(sales_order_name: str) -> str:
	return frappe.db.get_value(
		"Sales Invoice Item", {"sales_order": sales_order_name, "docstatus": 1}, "parent"
	)


def get_ledger(sales_order_name: str) -> list:
	frappe.db.rollback()
	return frappe.get_all(
		"Loyalty Ledger Entry",
		filters={"sales_order": sales_order_name},
		fields=["reason", "points", "refunded_amount", "event_id"],
		order_by="creation",
		as_list=True,
	)


def get_events(sales_order_name: str) -> list:
	frappe.db.rollback()
	events = frappe.get_all(
		"Commera Event",
		filters={"reference_doctype": "Sales Order", "reference_name": sales_order_name},
		fields=["name", "event"],
		order_by="creation",
	)
	deliveries = frappe.get_all(
		"Commera Event Delivery",
		filters={"parent": ["in", [event.name for event in events] or [""]], "app": APP},
		fields=["parent", "status", "attempts"],
	)
	delivery_by_event = {delivery.parent: delivery for delivery in deliveries}
	return [
		(event.event, delivery_by_event[event.name].status if event.name in delivery_by_event else None)
		for event in events
	]


def wait_for(read, is_ready, timeout=60):
	started_at = time.time()
	while time.time() - started_at < timeout:
		value = read()
		if is_ready(value):
			return value
		time.sleep(1)
	return read()

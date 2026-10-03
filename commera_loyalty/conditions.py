import frappe


def has_ledger_entries(doctype: str, name: str) -> bool:
	return bool(frappe.db.exists("Loyalty Ledger Entry", {"sales_order": name}))

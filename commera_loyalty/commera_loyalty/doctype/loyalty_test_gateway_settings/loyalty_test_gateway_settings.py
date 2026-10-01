import frappe
from bwh_payments.base_class import PaymentGatewayBase
from frappe import _
from frappe.model.document import Document


class LoyaltyTestGatewaySettings(Document, PaymentGatewayBase):
	def create_session(self, amount, currency, reference=None, customer=None) -> dict:
		return {
			"session_id": f"loyalty_test_{frappe.generate_hash(length=12)}",
			"redirect_url": "",
			"success_url": "",
			"cancel_url": "",
			"failure_url": "",
		}

	def get_payment_status(self, session_id: str) -> str:
		return "Paid"

	def refund_payment(self, session_id: str, amount: float, currency: str | None = None) -> dict:
		if self.fail_refunds:
			frappe.throw(_("The test gateway refused this refund."))
		return {"refund_id": f"re_{frappe.generate_hash(length=10)}", "status": "Refunded", "amount": amount}

	def handle_webhook(self, payload: bytes, headers: dict) -> dict:
		return {}

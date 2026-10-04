app_name = "commera_loyalty"
app_title = "Loyalty"
app_publisher = "Rahul Agrawal"
app_description = "Loyalty points for Commera store orders"
app_email = "12agrawalrahul@gmail.com"
app_license = "mit"

required_apps = ["commera"]

commera_api_version = [1]

commera_events = {
	"order_paid": ["commera_loyalty.loyalty.on_order_paid"],
	"order_refunded": ["commera_loyalty.loyalty.on_order_refunded"],
	"order_cancelled": ["commera_loyalty.loyalty.on_order_cancelled"],
}

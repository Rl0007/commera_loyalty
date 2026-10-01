app_name = "commera_loyalty"
app_title = "Commera Loyalty"
app_publisher = "Rahul Agrawal"
app_description = "Loyalty points for Commera store orders"
app_email = "12agrawalrahul@gmail.com"
app_license = "mit"

required_apps = ["commera"]

commera_api_version = [1]

commera_order_paid = ["commera_loyalty.loyalty.on_order_paid"]
commera_order_refunded = ["commera_loyalty.loyalty.on_order_refunded"]
commera_order_cancelled = ["commera_loyalty.loyalty.on_order_cancelled"]

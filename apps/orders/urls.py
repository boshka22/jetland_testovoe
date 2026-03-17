from django.urls import path

from apps.orders.views import CreateOrderView

app_name = "orders"

urlpatterns = [
    path("orders/", CreateOrderView.as_view(), name="create-order"),
]

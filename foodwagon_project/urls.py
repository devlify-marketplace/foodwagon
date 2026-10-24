from django.contrib import admin
from django.urls import path

from foodwagon_site import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("basket/", views.basket, name="basket"),
    path("basket/add/<int:item_id>/", views.add_to_basket, name="add_to_basket"),
    path("basket/update/", views.update_basket, name="update_basket"),
    path("basket/remove/<int:item_id>/", views.remove_from_basket, name="remove_from_basket"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/<uuid:token>/", views.order_status, name="order_status"),
    path("orders/<uuid:token>/retry-payment/", views.retry_payment, name="retry_payment"),
    path("payments/paystack/return/", views.payment_return, name="payment_return"),
    path("payments/paystack/webhook/", views.paystack_webhook, name="paystack_webhook"),
    # Compatibility aliases for the earlier demo-only paths.
    path("demo/cart/add/<int:item_id>/", views.add_to_basket, name="add_to_cart"),
    path("demo/order/", views.submit_demo_order, name="submit_demo_order"),
    path("demo/order/complete/", views.demo_order_complete, name="demo_order_complete"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
]

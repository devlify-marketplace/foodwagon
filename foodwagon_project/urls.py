from django.contrib import admin
from django.urls import path
from foodwagon_site import views
urlpatterns = [
    path("admin/", admin.site.urls), path("", views.home, name="home"),
    path("demo/cart/add/<int:item_id>/", views.add_to_cart, name="add_to_cart"),
    path("demo/order/", views.submit_demo_order, name="submit_demo_order"),
    path("demo/order/complete/", views.demo_order_complete, name="demo_order_complete"),
    path("dashboard/", views.dashboard, name="dashboard"), path("robots.txt", views.robots, name="robots"), path("sitemap.xml", views.sitemap, name="sitemap"),
]

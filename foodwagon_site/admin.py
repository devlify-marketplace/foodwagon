from django.contrib import admin
from .models import Category, DeliveryZone, DemoOrder, DemoOrderLine, MenuItem, OperatingHour, RestaurantProfile

class DemoLabelAdmin(admin.ModelAdmin):
    list_display = ("__str__", "is_demo")
    list_filter = ("is_demo",)
    def get_queryset(self, request): return super().get_queryset(request)

@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(DemoLabelAdmin):
    fieldsets = (("DEMO ONLY — restaurant/service profile", {"fields": ("is_demo", "name", "description", "public_email", "public_phone", "address", "service_area", "opening_schedule")}), ("Fail-closed controls", {"fields": ("live_ordering_enabled", "live_payments_enabled")}))
    def has_add_permission(self, request): return not RestaurantProfile.objects.exists()

@admin.register(Category)
class CategoryAdmin(DemoLabelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "sort_order", "is_active", "is_demo")

@admin.register(MenuItem)
class MenuItemAdmin(DemoLabelAdmin):
    list_display = ("name", "category", "price_ngn", "is_available", "is_demo")
    list_filter = ("category", "is_available", "is_demo")

@admin.register(OperatingHour)
class OperatingHourAdmin(DemoLabelAdmin):
    list_display = ("weekday", "opens_at", "closes_at", "is_closed", "is_demo")

@admin.register(DeliveryZone)
class DeliveryZoneAdmin(DemoLabelAdmin):
    list_display = ("name", "description", "delivery_fee_ngn", "is_active", "is_demo")

class DemoOrderLineInline(admin.TabularInline):
    model = DemoOrderLine
    extra = 0
    readonly_fields = ("item_name", "unit_price_ngn", "quantity", "is_demo")
    can_delete = False

@admin.register(DemoOrder)
class DemoOrderAdmin(DemoLabelAdmin):
    list_display = ("id", "customer_name", "total_ngn", "status", "created_at", "is_demo")
    list_filter = ("status", "is_demo", "created_at")
    readonly_fields = ("total_ngn", "created_at", "acknowledgement")
    inlines = [DemoOrderLineInline]

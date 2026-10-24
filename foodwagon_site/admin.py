from django.contrib import admin

from .models import (
    Category,
    DeliveryZone,
    DemoOrder,
    DemoOrderLine,
    MenuItem,
    OperatingHour,
    Order,
    OrderLine,
    PaystackWebhookEvent,
    PaymentAttempt,
    RestaurantProfile,
)


class DemoLabelAdmin(admin.ModelAdmin):
    list_filter = ("is_demo",)


@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(DemoLabelAdmin):
    fieldsets = (
        ("Business details — DEMO until verified", {"fields": (
            "is_demo", "name", "description", "public_email", "public_phone",
            "address", "service_area", "opening_schedule", "privacy_notice_url", "terms_url",
        )}),
        ("Live readiness — all checks required", {"fields": (
            "live_ordering_enabled", "live_payments_enabled", "live_readiness_confirmed",
        )}),
    )

    def has_add_permission(self, request):
        return not RestaurantProfile.objects.exists()

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            fields.extend(("live_ordering_enabled", "live_payments_enabled", "live_readiness_confirmed"))
        return tuple(fields)


@admin.register(Category)
class CategoryAdmin(DemoLabelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "sort_order", "is_active", "is_demo")


@admin.register(MenuItem)
class MenuItemAdmin(DemoLabelAdmin):
    list_display = ("name", "category", "price_ngn", "is_available", "is_demo")
    list_filter = ("category", "is_available", "is_demo")
    search_fields = ("name", "description")


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


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    can_delete = False
    fields = ("item_name", "unit_price_ngn", "quantity", "is_demo")
    readonly_fields = fields


class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0
    can_delete = False
    fields = ("mode", "reference", "amount_kobo", "status", "created_at", "verified_at")
    readonly_fields = fields


@admin.register(Order)
class OrderAdmin(DemoLabelAdmin):
    list_display = (
        "short_reference", "created_at", "customer_name", "fulfilment_method",
        "total_ngn", "payment_mode", "payment_status", "status", "is_demo",
    )
    list_filter = ("status", "payment_status", "payment_mode", "fulfilment_method", "is_demo", "created_at")
    search_fields = ("customer_name", "email", "phone", "public_token__iexact")
    readonly_fields = (
        "public_token", "checkout_token", "customer_name", "email", "phone",
        "fulfilment_method", "delivery_zone_name", "delivery_address", "special_instructions",
        "terms_accepted_at", "terms_url_snapshot", "privacy_notice_url_snapshot",
        "subtotal_ngn", "delivery_fee_ngn", "total_ngn", "currency", "payment_mode",
        "payment_status", "is_demo", "created_at", "updated_at",
    )
    inlines = [OrderLineInline, PaymentAttemptInline]
    date_hierarchy = "created_at"

    @admin.display(description="Reference")
    def short_reference(self, obj):
        return f"{'DEMO' if obj.is_demo else 'FW'}-{obj.public_token.hex[:10].upper()}"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and (
            obj.payment_mode != "live"
            or obj.is_demo
            or obj.payment_status != "paid"
            or obj.status == "payment_review"
        ):
            fields.append("status")
        return tuple(fields)

    def save_model(self, request, obj, form, change):
        if obj.payment_mode == "live" and obj.payment_status != "paid":
            obj.status = "payment_review" if obj.payment_status == "review" else "awaiting_payment"
        super().save_model(request, obj, form, change)


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("reference", "order", "mode", "amount_kobo", "status", "created_at", "verified_at")
    list_filter = ("mode", "status", "created_at")
    search_fields = ("reference", "order__customer_name", "order__email")
    readonly_fields = tuple(field.name for field in PaymentAttempt._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaystackWebhookEvent)
class PaystackWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "reference", "result", "received_at", "processed_at")
    list_filter = ("event_type", "result", "received_at")
    search_fields = ("reference", "payload_digest")
    readonly_fields = tuple(field.name for field in PaystackWebhookEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

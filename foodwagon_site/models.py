import uuid

from django.core.validators import MinValueValidator
from django.db import models


class DemoRecord(models.Model):
    is_demo = models.BooleanField(
        default=True,
        help_text="Keep enabled for synthetic/example content and all demo/test orders.",
    )

    class Meta:
        abstract = True


class RestaurantProfile(DemoRecord):
    name = models.CharField(max_length=120, default="Foodwagon")
    public_email = models.EmailField(default="sadiq@devlify.com.ng")
    public_phone = models.CharField(max_length=32, default="+2349034303594")
    address = models.CharField(max_length=200, blank=True, default="")
    service_area = models.CharField(max_length=200, blank=True, default="")
    opening_schedule = models.CharField(max_length=250, blank=True, default="")
    description = models.TextField(blank=True, default="")
    privacy_notice_url = models.URLField(blank=True, default="")
    terms_url = models.URLField(blank=True, default="")
    live_ordering_enabled = models.BooleanField(
        default=False,
        help_text="Must be explicitly enabled alongside environment and verified profile checks.",
    )
    live_payments_enabled = models.BooleanField(
        default=False,
        help_text="Must be explicitly enabled alongside environment and verified profile checks.",
    )
    live_readiness_confirmed = models.BooleanField(
        default=False,
        help_text="Owner confirms business identity, menu/prices, fulfilment, legal notices, and support details are verified.",
    )

    class Meta:
        verbose_name = "restaurant profile"

    def __str__(self):
        return f"{self.name}{' (DEMO)' if self.is_demo else ''}"


class Category(DemoRecord):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}{' (DEMO)' if self.is_demo else ''}"

    class Meta:
        ordering = ["sort_order", "name"]


class MenuItem(DemoRecord):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=240)
    price_ngn = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    image = models.CharField(
        max_length=200,
        blank=True,
        help_text="Theme-relative path, e.g. img/refresh/jollof-chicken.webp",
    )
    is_available = models.BooleanField(default=True)

    def __str__(self):
        label = " (DEMO)" if self.is_demo or self.category.is_demo else ""
        return f"{self.name} — ₦{self.price_ngn}{label}"

    class Meta:
        ordering = ["category__sort_order", "name"]


class OperatingHour(DemoRecord):
    weekday = models.PositiveSmallIntegerField(
        choices=[
            (i, day)
            for i, day in enumerate(
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            )
        ]
    )
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    note = models.CharField(max_length=160, default="DEMO ONLY — not operating hours")

    class Meta:
        ordering = ["weekday"]
        unique_together = [("weekday", "is_demo")]

    def __str__(self):
        return f"{self.get_weekday_display()}{' (DEMO)' if self.is_demo else ''}"


class DeliveryZone(DemoRecord):
    name = models.CharField(max_length=100)
    description = models.CharField(
        max_length=200,
        help_text="Clearly mark fictional areas as demo.",
    )
    delivery_fee_ngn = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}{' (DEMO)' if self.is_demo else ''}"


class DemoOrder(DemoRecord):
    """Legacy local-only submissions retained for backward-compatible history."""

    STATUS = [("received", "Demo received"), ("cancelled", "Cancelled")]
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=32)
    address = models.CharField(max_length=250)
    status = models.CharField(max_length=20, choices=STATUS, default="received")
    total_ngn = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledgement = models.CharField(
        max_length=250,
        default="DEMO ONLY — no real order, payment, email, or delivery was sent.",
    )

    def __str__(self):
        return f"DEMO order #{self.pk} — {self.customer_name}"

    class Meta:
        ordering = ["-created_at"]


class DemoOrderLine(DemoRecord):
    order = models.ForeignKey(DemoOrder, related_name="lines", on_delete=models.CASCADE)
    item_name = models.CharField(max_length=100)
    unit_price_ngn = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        return f"{self.item_name} × {self.quantity} (DEMO)"


class Order(DemoRecord):
    FULFILMENT_CHOICES = [("delivery", "Delivery"), ("pickup", "Pickup")]
    STATUS_CHOICES = [
        ("awaiting_payment", "Awaiting payment"),
        ("demo_complete", "Demo/test complete — no fulfilment"),
        ("received", "Received"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("payment_review", "Payment review required"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("demo", "Demo — no payment"),
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("review", "Review required"),
    ]
    PAYMENT_MODE_CHOICES = [("demo", "Demo"), ("test", "Paystack test"), ("live", "Paystack live")]

    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checkout_token = models.UUIDField(unique=True, editable=False)
    customer_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    fulfilment_method = models.CharField(max_length=12, choices=FULFILMENT_CHOICES)
    delivery_zone_name = models.CharField(max_length=100, blank=True)
    delivery_address = models.CharField(max_length=250, blank=True)
    special_instructions = models.CharField(max_length=500, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_url_snapshot = models.URLField(blank=True, default="")
    privacy_notice_url_snapshot = models.URLField(blank=True, default="")
    subtotal_ngn = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee_ngn = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_ngn = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="NGN")
    payment_mode = models.CharField(max_length=8, choices=PAYMENT_MODE_CHOICES, default="demo")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="awaiting_payment")
    payment_status = models.CharField(max_length=12, choices=PAYMENT_STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        prefix = "DEMO" if self.is_demo else "FW"
        return f"{prefix}-{self.public_token.hex[:10].upper()} — ₦{self.total_ngn}"


class OrderLine(DemoRecord):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.CASCADE)
    menu_item = models.ForeignKey(
        MenuItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_lines",
    )
    item_name = models.CharField(max_length=100)
    unit_price_ngn = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    @property
    def line_total_ngn(self):
        return self.unit_price_ngn * self.quantity

    def __str__(self):
        label = " (DEMO)" if self.is_demo else ""
        return f"{self.item_name} × {self.quantity}{label}"


class PaymentAttempt(models.Model):
    MODE_CHOICES = [("test", "Paystack test"), ("live", "Paystack live")]
    STATUS_CHOICES = [
        ("initializing", "Initializing"),
        ("initialized", "Initialized"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("review", "Review required"),
    ]

    order = models.ForeignKey(Order, related_name="payment_attempts", on_delete=models.CASCADE)
    mode = models.CharField(max_length=4, choices=MODE_CHOICES)
    reference = models.CharField(max_length=80, unique=True)
    amount_kobo = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="initializing")
    authorization_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["order", "status"])]

    def __str__(self):
        return f"{self.reference} ({self.mode}, {self.status})"


class PaystackWebhookEvent(models.Model):
    payload_digest = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=80)
    reference = models.CharField(max_length=80, blank=True)
    payment_attempt = models.ForeignKey(
        PaymentAttempt,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="webhook_events",
    )
    result = models.CharField(max_length=32, default="received")
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"Paystack {self.event_type} · {self.reference or 'unknown'} · {self.result}"

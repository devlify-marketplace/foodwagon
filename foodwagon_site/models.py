from django.core.validators import MinValueValidator
from django.db import models

class DemoRecord(models.Model):
    is_demo = models.BooleanField(default=True, help_text="Must remain enabled for all synthetic/example content.")
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
    live_ordering_enabled = models.BooleanField(default=False, help_text="Reserved for future live mode. Application code rejects live fulfilment regardless of this flag.")
    live_payments_enabled = models.BooleanField(default=False, help_text="Reserved for future payment integration; no provider is implemented.")
    class Meta:
        verbose_name = "restaurant profile"
    def __str__(self): return f"{self.name}{' (DEMO)' if self.is_demo else ''}"

class Category(DemoRecord):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    def __str__(self): return f"{self.name} (DEMO)"
    class Meta: ordering = ["sort_order", "name"]

class MenuItem(DemoRecord):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=240)
    price_ngn = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    image = models.CharField(max_length=200, blank=True, help_text="Theme-relative path, e.g. img/refresh/jollof-chicken.webp")
    is_available = models.BooleanField(default=True)
    def __str__(self): return f"{self.name} — ₦{self.price_ngn} (DEMO)"
    class Meta: ordering = ["category__sort_order", "name"]

class OperatingHour(DemoRecord):
    weekday = models.PositiveSmallIntegerField(choices=[(i, day) for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])] )
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    note = models.CharField(max_length=160, default="DEMO ONLY — not operating hours")
    class Meta: ordering = ["weekday"]; unique_together = [("weekday", "is_demo")]
    def __str__(self): return f"{self.get_weekday_display()} (DEMO)"

class DeliveryZone(DemoRecord):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, help_text="Clearly mark fictional areas as demo.")
    delivery_fee_ngn = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    def __str__(self): return f"{self.name} (DEMO)"

class DemoOrder(DemoRecord):
    STATUS = [("received", "Demo received"), ("cancelled", "Cancelled")]
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=32)
    address = models.CharField(max_length=250)
    status = models.CharField(max_length=20, choices=STATUS, default="received")
    total_ngn = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledgement = models.CharField(max_length=250, default="DEMO ONLY — no real order, payment, email, or delivery was sent.")
    def __str__(self): return f"DEMO order #{self.pk} — {self.customer_name}"
    class Meta: ordering = ["-created_at"]

class DemoOrderLine(DemoRecord):
    order = models.ForeignKey(DemoOrder, related_name="lines", on_delete=models.CASCADE)
    item_name = models.CharField(max_length=100)
    unit_price_ngn = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    def __str__(self): return f"{self.item_name} × {self.quantity} (DEMO)"

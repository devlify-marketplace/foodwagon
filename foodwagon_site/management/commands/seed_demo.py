from django.core.management.base import BaseCommand

from foodwagon_site.models import Category, DeliveryZone, MenuItem, RestaurantProfile


class Command(BaseCommand):
    help = "Create an editable demo profile, sample menu, and fictional delivery zone; never enable live orders or payments."

    def handle(self, *args, **options):
        profile, profile_created = RestaurantProfile.objects.get_or_create(
            is_demo=True,
            defaults={
                "name": "Foodwagon DEMO",
                "public_email": "sadiq@devlify.com.ng",
                "public_phone": "+2349034303594",
                "address": "",
                "service_area": "",
                "opening_schedule": "",
                "description": "DEMO ONLY — edit with owner-verified restaurant details.",
                "privacy_notice_url": "",
                "terms_url": "",
                "live_ordering_enabled": False,
                "live_payments_enabled": False,
                "live_readiness_confirmed": False,
            },
        )

        mains, _ = Category.objects.get_or_create(
            slug="demo-nigerian-classics",
            defaults={"name": "DEMO — Nigerian classics", "sort_order": 10, "is_demo": True},
        )
        small_bites, _ = Category.objects.get_or_create(
            slug="demo-small-bites",
            defaults={"name": "DEMO — Small bites", "sort_order": 20, "is_demo": True},
        )
        samples = [
            (mains, "DEMO Jollof Rice & Chicken", "Illustrative sample dish — replace before any launch.", "3800.00", "img/refresh/jollof-chicken.webp"),
            (mains, "DEMO Garden Salad Bowl", "Illustrative sample dish — not an actual menu listing.", "2600.00", "img/refresh/salad-bowl.webp"),
            (small_bites, "DEMO Plantain & Suya Plate", "Fictional sample menu item for checkout rehearsal.", "2800.00", "img/refresh/family-platter.webp"),
        ]
        created_items = 0
        for category, name, description, price, image in samples:
            _, created = MenuItem.objects.get_or_create(
                category=category,
                name=name,
                defaults={
                    "description": description,
                    "price_ngn": price,
                    "image": image,
                    "is_available": True,
                    "is_demo": True,
                },
            )
            created_items += int(created)

        _, zone_created = DeliveryZone.objects.get_or_create(
            name="DEMO — Example District",
            is_demo=True,
            defaults={
                "description": "Fictional sample only — no delivery is available.",
                "delivery_fee_ngn": "500.00",
                "is_active": True,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo setup ready: "
                f"profile {'created' if profile_created else 'kept unchanged'}, "
                f"{created_items} sample item(s) created, "
                f"demo delivery zone {'created' if zone_created else 'already exists'}. "
                "Every sample remains marked DEMO; live ordering and payment switches remain off."
            )
        )

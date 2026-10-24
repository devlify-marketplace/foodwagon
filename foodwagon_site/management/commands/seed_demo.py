from django.core.management.base import BaseCommand
from foodwagon_site.models import RestaurantProfile


class Command(BaseCommand):
    help = "Create the empty Foodwagon profile with confirmed contact details; never invent menu or operating data."

    def handle(self, *args, **options):
        profile, created = RestaurantProfile.objects.get_or_create(
            is_demo=True,
            defaults={
                "name": "Foodwagon",
                "public_email": "sadiq@devlify.com.ng",
                "public_phone": "+2349034303594",
                "address": "",
                "service_area": "",
                "opening_schedule": "",
                "description": "",
                "live_ordering_enabled": False,
                "live_payments_enabled": False,
            },
        )
        state = "created" if created else "already exists"
        self.stdout.write(
            self.style.SUCCESS(
                f"Foodwagon profile {state}. Menu, prices, address, service areas, hours, and fees remain unconfigured. Live ordering and payments are disabled."
            )
        )

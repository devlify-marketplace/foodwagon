from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, DeliveryZone, MenuItem, OperatingHour, RestaurantProfile


@override_settings(SECURE_SSL_REDIRECT=False)
class FoodwagonTests(TestCase):
    def test_profile_uses_only_confirmed_contacts_and_leaves_operations_blank(self):
        profile = RestaurantProfile.objects.create()
        self.assertEqual(profile.name, "Foodwagon")
        self.assertEqual(profile.public_email, "sadiq@devlify.com.ng")
        self.assertEqual(profile.public_phone, "+2349034303594")
        self.assertEqual(profile.address, "")
        self.assertEqual(profile.service_area, "")
        self.assertEqual(profile.opening_schedule, "")
        self.assertFalse(profile.live_ordering_enabled)
        self.assertFalse(profile.live_payments_enabled)

    def test_seed_command_does_not_invent_menu_prices_hours_or_zones(self):
        call_command("seed_demo", verbosity=0)
        self.assertEqual(MenuItem.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(OperatingHour.objects.count(), 0)
        self.assertEqual(DeliveryZone.objects.count(), 0)
        self.assertEqual(RestaurantProfile.objects.count(), 1)

    def test_empty_storefront_explains_that_menu_is_not_configured(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Menu details have not been configured")
        self.assertContains(response, "Ordering and payment are not available")
        self.assertContains(response, "Order now")
        self.assertContains(response, "Sign up")
        self.assertContains(response, "Log in")
        self.assertContains(response, "food-category-card--burger")
        self.assertContains(response, "food-hero__doodles")
        self.assertContains(response, "Delivery")
        self.assertContains(response, "Pickup")
        self.assertContains(response, "not on menu")
        self.assertNotContains(response, ">4.8<")
        self.assertNotContains(response, "8–10 mins")
        self.assertNotContains(response, "₦4,200")

    def test_menu_search_filters_catalog_and_marks_demo_entries(self):
        burger_category = Category.objects.create(name="Burger", slug="burger")
        cake_category = Category.objects.create(name="Cake", slug="cake")
        MenuItem.objects.create(
            category=burger_category,
            name="Example Burger",
            description="Illustrative sample item",
            price_ngn="2000.00",
        )
        MenuItem.objects.create(
            category=cake_category,
            name="Example Cake",
            description="Another sample item",
            price_ngn="2500.00",
        )

        response = self.client.get(reverse("home"), {"q": "burger"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Example Burger")
        self.assertContains(response, "SAMPLE · NOT FOR SALE")
        self.assertNotContains(response, "Example Cake")

    def test_public_order_actions_fail_closed_without_saving_personal_data(self):
        category = Category.objects.create(name="Verified", slug="verified", is_demo=False)
        item = MenuItem.objects.create(
            category=category,
            name="Verified dish",
            description="Owner-entered listing",
            price_ngn="1500.00",
            is_demo=False,
        )
        add_response = self.client.post(reverse("add_to_cart", args=[item.pk]))
        order_response = self.client.post(
            reverse("submit_demo_order"),
            {"customer_name": "Example", "phone": "000", "address": "Example"},
        )
        self.assertEqual(add_response.status_code, 503)
        self.assertEqual(order_response.status_code, 503)
        self.assertEqual(self.client.session.get("demo_cart"), None)

    def test_staff_dashboard_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
        staff = get_user_model().objects.create_user(
            "staff", password="A-secure-test-password", is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_production_http_requests_redirect_to_https(self):
        with override_settings(SECURE_SSL_REDIRECT=True):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))

    def test_robots_and_sitemap_are_available(self):
        robots = self.client.get(reverse("robots"))
        self.assertEqual(robots.status_code, 200)
        self.assertContains(robots, "Disallow: /")
        home = self.client.get(reverse("home"))
        self.assertContains(home, 'name="robots" content="noindex,nofollow"')
        sitemap = self.client.get(reverse("sitemap"))
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("application/xml", sitemap["Content-Type"])

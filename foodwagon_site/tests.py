import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import (
    Category,
    DeliveryZone,
    MenuItem,
    OperatingHour,
    Order,
    OrderLine,
    PaystackWebhookEvent,
    PaymentAttempt,
    RestaurantProfile,
)
from .payments import PaystackAPIError, amount_to_kobo, initialize_transaction, verify_transaction


TEST_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "PAYMENT_MODE": "demo",
    "PAYSTACK_TEST_SECRET_KEY": "",
    "PAYSTACK_LIVE_SECRET_KEY": "",
    "LIVE_ORDERING_ENABLED": False,
    "LIVE_PAYMENTS_ENABLED": False,
    "FOODWAGON_LIVE_CHECKOUT_APPROVED": False,
}


@override_settings(**TEST_SETTINGS)
class FoodwagonTests(TestCase):
    def make_item(self, *, price="2500.00", demo=True):
        slug = f"{'demo' if demo else 'verified'}-{uuid.uuid4().hex[:8]}"
        category = Category.objects.create(
            name=f"{'DEMO ' if demo else ''}Example category",
            slug=slug,
            is_demo=demo,
        )
        return MenuItem.objects.create(
            category=category,
            name=f"{'DEMO ' if demo else ''}Example meal",
            description="Synthetic sample for automated checkout tests.",
            price_ngn=price,
            is_demo=demo,
        )

    def make_zone(self, *, fee="500.00", demo=True):
        return DeliveryZone.objects.create(
            name=f"{'DEMO ' if demo else ''}Example area {uuid.uuid4().hex[:5]}",
            description="Fictional test area only.",
            delivery_fee_ngn=fee,
            is_demo=demo,
        )

    def add_to_basket(self, item, quantity=1):
        return self.client.post(
            reverse("add_to_basket", args=[item.pk]),
            {"quantity": quantity},
        )

    def checkout_data(self, *, token, zone, mode="demo", quantity=1):
        data = {
            "customer_name": "Synthetic Test Customer",
            "email": "checkout-test@example.test",
            "phone": "+234 900 000 0000",
            "fulfilment_method": "delivery",
            "delivery_zone": str(zone.pk),
            "delivery_address": "DEMO ONLY — Example address",
            "special_instructions": "Synthetic test order",
            "checkout_token": token,
        }
        if mode in {"demo", "test"}:
            data["demo_data_acknowledgement"] = "on"
        if mode == "live":
            data["terms_accepted"] = "on"
        return data

    def make_test_order_and_attempt(self, *, price="5500.00", fee="500.00"):
        total = Decimal(price) + Decimal(fee)
        order = Order.objects.create(
            checkout_token=uuid.uuid4(),
            is_demo=True,
            customer_name="Synthetic Customer",
            email="synthetic@example.test",
            phone="+2349000000000",
            fulfilment_method="delivery",
            delivery_zone_name="DEMO Example area",
            delivery_address="DEMO address",
            subtotal_ngn=price,
            delivery_fee_ngn=fee,
            total_ngn=total,
            currency="NGN",
            payment_mode="test",
            status="awaiting_payment",
            payment_status="pending",
        )
        attempt = PaymentAttempt.objects.create(
            order=order,
            mode="test",
            reference=f"FW-{uuid.uuid4().hex}",
            amount_kobo=amount_to_kobo(total),
            status="initialized",
            authorization_url="https://checkout.paystack.com/test-checkout",
        )
        return order, attempt

    def test_profile_defaults_only_to_confirmed_contact_and_live_off(self):
        profile = RestaurantProfile.objects.create()
        self.assertEqual(profile.name, "Foodwagon")
        self.assertEqual(profile.public_email, "sadiq@devlify.com.ng")
        self.assertEqual(profile.public_phone, "+2349034303594")
        self.assertEqual(profile.address, "")
        self.assertEqual(profile.service_area, "")
        self.assertEqual(profile.opening_schedule, "")
        self.assertEqual(profile.privacy_notice_url, "")
        self.assertEqual(profile.terms_url, "")
        self.assertTrue(profile.is_demo)
        self.assertFalse(profile.live_ordering_enabled)
        self.assertFalse(profile.live_payments_enabled)
        self.assertFalse(profile.live_readiness_confirmed)

    def test_seed_command_creates_only_editable_labeled_demo_data_and_is_idempotent(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(RestaurantProfile.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(MenuItem.objects.count(), 3)
        self.assertEqual(DeliveryZone.objects.count(), 1)
        self.assertTrue(all(item.is_demo and item.category.is_demo for item in MenuItem.objects.select_related("category")))
        self.assertTrue(all("DEMO" in item.name for item in MenuItem.objects.all()))
        self.assertTrue(DeliveryZone.objects.get().is_demo)
        self.assertFalse(RestaurantProfile.objects.get().live_readiness_confirmed)

    def test_storefront_keeps_reference_design_but_labels_demo_and_blocks_indexing(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DEMO MODE")
        self.assertContains(response, "Order now")
        self.assertContains(response, "Sign up")
        self.assertContains(response, "Log in")
        self.assertContains(response, "food-category-card--burger")
        self.assertContains(response, "food-hero__doodles")
        self.assertContains(response, "Delivery")
        self.assertContains(response, "Pickup")
        self.assertContains(response, 'name="robots" content="noindex,nofollow"')
        self.assertNotContains(response, ">4.8<")
        self.assertNotContains(response, "8–10 mins")
        self.assertNotContains(response, "₦4,200")
        self.assertEqual(self.client.get(reverse("robots")).status_code, 200)
        self.assertContains(self.client.get(reverse("robots")), "Disallow: /")
        sitemap = self.client.get(reverse("sitemap"))
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("application/xml", sitemap["Content-Type"])
        self.assertNotContains(sitemap, "/<")

    def test_menu_search_filters_items_and_displays_demo_status(self):
        burger = self.make_item(price="2000.00")
        cake = self.make_item(price="2500.00")
        burger.name = "DEMO Burger"
        burger.save(update_fields=["name"])
        cake.name = "DEMO Cake"
        cake.save(update_fields=["name"])
        response = self.client.get(reverse("home"), {"q": "burger"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DEMO Burger")
        self.assertContains(response, "SAMPLE · NOT FOR SALE")
        self.assertNotContains(response, "DEMO Cake")

    def test_basket_add_update_remove_and_server_price(self):
        item = self.make_item(price="1250.00")
        response = self.add_to_basket(item, quantity=2)
        self.assertRedirects(response, reverse("basket"))
        basket_page = self.client.get(reverse("basket"))
        self.assertContains(basket_page, "₦1250.00")
        self.assertContains(basket_page, "₦2500.00")
        self.assertContains(basket_page, "DEMO BASKET")
        self.assertIn("no-store", basket_page["Cache-Control"])
        updated = self.client.post(reverse("update_basket"), {f"quantity_{item.pk}": "3"})
        self.assertRedirects(updated, reverse("basket"))
        self.assertEqual(self.client.session["basket"][str(item.pk)], 3)
        self.client.post(reverse("remove_from_basket", args=[item.pk]))
        self.assertNotIn(str(item.pk), self.client.session["basket"])

    def test_demo_checkout_snapshots_prices_and_never_calls_paystack(self):
        item = self.make_item(price="1200.00")
        zone = self.make_zone(fee="500.00")
        self.add_to_basket(item, quantity=2)
        get_response = self.client.get(reverse("checkout"))
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("no-store", get_response["Cache-Control"])
        token = self.client.session["checkout_token"]
        with patch("foodwagon_site.views.initialize_transaction") as initialize:
            response = self.client.post(reverse("checkout"), self.checkout_data(token=token, zone=zone))
        initialize.assert_not_called()
        order = Order.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("order_status", args=[order.public_token]))
        self.assertEqual(order.payment_mode, "demo")
        self.assertTrue(order.is_demo)
        self.assertEqual(order.payment_status, "demo")
        self.assertEqual(order.status, "demo_complete")
        self.assertEqual(order.subtotal_ngn, Decimal("2400.00"))
        self.assertEqual(order.delivery_fee_ngn, Decimal("500.00"))
        self.assertEqual(order.total_ngn, Decimal("2900.00"))
        self.assertEqual(order.lines.count(), 1)
        self.assertEqual(order.lines.get().unit_price_ngn, Decimal("1200.00"))
        self.assertEqual(order.lines.get().quantity, 2)
        self.assertEqual(PaymentAttempt.objects.count(), 0)
        status_page = self.client.get(reverse("order_status", args=[order.public_token]))
        self.assertContains(status_page, "DEMO ORDER SAVED LOCALLY")
        self.assertContains(status_page, 'name="robots" content="noindex,nofollow"')
        self.assertIn("no-store", status_page["Cache-Control"])
        self.assertNotContains(status_page, "Synthetic Test Customer")
        self.assertNotContains(status_page, "+234 900 000 0000")
        self.assertNotContains(status_page, "DEMO ONLY — Example address")

    @override_settings(PAYMENT_MODE="test", PAYSTACK_TEST_SECRET_KEY="sk_test_unit_fake")
    def test_paystack_test_checkout_uses_server_total_and_never_makes_a_real_request(self):
        item = self.make_item(price="5500.00")
        zone = self.make_zone(fee="500.00")
        self.add_to_basket(item)
        self.assertEqual(self.client.get(reverse("checkout"), secure=True).status_code, 200)
        token = self.client.session["checkout_token"]
        with patch("foodwagon_site.views.initialize_transaction", return_value="https://checkout.paystack.com/authorized-test") as initialize:
            response = self.client.post(
                reverse("checkout"),
                self.checkout_data(token=token, zone=zone, mode="test"),
                secure=True,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://checkout.paystack.com/authorized-test")
        order = Order.objects.get()
        attempt = PaymentAttempt.objects.get(order=order)
        self.assertTrue(order.is_demo)
        self.assertEqual(order.payment_mode, "test")
        self.assertEqual(order.payment_status, "pending")
        self.assertEqual(order.total_ngn, Decimal("6000.00"))
        self.assertEqual(attempt.amount_kobo, 600000)
        self.assertEqual(attempt.status, "initialized")
        kwargs = initialize.call_args.kwargs
        self.assertEqual(kwargs["email"], "checkout-test@example.test")
        self.assertTrue(kwargs["callback_url"].startswith("https://testserver/payments/paystack/return/?token="))
        self.assertEqual(self.client.session["basket"], {})
        replay = self.client.post(reverse("checkout"), self.checkout_data(token=token, zone=zone, mode="test"), secure=True)
        self.assertEqual(replay.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    @override_settings(PAYMENT_MODE="test", PAYSTACK_TEST_SECRET_KEY="sk_test_unit_fake")
    def test_initialization_failure_reuses_order_and_status_retry_creates_one_new_attempt(self):
        item = self.make_item(price="5500.00")
        zone = self.make_zone(fee="500.00")
        self.add_to_basket(item)
        self.client.get(reverse("checkout"), secure=True)
        token = self.client.session["checkout_token"]
        data = self.checkout_data(token=token, zone=zone, mode="test")
        with patch("foodwagon_site.views.initialize_transaction", side_effect=PaystackAPIError("mocked provider failure")) as initialize:
            failed = self.client.post(reverse("checkout"), data, secure=True)
            self.assertEqual(initialize.call_count, 1)
            order = Order.objects.get()
            attempt = PaymentAttempt.objects.get(order=order)
            self.assertEqual(attempt.status, "failed")
            self.assertEqual(order.payment_status, "failed")
            repeated = self.client.post(reverse("checkout"), data, secure=True)
            self.assertEqual(repeated.status_code, 302)
            self.assertEqual(initialize.call_count, 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(PaymentAttempt.objects.count(), 1)
        self.assertEqual(failed.status_code, 200)

        with patch("foodwagon_site.views.initialize_transaction", return_value="https://checkout.paystack.com/retry-test") as retry_init:
            retry = self.client.post(reverse("retry_payment", args=[order.public_token]), secure=True)
        self.assertEqual(retry.status_code, 302)
        self.assertEqual(retry["Location"], "https://checkout.paystack.com/retry-test")
        self.assertEqual(retry_init.call_count, 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(PaymentAttempt.objects.filter(order=order).count(), 2)
        order.refresh_from_db()
        self.assertEqual(order.total_ngn, Decimal("6000.00"))

    @override_settings(PAYMENT_MODE="test", PAYSTACK_TEST_SECRET_KEY="sk_test_unit_fake")
    def test_paystack_api_client_sends_ngn_kobo_and_verifies_reference(self):
        order, attempt = self.make_test_order_and_attempt(price="5500.00", fee="500.00")
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status": True,
            "data": {
                "authorization_url": "https://checkout.paystack.com/example",
                "reference": attempt.reference,
            },
        }
        callback = "https://staging.example.test/payments/paystack/return/?token=" + str(order.public_token)
        with patch("foodwagon_site.payments.requests.post", return_value=response) as post:
            url = initialize_transaction(attempt, email=order.email, callback_url=callback)
        self.assertEqual(url, "https://checkout.paystack.com/example")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.paystack.co/transaction/initialize")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk_test_unit_fake")
        self.assertEqual(kwargs["json"]["amount"], "600000")
        self.assertEqual(kwargs["json"]["currency"], "NGN")
        self.assertEqual(kwargs["json"]["reference"], attempt.reference)
        self.assertEqual(amount_to_kobo("100.00"), 10000)

        verify_response = Mock()
        verify_response.raise_for_status.return_value = None
        verify_response.json.return_value = {
            "status": True,
            "data": {"reference": attempt.reference, "amount": attempt.amount_kobo, "currency": "NGN", "domain": "test", "status": "success"},
        }
        with patch("foodwagon_site.payments.requests.get", return_value=verify_response) as get:
            verified = verify_transaction(attempt)
        self.assertEqual(verified["reference"], attempt.reference)
        self.assertEqual(get.call_args.args[0], f"https://api.paystack.co/transaction/verify/{attempt.reference}")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer sk_test_unit_fake")

    @override_settings(PAYMENT_MODE="test", PAYSTACK_TEST_SECRET_KEY="sk_test_unit_fake")
    def test_callback_verifies_before_marking_test_payment_and_is_idempotent(self):
        order, attempt = self.make_test_order_and_attempt()
        data = {
            "reference": attempt.reference,
            "amount": attempt.amount_kobo,
            "currency": "NGN",
            "domain": "test",
            "status": "success",
        }
        url = reverse("payment_return")
        params = {"reference": attempt.reference, "token": str(order.public_token)}
        with patch("foodwagon_site.views.verify_transaction", return_value=data) as verify:
            first = self.client.get(url, params)
            second = self.client.get(url, params)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        verify.assert_called_once_with(attempt)
        order.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.status, "demo_complete")
        self.assertEqual(attempt.status, "success")

    @override_settings(PAYMENT_MODE="test", PAYSTACK_TEST_SECRET_KEY="sk_test_unit_fake")
    def test_signed_webhook_verifies_signature_deduplicates_and_checks_amount_currency(self):
        order, attempt = self.make_test_order_and_attempt()
        payload = {
            "event": "charge.success",
            "data": {
                "status": "success",
                "reference": attempt.reference,
                "amount": attempt.amount_kobo,
                "currency": "NGN",
                "domain": "test",
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"sk_test_unit_fake", body, hashlib.sha512).hexdigest()
        kwargs = {"data": body, "content_type": "application/json", "HTTP_X_PAYSTACK_SIGNATURE": signature}
        first = self.client.post(reverse("paystack_webhook"), **kwargs)
        repeated = self.client.post(reverse("paystack_webhook"), **kwargs)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["status"], "duplicate")
        self.assertEqual(PaystackWebhookEvent.objects.count(), 1)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.status, "demo_complete")

        bad_payload = {
            "event": "charge.success",
            "data": {
                "status": "success",
                "reference": attempt.reference,
                "amount": attempt.amount_kobo - 1,
                "currency": "USD",
                "domain": "test",
            },
        }
        bad_body = json.dumps(bad_payload, separators=(",", ":")).encode()
        bad_signature = hmac.new(b"sk_test_unit_fake", bad_body, hashlib.sha512).hexdigest()
        mismatch = self.client.post(
            reverse("paystack_webhook"),
            data=bad_body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=bad_signature,
        )
        self.assertEqual(mismatch.status_code, 200)
        self.assertEqual(PaystackWebhookEvent.objects.count(), 2)
        # A payment already marked successful cannot be downgraded by a later malformed event.
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")

    @override_settings(PAYMENT_MODE="test", PAYSTACK_TEST_SECRET_KEY="sk_test_unit_fake")
    def test_amount_or_currency_mismatch_moves_unpaid_order_to_review_not_fulfilment(self):
        order, attempt = self.make_test_order_and_attempt()
        wrong_amount = {"reference": attempt.reference, "amount": attempt.amount_kobo - 1, "currency": "NGN", "domain": "test", "status": "success"}
        from foodwagon_site.views import _apply_payment_result
        self.assertEqual(_apply_payment_result(attempt.pk, wrong_amount), "review")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "review")
        self.assertEqual(order.status, "payment_review")

        order2, attempt2 = self.make_test_order_and_attempt()
        wrong_currency = {
            "reference": attempt2.reference,
            "amount": attempt2.amount_kobo,
            "currency": "USD",
            "domain": "test",
            "status": "success",
        }
        self.assertEqual(_apply_payment_result(attempt2.pk, wrong_currency), "review")
        order2.refresh_from_db()
        self.assertEqual(order2.payment_status, "review")
        self.assertEqual(order2.status, "payment_review")

        order3, attempt3 = self.make_test_order_and_attempt()
        wrong_domain = {"reference": attempt3.reference, "amount": attempt3.amount_kobo, "currency": "NGN", "domain": "live", "status": "success"}
        self.assertEqual(_apply_payment_result(attempt3.pk, wrong_domain), "review")
        order3.refresh_from_db()
        self.assertEqual(order3.payment_status, "review")
        self.assertEqual(order3.status, "payment_review")

    @override_settings(PAYMENT_MODE="test", PAYSTACK_TEST_SECRET_KEY="sk_test_unit_fake")
    def test_bad_webhook_signature_is_rejected_without_event_or_order_change(self):
        order, attempt = self.make_test_order_and_attempt()
        body = json.dumps({"event": "charge.success", "data": {"reference": attempt.reference}}).encode()
        response = self.client.post(
            reverse("paystack_webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE="0" * 128,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PaystackWebhookEvent.objects.count(), 0)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")

    def test_oversized_webhook_is_rejected_without_event_persistence(self):
        from foodwagon_site.views import MAX_WEBHOOK_BYTES

        body = b"{" + (b" " * MAX_WEBHOOK_BYTES)
        response = self.client.post(
            reverse("paystack_webhook"),
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(PaystackWebhookEvent.objects.count(), 0)

    @override_settings(PAYMENT_MODE="test", PAYSTACK_TEST_SECRET_KEY="")
    def test_test_mode_without_test_key_fails_closed(self):
        self.assertEqual(self.client.get(reverse("checkout")).status_code, 503)
        self.assertEqual(self.client.get(reverse("basket")).status_code, 503)
        self.assertEqual(Order.objects.count(), 0)

    @override_settings(
        PAYMENT_MODE="live",
        PAYSTACK_LIVE_SECRET_KEY="",
        LIVE_ORDERING_ENABLED=True,
        LIVE_PAYMENTS_ENABLED=True,
        FOODWAGON_LIVE_CHECKOUT_APPROVED=True,
    )
    def test_live_checkout_remains_off_without_real_key_and_verified_profile(self):
        profile = RestaurantProfile.objects.create(
            is_demo=True,
            live_ordering_enabled=True,
            live_payments_enabled=True,
            live_readiness_confirmed=True,
        )
        self.assertEqual(self.client.get(reverse("checkout")).status_code, 503)
        self.assertEqual(Order.objects.count(), 0)
        self.assertTrue(profile.is_demo)

    def test_dashboard_and_admin_are_staff_protected_and_manage_payment_status_readonly(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
        staff = get_user_model().objects.create_user(
            "staff", password="A-secure-test-password", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent orders")
        self.assertContains(response, "Django admin")
        self.assertIn("no-store", response["Cache-Control"])
        order, _attempt = self.make_test_order_and_attempt()
        request = RequestFactory().get("/admin/")
        request.user = staff
        order_admin = admin.site._registry[Order]
        self.assertIn("status", order_admin.get_readonly_fields(request, order))
        profile_admin = admin.site._registry[RestaurantProfile]
        self.assertIn("live_readiness_confirmed", profile_admin.get_readonly_fields(request))

    def test_public_mutations_require_csrf_tokens(self):
        item = self.make_item()
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(reverse("add_to_basket", args=[item.pk]), {"quantity": 1})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("basket", csrf_client.session)

    def test_production_http_requests_redirect_to_https(self):
        with override_settings(SECURE_SSL_REDIRECT=True):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))

    def test_saved_demo_order_and_private_routes_are_not_indexable(self):
        item = self.make_item(price="1000.00")
        zone = self.make_zone(fee="0.00")
        self.add_to_basket(item)
        self.client.get(reverse("checkout"))
        token = self.client.session["checkout_token"]
        self.client.post(reverse("checkout"), self.checkout_data(token=token, zone=zone))
        order = Order.objects.get()
        status = self.client.get(reverse("order_status", args=[order.public_token]))
        self.assertContains(status, 'name="robots" content="noindex,nofollow"')
        self.assertContains(self.client.get(reverse("basket")), 'name="robots" content="noindex,nofollow"')
        self.add_to_basket(item)
        self.assertContains(self.client.get(reverse("checkout")), 'name="robots" content="noindex,nofollow"')

    def test_paystack_rejects_unexpected_checkout_host(self):
        order, attempt = self.make_test_order_and_attempt()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status": True,
            "data": {"authorization_url": "https://evil.example/steal", "reference": attempt.reference},
        }
        with override_settings(PAYSTACK_TEST_SECRET_KEY="sk_test_unit_fake"):
            with patch("foodwagon_site.payments.requests.post", return_value=response):
                with self.assertRaises(PaystackAPIError):
                    initialize_transaction(
                        attempt,
                        email=order.email,
                        callback_url="https://staging.example.test/paystack/return/",
                    )

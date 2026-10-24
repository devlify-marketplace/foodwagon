import json
import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlsplit

import requests
from django.conf import settings

from .models import Category, DeliveryZone, MenuItem


PAYSTACK_BASE_URL = "https://api.paystack.co"
PAYSTACK_CHECKOUT_HOST = "checkout.paystack.com"
NGN_MINIMUM_KOBO = 5000  # Paystack's documented NGN minimum is ₦50.00.


class PaystackAPIError(Exception):
    """Sanitized provider/API failure; never carries a secret or raw response body."""


def secret_for_mode(mode):
    if mode == "test":
        secret = getattr(settings, "PAYSTACK_TEST_SECRET_KEY", "")
        return secret if secret.startswith("sk_test_") else ""
    if mode == "live":
        secret = getattr(settings, "PAYSTACK_LIVE_SECRET_KEY", "")
        return secret if secret.startswith("sk_live_") else ""
    return ""


def live_readiness_errors(profile):
    errors = []
    if not getattr(settings, "FOODWAGON_LIVE_CHECKOUT_APPROVED", False):
        errors.append("the explicit environment approval is off")
    if not getattr(settings, "LIVE_ORDERING_ENABLED", False):
        errors.append("live ordering is disabled in the environment")
    if not getattr(settings, "LIVE_PAYMENTS_ENABLED", False):
        errors.append("live payments are disabled in the environment")
    if not secret_for_mode("live"):
        errors.append("a valid Paystack live secret key is not configured")
    if not profile:
        errors.append("the restaurant profile is missing")
        return errors
    if profile.is_demo:
        errors.append("the restaurant profile is still marked DEMO")
    if not profile.live_ordering_enabled:
        errors.append("live ordering is not enabled in the restaurant profile")
    if not profile.live_payments_enabled:
        errors.append("live payments are not enabled in the restaurant profile")
    if not profile.live_readiness_confirmed:
        errors.append("the owner has not confirmed live business readiness")
    for field, label in (
        ("name", "business name"),
        ("public_email", "support email"),
        ("public_phone", "support phone"),
        ("address", "pickup/business address"),
        ("service_area", "service area"),
        ("opening_schedule", "operating hours"),
        ("privacy_notice_url", "privacy notice URL"),
        ("terms_url", "terms URL"),
    ):
        if not getattr(profile, field, ""):
            errors.append(f"{label} is not configured")
    if not MenuItem.objects.filter(
        is_demo=False,
        is_available=True,
        category__is_demo=False,
        category__is_active=True,
    ).exists():
        errors.append("there is no owner-verified available menu item")
    if not DeliveryZone.objects.filter(is_demo=False, is_active=True).exists():
        errors.append("there is no owner-verified active delivery zone")
    if not Category.objects.filter(is_demo=False, is_active=True).exists():
        errors.append("there is no owner-verified active menu category")
    return errors


def checkout_mode(profile=None):
    configured_mode = getattr(settings, "PAYMENT_MODE", "disabled")
    if configured_mode == "demo":
        return "demo"
    if configured_mode == "test" and secret_for_mode("test"):
        return "test"
    if configured_mode == "live" and not live_readiness_errors(profile):
        return "live"
    return "disabled"


def amount_to_kobo(amount_ngn):
    try:
        amount = Decimal(amount_ngn).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid NGN amount") from None
    if amount < 0 or amount != Decimal(amount_ngn):
        raise ValueError("NGN amounts must be non-negative with no more than two decimal places")
    return int(amount * 100)


def new_reference(order):
    return f"FW-{order.public_token.hex}-{uuid.uuid4().hex[:20]}"


def _api_response(response):
    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaystackAPIError("Paystack could not complete the request.") from exc
    if not isinstance(payload, dict) or payload.get("status") is not True:
        raise PaystackAPIError("Paystack returned an unsuccessful response.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise PaystackAPIError("Paystack returned an invalid response.")
    return data


def initialize_transaction(attempt, *, email, callback_url, timeout=None):
    secret = secret_for_mode(attempt.mode)
    if not secret:
        raise PaystackAPIError("The matching Paystack environment key is not configured.")
    if amount_to_kobo(attempt.order.total_ngn) != attempt.amount_kobo:
        raise PaystackAPIError("The payment amount does not match the order.")
    if attempt.amount_kobo < NGN_MINIMUM_KOBO:
        raise PaystackAPIError("Paystack requires a minimum NGN payment of ₦50.00.")
    callback = urlsplit(callback_url)
    if callback.scheme != "https" or not callback.netloc:
        raise PaystackAPIError("Paystack callbacks require a public HTTPS site URL.")
    payload = {
        "email": email,
        "amount": str(attempt.amount_kobo),
        "currency": "NGN",
        "reference": attempt.reference,
        "callback_url": callback_url,
        "metadata": json.dumps(
            {"foodwagon_order": attempt.order.public_token.hex, "mode": attempt.mode},
            separators=(",", ":"),
        ),
    }
    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/initialize",
            json=payload,
            headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
            timeout=timeout or settings.PAYSTACK_API_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise PaystackAPIError("Paystack could not be reached; no checkout URL was returned.") from exc
    data = _api_response(response)
    authorization_url = data.get("authorization_url", "")
    returned_reference = data.get("reference", "")
    parsed_url = urlsplit(authorization_url)
    if (
        not authorization_url
        or parsed_url.scheme != "https"
        or parsed_url.hostname != PAYSTACK_CHECKOUT_HOST
        or parsed_url.username
        or parsed_url.password
        or returned_reference != attempt.reference
    ):
        raise PaystackAPIError("Paystack returned an unexpected checkout response.")
    return authorization_url


def verify_transaction(attempt, *, timeout=None):
    secret = secret_for_mode(attempt.mode)
    if not secret:
        raise PaystackAPIError("The matching Paystack environment key is not configured.")
    try:
        response = requests.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{quote(attempt.reference, safe='')}",
            headers={"Authorization": f"Bearer {secret}"},
            timeout=timeout or settings.PAYSTACK_API_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise PaystackAPIError("Paystack could not be reached to verify this payment.") from exc
    return _api_response(response)

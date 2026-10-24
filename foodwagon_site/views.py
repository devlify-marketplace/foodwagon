import hashlib
import hmac
import json
import logging
import uuid
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import CheckoutForm
from .models import (
    Category,
    DemoOrder,
    DeliveryZone,
    MenuItem,
    Order,
    OrderLine,
    PaystackWebhookEvent,
    PaymentAttempt,
    RestaurantProfile,
)
from .payments import (
    NGN_MINIMUM_KOBO,
    PaystackAPIError,
    amount_to_kobo,
    checkout_mode as configured_checkout_mode,
    initialize_transaction,
    live_readiness_errors,
    new_reference,
    secret_for_mode,
    verify_transaction,
)


logger = logging.getLogger(__name__)
PUBLIC_EMAIL = "sadiq@devlify.com.ng"
PUBLIC_PHONE = "+2349034303594"
MAX_CART_QUANTITY = 20
MAX_WEBHOOK_BYTES = 64 * 1024


def profile():
    return RestaurantProfile.objects.order_by("is_demo", "pk").first()


def _private_response(response):
    add_never_cache_headers(response)
    return response


def _safe_cart(request):
    raw = request.session.get("basket", {})
    if not isinstance(raw, dict):
        request.session["basket"] = {}
        return {}
    cart = {}
    for raw_id, raw_quantity in raw.items():
        try:
            item_id = int(raw_id)
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            continue
        if item_id > 0 and 1 <= quantity <= MAX_CART_QUANTITY:
            cart[str(item_id)] = quantity
    if cart != raw:
        request.session["basket"] = cart
    return cart


def _cart_count(request):
    return sum(_safe_cart(request).values())


def _rotate_checkout_token(request):
    request.session.pop("checkout_token", None)


def _cart_summary(request, mode):
    cart = _safe_cart(request)
    if not cart:
        return [], Decimal("0.00")
    query = MenuItem.objects.filter(
        pk__in=[int(item_id) for item_id in cart],
        is_available=True,
        category__is_active=True,
    ).select_related("category")
    if mode == "live":
        query = query.filter(is_demo=False, category__is_demo=False)
    items = {str(item.pk): item for item in query}
    valid_cart = {}
    lines = []
    subtotal = Decimal("0.00")
    for item_id, quantity in cart.items():
        item = items.get(item_id)
        if not item:
            continue
        valid_cart[item_id] = quantity
        line_total = item.price_ngn * quantity
        subtotal += line_total
        lines.append({"item": item, "quantity": quantity, "line_total": line_total})
    if valid_cart != cart:
        request.session["basket"] = valid_cart
        _rotate_checkout_token(request)
    return lines, subtotal


def _checkout_mode(profile_obj=None):
    return configured_checkout_mode(profile_obj)


def _render_checkout_unavailable(request, profile_obj=None):
    return _private_response(render(
        request,
        "foodwagon/checkout_unavailable.html",
        {
            "profile": profile_obj,
            "checkout_mode": "disabled",
            "cart_enabled": False,
            "cart_count": _cart_count(request),
            "setup_requirements": live_readiness_errors(profile_obj)
            if getattr(settings, "PAYMENT_MODE", "disabled") == "live"
            else [],
            "page_noindex": True,
            "canonical": request.build_absolute_uri(reverse("home")),
        },
        status=503,
    ))


def home(request):
    current_profile = profile()
    mode = _checkout_mode(current_profile)
    query = request.GET.get("q", "").strip()[:80]
    menu_items = MenuItem.objects.filter(
        is_available=True,
        category__is_active=True,
    ).select_related("category")
    if query:
        menu_items = menu_items.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )
    categories = Category.objects.filter(is_active=True)
    if query:
        categories = categories.filter(items__in=menu_items).distinct()
    categories = categories.prefetch_related(Prefetch("items", queryset=menu_items))
    return render(
        request,
        "foodwagon/home.html",
        {
            "categories": categories,
            "items": menu_items,
            "query": query,
            "profile": current_profile,
            "checkout_mode": mode,
            "cart_enabled": mode != "disabled",
            "cart_count": _cart_count(request),
            "page_noindex": mode != "live",
            "canonical": request.build_absolute_uri(reverse("home")),
            "public_email": PUBLIC_EMAIL,
            "public_phone": PUBLIC_PHONE,
        },
    )


@require_POST
def add_to_basket(request, item_id):
    current_profile = profile()
    mode = _checkout_mode(current_profile)
    if mode == "disabled":
        return _render_checkout_unavailable(request, current_profile)
    item = get_object_or_404(
        MenuItem.objects.select_related("category"),
        pk=item_id,
        is_available=True,
        category__is_active=True,
    )
    if mode == "live" and (item.is_demo or item.category.is_demo):
        messages.error(request, "This sample item cannot be ordered as a live menu item.")
        return redirect("home")
    try:
        quantity = int(request.POST.get("quantity", "1"))
    except (TypeError, ValueError):
        quantity = 0
    if not 1 <= quantity <= MAX_CART_QUANTITY:
        messages.error(request, f"Choose a quantity between 1 and {MAX_CART_QUANTITY}.")
        return redirect("home")
    cart = _safe_cart(request)
    new_quantity = cart.get(str(item.pk), 0) + quantity
    if new_quantity > MAX_CART_QUANTITY:
        messages.error(request, f"The basket limit is {MAX_CART_QUANTITY} of each item.")
        return redirect("basket")
    cart[str(item.pk)] = new_quantity
    request.session["basket"] = cart
    _rotate_checkout_token(request)
    messages.success(request, f"Added {item.name} to your basket.")
    return redirect("basket")


@require_GET
def basket(request):
    current_profile = profile()
    mode = _checkout_mode(current_profile)
    if mode == "disabled":
        return _render_checkout_unavailable(request, current_profile)
    lines, subtotal = _cart_summary(request, mode)
    return _private_response(render(
        request,
        "foodwagon/basket.html",
        {
            "profile": current_profile,
            "checkout_mode": mode,
            "cart_enabled": True,
            "cart_count": _cart_count(request),
            "page_noindex": True,
            "canonical": request.build_absolute_uri(reverse("home")),
            "lines": lines,
            "subtotal": subtotal,
        },
    ))


@require_POST
def update_basket(request):
    current_profile = profile()
    mode = _checkout_mode(current_profile)
    if mode == "disabled":
        return _render_checkout_unavailable(request, current_profile)
    cart = _safe_cart(request)
    updated = {}
    errors = []
    for item_id in cart:
        raw = request.POST.get(f"quantity_{item_id}", str(cart[item_id]))
        try:
            quantity = int(raw)
        except (TypeError, ValueError):
            errors.append("Enter a whole-number quantity.")
            continue
        if not 0 <= quantity <= MAX_CART_QUANTITY:
            errors.append(f"Quantities must be between 0 and {MAX_CART_QUANTITY}.")
            continue
        if quantity:
            updated[item_id] = quantity
    if errors:
        for error in errors:
            messages.error(request, error)
    else:
        request.session["basket"] = updated
        _rotate_checkout_token(request)
        messages.success(request, "Basket updated.")
    return redirect("basket")


@require_POST
def remove_from_basket(request, item_id):
    cart = _safe_cart(request)
    cart.pop(str(item_id), None)
    request.session["basket"] = cart
    _rotate_checkout_token(request)
    messages.success(request, "Item removed from basket.")
    return redirect("basket")


def _place_order(request, form, mode, current_profile, lines, subtotal):
    cleaned = form.cleaned_data
    fulfilment = cleaned["fulfilment_method"]
    zone = cleaned.get("delivery_zone") if fulfilment == "delivery" else None
    delivery_fee = zone.delivery_fee_ngn if zone else Decimal("0.00")
    total = subtotal + delivery_fee
    if mode in {"test", "live"}:
        try:
            amount_kobo = amount_to_kobo(total)
        except ValueError:
            form.add_error(None, "The order total is not a valid NGN amount.")
            return None
        if amount_kobo < NGN_MINIMUM_KOBO:
            form.add_error(None, "Paystack's minimum NGN payment is ₦50.00. Add items to reach the provider minimum.")
            return None
    try:
        checkout_token = uuid.UUID(str(cleaned["checkout_token"]))
    except (TypeError, ValueError, AttributeError):
        form.add_error(None, "This checkout session expired. Please review your basket and try again.")
        return None
    if str(request.session.get("checkout_token", "")) != str(checkout_token):
        form.add_error(None, "This checkout session expired. Please review your basket and try again.")
        return None

    if mode == "live":
        current_mode = _checkout_mode(profile())
        if current_mode != "live" or not request.is_secure():
            form.add_error(None, "Live checkout is not available for this request. No payment was started.")
            return None
        if cleaned.get("delivery_zone") and cleaned["delivery_zone"].is_demo:
            form.add_error("delivery_zone", "A demo delivery area cannot be used for a live order.")
            return None
        if any(line["item"].is_demo or line["item"].category.is_demo for line in lines):
            form.add_error(None, "Demo menu items cannot be sold in live checkout.")
            return None

    defaults = {
        "is_demo": mode != "live",
        "customer_name": cleaned["customer_name"].strip(),
        "email": cleaned["email"].strip().lower(),
        "phone": cleaned["phone"].strip(),
        "fulfilment_method": fulfilment,
        "delivery_zone_name": str(zone) if zone else "",
        "delivery_address": cleaned.get("delivery_address", "").strip() if fulfilment == "delivery" else "",
        "special_instructions": cleaned.get("special_instructions", "").strip(),
        "terms_accepted_at": timezone.now() if mode == "live" else None,
        "terms_url_snapshot": current_profile.terms_url if mode == "live" else "",
        "privacy_notice_url_snapshot": current_profile.privacy_notice_url if mode == "live" else "",
        "subtotal_ngn": subtotal,
        "delivery_fee_ngn": delivery_fee,
        "total_ngn": total,
        "currency": "NGN",
        "payment_mode": mode,
        "status": "demo_complete" if mode == "demo" else "awaiting_payment",
        "payment_status": "demo" if mode == "demo" else "pending",
    }
    with transaction.atomic():
        order, created = Order.objects.get_or_create(
            checkout_token=checkout_token,
            defaults=defaults,
        )
        if created:
            OrderLine.objects.bulk_create(
                [
                    OrderLine(
                        order=order,
                        menu_item=line["item"],
                        item_name=line["item"].name,
                        unit_price_ngn=line["item"].price_ngn,
                        quantity=line["quantity"],
                        is_demo=mode != "live",
                    )
                    for line in lines
                ]
            )
        elif order.payment_mode != mode:
            form.add_error(None, "This checkout was already started in a different payment mode. Contact staff before retrying.")
            return None

        if not created:
            return redirect("order_status", token=order.public_token)

    if mode == "demo":
        request.session["basket"] = {}
        _rotate_checkout_token(request)
        return redirect("order_status", token=order.public_token)

    if order.payment_status == "paid" or order.payment_status == "review":
        return redirect("order_status", token=order.public_token)
    active_attempt = order.payment_attempts.filter(status="initialized").first()
    if active_attempt and active_attempt.authorization_url:
        request.session["basket"] = {}
        _rotate_checkout_token(request)
        return redirect(active_attempt.authorization_url)
    return _start_paystack_attempt(request, order, mode)


def _start_paystack_attempt(request, order, mode):
    if not request.is_secure():
        messages.error(request, "Paystack checkout requires a public HTTPS site. No payment was started.")
        return None
    try:
        amount_kobo = amount_to_kobo(order.total_ngn)
    except ValueError:
        messages.error(request, "The saved order total cannot be sent to the payment provider.")
        return None
    attempt = PaymentAttempt.objects.create(
        order=order,
        mode=mode,
        reference=new_reference(order),
        amount_kobo=amount_kobo,
        status="initializing",
    )
    callback_url = request.build_absolute_uri(reverse("payment_return"))
    callback_url = f"{callback_url}?{urlencode({'token': str(order.public_token)})}"
    try:
        authorization_url = initialize_transaction(
            attempt,
            email=order.email,
            callback_url=callback_url,
        )
    except PaystackAPIError:
        attempt.status = "failed"
        attempt.save(update_fields=["status", "updated_at"])
        order.payment_status = "failed"
        order.save(update_fields=["payment_status", "updated_at"])
        logger.warning("Paystack initialization failed for order %s", order.public_token.hex[:10])
        messages.error(request, "Paystack did not return a checkout link. No payment was started; review the order and try again.")
        return None
    attempt.status = "initialized"
    attempt.authorization_url = authorization_url
    attempt.save(update_fields=["status", "authorization_url", "updated_at"])
    order.payment_status = "pending"
    order.save(update_fields=["payment_status", "updated_at"])
    request.session["basket"] = {}
    _rotate_checkout_token(request)
    return redirect(authorization_url)


@require_http_methods(["GET", "POST"])
def checkout(request):
    current_profile = profile()
    mode = _checkout_mode(current_profile)
    if mode == "disabled":
        return _render_checkout_unavailable(request, current_profile)
    lines, subtotal = _cart_summary(request, mode)
    if not lines:
        messages.info(request, "Your basket is empty or its menu items are no longer available.")
        return redirect("basket")
    checkout_token = request.session.get("checkout_token")
    if not checkout_token:
        checkout_token = str(uuid.uuid4())
        request.session["checkout_token"] = checkout_token
    initial = {"checkout_token": checkout_token}
    form = CheckoutForm(
        data=request.POST if request.method == "POST" else None,
        initial=initial,
        mode=mode,
        profile=current_profile,
    )
    if request.method == "POST" and form.is_valid():
        if mode != _checkout_mode(profile()):
            form.add_error(None, "Checkout configuration changed. No order was submitted; please reload this page.")
        else:
            result = _place_order(request, form, mode, current_profile, lines, subtotal)
            if result is not None:
                return result
    return _private_response(render(
        request,
        "foodwagon/checkout.html",
        {
            "profile": current_profile,
            "checkout_mode": mode,
            "cart_enabled": True,
            "cart_count": _cart_count(request),
            "page_noindex": True,
            "canonical": request.build_absolute_uri(reverse("home")),
            "lines": lines,
            "subtotal": subtotal,
            "delivery_zones": form.fields["delivery_zone"].queryset,
            "form": form,
            "payment_minimum_ngn": Decimal("50.00"),
        },
    ))


@require_GET
def order_status(request, token):
    current_profile = profile()
    order = get_object_or_404(
        Order.objects.prefetch_related("lines", "payment_attempts"),
        public_token=token,
    )
    latest_attempt = order.payment_attempts.first()
    mode = _checkout_mode(current_profile)
    active_url = ""
    if latest_attempt and latest_attempt.status == "initialized":
        active_url = latest_attempt.authorization_url
    can_retry = bool(
        order.payment_mode in {"test", "live"}
        and order.payment_status == "failed"
        and mode == order.payment_mode
        and order.status not in {"cancelled", "completed", "payment_review"}
    )
    return _private_response(render(
        request,
        "foodwagon/order_status.html",
        {
            "profile": current_profile,
            "checkout_mode": mode,
            "cart_enabled": mode != "disabled",
            "cart_count": _cart_count(request),
            "page_noindex": True,
            "canonical": request.build_absolute_uri(reverse("home")),
            "order": order,
            "latest_attempt": latest_attempt,
            "active_payment_url": active_url,
            "can_retry": can_retry,
        },
    ))


def _apply_payment_result(attempt_id, data):
    with transaction.atomic():
        attempt = PaymentAttempt.objects.select_for_update().select_related("order").get(pk=attempt_id)
        order = Order.objects.select_for_update().get(pk=attempt.order_id)
        if attempt.status == "success" and order.payment_status == "paid":
            return "duplicate"

        expected_kobo = amount_to_kobo(order.total_ngn)
        reference = data.get("reference") if isinstance(data, dict) else None
        currency = data.get("currency") if isinstance(data, dict) else None
        domain = data.get("domain") if isinstance(data, dict) else None
        amount = data.get("amount") if isinstance(data, dict) else None
        status = data.get("status") if isinstance(data, dict) else None
        valid_amount = isinstance(amount, int) and not isinstance(amount, bool) and amount == expected_kobo == attempt.amount_kobo
        valid_identity = (
            reference == attempt.reference
            and currency == "NGN"
            and order.currency == "NGN"
            and domain == attempt.mode
        )

        if status != "success":
            if status in {"failed", "abandoned", "reversed"}:
                attempt.status = "failed"
                attempt.verified_at = timezone.now()
                attempt.save(update_fields=["status", "verified_at", "updated_at"])
                if order.payment_status != "paid":
                    order.payment_status = "failed"
                    order.save(update_fields=["payment_status", "updated_at"])
                return "failed"
            return "pending"

        if not valid_amount or not valid_identity:
            attempt.status = "review"
            attempt.verified_at = timezone.now()
            attempt.save(update_fields=["status", "verified_at", "updated_at"])
            order.payment_status = "review"
            order.status = "payment_review"
            order.save(update_fields=["payment_status", "status", "updated_at"])
            return "review"

        attempt.status = "success"
        attempt.verified_at = timezone.now()
        attempt.save(update_fields=["status", "verified_at", "updated_at"])
        order.payment_status = "paid"
        if order.status in {"cancelled", "completed", "payment_review"}:
            order.status = "payment_review"
        elif attempt.mode == "test" and order.is_demo:
            order.status = "demo_complete"
        elif attempt.mode == "live" and not order.is_demo and not live_readiness_errors(profile()):
            order.status = "received"
        else:
            order.status = "payment_review"
        order.save(update_fields=["payment_status", "status", "updated_at"])
        return "paid" if order.status != "payment_review" else "review"


@require_GET
def payment_return(request):
    reference = request.GET.get("reference") or request.GET.get("trxref")
    raw_token = request.GET.get("token")
    if not reference or not raw_token:
        return HttpResponseBadRequest("Missing payment reference or order token.")
    try:
        token = uuid.UUID(raw_token)
    except (TypeError, ValueError, AttributeError):
        return HttpResponseBadRequest("Invalid order token.")
    attempt = get_object_or_404(
        PaymentAttempt.objects.select_related("order"),
        reference=reference,
        order__public_token=token,
    )
    if attempt.status == "success":
        return redirect("order_status", token=token)
    try:
        data = verify_transaction(attempt)
    except PaystackAPIError:
        logger.warning("Paystack verification unavailable for order %s", token.hex[:10])
        messages.warning(request, "Payment verification is pending. Your order is not confirmed yet; refresh status shortly.")
        return redirect("order_status", token=token)
    outcome = _apply_payment_result(attempt.pk, data)
    if outcome == "review":
        messages.error(request, "Payment details need staff review. Do not submit another payment.")
    elif outcome == "failed":
        messages.warning(request, "The payment was not completed. You can retry from the order status page.")
    return redirect("order_status", token=token)


@require_POST
def retry_payment(request, token):
    current_profile = profile()
    order = get_object_or_404(Order, public_token=token)
    mode = _checkout_mode(current_profile)
    if order.payment_mode not in {"test", "live"} or mode != order.payment_mode:
        messages.error(request, "The matching Paystack mode is not configured; no payment was started.")
        return redirect("order_status", token=token)
    if order.payment_status == "paid" or order.status in {"cancelled", "completed", "payment_review"}:
        return redirect("order_status", token=token)
    if order.payment_mode == "live" and order.is_demo:
        messages.error(request, "A demo order cannot be charged using live credentials.")
        return redirect("order_status", token=token)
    active = order.payment_attempts.filter(status="initialized").first()
    if active:
        return redirect(active.authorization_url)
    response = _start_paystack_attempt(request, order, mode)
    if response is None:
        return redirect("order_status", token=token)
    return response


@csrf_exempt
@require_POST
def paystack_webhook(request):
    content_length = request.META.get("CONTENT_LENGTH", "")
    if content_length:
        try:
            if int(content_length) > MAX_WEBHOOK_BYTES:
                return HttpResponse("Payload too large.", status=413)
        except ValueError:
            return HttpResponseBadRequest("Invalid content length.")
    raw_body = request.body
    if len(raw_body) > MAX_WEBHOOK_BYTES:
        return HttpResponse("Payload too large.", status=413)
    signature = request.headers.get("x-paystack-signature", "")
    if not signature:
        return HttpResponseForbidden("Invalid signature.")
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid JSON.")
    if not isinstance(payload, dict):
        return HttpResponseBadRequest("Invalid event.")
    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}
    event_type = str(payload.get("event", "unknown"))[:80]
    reference = str(data.get("reference", ""))[:80]
    attempt = PaymentAttempt.objects.filter(reference=reference).first() if reference else None
    candidate_secrets = [secret_for_mode(attempt.mode)] if attempt else [
        secret_for_mode("test"),
        secret_for_mode("live"),
    ]
    valid_signature = False
    for secret in candidate_secrets:
        if not secret:
            continue
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
        valid_signature = hmac.compare_digest(expected, signature) or valid_signature
    if not valid_signature:
        return HttpResponseForbidden("Invalid signature.")

    digest = hashlib.sha256(raw_body).hexdigest()
    with transaction.atomic():
        event, created = PaystackWebhookEvent.objects.get_or_create(
            payload_digest=digest,
            defaults={"event_type": event_type, "reference": reference},
        )
        if not created:
            return JsonResponse({"status": "duplicate"}, status=200)
        attempt = PaymentAttempt.objects.select_for_update().filter(reference=reference).first() if reference else None
        if event_type != "charge.success":
            event.result = "ignored"
        elif not attempt:
            event.result = "unknown_reference"
        else:
            event.payment_attempt = attempt
            event.result = _apply_payment_result(attempt.pk, data)
        event.processed_at = timezone.now()
        event.save(update_fields=["payment_attempt", "result", "processed_at"])
    return JsonResponse({"status": "received"}, status=200)


@require_POST
def submit_demo_order(request):
    """Backward-compatible URL name; now submits the same validated checkout."""
    return checkout(request)


def demo_order_complete(request):
    return HttpResponse(
        "Use the private order-status link from checkout.",
        status=410,
        content_type="text/plain; charset=utf-8",
    )


@staff_member_required
def dashboard(request):
    current_profile = profile()
    orders = Order.objects.prefetch_related("lines", "payment_attempts")[:50]
    return _private_response(render(
        request,
        "foodwagon/dashboard.html",
        {
            "orders": orders,
            "order_count": Order.objects.count(),
            "awaiting_payment_count": Order.objects.filter(payment_status="pending").count(),
            "paid_count": Order.objects.filter(payment_status="paid").count(),
            "legacy_demo_orders": DemoOrder.objects.filter(is_demo=True)[:20],
            "items": MenuItem.objects.count(),
            "categories": Category.objects.count(),
            "profile": current_profile,
            "checkout_mode": _checkout_mode(current_profile),
            "cart_enabled": _checkout_mode(current_profile) != "disabled",
            "cart_count": _cart_count(request),
            "page_noindex": True,
            "canonical": request.build_absolute_uri(reverse("home")),
        },
    ))


def robots(request):
    current_profile = profile()
    if current_profile is None or current_profile.is_demo or _checkout_mode(current_profile) != "live":
        return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    return HttpResponse(
        "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /dashboard/\n"
        f"Sitemap: {sitemap_url}\n",
        content_type="text/plain",
    )


def sitemap(request):
    current_profile = profile()
    if current_profile is None or current_profile.is_demo or _checkout_mode(current_profile) != "live":
        return HttpResponse(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
            content_type="application/xml",
        )
    url = request.build_absolute_uri(reverse("home"))
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{url}</loc></url>"
        "</urlset>",
        content_type="application/xml",
    )

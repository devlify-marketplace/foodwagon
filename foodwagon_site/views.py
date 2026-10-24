from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Category, DemoOrder, MenuItem, RestaurantProfile

PUBLIC_EMAIL = "sadiq@devlify.com.ng"
PUBLIC_PHONE = "+2349034303594"


def profile():
    return RestaurantProfile.objects.order_by("is_demo", "pk").first()


def home(request):
    categories = Category.objects.filter(is_active=True).prefetch_related("items")
    menu_items = MenuItem.objects.filter(
        is_available=True,
        category__is_active=True,
    ).select_related("category")
    return render(
        request,
        "foodwagon/home.html",
        {
            "categories": categories,
            "items": menu_items,
            "profile": profile(),
            "canonical": request.build_absolute_uri(reverse("home")),
            "public_email": PUBLIC_EMAIL,
            "public_phone": PUBLIC_PHONE,
        },
    )


def ordering_unavailable(request, item_id=None):
    return HttpResponse(
        "Online ordering is not configured. No order, payment, email, or delivery was accepted.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )


@require_POST
def add_to_cart(request, item_id):
    return ordering_unavailable(request, item_id)


@require_POST
def submit_demo_order(request):
    return ordering_unavailable(request)


def demo_order_complete(request):
    return HttpResponse(
        "There is no public order checkout. Contact Foodwagon directly for verified service information.",
        status=410,
        content_type="text/plain; charset=utf-8",
    )


@staff_member_required

def dashboard(request):
    return render(
        request,
        "foodwagon/dashboard.html",
        {
            "orders": DemoOrder.objects.filter(is_demo=True)[:50],
            "items": MenuItem.objects.count(),
            "categories": Category.objects.count(),
            "profile": profile(),
        },
    )


def robots(request):
    current_profile = profile()
    if current_profile is None or current_profile.is_demo:
        return HttpResponse(
            "User-agent: *\nDisallow: /\n",
            content_type="text/plain",
        )
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    return HttpResponse(
        "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /dashboard/\n"
        f"Sitemap: {sitemap_url}\n",
        content_type="text/plain",
    )


def sitemap(request):
    url = request.build_absolute_uri(reverse("home"))
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{url}</loc></url>"
        "</urlset>",
        content_type="application/xml",
    )

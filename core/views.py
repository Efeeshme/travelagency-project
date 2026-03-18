from django.shortcuts import render
from .models import PopularDestination, SiteSettings


def _get_settings():
    try:
        return SiteSettings.objects.get(pk=1)
    except SiteSettings.DoesNotExist:
        return None


def mainlanding(request):
    settings_obj = _get_settings()
    destinations = PopularDestination.objects.filter(is_active=True).order_by("order", "destination_city")[:8]

    return render(request, "core/mainlanding.html", {
        "settings": settings_obj,
        "destinations": destinations,
    })


def landing(request):
    settings_obj = _get_settings()
    destinations = PopularDestination.objects.filter(is_active=True).order_by("order", "destination_city")

    return render(request, "core/landing.html", {
        "settings": settings_obj,
        "destinations": destinations,
    })
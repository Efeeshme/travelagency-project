# flights/views.py
import logging
from datetime import date
from urllib.parse import quote
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit
from .services import AmadeusService
from core.models import SiteSettings

logger = logging.getLogger(__name__)

def _get_whatsapp_number() -> str:
    try:
        s = SiteSettings.objects.only("whatsapp_number").get(pk=1)
        return (s.whatsapp_number or "").strip()
    except SiteSettings.DoesNotExist:
        return ""

def _whatsapp_url(origin: str, destination: str, departure_date: str, return_date: str | None, adults: int) -> str:
    number = _get_whatsapp_number()
    if not number:
        return ""
    msg = f"Salam bu uçus üçün qiymet almaq isterdim:\n✈ {origin} → {destination}\n📅 Departure: {departure_date}"
    if return_date:
        msg += f"\n📅 Return: {return_date}"
    msg += f"\n👥 {adults} passenger(s)\n\nXaiş eliyirem en yaxşı qiymeti verin."
    return f"https://wa.me/{number}?text={quote(msg)}"

@ratelimit(key='header:x-forwarded-for', rate='20/h', method='GET', block=True)
def search_flights(request):
    if request.method != "GET":
        return JsonResponse({"mode": "error", "error": "GET only"}, status=405)

    origin = request.GET.get("origin", "").strip().upper()
    destination = request.GET.get("destination", "").strip().upper()
    departure_date = request.GET.get("departure_date", "").strip()
    return_date = request.GET.get("return_date", "").strip() or None

    try:
        adults = int(request.GET.get("adults", 1))
    except ValueError:
        adults = 1

    try:
        dep = date.fromisoformat(departure_date)
        if dep < date.today():
            return JsonResponse({"mode": "error", "error": "Departure date cannot be in the past"}, status=400)
    except ValueError:
        return JsonResponse({"mode": "error", "error": "Invalid departure date format (YYYY-MM-DD)"}, status=400)

    if return_date:
        try:
            ret = date.fromisoformat(return_date)
            if ret < dep:
                return JsonResponse({"mode": "error", "error": "Return date cannot be before departure"}, status=400)
        except ValueError:
            return JsonResponse({"mode": "error", "error": "Invalid return date format (YYYY-MM-DD)"}, status=400)

    if not origin or not destination or not departure_date:
        return JsonResponse({"mode": "error", "error": "Missing required fields"}, status=400)
    if len(origin) != 3 or len(destination) != 3:
        return JsonResponse({"mode": "error", "error": "Invalid airport codes (use 3-letter IATA)"}, status=400)
    if origin == destination:
        return JsonResponse({"mode": "error", "error": "Origin and destination cannot be the same"}, status=400)
    if adults < 1 or adults > 9:
        return JsonResponse({"mode": "error", "error": "Adults must be between 1 and 9"}, status=400)

    svc = AmadeusService()
    if not svc.credentials_present():
        logger.error("Amadeus credentials missing")
        return JsonResponse(
            {"mode": "error", "error": "Axtarış xidməti müvəqqəti əlçatmazdır.", "offers": [], "whatsapp_url": ""},
            status=500,
        )

    wa = _whatsapp_url(origin, destination, departure_date, return_date, adults)

    try:
        payload = svc.search_offers(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            max_results=10,
        )
        offers = svc.normalize_offers(payload)
        return JsonResponse(
            {
                "mode": "amadeus",
                "query": {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "adults": adults,
                },
                "count": len(offers),
                "offers": offers,
                "whatsapp_url": wa,
            }
        )
    except Exception as e:
        logger.error("Amadeus search error: %s", str(e), exc_info=True)
        return JsonResponse(
            {
                "mode": "error",
                "error": "Axtarış zamanı xəta baş verdi. Zəhmət olmasa yenidən cəhd edin.",
                "offers": [],
                "whatsapp_url": wa,
            },
            status=500,
        )

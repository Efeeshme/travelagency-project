from django.db import models
import re
from urllib.parse import urlparse, parse_qs, urlencode


def convert_to_embed_url(url: str) -> str:
    """
    Converts any Google Maps URL to the embed format.
    Supported input formats:
      - https://www.google.com/maps/embed?pb=...       (already embed)
      - https://maps.google.com/maps?q=...             (classic share)
      - https://www.google.com/maps/place/NAME/@lat,lng,...
      - https://maps.app.goo.gl/...                    (short link — cannot convert, return as-is)
      - Any other URL — return as-is
    """
    if not url:
        return url

    url = url.strip()

    # Already embed format — no change needed
    if "maps/embed" in url:
        return url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # ── Format 1: maps.google.com/maps?q=ADDRESS or ?ll=lat,lng ──
    # e.g. https://maps.google.com/maps?q=Besti+Bagirova+Meryem+Plaza
    if parsed.netloc in ("maps.google.com", "www.google.com") and parsed.path in ("/maps", "/maps/"):
        q = qs.get("q", [""])[0]
        ll = qs.get("ll", [""])[0]
        if q:
            embed_params = urlencode({"q": q, "output": "embed"})
            return f"https://maps.google.com/maps?{embed_params}"
        if ll:
            lat, lng = ll.split(",")[:2]
            embed_params = urlencode({"ll": ll, "q": f"{lat},{lng}", "output": "embed"})
            return f"https://maps.google.com/maps?{embed_params}"

    # ── Format 2: google.com/maps/place/NAME/@lat,lng,zoom ──
    # e.g. https://www.google.com/maps/place/Meryem+Plaza/@40.3795,49.8468,17z/...
    place_match = re.search(
        r"google\.com/maps/place/([^/]+)/@(-?\d+\.\d+),(-?\d+\.\d+)", url
    )
    if place_match:
        place_name = place_match.group(1).replace("+", " ")
        lat = place_match.group(2)
        lng = place_match.group(3)
        embed_params = urlencode({"q": f"{lat},{lng}", "output": "embed"})
        return f"https://maps.google.com/maps?{embed_params}"

    # ── Format 3: google.com/maps/@lat,lng,zoom (no place name) ──
    coord_match = re.search(r"google\.com/maps/@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if coord_match:
        lat = coord_match.group(1)
        lng = coord_match.group(2)
        embed_params = urlencode({"q": f"{lat},{lng}", "output": "embed"})
        return f"https://maps.google.com/maps?{embed_params}"

    # ── Format 4: short link (maps.app.goo.gl) — cannot expand server-side ──
    if "goo.gl" in url or "maps.app" in url:
        return url  # return unchanged; user should expand manually

    # Fallback: return as-is
    return url


class SiteSettings(models.Model):
    whatsapp_number = models.CharField(max_length=20, default="")
    office_address = models.TextField(blank=True)
    office_hours = models.CharField(max_length=100, blank=True)
    office_phone = models.CharField(max_length=20, blank=True)
    office_email = models.EmailField(blank=True)
    office_map_url = models.URLField(
        max_length=2000,
        blank=True,
        help_text=(
            "Google Maps URL — aşağıdakı formatlardan biri ilə girilə bilər:<br>"
            "• <b>maps.google.com/maps?q=ÜNVAN</b> — ünvan axtarışı<br>"
            "• <b>google.com/maps/place/AD/@lat,lng</b> — yer linki (Copy Link)<br>"
            "• <b>google.com/maps/embed?pb=…</b> — embed URL (Share → Embed)<br>"
            "Qısa linklər (goo.gl) dəstəklənmir — tam URL istifadə edin."
        ),
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Site Settings"

    def save(self, *args, **kwargs):
        self.pk = 1  # singleton
        # Auto-convert any Google Maps URL to embed format on save
        if self.office_map_url:
            self.office_map_url = convert_to_embed_url(self.office_map_url)
        super().save(*args, **kwargs)


class PopularDestination(models.Model):
    origin_city = models.CharField(max_length=100)
    origin_code = models.CharField(max_length=3, help_text="IATA code, e.g. IST")

    destination_city = models.CharField(max_length=100)
    destination_code = models.CharField(max_length=3, help_text="IATA code, e.g. CDG")

    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")

    image = models.ImageField(upload_to="destinations/", blank=True)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "destination_city"]
        verbose_name = "Popular Destination"
        verbose_name_plural = "Popular Destinations"

    def __str__(self):
        return f"{self.origin_city} → {self.destination_city}"
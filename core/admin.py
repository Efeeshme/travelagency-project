# core/admin.py
from django.contrib import admin
from django.utils.html import format_html

from .models import SiteSettings, PopularDestination


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("WhatsApp", {"fields": ("whatsapp_number",)}),
        (
            "Ofis Məlumatları",
            {
                "fields": (
                    "office_address",
                    "office_hours",
                    "office_phone",
                    "office_email",
                    "office_map_url",
                ),
                "description": (
                    "<div style='background:#e8f4fd;border-left:4px solid #00AEEF;"
                    "padding:10px 14px;margin:8px 0;border-radius:4px;font-size:13px'>"
                    "<b>📍 Xəritə URL-i haqqında:</b><br>"
                    "Google Maps-də yerinizi tapın → Sol üst küncü klikləyin → <b>Paylaş</b> → "
                    "<b>Linki kopyala</b> → bu sahəyə yapışdırın.<br>"
                    "Sistem URL-i avtomatik embed formatına çevirəcək."
                    "</div>"
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def map_preview(self, obj):
        if obj.office_map_url and "output=embed" in obj.office_map_url:
            return format_html(
                '<iframe src="{}" width="400" height="200" style="border:1px solid #ddd;'
                'border-radius:8px" loading="lazy"></iframe>',
                obj.office_map_url,
            )
        elif obj.office_map_url:
            return format_html(
                '<span style="color:#e53e3e">⚠ URL embed formatına çevrilə bilmədi. '
                "Lütfən 'Paylaş → Link kopyala' formatından istifadə edin.</span>"
            )
        return "—"

    map_preview.short_description = "Xəritə önizləmə"

    readonly_fields = ("map_preview",)

    fieldsets = (
        ("WhatsApp", {"fields": ("whatsapp_number",)}),
        (
            "Ofis Məlumatları",
            {
                "fields": (
                    "office_address",
                    "office_hours",
                    "office_phone",
                    "office_email",
                    "office_map_url",
                    "map_preview",
                ),
                "description": (
                    "<div style='background:#e8f4fd;border-left:4px solid #00AEEF;"
                    "padding:10px 14px;margin:8px 0;border-radius:4px;font-size:13px'>"
                    "<b>📍 Xəritə URL-i:</b> Google Maps → yeri tap → Sol üst → "
                    "<b>Paylaş → Linki kopyala</b> → bura yapışdır. "
                    "Sistem avtomatik embed URL-ə çevirir.</div>"
                ),
            },
        ),
    )


@admin.register(PopularDestination)
class PopularDestinationAdmin(admin.ModelAdmin):
    list_display = ("preview", "__str__", "price", "currency", "is_active", "order")
    list_editable = ("price", "is_active", "order")
    list_filter = ("is_active", "currency")
    search_fields = ("origin_city", "destination_city", "origin_code", "destination_code")
    ordering = ("order", "destination_city")

    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:56px;height:40px;object-fit:cover;'
                'border-radius:8px;border:1px solid #e2e8f0" />',
                obj.image.url,
            )
        return "—"

    preview.short_description = "Image"
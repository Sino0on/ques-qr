# app/admin.py
import base64
from io import BytesIO

import qrcode
from django.contrib import admin, messages
from django import forms
from django.utils.html import format_html
from django.contrib.admin.helpers import ActionForm
from django import forms

from django.utils.safestring import mark_safe

from .models import Gallery, MediaItem, QRTag, VisitLog, Occasion


# ---------- Inlines ----------

class QRTagInline(admin.TabularInline):
    model = QRTag
    extra = 0
    readonly_fields = ("token", "created_at")
    fields = ("token", "serial", "note", "created_at")
    show_change_link = True


class MediaItemInline(admin.TabularInline):
    model = MediaItem
    extra = 0
    fields = ("file", "preview", "kind", "caption", "sort_order", "is_featured")
    readonly_fields = ("preview",)

    @admin.display(description="Preview")
    def preview(self, obj: MediaItem):
        if not obj or not obj.file:
            return "-"
        # Простое превью для изображений
        if (obj.mime_type or "").startswith("image/"):
            return format_html('<img src="{}" style="max-height:120px;"/>', obj.file.url)
        # Заглушка для видео
        if (obj.mime_type or "").startswith("video/"):
            return mark_safe("🎬 Video")
        return "—"


# ---------- Admin Action с формой (кол-во QR для генерации) ----------

class GenerateQRActionForm(ActionForm):
    count = forms.IntegerField(
        label="Сколько QR сгенерировать на галерею",
        min_value=1,
        max_value=200,
        initial=2,
        help_text="Будут созданы новые QRTag с уникальными токенами"
    )


# ---------- Gallery Admin ----------

@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "title",
        "occasion",
        "template_key",
        "owner",
        "media_count",
        "qrtag_count",
        "is_active",
        "created_at",
        "public_path",
    )
    list_filter = ("occasion", "is_active", "created_at", "updated_at")
    search_fields = ("uuid", "title", "owner__username", "owner__email", "template_key")
    readonly_fields = ("uuid", "first_opened_at", "created_at", "updated_at", "public_path_help")
    inlines = (QRTagInline, MediaItemInline)

    # Экшен и форма к нему
    actions = ("generate_qr_tags",)
    action_form = GenerateQRActionForm

    fieldsets = (
        ("Основное", {
            "fields": ("uuid", "title", "occasion", "template_key", "owner", "is_active"),
        }),
        ("Доступ и защита (необязательно)", {
            "fields": ("view_pin", "upload_pin"),
            "classes": ("collapse",)
        }),
        ("Служебное", {
            "fields": ("first_opened_at", "public_path_help", "created_at", "updated_at"),
        }),
    )

    @admin.display(description="Публичный путь")
    def public_path(self, obj: Gallery):
        # Можно заменить на reverse(...) если настроено именованное URL
        return f"/g/{obj.public_url_slug}"

    @admin.display(description="Справка по публичной ссылке")
    def public_path_help(self, obj: Gallery):
        return mark_safe(
            f'Публичный URL (пример): <code>/g/{obj.public_url_slug}</code><br>'
            "Подставьте домен вашего проекта."
        )

    @admin.display(description="Медиа", ordering="id")
    def media_count(self, obj: Gallery):
        return obj.media.count()

    @admin.display(description="QR", ordering="id")
    def qrtag_count(self, obj: Gallery):
        return obj.qr_tags.count()

    @admin.action(description="Сгенерировать QR-брелки с токенами")
    def generate_qr_tags(self, request, queryset):
        count = self.action_form.cleaned_data.get("count", 2) if hasattr(self, "action_form") else 2
        total_created = 0
        for gallery in queryset:
            batch = [QRTag(gallery=gallery) for _ in range(count)]
            QRTag.objects.bulk_create(batch)
            total_created += len(batch)
        self.message_user(
            request,
            f"Создано {total_created} QRTag для {queryset.count()} галерей.",
            level=messages.SUCCESS
        )


# ---------- QRTag Admin ----------

@admin.register(QRTag)
class QRTagAdmin(admin.ModelAdmin):
    list_display = ("token", "gallery", "qr_preview", "created_at")

    @admin.display(description="QR-код")
    def qr_preview(self, obj):
        url = f"/g/{obj.gallery.public_url_slug}"
        img = qrcode.make(url)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return format_html(
            '<img src="data:image/png;base64,{}" width="100" height="100"/>'
            '<br><a href="/qr/{}/download/" target="_blank">Скачать</a>',
            img_str, obj.token
        )

    @admin.display(description="Путь")
    def public_path(self, obj: QRTag):
        # Токен можно тоже использовать как короткую ссылку, если так решишь
        return f"/g/{obj.gallery.public_url_slug}"


# ---------- MediaItem Admin ----------

@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ("id", "gallery", "kind", "caption", "is_featured", "sort_order", "file_size_fmt", "uploaded_at")
    list_filter = ("kind", "is_featured", "uploaded_at")
    search_fields = ("caption", "gallery__uuid", "gallery__title", "mime_type")
    readonly_fields = ("mime_type", "file_size", "uploaded_at", "preview")
    fields = ("gallery", "file", "preview", "kind", "caption", "sort_order", "is_featured", "mime_type", "file_size", "uploaded_at")

    @admin.display(description="Preview")
    def preview(self, obj: MediaItem):
        if not obj or not obj.file:
            return "-"
        if (obj.mime_type or "").startswith("image/"):
            return format_html('<img src="{}" style="max-height:200px;"/>', obj.file.url)
        if (obj.mime_type or "").startswith("video/"):
            return mark_safe("🎬 Video")
        return "—"

    @admin.display(description="Размер")
    def file_size_fmt(self, obj: MediaItem):
        s = int(obj.file_size or 0)
        if s >= 1024**2:
            return f"{s/1024**2:.1f} MB"
        if s >= 1024:
            return f"{s/1024:.1f} KB"
        return f"{s} B"


# ---------- VisitLog Admin (опционально) ----------

@admin.register(VisitLog)
class VisitLogAdmin(admin.ModelAdmin):
    list_display = ("gallery", "occurred_at", "ip", "ua_short")
    list_filter = ("occurred_at",)
    search_fields = ("gallery__uuid", "ip", "user_agent")

    @admin.display(description="UA")
    def ua_short(self, obj: VisitLog):
        if not obj.user_agent:
            return "-"
        return (obj.user_agent[:80] + "…") if len(obj.user_agent) > 80 else obj.user_agent

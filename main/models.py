import uuid
import mimetypes
from django.conf import settings
from django.db import models


def media_upload_path(instance, filename):
    # uploads/<gallery_uuid>/<original_filename>
    return f"uploads/{instance.gallery.uuid}/{filename}"


def generate_token_hex():
    # Импортируемая функция — миграции смогут её сериализовать
    return uuid.uuid4().hex


class Occasion(models.TextChoices):
    VALENTINE = "valentine", "14 февраля"
    WOMEN_DAY = "womens_day", "8 марта"
    BIRTHDAY  = "birthday", "День рождения"
    ANNIVERS  = "anniversary", "Годовщина"
    OTHER     = "other", "Другое"


class Gallery(models.Model):
    """
    Личное «хранилище воспоминаний», доступное по уникальной ссылке (uuid).
    К галерее можно привязать несколько физических QR-брелков (QRTag).
    """
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True, verbose_name="UUID")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="galleries",
        verbose_name="Владелец"
    )
    title = models.CharField(max_length=120, blank=True, help_text="Опциональный заголовок галереи", verbose_name="Заголовок")
    occasion = models.CharField(max_length=32, choices=Occasion.choices, default=Occasion.OTHER, verbose_name="Повод")
    template_key = models.CharField(max_length=64, default="default", verbose_name="Шаблон")

    first_opened_at = models.DateTimeField(null=True, blank=True, verbose_name="Первое открытие")

    view_pin = models.CharField(max_length=12, blank=True, help_text="Необязательный PIN на просмотр", verbose_name="PIN для просмотра")
    upload_pin = models.CharField(max_length=12, blank=True, help_text="Необязательный PIN на загрузку", verbose_name="PIN для загрузки")

    is_active = models.BooleanField(default=True, verbose_name="Активна")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Галерея"
        verbose_name_plural = "Галереи"

    def __str__(self):
        return f"Галерея {self.uuid} ({self.get_occasion_display()})"

    @property
    def public_url_slug(self) -> str:
        return str(self.uuid)


class QRTag(models.Model):
    """
    Физический QR (брелок/наклейка), который ведёт на конкретную галерею.
    Можно продавать 2 одинаковых QR к одной и той же Gallery.
    """
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="qr_tags", verbose_name="Галерея")
    serial = models.CharField(max_length=40, blank=True, db_index=True, verbose_name="Серийный номер")
    token = models.CharField(max_length=36, unique=True, default=generate_token_hex, verbose_name="Токен")
    note = models.CharField(max_length=120, blank=True, verbose_name="Заметка")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        indexes = [models.Index(fields=["token"])]
        verbose_name = "QR-брелок"
        verbose_name_plural = "QR-брелки"

    def __str__(self):
        return f"QR {self.token} → Галерея {self.gallery_id}"


class MediaItem(models.Model):
    """
    Фото/видео, загруженные в галерею.
    """
    class MediaKind(models.TextChoices):
        AUTO  = "auto", "Определять автоматически"
        IMAGE = "image", "Изображение"
        VIDEO = "video", "Видео"

    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="media", verbose_name="Галерея")
    file = models.FileField(upload_to=media_upload_path, verbose_name="Файл")
    kind = models.CharField(max_length=8, choices=MediaKind.choices, default=MediaKind.AUTO, verbose_name="Тип")
    caption = models.CharField(max_length=200, blank=True, verbose_name="Подпись")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Порядок")
    is_featured = models.BooleanField(default=False, help_text="Показывать как обложку/первым", verbose_name="Обложка")

    mime_type = models.CharField(max_length=100, blank=True, verbose_name="MIME-тип")
    file_size = models.BigIntegerField(default=0, verbose_name="Размер файла (байт)")
    duration_sec = models.PositiveIntegerField(default=0, help_text="Для видео, если нужно", blank=True, verbose_name="Длительность (сек)")

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="uploaded_media",
        verbose_name="Кем загружено"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Загружено")

    class Meta:
        ordering = ["sort_order", "uploaded_at"]
        verbose_name = "Медиафайл"
        verbose_name_plural = "Медиафайлы"

    def __str__(self):
        return f"Медиа #{self.id} в галерее {self.gallery_id}"

    def save(self, *args, **kwargs):
        if self.file and not self.mime_type:
            guessed, _ = mimetypes.guess_type(self.file.name)
            self.mime_type = guessed or ""
        if self.file and hasattr(self.file, "size"):
            self.file_size = self.file.size or 0

        if self.kind == self.MediaKind.AUTO and self.mime_type:
            if self.mime_type.startswith("image/"):
                self.kind = self.MediaKind.IMAGE
            elif self.mime_type.startswith("video/"):
                self.kind = self.MediaKind.VIDEO

        super().save(*args, **kwargs)


class VisitLog(models.Model):
    """
    Лог просмотров галереи (для аналитики).
    """
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="visits", verbose_name="Галерея")
    occurred_at = models.DateTimeField(auto_now_add=True, verbose_name="Время посещения")
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-адрес")
    user_agent = models.TextField(blank=True, verbose_name="User-Agent")

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "Посещение"
        verbose_name_plural = "Посещения"

    def __str__(self):
        return f"Посещение {self.gallery_id} в {self.occurred_at}"

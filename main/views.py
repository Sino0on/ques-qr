# app/views.py
from io import BytesIO
import qrcode
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings

from .models import Gallery, QRTag, MediaItem
from .forms import MultiUploadForm

# уже были:
def qrcode_image(request, token: str):
    try:
        tag = QRTag.objects.select_related("gallery").get(token=token)
    except QRTag.DoesNotExist:
        raise Http404("QR не найден")
    url = request.build_absolute_uri(f"/g/{tag.gallery.public_url_slug}")
    img = qrcode.make(url)
    resp = HttpResponse(content_type="image/png")
    img.save(resp, "PNG")
    return resp

def qrcode_download(request, token: str):
    try:
        tag = QRTag.objects.select_related("gallery").get(token=token)
    except QRTag.DoesNotExist:
        raise Http404("QR не найден")
    url = request.build_absolute_uri(f"/g/{tag.gallery.public_url_slug}")
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    resp = HttpResponse(buf.getvalue(), content_type="image/png")
    resp["Content-Disposition"] = f'attachment; filename="qrcode_{tag.token}.png"'
    return resp


# новая вьюха галереи с загрузкой
def gallery_view(request, uuid: str):
    gallery = get_object_or_404(Gallery.objects.prefetch_related("media"), uuid=uuid)

    # первое открытие зафиксируем один раз
    if not gallery.first_opened_at:
        gallery.first_opened_at = timezone.now()
        gallery.save(update_fields=["first_opened_at"])

    # лимиты (можно вынести в settings)
    max_mb = getattr(settings, "GALLERY_MAX_UPLOAD_MB", 100)
    max_bytes = max_mb * 1024 * 1024
    allowed_prefixes = ("image/", "video/")  # разрешаем картинки и видео

    if request.method == "POST":
        form = MultiUploadForm(request.POST)
        if form.is_valid():
            want_pin = gallery.upload_pin.strip() if gallery.upload_pin else ""
            got_pin = form.cleaned_data.get("pin", "").strip()
            if want_pin and want_pin != got_pin:
                messages.error(request, "Неверный PIN для загрузки.")
                return redirect("gallery_view", uuid=str(gallery.uuid))

            files = request.FILES.getlist("files")  # <-- берём напрямую
            caption = form.cleaned_data.get("caption", "").strip()

            if not files:
                messages.error(request, "Не выбраны файлы.")
                return redirect("gallery_view", uuid=str(gallery.uuid))


            created = 0
            errors = 0
            print(files)
            for f in files:
                # валидации
                size_ok = (f.size or 0) <= max_bytes
                mime = getattr(f, "content_type", "") or ""
                type_ok = mime.startswith(allowed_prefixes)

                if not size_ok:
                    messages.warning(request, f"{f.name}: превышает {max_mb} MB.")
                    errors += 1
                    continue
                if not type_ok:
                    messages.warning(request, f"{f.name}: недопустимый тип ({mime}).")
                    errors += 1
                    continue

                MediaItem.objects.create(
                    gallery=gallery,
                    file=f,
                    caption=caption,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                    # kind/mime/file_size автоопределятся в save()
                )
                created += 1

            if created:
                messages.success(request, f"Загружено файлов: {created}.")
            if errors and not created:
                messages.error(request, "Ни один файл не был загружен.")
            return redirect("gallery_view", uuid=str(gallery.uuid))
        else:
            print(form.errors)
    else:
        form = MultiUploadForm()

    context = {
        "gallery": gallery,
        "media_items": gallery.media.all().order_by("sort_order", "uploaded_at"),
        "form": form,
        "max_mb": max_mb,
        "need_pin": bool(gallery.upload_pin.strip()) if gallery.upload_pin else False,
    }
    # рендерим шаблон по ключу (default/valentine/…)
    return render(request, f"galleries/{gallery.template_key}.html", context)

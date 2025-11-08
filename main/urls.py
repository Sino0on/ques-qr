# app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("qr/<uuid:uuid>/image/", views.qrcode_image, name="qrcode_image"),
    path("qr/<uuid:uuid>/download/", views.qrcode_download, name="qrcode_download"),
    path("g/<uuid:uuid>/", views.gallery_view, name="gallery_view"),
    path("g/<uuid:uuid>/delete/<int:item_id>/", views.media_delete, name="media_delete"),
]

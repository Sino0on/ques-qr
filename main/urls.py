# app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("qr/<str:token>/image/", views.qrcode_image, name="qrcode_image"),
    path("qr/<str:token>/download/", views.qrcode_download, name="qrcode_download"),
    path("g/<uuid:uuid>/", views.gallery_view, name="gallery_view"),
]

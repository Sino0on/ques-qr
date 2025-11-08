# app/forms.py
from django import forms

class MultiUploadForm(forms.Form):
    caption = forms.CharField(max_length=200, required=False, label="Подпись (для всех файлов)")
    pin = forms.CharField(max_length=12, required=False, label="PIN для загрузки")
    sort_order = forms.IntegerField(required=False, min_value=0, label="Порядок (начиная с)")

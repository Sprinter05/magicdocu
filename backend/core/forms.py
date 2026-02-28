from django import forms
from django.forms.models import ModelForm

from core.models import Document

class UploadFileForm(ModelForm):
    class Meta:
        model = Document
        fields = ["file"]

class SelectFileForm(ModelForm):
    class Meta:
        model = Document
        fields = ["file"]
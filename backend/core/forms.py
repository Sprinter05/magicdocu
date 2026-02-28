from django import forms
from django.forms.models import ModelForm

from core.models import Document


class UploadFileForm(ModelForm):
    class Meta:
        model = Document
        fields = ["file", "author", "filetype", "modified_date", "created_date", "accessed_date", "size", "tags", "shared_users"]


class SelectFileForm(ModelForm):
    class Meta:
        model = Document
        fields = ["file"]

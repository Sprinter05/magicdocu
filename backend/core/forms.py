from django import forms
from django.forms.models import ModelForm


class UploadFileForm(ModelForm):
    title = forms.CharField(max_length=50)
    file = forms.FileField()
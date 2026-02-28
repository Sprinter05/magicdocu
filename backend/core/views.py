from django.http import HttpResponseRedirect
from django.shortcuts import render
from .forms import UploadFileForm, SelectFileForm
from django.views.generic.list import ListView
from core.models import Document
from core.workers import *

def upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect("/success/url/")
    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})

def document_list(request):
    if request.method == "POST":
        document_id = request.POST.get("document_id")
        document = Document.objects.get(id=document_id)
        print(extract_text(document.file.name))

    documents = Document.objects.filter(author=request.user)
    return render(request, "document_list.html", {"documents": documents})

import mimetypes
import os
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.shortcuts import render
from core.forms import UploadFileForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .elastic import ElasticDoc


def index(request):
    return render(request, "index.html")

@login_required
def dashboard(request):
    return render(request, "dashboard.html")

def upload_file(request):
    file_meta = None
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        uploaded_file = request.FILES.get("file")
        if uploaded_file:
            content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or ""
            file_meta = {
                "name": uploaded_file.name,
                "size": uploaded_file.size,
                "content_type": content_type,
            }
            if hasattr(uploaded_file, "temporary_file_path"):
                # If Django stored the upload on disk, we can inspect filesystem times
                tmp_path = uploaded_file.temporary_file_path()
                stat = os.stat(tmp_path)
                file_meta["modified_time"] = stat.st_mtime
                file_meta["created_time"] = stat.st_ctime
            now = timezone.now()
            form.instance.size = uploaded_file.size
            form.instance.filetype = content_type
            form.instance.modified_date = now
            form.instance.created_date = now
            form.instance.accessed_date = now
            form.instance.author = request.user
        if form.is_valid():
            form.save()
            return HttpResponseRedirect("/success/url/")
    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form, "file_meta": file_meta})

def search(request):
    query = request.GET.get('q')
    if query:
        docs = ElasticDoc.search().query("match", description=query)
    
    else:
        docs = ElasticDoc.search()

    docs.to_queryset()
    breakpoint()
    return render(request, 'search_result.html', {'docs': docs})
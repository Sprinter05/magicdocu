from django.urls import path, include

from core import views

urlpatterns = [
    path('upload/', views.upload_file, name='upload'),
    path('extract/', views.document_list, name='extract')
]
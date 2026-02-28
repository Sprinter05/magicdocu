from django.urls import path, include

from core import views

urlpatterns = [
    path('/', views.upload_file, name='upload')
]
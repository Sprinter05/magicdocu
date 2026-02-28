from django.urls import path

from core import views

urlpatterns = [
    path('', views.upload_file, name='upload'),
    path('/chat/<int:document_id>/', views.chat_view, name='chat'),
    path('/api/chat/', views.chat_api, name='chat_api'),
    path('documents', views.document_view, name='documents'),
]
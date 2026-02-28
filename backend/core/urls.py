from django.urls import path

from core import views

urlpatterns = [
    path('', views.document_view, name='documents'),
    path('upload/', views.upload_file, name='upload'),
    path('upload/status/<int:document_id>/', views.upload_status, name='upload_status'),
    path('chat/<int:document_id>/', views.chat_view, name='chat'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('<int:id>/', views.document_detail, name='document_detail')
]
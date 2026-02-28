from django.urls import path

from core import views

urlpatterns = [
    path('documents/', views.document_view, name='documents'),
    path('documents/<int:id>/', views.document_detail, name='document_detail'),
    path('upload/', views.upload_file, name='upload'),
    path('chat/<int:document_id>/', views.chat_view, name='chat'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('search/', views.search_view, name='search'),
]
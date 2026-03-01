from django.urls import path

from core import views

urlpatterns = [
    path('', views.document_view, name='documents'),
    path('upload/', views.upload_file, name='upload'),
    path('upload/status/<int:document_id>/', views.upload_status, name='upload_status'),
    path('chat/<int:document_id>/', views.chat_view, name='chat'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('<int:id>/', views.document_detail, name='document_detail'),
    path('<int:id>/tags/add/', views.document_add_tag, name='document_add_tag'),
    path('<int:id>/tags/assign/', views.document_assign_tags, name='document_assign_tags'),
    path('tags/add/', views.tags_add, name='tags_add'),
    path('tags/<int:tag_id>/delete/', views.tags_delete, name='tags_delete'),
    path('<int:id>/content/', views.document_content, name='document_content'),
]
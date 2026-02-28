from django.contrib import admin
from core.models import *

admin.site.register(Tag)
admin.site.register(Keyword)
admin.site.register(Document)
admin.site.register(DocumentChunk)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)

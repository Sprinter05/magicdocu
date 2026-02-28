from django.db import models
from pgvector.django import VectorField

# Create your models here.
class Document(models.Model):
    path = models.TextField(null=False, unique=True)
    author = models.ForeignKey("users.AuthUser", on_delete=models.CASCADE)
    filetype = models.CharField(null=False)
    modified_date = models.DateTimeField(null=False)
    created_date = models.DateTimeField(null=False)
    accessed_date = models.DateTimeField(null=False)
    size = models.IntegerField(null=False)

class Tag(models.Model):
    name = models.CharField(unique=True)
    color = models.CharField() # Use hex color to store (e.g. #AF567D)

class DocumentTags(models.Model):
    document_id = models.ForeignKey("core.Document", on_delete=models.CASCADE)
    tag = models.ForeignKey("core.Tag", on_delete=models.CASCADE)
    
class DocumentHistory(models.Model):
    document_id = models.ForeignKey("core.Document", on_delete=models.CASCADE)
    user_id = models.ForeignKey("users.AuthUser", on_delete=models.CASCADE)
    modification_date = models.DateTimeField(null=False)

class DocumentSharedUsers(models.Model):
    document_id = models.ForeignKey("core.Document", on_delete=models.CASCADE)
    user_id = models.ForeignKey("users.AuthUser", on_delete=models.CASCADE)

class DocumentKeywords(models.Model):
    document_id = models.ForeignKey("core.Document", on_delete=models.CASCADE)
    keyword = models.TextField(null=False)
    embedding = VectorField(
        dimensions=1024,
        null=True,
        blank=True,
    )
    
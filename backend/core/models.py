from django.db import models
from pgvector.django import VectorField

# Create your models here.
class Tag(models.Model):
    name = models.CharField(unique=True)
    color = models.CharField() # Use hex color to store (e.g. #AF567D)

class Document(models.Model):
    path = models.TextField(null=False, unique=True)
    author = models.ForeignKey("users.AuthUser", on_delete=models.CASCADE)
    filetype = models.CharField(null=False)
    modified_date = models.DateTimeField(null=False)
    created_date = models.DateTimeField(null=False)
    accessed_date = models.DateTimeField(null=False)
    size = models.IntegerField(null=False)
    tags = models.ManyToManyField("core.Tag")
    shared_users = models.ManyToManyField("users.AuthUser")
    
class DocumentHistory(models.Model):
    document = models.ForeignKey("core.Document", on_delete=models.CASCADE)
    user = models.ForeignKey("users.AuthUser", on_delete=models.CASCADE)
    modification_date = models.DateTimeField(null=False)

class DocumentKeywords(models.Model):
    pk = models.CompositePrimaryKey("keyword", "document_id")
    document = models.ForeignKey("core.Document", on_delete=models.CASCADE)
    keyword = models.TextField(null=False)
    embedding = VectorField(
        dimensions=1024,
        null=True,
        blank=True,
    )
    
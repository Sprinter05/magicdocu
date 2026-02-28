from django.db import models
from pgvector.django import VectorField

# Create your models here.
class Tag(models.Model):
    name = models.CharField(unique=True)
    color = models.CharField() # Use hex color to store (e.g. #AF567D)

class Document(models.Model):
    file = models.FileField(upload_to="uploads/", null=True)
    author = models.ForeignKey("users.AuthUser", on_delete=models.CASCADE)
    filetype = models.CharField(null=False)
    modified_date = models.DateTimeField(null=False)
    created_date = models.DateTimeField(null=False)
    accessed_date = models.DateTimeField(null=False)
    size = models.IntegerField(null=False)
    tags = models.ManyToManyField("core.Tag", related_name="documents")
    shared_users = models.ManyToManyField("users.AuthUser", related_name="documents")
    
class DocumentHistory(models.Model):
    document = models.ForeignKey("core.Document", on_delete=models.CASCADE)
    user = models.ForeignKey("users.AuthUser", on_delete=models.CASCADE)
    modification_date = models.DateTimeField(null=False)

class DocumentKeywords(models.Model):
    document = models.ForeignKey("core.Document", on_delete=models.CASCADE)
    keyword = models.TextField(null=False)
    embedding = VectorField(
        dimensions=1024,
        null=True,
        blank=True,
    )
    
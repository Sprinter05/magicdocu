from django.db import models
from pgvector.django import VectorField, HnswIndex

# Create your models here.
class Tag(models.Model):
    name = models.CharField(unique=True)
    color = models.CharField() # Use hex color to store (e.g. #AF567D)

class Document(models.Model):
    file = models.FileField(upload_to="uploads/", null=True)
    author = models.ForeignKey("users.AuthUser", on_delete=models.CASCADE)
    filetype = models.CharField(null=False)
    summary = models.TextField(null=True)
    modified_date = models.DateTimeField(null=False)
    created_date = models.DateTimeField(null=False)
    accessed_date = models.DateTimeField(null=False)
    size = models.IntegerField(null=False)
    tags = models.ManyToManyField("core.Tag", related_name="documents")
    shared_users = models.ManyToManyField("users.AuthUser", related_name="documents")
    embedded = models.BooleanField(default=False)

    def __str__(self):
        return self.file.name if self.file else f"Document {self.pk}"

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

class DocumentChunk(models.Model):
    """Stores text chunks of a document along with their vector embeddings."""
    document = models.ForeignKey(
        "core.Document", on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.IntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=1024, null=True, blank=True)

    class Meta:
        ordering = ["document", "chunk_index"]
        indexes = [
            HnswIndex(
                name="chunk_embedding_hnsw_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document}"


class ChatSession(models.Model):
    """A conversation session between a user and a document."""
    document = models.ForeignKey(
        "core.Document", on_delete=models.CASCADE, related_name="chat_sessions"
    )
    user = models.ForeignKey(
        "users.AuthUser", on_delete=models.CASCADE, related_name="chat_sessions"
    )
    title = models.CharField(max_length=255, default="New chat")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.document})"


class ChatMessage(models.Model):
    """A single message in a chat session."""
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]
    session = models.ForeignKey(
        "core.ChatSession", on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"

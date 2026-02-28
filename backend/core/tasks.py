import logging

import fitz  # PyMuPDF
import ollama
from celery import shared_task
from django.conf import settings
from pgvector.django import CosineDistance
from .workers import convert_to_md
import json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 100  # overlap between consecutive chunks


def _extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    text_parts: list[str] = []
    with fitz.open(file_path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split *text* into overlapping chunks of approximately *chunk_size* characters."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts via Ollama."""
    client = ollama.Client(host=settings.OLLAMA_BASE_URL)
    response = client.embed(model=settings.OLLAMA_EMBED_MODEL, input=texts)
    return response.embeddings


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def get_document_summary(self, document_id: int):
    from core.models import Document

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        logger.error("Document %s does not exist", document_id)
        return

    text = convert_to_md(document.file.name)

    if not text:
        Document.objects.filter(pk=document_id).update(summary="No text could be extracted from the document", summarised=True)
        return

    base = f"Only output in your following prompt a summary of the following text, up to a max of 30 words: "
    response = ollama.chat(
        model=settings.OLLAMA_CHAT_MODEL,
        messages=[{"role": "user", "content": f"{base} {text}"}],
    )

    summary = (json.loads(response.model_dump_json())["message"]["content"])

    document.summary = summary
    document.summarised = True
    document.save(update_fields=["summary", "summarised"])


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_document_keywords(self, document_id: int):
    from core.models import Document, Keyword  # local import to avoid circular

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        logger.error("Document %s does not exist", document_id)
        return

    text = convert_to_md(document.file.name)

    base = f"Only output in your following prompt a comma separated list of keywords for the following text, up to a max of 10 keywords: "
    keywords = ollama.chat(
        model=settings.OLLAMA_CHAT_MODEL,
        messages=[{"role": "user", "content": f"{base} {text}"}],
    )

    words = (json.loads(keywords.model_dump_json())["message"]["content"]).split(", ")
    embeddings = _embed_texts(words)

    for idx, (text, embedding) in enumerate(zip(words, embeddings)):
        key = Keyword(
            keyword = text,
            embedding = embedding
        )
        key.save()
        document.keywords.add(key)



@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def search_by_text(self, text: str):
    from core.models import Document, Keyword  # local import to avoid circular
    texts = text.split(",")
    
    try:
        embeddings = _embed_texts(texts)
    except Exception as exc:
        logger.exception("Embedding generation failed for search %s", text)
        raise self.retry(exc=exc)
    
    objs = Keyword.objects.none()
    for idx, (chunk_text, embedding) in enumerate(zip(texts, embeddings)):
        obj = (
            Keyword.objects.annotate(
                distance=CosineDistance("embedding", embedding)
            )
            .filter(distance__lte=0.5)
            .order_by("distance")
        )
        objs |= obj

    docs = Document.objects.all().filter(id__in=objs.values_list("document_id"))
    return docs


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_document_embeddings(self, document_id: int):
    """Extract text from a PDF document, chunk it, generate embeddings and store them."""
    from core.models import Document, DocumentChunk  # local import to avoid circular

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        logger.error("Document %s does not exist", document_id)
        return

    file_path = document.file.path
    logger.info("Processing embeddings for document %s (%s)", document_id, file_path)

    # 1. Extract text
    text = _extract_text_from_pdf(file_path)
    if not text.strip():
        logger.warning("No text extracted from document %s", document_id)
        document.embedded = True
        document.save(update_fields=["embedded"])
        return

    # 2. Chunk
    chunks = _split_text(text)
    logger.info("Split document %s into %d chunks", document_id, len(chunks))

    # 3. Generate embeddings (batch)
    try:
        embeddings = _embed_texts(chunks)
    except Exception as exc:
        logger.exception("Embedding generation failed for document %s", document_id)
        raise self.retry(exc=exc)

    # 4. Store chunks + embeddings
    DocumentChunk.objects.filter(document=document).delete()  # idempotent re-run
    chunk_objs = [
        DocumentChunk(
            document=document,
            chunk_index=idx,
            text=chunk_text,
            embedding=embedding,
        )
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings))
    ]
    DocumentChunk.objects.bulk_create(chunk_objs)

    document.embedded = True
    document.save(update_fields=["embedded"])
    logger.info("Successfully stored %d chunks for document %s", len(chunk_objs), document_id)


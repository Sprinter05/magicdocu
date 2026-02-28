import json
import logging
import mimetypes
import os
import math

import ollama
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from pgvector.django import CosineDistance

from core.forms import UploadFileForm, SelectFileForm
from core.models import ChatMessage, ChatSession, Document, DocumentChunk
from core.tasks import *
from core.workers import *

logger = logging.getLogger(__name__)


def index(request):
    return render(request, "index.html")


@login_required
def dashboard(request):
    docs = search_by_embeddings.delay("prescripciones")
    documents = Document.objects.filter(
        Q(author=request.user) | Q(shared_users=request.user)
    ).distinct()
    return render(request, "dashboard.html", {"documents": documents})


def upload_file(request):
    file_meta = None
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        uploaded_file = request.FILES.get("file")
        if uploaded_file:
            content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or ""
            file_meta = {
                "name": uploaded_file.name,
                "size": uploaded_file.size,
                "content_type": content_type,
            }
            if hasattr(uploaded_file, "temporary_file_path"):
                tmp_path = uploaded_file.temporary_file_path()
                stat = os.stat(tmp_path)
                file_meta["modified_time"] = stat.st_mtime
                file_meta["created_time"] = stat.st_ctime
            now = timezone.now()
            form.instance.size = uploaded_file.size
            form.instance.filetype = content_type
            form.instance.modified_date = now
            form.instance.created_date = now
            form.instance.accessed_date = now
            form.instance.author = request.user
        if form.is_valid():
            doc = form.save()
            # Trigger async embedding generation for PDFs
            if doc.filetype and "pdf" in doc.filetype.lower():
                get_document_summary.delay(doc.id)
                process_document_embeddings.delay(doc.id)
                process_document_keywords.delay(doc.id)
            return HttpResponseRedirect("/")
    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form, "file_meta": file_meta})

# ---------------------------------------------------------------------------
# Chat views
# ---------------------------------------------------------------------------

TOP_K_CHUNKS = 5  # number of relevant chunks to retrieve


def _get_accessible_document(user, document_id):
    """Return a Document the user has access to, or 404."""
    return get_object_or_404(
        Document.objects.filter(Q(author=user) | Q(shared_users=user)).distinct(),
        pk=document_id,
    )


def _embed_query(text: str) -> list[float]:
    """Generate an embedding for a single query string."""
    client = ollama.Client(host=settings.OLLAMA_BASE_URL)
    response = client.embed(model=settings.OLLAMA_EMBED_MODEL, input=[text])
    return response.embeddings[0]


def _retrieve_context(document: Document, query_embedding: list[float], top_k: int = TOP_K_CHUNKS) -> str:
    """Retrieve the most relevant chunks for a query using cosine distance."""
    chunks = (
        DocumentChunk.objects
        .filter(document=document)
        .order_by(CosineDistance("embedding", query_embedding))[:top_k]
    )
    return "\n\n---\n\n".join(c.text for c in chunks)


def _build_messages(session: ChatSession, context: str, user_message: str) -> list[dict]:
    """Build the message list to send to the LLM."""
    system_prompt = (
        "You are a helpful assistant that answers questions about a document. "
        "Use ONLY the following context extracted from the document to answer. "
        "If the answer is not in the context, say so honestly.\n\n"
        f"### Document context:\n{context}"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add recent history (last 10 messages to keep context window manageable)
    history = session.messages.order_by("created_at")[:20]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": user_message})
    return messages


@login_required
def chat_view(request, document_id):
    """Render the chat interface for a specific document."""
    document = _get_accessible_document(request.user, document_id)
    sessions = ChatSession.objects.filter(document=document, user=request.user)

    session_id = request.GET.get("session")
    current_session = None
    messages = []
    if session_id:
        current_session = ChatSession.objects.filter(
            pk=session_id, document=document, user=request.user
        ).first()
        if current_session:
            messages = current_session.messages.all()

    return render(request, "chat.html", {
        "document": document,
        "sessions": sessions,
        "current_session": current_session,
        "messages": messages,
    })


@login_required
@require_POST
def chat_api(request):
    """AJAX endpoint: receive a user message and return the LLM response."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    document_id = data.get("document_id")
    session_id = data.get("session_id")
    user_message = data.get("message", "").strip()

    if not document_id or not user_message:
        return JsonResponse({"error": "document_id and message are required"}, status=400)

    document = _get_accessible_document(request.user, document_id)

    if not document.embedded:
        return JsonResponse({"error": "Document is still being processed. Please try again shortly."}, status=202)

    # Get or create session
    if session_id:
        session = get_object_or_404(
            ChatSession, pk=session_id, document=document, user=request.user
        )
    else:
        title = user_message[:60] + ("…" if len(user_message) > 60 else "")
        session = ChatSession.objects.create(
            document=document, user=request.user, title=title
        )

    # Save user message
    ChatMessage.objects.create(session=session, role="user", content=user_message)

    # RAG: embed query → retrieve chunks → build prompt → call LLM
    try:
        query_embedding = _embed_query(user_message)
        context = _retrieve_context(document, query_embedding)

        llm_messages = _build_messages(session, context, user_message)
        client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        response = client.chat(model=settings.OLLAMA_CHAT_MODEL, messages=llm_messages)
        assistant_content = response.message.content
    except Exception:
        logger.exception("LLM call failed")
        assistant_content = "Sorry, I encountered an error processing your request. Please try again."

    # Save assistant message
    ChatMessage.objects.create(session=session, role="assistant", content=assistant_content)

    return JsonResponse({
        "session_id": session.pk,
        "message": assistant_content,
    })

@login_required
def document_view(request):
    documents = []
    for document in Document.objects.all():
        raw_filetype = document.filetype or ""
        if raw_filetype == "application/pdf":
            filetype_display = "PDF"
        elif "/" in raw_filetype:
            filetype_display = raw_filetype.split("/")[-1].upper()
        else:
            filetype_display = raw_filetype.upper()
        file_name = ""
        if document.file and getattr(document.file, "name", ""):
            file_name = document.file.name.split("/")[-1]
        documents.append({
            "id": document.pk,
            "name": file_name or f"Document {document.pk}",
            "author": document.author,
            "filetype": filetype_display,
            "modified_date": document.modified_date,
            "created_date": document.created_date,
            "accessed_date": document.accessed_date,
            "size": round(document.size / 1024 / 1024, 2),
            "tags": document.tags,
            "shared_users": document.shared_users,
        })
    context = {"documents": documents}
    return render(request, "documents.html", context)

import csv
import io
import mimetypes
import os
import re
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, FileResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import UploadFileForm
from core.models import ChatMessage, ChatSession, Document, DocumentChunk, Tag
from core.tasks import *

from users.models import AuthUser

logger = logging.getLogger(__name__)

DEFAULT_TAG_COLOR = "#94a3b8"
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _normalize_tag_color(value: str) -> str:
    if value and HEX_COLOR_RE.match(value):
        return value.lower()
    return DEFAULT_TAG_COLOR


def index(request):
    return render(request, "index.html")


@login_required
def dashboard(request):
    documents = Document.objects.filter(
        Q(author=request.user) | Q(shared_users=request.user)
    ).distinct()

    recent_documents = documents.filter(created_date__gte=timezone.localdate())
    return render(request, "dashboard.html", {
        "documents": documents,
        "document_count": len(documents),
        "recent_document_count": len(recent_documents)
        })


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
            get_document_summary.delay(doc.id)
            process_document_embeddings.delay(doc.id)
            process_document_keywords.delay(doc.id)
            # If the client expects JSON (fetch/AJAX), return the new document id so frontend can poll /upload/status/<id>
            return JsonResponse({'id': doc.id}, status=201)
    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form, "file_meta": file_meta})


def upload_status(request, document_id):
    document = get_object_or_404(Document, pk=document_id, author=request.user)
    status = {
        "embedded": document.embedded,
        "summarised": document.summarised,
    }
    return JsonResponse(status)


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
    document_tags = []
    documents = []
    all_extensions = []
    all_tags = Tag.objects.all().order_by("name")
    all_documents = Document.objects.filter(Q(author=request.user) | Q(shared_users=request.user)).distinct()

    downfile = request.GET.get("download")
    if downfile:
        return FileResponse(all_documents.filter(file=downfile).first().file.open("rb"), as_attachment=True)

    delfile = request.GET.get("delete")
    if delfile:
        all_documents.filter(file=delfile).first().delete()
    
    filtered_documents = all_documents
    tag_filter = request.GET.get("tags")
    if tag_filter:
        tag_filter = [tag.strip() for tag in tag_filter.split(",") if tag.strip()]
        tag_names = [tag for tag in tag_filter if tag.lower() != "untagged"]

        tag_query = Q()
        if tag_names:
            tag_query |= Q(tags__name__in=tag_names)
        if any(tag.lower() == "untagged" for tag in tag_filter):
            tag_query |= Q(tags__isnull=True)

        if tag_query:
            filtered_documents = filtered_documents.filter(tag_query).distinct()

    filetype_param = request.GET.get("filetype")
    if filetype_param:
        filetype_filter = [ft.strip().lower() for ft in filetype_param.split(",") if ft.strip()]
        filetype_query = Q()
        for ft in filetype_filter:
            filetype_query |= Q(file__iendswith=f".{ft}")
        filtered_documents = filtered_documents.filter(filetype_query)

    date_filter = request.GET.get("date_filter")
    
    if date_filter == "today":
        filtered_documents = filtered_documents.filter(created_date__gte=timezone.localdate())
    elif date_filter == "30":
        filtered_documents = filtered_documents.filter(created_date__gte=timezone.now() - timedelta(days=30))
    elif date_filter == "7":
        filtered_documents = filtered_documents.filter(created_date__gte=timezone.now() - timedelta(days=7))

    query = request.GET.get("q", "").strip()
    if query:
        result = search_by_text(query)
        filtered_documents = filtered_documents.filter(id__in=[(doc.id) for doc in result])

    for document in filtered_documents:
        file_name = document.file.name.split("/")[-1]
        extension = file_name.split(".")[-1]

        if extension not in all_extensions:
            all_extensions.append(extension)

        document_tags = document.tags.all()

        documents.append({
            "id": document.pk,
            "name": file_name,
            "author": document.author,
            "filetype": extension,
            "modified_date": document.modified_date,
            "created_date": document.created_date,
            "accessed_date": document.accessed_date,
            "size": round(document.size / 1048576, 2),
            "tags": document_tags,
            "shared_users": document.shared_users,
        })

    context = {
        "documents": documents,
        "all_extensions": all_extensions,
        "all_tags": all_tags
    }
    return render(request, "documents.html", context)


def document_detail(request, id):
    document = get_object_or_404(Document, pk=id)
    file_name = document.file.name.split("/")[-1]
    extension = file_name.split(".")[-1].upper()
    document_tags = document.tags.all()
    all_tags = Tag.objects.all().order_by("name")

    if request.method == "POST":
        shared_user_ids = request.POST.getlist("shared_user_ids")
        selected_users = AuthUser.objects.filter(id__in=shared_user_ids)
        document.shared_users.set(selected_users)
        return redirect("document_detail", id=id)

    shared_user = request.GET.get("add_shared_user")
    if shared_user:
        document.shared_users.add(AuthUser.objects.all().filter(username=shared_user).first())

    all_users = AuthUser.objects.exclude(id=document.author_id).order_by("username")

    doc_data = {
        "id": document.pk,
        "name": file_name,
        "file": document.file,
        "summary": document.summary,
        "author": document.author,
        "filetype": extension,
        "modified_date": document.modified_date,
        "created_date": document.created_date,
        "accessed_date": document.accessed_date,
        "size": round(document.size / 1048576, 2),
        "tags": document_tags,
        "tag_ids": list(document_tags.values_list("id", flat=True)),
        "shared_users": document.shared_users,
        "shared_user_ids": list(document.shared_users.values_list("id", flat=True)),
    }
    return render(request, "document_detail.html", {
        "document": doc_data,
        "all_tags": all_tags,
        "all_users": all_users,
    })


@login_required
@require_POST
def document_assign_tags(request, id):
    document = _get_accessible_document(request.user, id)
    tag_ids = request.POST.getlist("tag_ids")
    tags = Tag.objects.filter(id__in=tag_ids)
    document.tags.set(tags)

    return redirect("document_detail", id=id)


@login_required
@require_POST
def document_add_tag(request, id):
    document = _get_accessible_document(request.user, id)
    tag_name = request.POST.get("tag_name", "").strip()
    if not tag_name:
        return redirect("document_detail", id=id)

    cleaned_name = " ".join(tag_name.split())
    tag_color = _normalize_tag_color(request.POST.get("tag_color", "").strip())

    tag = Tag.objects.filter(name__iexact=cleaned_name).first()
    if not tag:
        tag = Tag.objects.create(name=cleaned_name, color=tag_color)
    document.tags.add(tag)

    return redirect("document_detail", id=id)


@login_required
@require_POST
def tags_add(request):
    tag_name = request.POST.get("tag_name", "").strip()
    if not tag_name:
        return redirect("documents")

    cleaned_name = " ".join(tag_name.split())
    tag_color = _normalize_tag_color(request.POST.get("tag_color", "").strip())

    tag = Tag.objects.filter(name__iexact=cleaned_name).first()
    if not tag:
        Tag.objects.create(name=cleaned_name, color=tag_color)

    return redirect("documents")


@login_required
@require_POST
def tags_delete(request, tag_id):
    Tag.objects.filter(id=tag_id).delete()
    return redirect("documents")


@login_required
def document_content(request, id):
    """Return file content for preview (CSV, TXT, etc.)"""
    document = get_object_or_404(Document, pk=id)
    file_name = document.file.name.split("/")[-1]
    extension = file_name.split(".")[-1].upper()

    try:
        if extension == "CSV":
            # Read CSV and return as JSON
            with document.file.open('r') as f:
                content = f.read()
                # Detect delimiter
                sniffer = csv.Sniffer()
                try:
                    dialect = sniffer.sniff(content[:1024])
                    delimiter = dialect.delimiter
                except:
                    delimiter = ','

                reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
                rows = list(reader)
                if rows:
                    headers = list(rows[0].keys())
                    return JsonResponse({"type": "csv", "headers": headers, "rows": rows})
                return JsonResponse({"type": "csv", "headers": [], "rows": []})

        elif extension in ["TXT", "MD", "LOG"]:
            # Read text file
            with document.file.open('r') as f:
                content = f.read()
                return JsonResponse({"type": "text", "content": content})

        else:
            return JsonResponse({"error": "Unsupported file type for preview"}, status=400)

    except Exception as e:
        logger.error(f"Error reading file content: {e}")
        return JsonResponse({"error": str(e)}, status=500)



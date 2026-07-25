from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    HealthResponse,
    DocumentListResponse,
    DocumentMetadata,
    KnowledgeBaseResponse,
    ChunksResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    IndexResponse,
    VectorStoreStatus,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedSource,
    AskRequest,
    AskResponse,
    AnswerSource,
)
from app.services.document_loader import DocumentLoader, DocumentChunker
import pathlib

router = APIRouter()

# Path to the knowledge base directory
KNOWLEDGE_BASE_DIR = pathlib.Path(__file__).parent.parent / "knowledge_base"

# Shared instances so documents are loaded once at startup
_loader = DocumentLoader(KNOWLEDGE_BASE_DIR)
_chunker = DocumentChunker(chunk_size=600, overlap=100)

_documents = _loader.load_all()
_chunks = _chunker.chunk_all(_documents)

print(f"[Northstar] Loaded {len(_documents)} documents, generated {len(_chunks)} chunks")

# Lazy-loaded services (avoids loading the embedding model at import time)
_vector_service = None
_retrieval_service = None


def _get_vector_service():
    """Return the shared VectorStoreService instance, creating it on first use."""
    global _vector_service
    if _vector_service is None:
        from app.services.vector_store import VectorStoreService
        _vector_service = VectorStoreService()
    return _vector_service


def _get_retrieval_service():
    """Return the shared RetrievalService instance, creating it on first use."""
    global _retrieval_service
    if _retrieval_service is None:
        from app.services.retrieval_service import RetrievalService
        _retrieval_service = RetrievalService(_get_vector_service())
    return _retrieval_service


# Lazy-loaded LLM service
_llm_service = None


def _get_llm_service():
    """Return the shared LLMService instance, creating it on first use."""
    global _llm_service
    if _llm_service is None:
        from app.services.llm_service import LLMService
        _llm_service = LLMService(_get_retrieval_service())
    return _llm_service


# ── Phase-1 endpoints ────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Return the health status of the API."""
    return HealthResponse(
        status="healthy",
        service="Northstar AI Knowledge Assistant"
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """Return filenames of all Markdown documents in the knowledge base."""
    documents = []

    if KNOWLEDGE_BASE_DIR.exists() and KNOWLEDGE_BASE_DIR.is_dir():
        for file_path in KNOWLEDGE_BASE_DIR.glob("*.md"):
            documents.append(file_path.name)

    # Sort for consistent output
    documents.sort()

    return DocumentListResponse(
        count=len(documents),
        documents=documents
    )


# ── Phase-2 endpoints: Document Processing ────────────────────────────


@router.get("/knowledge-base", response_model=KnowledgeBaseResponse)
async def get_knowledge_base():
    """Return metadata for every loaded document."""
    metadata_list = [
        DocumentMetadata(
            filename=doc["filename"],
            title=doc["title"],
            size=doc["size"],
            number_of_lines=doc["number_of_lines"],
        )
        for doc in _documents
    ]
    return KnowledgeBaseResponse(documents=metadata_list)


@router.get("/chunks/preview", response_model=ChunksResponse)
async def preview_chunks():
    """Return the first 5 chunks (useful for debugging)."""
    preview = _chunks[:5]
    return ChunksResponse(count=len(preview), chunks=preview)


@router.get("/chunks/{document_name}", response_model=ChunksResponse)
async def get_chunks_by_document(document_name: str):
    """Return all chunks for a specific document.

    Raises 404 if the document name is not found.
    """
    filtered = [c for c in _chunks if c["document_name"] == document_name]

    if not filtered:
        raise HTTPException(
            status_code=404,
            detail=f"No chunks found for document '{document_name}'",
        )

    return ChunksResponse(count=len(filtered), chunks=filtered)


@router.get("/chunks", response_model=ChunksResponse)
async def get_all_chunks():
    """Return every chunk across all documents."""
    return ChunksResponse(count=len(_chunks), chunks=_chunks)


# ── Phase-3 endpoints: Vector Store & Search ──────────────────────────


@router.post("/vector-store/index", response_model=IndexResponse)
async def index_documents():
    """Embed all knowledge-base chunks and store them in ChromaDB.

    Safe to call multiple times — duplicates are skipped.
    """
    service = _get_vector_service()
    result = service.index()
    return IndexResponse(**result)


@router.post("/vector-store/rebuild", response_model=IndexResponse)
async def rebuild_index():
    """Delete the existing collection and re-index from scratch."""
    service = _get_vector_service()
    result = service.rebuild()
    return IndexResponse(**result)


@router.get("/vector-store/status", response_model=VectorStoreStatus)
async def vector_store_status():
    """Return information about the vector store."""
    service = _get_vector_service()
    result = service.status()
    return VectorStoreStatus(**result)


@router.post("/search", response_model=SearchResponse)
async def semantic_search(request: SearchRequest):
    """Perform semantic search over the indexed knowledge base.

    Expects a JSON body with 'query' (required) and 'top_k' (optional, 1-10).
    """
    service = _get_vector_service()

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    raw_results = service.search(query=request.query, top_k=request.top_k)

    results = [SearchResult(**r) for r in raw_results]

    return SearchResponse(
        query=request.query,
        count=len(results),
        results=results,
    )


# ── Phase-4 endpoints: Retrieval Pipeline ─────────────────────────────


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_context(request: RetrievalRequest):
    """Run the full retrieval pipeline for a question.

    Steps: semantic search → relevance filter → deduplication
    → source selection → context construction.
    """
    # Check that the vector store is ready
    vs = _get_vector_service()
    status = vs.status()
    if not status["ready"]:
        raise HTTPException(
            status_code=503,
            detail="Vector store is not ready. Index documents first.",
        )

    retrieval = _get_retrieval_service()

    try:
        result = retrieval.retrieve(
            question=request.question,
            top_k=request.top_k,
            candidate_count=request.candidate_count,
            minimum_relevance=request.minimum_relevance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during retrieval.",
        )

    sources = [RetrievedSource(**s) for s in result["sources"]]

    return RetrievalResponse(
        question=result["question"],
        sufficient_context=result["sufficient_context"],
        context=result["context"],
        sources=sources,
        retrieved_count=result["retrieved_count"],
        highest_relevance=result["highest_relevance"],
    )


# ── Phase-5 endpoints: LLM Answer Generation ─────────────────────────


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Answer a question using retrieval-augmented generation.

    Flow: question → RetrievalService → sufficient-context check
    → LLMService (Gemini) → grounded answer with source citations.
    """
    # Check that the vector store is ready
    vs = _get_vector_service()
    status = vs.status()
    if not status["ready"]:
        raise HTTPException(
            status_code=503,
            detail="Vector store is not ready. Index documents first.",
        )

    llm = _get_llm_service()

    try:
        result = llm.ask(
            question=request.question,
            top_k=request.top_k,
            minimum_relevance=request.minimum_relevance,
        )
    except RuntimeError as exc:
        # Missing API key or Gemini provider error
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating the answer.",
        )

    sources = [AnswerSource(**s) for s in result["sources"]]

    return AskResponse(
        question=result["question"],
        answer=result["answer"],
        sources=sources,
        sufficient_context=result["sufficient_context"],
        model=result["model"],
        response_time_ms=result["response_time_ms"],
    )

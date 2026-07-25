from pydantic import BaseModel, Field
from typing import List


class HealthResponse(BaseModel):
    status: str
    service: str


class RootResponse(BaseModel):
    message: str


class DocumentListResponse(BaseModel):
    count: int
    documents: List[str]


# ── Phase 2: Document Processing Models ──────────────────────────────


class DocumentMetadata(BaseModel):
    """Metadata for a single knowledge-base document."""
    filename: str
    title: str
    size: int
    number_of_lines: int


class DocumentChunk(BaseModel):
    """A single text chunk produced by the DocumentChunker."""
    chunk_id: str
    document_name: str
    title: str
    chunk_index: int
    text: str
    start_character: int
    end_character: int


class KnowledgeBaseResponse(BaseModel):
    """Response model for GET /api/knowledge-base."""
    documents: List[DocumentMetadata]


class ChunksResponse(BaseModel):
    """Response model for chunk list endpoints."""
    count: int
    chunks: List[DocumentChunk]


# ── Phase 3: Vector Store & Search Models ─────────────────────────────


class SearchRequest(BaseModel):
    """Request body for POST /api/search."""
    query: str
    top_k: int = Field(default=3, ge=1, le=10)


class SearchResult(BaseModel):
    """A single search result with relevance score."""
    chunk_id: str
    document_name: str
    title: str
    text: str
    relevance_score: float


class SearchResponse(BaseModel):
    """Response model for POST /api/search."""
    query: str
    count: int
    results: List[SearchResult]


class IndexResponse(BaseModel):
    """Response model for indexing endpoints."""
    status: str
    documents_processed: int
    chunks_indexed: int
    collection: str


class VectorStoreStatus(BaseModel):
    """Response model for GET /api/vector-store/status."""
    collection: str
    vector_db_path: str
    indexed_chunks: int
    embedding_model: str
    ready: bool


# ── Phase 4: Retrieval Pipeline Models ────────────────────────────────


class RetrievalRequest(BaseModel):
    """Request body for POST /api/retrieve."""
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=8)
    candidate_count: int = Field(default=8, ge=1, le=20)
    minimum_relevance: float = Field(default=0.55, ge=0.0, le=1.0)


class RetrievedSource(BaseModel):
    """A single source returned by the retrieval pipeline."""
    source_number: int
    chunk_id: str
    document_name: str
    title: str
    text: str
    relevance_score: float


class RetrievalResponse(BaseModel):
    """Response model for POST /api/retrieve."""
    question: str
    sufficient_context: bool
    context: str
    sources: List[RetrievedSource]
    retrieved_count: int
    highest_relevance: float


# ── Phase 5: LLM Answer Generation Models ────────────────────────────


class AskRequest(BaseModel):
    """Request body for POST /api/ask."""
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=8)
    minimum_relevance: float = Field(default=0.55, ge=0.0, le=1.0)


class AnswerSource(BaseModel):
    """A source cited in an LLM-generated answer."""
    source_number: int
    document_name: str
    title: str
    excerpt: str
    relevance_score: float


class AskResponse(BaseModel):
    """Response model for POST /api/ask."""
    question: str
    answer: str
    sources: List[AnswerSource]
    sufficient_context: bool
    model: str
    response_time_ms: int

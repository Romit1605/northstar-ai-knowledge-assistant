"""
Retrieval Service

Builds a reliable retrieval pipeline on top of the existing ChromaDB
semantic search.  Performs:

    semantic search → filtering → source selection → context construction

Does NOT use any LLM.  All logic is rule-based.
"""

import re
from typing import List

from app.services.vector_store import VectorStoreService


# Regex to strip the fictional-document HTML comment from chunk text
_COMMENT_RE = re.compile(
    r"<!--\s*FICTIONAL DOCUMENT.*?-->\s*",
    re.DOTALL,
)


class RetrievalService:
    """Retrieves, filters, and formats knowledge-base context for a question.

    Pipeline:
        1. Semantic search  – retrieve candidate chunks from ChromaDB.
        2. Relevance filter  – drop chunks below minimum_relevance.
        3. Deduplication      – remove exact-duplicate text.
        4. Source selection   – cap per-document chunks (max 3).
        5. Context build     – assemble a numbered context string.

    Usage:
        service = RetrievalService(vector_store)
        result  = service.retrieve("How many PTO days do I get?")
    """

    MAX_QUESTION_LENGTH = 1000
    MAX_CHUNKS_PER_DOCUMENT = 3

    def __init__(self, vector_store: VectorStoreService):
        self._vector_store = vector_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        question: str,
        top_k: int = 4,
        candidate_count: int = 8,
        minimum_relevance: float = 0.55,
    ) -> dict:
        """Run the full retrieval pipeline.

        Args:
            question:          Natural-language question (1–1000 chars).
            top_k:             Maximum sources to return (1–8).
            candidate_count:   How many raw results to fetch (1–20).
            minimum_relevance: Lowest acceptable relevance score (0–1).

        Returns:
            A dict with question, sufficient_context, context, sources,
            retrieved_count, and highest_relevance.
        """
        # ── 1. Validate & normalise ──────────────────────────────────
        question = self._validate_question(question)

        # ── 2. Semantic search ───────────────────────────────────────
        raw_results = self._vector_store.search(
            query=question,
            top_k=candidate_count,
        )

        # ── 3. Relevance filter (Absolute & Dynamic) ─────────────────
        filtered = [
            r for r in raw_results
            if r["relevance_score"] >= minimum_relevance
        ]

        if filtered:
            best_score = max(r["relevance_score"] for r in filtered)
            # Drop sources that are significantly weaker than the best source
            filtered = [r for r in filtered if r["relevance_score"] >= best_score - 0.15]

        # ── 4. Deduplication ─────────────────────────────────────────
        filtered = self._deduplicate(filtered)

        # ── 5. Source selection (cap per document) ───────────────────
        filtered = self._cap_per_document(filtered)

        # ── 6. Sort by relevance descending, limit to top_k ─────────
        filtered.sort(key=lambda r: r["relevance_score"], reverse=True)
        filtered = filtered[:top_k]

        # ── 7. Clean text & build context ────────────────────────────
        sources = self._build_sources(filtered)
        context = self._build_context(sources)
        highest = sources[0]["relevance_score"] if sources else 0.0
        sufficient = len(sources) > 0 and highest >= minimum_relevance

        return {
            "question": question,
            "sufficient_context": sufficient,
            "context": context,
            "sources": sources,
            "retrieved_count": len(sources),
            "highest_relevance": round(highest, 4),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @classmethod
    def _validate_question(cls, question: str) -> str:
        """Trim, length-check, and reject empty questions."""
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty")
        if len(question) > cls.MAX_QUESTION_LENGTH:
            raise ValueError(
                f"Question exceeds {cls.MAX_QUESTION_LENGTH} characters"
            )
        return question

    @staticmethod
    def _deduplicate(results: List[dict]) -> List[dict]:
        """Remove duplicate or nearly identical chunks."""
        unique = []
        for r in results:
            text = r["text"].strip()
            # Tokenize into a set of lowercase words for basic overlap checking
            words = set(text.lower().split())
            is_duplicate = False
            for u in unique:
                u_words = set(u["text"].strip().lower().split())
                if not words or not u_words:
                    continue
                overlap = len(words & u_words)
                # If more than 80% of words overlap with an existing chunk, skip it
                if overlap / len(words) > 0.8 or overlap / len(u_words) > 0.8:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(r)
        return unique

    @classmethod
    def _cap_per_document(cls, results: List[dict]) -> List[dict]:
        """Allow at most MAX_CHUNKS_PER_DOCUMENT from any single document."""
        doc_counts: dict[str, int] = {}
        capped = []
        for r in results:
            doc = r["document_name"]
            count = doc_counts.get(doc, 0)
            if count < cls.MAX_CHUNKS_PER_DOCUMENT:
                capped.append(r)
                doc_counts[doc] = count + 1
        return capped

    @staticmethod
    def _clean_text(text: str) -> str:
        """Strip the fictional-document HTML comment from chunk text."""
        return _COMMENT_RE.sub("", text).strip()

    @classmethod
    def _build_sources(cls, results: List[dict]) -> List[dict]:
        """Convert raw search results into numbered source dicts."""
        sources = []
        for i, r in enumerate(results, start=1):
            sources.append({
                "source_number": i,
                "chunk_id": r["chunk_id"],
                "document_name": r["document_name"],
                "title": r["title"],
                "text": cls._clean_text(r["text"]),
                "relevance_score": round(r["relevance_score"], 4),
            })
        return sources

    @staticmethod
    def _build_context(sources: List[dict]) -> str:
        """Assemble a numbered context string from source dicts.

        Format:
            [SOURCE 1]
            Document: filename.md
            Title: …
            Relevance: 0.82
            Content:
            <chunk text>
        """
        if not sources:
            return ""

        blocks = []
        for src in sources:
            block = (
                f"[Source {src['source_number']}]\n"
                f"Document: {src['document_name']}\n"
                f"Title: {src['title']}\n"
                f"Relevance: {src['relevance_score']}\n"
                f"Content:\n{src['text']}"
            )
            blocks.append(block)

        return "\n\n".join(blocks)

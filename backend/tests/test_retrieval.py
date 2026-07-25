"""
Tests for the retrieval pipeline.

Run with:  pytest tests/test_retrieval.py -v
"""

import pytest
from unittest.mock import patch

from app.services.vector_store import VectorStoreService
from app.services.retrieval_service import RetrievalService


@pytest.fixture(scope="module")
def retrieval_service():
    """Create a VectorStoreService and RetrievalService for testing.

    Ensures the vector store is indexed before tests run.
    """
    vs = VectorStoreService()
    vs.index()
    return RetrievalService(vs)


def test_relevant_question_returns_context(retrieval_service):
    """A question about a known policy should return sufficient context."""
    result = retrieval_service.retrieve(
        question="How many days can employees work remotely?",
        top_k=4,
        candidate_count=8,
        minimum_relevance=0.55,
    )

    assert result["sufficient_context"] is True
    assert result["retrieved_count"] >= 1
    assert len(result["sources"]) >= 1
    assert result["highest_relevance"] >= 0.55
    assert result["context"] != ""
    # The top result should reference the remote work policy
    assert "remote" in result["sources"][0]["document_name"].lower() or \
           "remote" in result["sources"][0]["text"].lower()


def test_unrelated_question_with_high_threshold(retrieval_service):
    """An unrelated question with a very high threshold should return no context."""
    result = retrieval_service.retrieve(
        question="What is the recipe for chocolate chip cookies?",
        top_k=4,
        candidate_count=8,
        minimum_relevance=0.99,  # Impossibly high threshold
    )

    assert result["sufficient_context"] is False
    assert result["retrieved_count"] == 0
    assert result["context"] == ""
    assert result["sources"] == []


def test_deduplication_removes_identical_chunks(retrieval_service):
    """Test that highly overlapping or identical chunks are removed."""
    # We mock the _vector_store.search to return duplicates
    with patch.object(retrieval_service._vector_store, 'search') as mock_search:
        mock_search.return_value = [
            {
                "chunk_id": "doc1_0", "document_name": "doc1.md", "title": "Doc 1",
                "text": "This is a test document about remote work.",
                "relevance_score": 0.90
            },
            {
                "chunk_id": "doc1_1", "document_name": "doc1.md", "title": "Doc 1",
                "text": "This is a test document about remote work.", # Exact duplicate
                "relevance_score": 0.89
            },
            {
                "chunk_id": "doc2_0", "document_name": "doc2.md", "title": "Doc 2",
                "text": "Completely different text about office hours.",
                "relevance_score": 0.85
            }
        ]
        
        result = retrieval_service.retrieve("remote work", candidate_count=3, minimum_relevance=0.5)
        
        # Should only have 2 sources: doc1_0 and doc2_0
        assert result["retrieved_count"] == 2
        assert result["sources"][0]["chunk_id"] == "doc1_0"
        assert result["sources"][1]["chunk_id"] == "doc2_0"


def test_dynamic_threshold_removes_weak_sources(retrieval_service):
    """Test that sources significantly weaker than the best source are dropped."""
    with patch.object(retrieval_service._vector_store, 'search') as mock_search:
        mock_search.return_value = [
            {
                "chunk_id": "doc1_0", "document_name": "doc1.md", "title": "Doc 1",
                "text": "Perfect match for the query.",
                "relevance_score": 0.90
            },
            {
                "chunk_id": "doc2_0", "document_name": "doc2.md", "title": "Doc 2",
                "text": "A very weak match that passes absolute threshold but is relatively weak.",
                "relevance_score": 0.60 # > 0.55 but < 0.90 - 0.15 (0.75)
            }
        ]
        
        result = retrieval_service.retrieve("match", candidate_count=2, minimum_relevance=0.55)
        
        # Only the strong source should remain
        assert result["retrieved_count"] == 1
        assert result["sources"][0]["chunk_id"] == "doc1_0"

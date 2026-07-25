"""
Tests for the LLM answer-generation service.

All tests use mocks — no real Gemini API calls are made.

Run with:  pytest tests/test_llm_service.py -v
"""

from unittest.mock import patch, MagicMock
import pytest

from app.services.llm_service import LLMService, FALLBACK_ANSWER


# ── Helpers ──────────────────────────────────────────────────────────


def _mock_retrieval_sufficient():
    """Return a mock RetrievalService that reports sufficient context."""
    mock = MagicMock()
    mock.retrieve.return_value = {
        "question": "How many remote days per week?",
        "sufficient_context": True,
        "context": (
            "[SOURCE 1]\n"
            "Document: 02_remote_work_policy.md\n"
            "Title: Northstar Innovation — Remote Work Policy\n"
            "Relevance: 0.82\n"
            "Content:\n"
            "Hybrid employees must work from a Northstar office "
            "at least two days per week."
        ),
        "sources": [
            {
                "source_number": 1,
                "chunk_id": "02_remote_work_policy_0",
                "document_name": "02_remote_work_policy.md",
                "title": "Northstar Innovation — Remote Work Policy",
                "text": (
                    "Hybrid employees must work from a Northstar office "
                    "at least two days per week."
                ),
                "relevance_score": 0.82,
            }
        ],
        "retrieved_count": 1,
        "highest_relevance": 0.82,
    }
    return mock


def _mock_retrieval_insufficient():
    """Return a mock RetrievalService that reports insufficient context."""
    mock = MagicMock()
    mock.retrieve.return_value = {
        "question": "What is the recipe for cookies?",
        "sufficient_context": False,
        "context": "",
        "sources": [],
        "retrieved_count": 0,
        "highest_relevance": 0.0,
    }
    return mock


# ── Test 1: Relevant question calls Gemini ───────────────────────────


@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_relevant_question_calls_gemini(mock_settings, mock_genai):
    """When context is sufficient, Gemini should be called and an answer returned."""
    # Configure the mocked settings
    mock_settings.gemini_api_key = "test-key-123"
    mock_settings.gemini_model = "gemini-2.0-flash"

    # Set up the mock Gemini response
    mock_response = MagicMock()
    mock_response.text = (
        "Hybrid employees may work remotely up to three days per week. [1]"
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    retrieval = _mock_retrieval_sufficient()
    service = LLMService(retrieval)

    result = service.ask("How many remote days per week?")

    # Gemini was called
    mock_client.models.generate_content.assert_called_once()

    # Response structure is correct
    assert result["sufficient_context"] is True
    assert "three days" in result["answer"]
    assert result["question"] == "How many remote days per week?"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["document_name"] == "02_remote_work_policy.md"
    assert result["model"] == "gemini-2.0-flash"
    assert "response_time_ms" in result


# ── Test 2: Insufficient context skips Gemini ────────────────────────


@patch("app.services.llm_service.genai")
def test_insufficient_context_skips_gemini(mock_genai):
    """When context is insufficient, Gemini must NOT be called."""
    retrieval = _mock_retrieval_insufficient()
    service = LLMService(retrieval)

    result = service.ask(
        "What is the recipe for chocolate chip cookies?",
        minimum_relevance=0.99,
    )

    # Gemini was never called
    mock_genai.Client.assert_not_called()

    # Fallback answer is returned
    assert result["sufficient_context"] is False
    assert result["answer"] == FALLBACK_ANSWER
    assert result["sources"] == []
    assert result["response_time_ms"] >= 0


# ── Test 3: Missing API key returns clear error ──────────────────────


@patch("app.services.llm_service.settings")
def test_missing_api_key_raises_error(mock_settings):
    """When gemini_api_key is empty, ask() should raise RuntimeError."""
    mock_settings.gemini_api_key = ""
    mock_settings.gemini_model = "gemini-2.0-flash"

    retrieval = _mock_retrieval_sufficient()
    service = LLMService(retrieval)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        service.ask("How many remote days per week?")


# ── Test 4: Source filtering based on citations ──────────────────────


@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_source_filtering_keeps_only_cited_sources(mock_settings, mock_genai):
    """When Gemini cites only specific sources, un-cited sources should be removed."""
    mock_settings.gemini_api_key = "test-key-123"
    mock_settings.gemini_model = "gemini-2.0-flash"

    # Set up the mock Gemini response to cite ONLY [1]
    mock_response = MagicMock()
    mock_response.text = "You can work remotely up to three days. [1]"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    # Create a mock retrieval that returns TWO sources
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "question": "How many remote days per week?",
        "sufficient_context": True,
        "context": "Context here",
        "sources": [
            {
                "source_number": 1,
                "document_name": "doc1.md",
                "title": "Doc 1",
                "text": "remote 3 days",
                "relevance_score": 0.9,
            },
            {
                "source_number": 2,
                "document_name": "doc2.md",
                "title": "Doc 2",
                "text": "unrelated",
                "relevance_score": 0.8,
            }
        ],
        "retrieved_count": 2,
        "highest_relevance": 0.9,
    }
    
    service = LLMService(mock_retrieval)
    result = service.ask("How many remote days per week?")

    # Only source 1 should be in the final sources list
    assert len(result["sources"]) == 1
    assert result["sources"][0]["source_number"] == 1
    assert result["sources"][0]["document_name"] == "doc1.md"


# ── Test 5: Multi-part question with duplicated chunks ────────────────

@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_multipart_question_handles_citations(mock_settings, mock_genai):
    """Test that a multi-part question answers both parts and filters duplicate/uncited sources."""
    mock_settings.gemini_api_key = "test-key-123"
    mock_settings.gemini_model = "gemini-2.0-flash"

    # Set up the mock Gemini response with two numbered sections
    mock_response = MagicMock()
    mock_response.text = (
        "1. Manager approval is required for all hardware purchases. [1]\n"
        "2. Remote employees get a $500 stipend for home office setup. [3]"
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    # Create a mock retrieval that returns THREE sources
    # [1] Hardware policy
    # [2] Identical Hardware policy (to simulate duplicate, though retrieval should remove it)
    # [3] Remote benefits
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "question": "What company policies mention manager approval? What benefits are available to employees who work remotely?",
        "sufficient_context": True,
        "context": "Context here",
        "sources": [
            {
                "source_number": 1,
                "document_name": "hardware.md",
                "title": "Hardware Policy",
                "text": "Managers must approve hardware.",
                "relevance_score": 0.95,
            },
            {
                "source_number": 2,
                "document_name": "hardware.md",
                "title": "Hardware Policy",
                "text": "Unrelated hardware stuff without citation.",
                "relevance_score": 0.85,
            },
            {
                "source_number": 3,
                "document_name": "remote.md",
                "title": "Remote Work",
                "text": "Remote workers get a $500 stipend.",
                "relevance_score": 0.90,
            }
        ],
        "retrieved_count": 3,
        "highest_relevance": 0.95,
    }
    
    service = LLMService(mock_retrieval)
    result = service.ask("What company policies mention manager approval? What benefits are available to employees who work remotely?")

    # Verify both parts are answered (checked by looking for "1." and "2.")
    assert "1. Manager approval" in result["answer"]
    assert "2. Remote employees" in result["answer"]

    # Only cited sources (1 and 3) should be returned
    assert len(result["sources"]) == 2
    returned_source_numbers = [src["source_number"] for src in result["sources"]]
    assert 1 in returned_source_numbers
    assert 3 in returned_source_numbers
    assert 2 not in returned_source_numbers


# ── Test 6: Two independent questions ─────────────────────────────────────

@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_two_independent_questions(mock_settings, mock_genai):
    """Test that a prompt with two independent questions is answered and numbered."""
    mock_settings.gemini_api_key = "test-key"
    mock_settings.gemini_model = "gemini-model"

    mock_response = MagicMock()
    mock_response.text = (
        "1. Hybrid employees must work 2 days in the office. [1]\n"
        "2. The cafeteria serves pizza on Fridays. [2]"
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "question": "How many days in office? What is for lunch on Friday?",
        "sufficient_context": True,
        "context": "Context",
        "sources": [
            {"source_number": 1, "document_name": "policy.md", "title": "P", "text": "2 days in office", "relevance_score": 0.9},
            {"source_number": 2, "document_name": "menu.md", "title": "M", "text": "Pizza on Fridays", "relevance_score": 0.8}
        ],
        "retrieved_count": 2,
        "highest_relevance": 0.9,
    }
    
    service = LLMService(mock_retrieval)
    result = service.ask("How many days in office? What is for lunch on Friday?")
    assert "1." in result["answer"]
    assert "2." in result["answer"]
    assert len(result["sources"]) == 2


# ── Test 7: Four independent questions ────────────────────────────────────

@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_four_independent_questions(mock_settings, mock_genai):
    """Test that a prompt with four independent questions is answered and numbered."""
    mock_settings.gemini_api_key = "test-key"
    mock_settings.gemini_model = "gemini-model"

    mock_response = MagicMock()
    mock_response.text = (
        "1. Answer one. [1]\n"
        "2. Answer two. [2]\n"
        "3. Answer three. [3]\n"
        "4. Answer four. [4]"
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "question": "Q1? Q2? Q3? Q4?",
        "sufficient_context": True,
        "context": "Context",
        "sources": [
            {"source_number": 1, "document_name": "1", "title": "1", "text": "1", "relevance_score": 0.9},
            {"source_number": 2, "document_name": "2", "title": "2", "text": "2", "relevance_score": 0.9},
            {"source_number": 3, "document_name": "3", "title": "3", "text": "3", "relevance_score": 0.9},
            {"source_number": 4, "document_name": "4", "title": "4", "text": "4", "relevance_score": 0.9}
        ],
        "retrieved_count": 4,
        "highest_relevance": 0.9,
    }
    
    service = LLMService(mock_retrieval)
    result = service.ask("Q1? Q2? Q3? Q4?")
    for i in range(1, 5):
        assert f"{i}." in result["answer"]
    assert len(result["sources"]) == 4


# ── Test 8: One unanswered question mixed with answered questions ─────────

@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_unanswered_question_mixed(mock_settings, mock_genai):
    """Test that missing context for one question is explicitly stated while others are answered."""
    mock_settings.gemini_api_key = "test-key"
    mock_settings.gemini_model = "gemini-model"

    mock_response = MagicMock()
    mock_response.text = (
        "1. Hybrid employees must work 2 days in the office. [1]\n"
        "2. I do not have enough information in the supplied company documents to answer what the CEO's favorite color is.\n"
        "3. The cafeteria serves pizza on Fridays. [2]"
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "question": "How many days in office? What is the CEO's favorite color? What is for lunch on Friday?",
        "sufficient_context": True,
        "context": "Context",
        "sources": [
            {"source_number": 1, "document_name": "policy.md", "title": "P", "text": "2 days in office", "relevance_score": 0.9},
            {"source_number": 2, "document_name": "menu.md", "title": "M", "text": "Pizza on Fridays", "relevance_score": 0.8}
        ],
        "retrieved_count": 2,
        "highest_relevance": 0.9,
    }
    
    service = LLMService(mock_retrieval)
    result = service.ask("How many days in office? What is the CEO's favorite color? What is for lunch on Friday?")
    
    assert "not have enough information" in result["answer"]
    assert "1." in result["answer"]
    assert "3." in result["answer"]
    # Should only return the two cited sources
    assert len(result["sources"]) == 2


# ── Test 9: Complete five-point summary ───────────────────────────────────

@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_five_point_summary(mock_settings, mock_genai):
    """Test that a summary request passes correct top_k and formats as bullet points."""
    mock_settings.gemini_api_key = "test-key"
    mock_settings.gemini_model = "gemini-model"

    mock_response = MagicMock()
    mock_response.text = (
        "* Point 1 [1]\n"
        "* Point 2 [2]\n"
        "* Point 3 [1]\n"
        "* Point 4 [3]\n"
        "* Point 5 [2]"
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "question": "Summarize the remote work policy in five bullet points.",
        "sufficient_context": True,
        "context": "Context",
        "sources": [
            {"source_number": 1, "document_name": "remote.md", "title": "R", "text": "T1", "relevance_score": 0.9},
            {"source_number": 2, "document_name": "remote.md", "title": "R", "text": "T2", "relevance_score": 0.8},
            {"source_number": 3, "document_name": "remote.md", "title": "R", "text": "T3", "relevance_score": 0.7}
        ],
        "retrieved_count": 3,
        "highest_relevance": 0.9,
    }
    
    service = LLMService(mock_retrieval)
    # the default top_k=4 will be boosted for summary
    result = service.ask("Summarize the remote work policy in five bullet points.")
    
    # Check that retrieve was called with boosted top_k (>=10) and candidate_count (>=16)
    call_kwargs = mock_retrieval.retrieve.call_args[1]
    assert call_kwargs["top_k"] >= 10
    assert call_kwargs["candidate_count"] >= 16
    assert "* Point 5" in result["answer"]
    assert len(result["sources"]) == 3


# ── Test 10: Comparison of policies ───────────────────────────────────────

@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_policy_comparison(mock_settings, mock_genai):
    """Test that a comparison request boosts top_k correctly and returns sections."""
    mock_settings.gemini_api_key = "test-key"
    mock_settings.gemini_model = "gemini-model"

    mock_response = MagicMock()
    mock_response.text = (
        "### Remote Policy\n"
        "Remote allows 3 days at home [1].\n\n"
        "### Leave Policy\n"
        "Leave gives 20 days off [2]."
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "question": "Compare the remote policy and the leave policy.",
        "sufficient_context": True,
        "context": "Context",
        "sources": [
            {"source_number": 1, "document_name": "remote.md", "title": "R", "text": "T1", "relevance_score": 0.9},
            {"source_number": 2, "document_name": "leave.md", "title": "L", "text": "T2", "relevance_score": 0.8},
        ],
        "retrieved_count": 2,
        "highest_relevance": 0.9,
    }
    
    service = LLMService(mock_retrieval)
    result = service.ask("Compare the remote policy and the leave policy.")
    
    # Check that retrieve was called with boosted top_k (>=12) and candidate_count (>=20)
    call_kwargs = mock_retrieval.retrieve.call_args[1]
    assert call_kwargs["top_k"] >= 12
    assert call_kwargs["candidate_count"] >= 20
    assert "### Remote Policy" in result["answer"]
    assert len(result["sources"]) == 2


# ── Test 11: Single question without unnecessary numbering ───────────────

@patch("app.services.llm_service.genai")
@patch("app.services.llm_service.settings")
def test_single_question_no_numbering(mock_settings, mock_genai):
    """Test that a single question is answered directly without '1.' numbering."""
    mock_settings.gemini_api_key = "test-key"
    mock_settings.gemini_model = "gemini-model"

    mock_response = MagicMock()
    mock_response.text = "You get 20 days of PTO per year. [1]"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "question": "How many days of PTO do I get?",
        "sufficient_context": True,
        "context": "Context",
        "sources": [
            {"source_number": 1, "document_name": "pto.md", "title": "P", "text": "T1", "relevance_score": 0.9},
        ],
        "retrieved_count": 1,
        "highest_relevance": 0.9,
    }
    
    service = LLMService(mock_retrieval)
    result = service.ask("How many days of PTO do I get?")
    
    # Confirm it does NOT have unnecessary numbering
    assert "1." not in result["answer"]
    assert "20 days" in result["answer"]


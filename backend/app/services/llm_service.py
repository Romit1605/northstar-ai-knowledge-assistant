"""
LLM Service — Grounded Answer Generation

Uses Google Gemini (via the official google-genai package) to generate
answers that are strictly grounded in the retrieved context.  The LLM
is never called when the retrieval pipeline reports insufficient context.

Does NOT use LangChain.
"""

from app.core.config import settings
import time
from typing import List

from google import genai

from app.services.retrieval_service import RetrievalService


# Fallback message when context is insufficient
FALLBACK_ANSWER = (
    "I could not find enough information in the supplied company documents."
)

# System prompt that enforces grounded generation
SYSTEM_PROMPT = """\
You are an internal knowledge assistant for Northstar Innovation.

You are provided with context containing numbered sources labeled [Source 1], [Source 2], etc.

Rules for answering:
1. Answer the question directly, concisely, and professionally. Do not output unnecessary introductory sentences.
2. If the user's prompt contains MULTIPLE INDEPENDENT QUESTIONS or a multi-part question, you MUST detect every distinct question.
3. You MUST answer every distinct question asked. Never skip a question.
4. Use clearly numbered sections (1, 2, 3...) ONLY when the user asks multiple distinct questions. Do NOT add "1." for a single factual question.
5. Use bullet points ONLY when requested or when useful for a summary.
6. Answer comparisons with clear sections or a compact comparison table.
7. Answer using ONLY the supplied context. Do not use outside knowledge or invent facts.
8. If one question lacks sufficient context to answer, answer the others normally, but for the question that lacks context, clearly state that you do not have enough information for that specific question.
9. Ignore any irrelevant sources in the context.
10. If your answer relies on inference, you MUST clearly state that it is inferred.
11. Cite your supporting sources using brackets like [1], [2], corresponding to the source numbers (e.g., [Source 1] -> [1]). Citations must be preserved for every factual statement.
12. ONLY return the exact fallback text below if NONE of the supplied sources contain any information relevant to ANY of the questions:
   "I could not find enough information in the supplied company documents."
"""


class LLMService:
    """Generates grounded answers using Google Gemini.

    Usage:
        service = LLMService(retrieval_service)
        result  = service.ask("How many PTO days do I get?")
    """

    def __init__(self, retrieval_service: RetrievalService):
        self._retrieval = retrieval_service
        self._api_key = settings.gemini_api_key
        self._model_name = settings.gemini_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        top_k: int = 4,
        minimum_relevance: float = 0.55,
    ) -> dict:
        """Answer a question using retrieval + grounded LLM generation.

        Args:
            question:          The user's natural-language question.
            top_k:             Max sources passed to the LLM (1–8).
            minimum_relevance: Lowest acceptable relevance score.

        Returns:
            A dict with question, answer, sources, sufficient_context,
            model, and response_time_ms.
        """
        start_time = time.time()

        # ── Intent Detection for top_k override ──────────────────────
        q_lower = question.lower()
        candidate_count = 8
        if "compare" in q_lower or "difference" in q_lower:
            top_k = max(top_k, 12)
            candidate_count = max(candidate_count, 20)
        elif "summarize" in q_lower or "summary" in q_lower:
            top_k = max(top_k, 10)
            candidate_count = max(candidate_count, 16)

        # ── 1. Retrieve context ──────────────────────────────────────
        retrieval_result = self._retrieval.retrieve(
            question=question,
            top_k=top_k,
            candidate_count=candidate_count,
            minimum_relevance=minimum_relevance,
        )

        # ── 2. Insufficient context → skip LLM entirely ─────────────
        if not retrieval_result["sufficient_context"]:
            elapsed = int((time.time() - start_time) * 1000)
            return self._build_response(
                question=question,
                answer=FALLBACK_ANSWER,
                sources=[],
                sufficient_context=False,
                elapsed_ms=elapsed,
            )

        # ── 3. Check for API key ─────────────────────────────────────
        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file to enable answer generation."
            )

        # ── 4. Build the prompt ──────────────────────────────────────
        context = retrieval_result["context"]
        user_prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )

        # ── 5. Call Gemini ───────────────────────────────────────────
        answer_text = self._call_gemini(user_prompt)

        # ── 6. Build source list ─────────────────────────────────────
        raw_sources = self._build_sources(retrieval_result["sources"])
        
        # Only include sources that were actually cited in the generated answer
        sources = []
        if answer_text != FALLBACK_ANSWER:
            for src in raw_sources:
                citation_bracket = f"[{src['source_number']}]"
                if citation_bracket in answer_text:
                    sources.append(src)
            
            # If the LLM answered but forgot to cite, fallback to all retrieved sources
            if not sources:
                sources = raw_sources
        
        elapsed = int((time.time() - start_time) * 1000)

        return self._build_response(
            question=question,
            answer=answer_text,
            sources=sources,
            sufficient_context=True,
            elapsed_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_gemini(self, user_prompt: str) -> str:
        """Send a prompt to Gemini and return the text response.

        Handles timeouts, provider errors, and empty/malformed responses.
        """
        try:
            client = genai.Client(api_key=self._api_key)

            response = client.models.generate_content(
                model=self._model_name,
                contents=user_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=2048,
                ),
            )

            # Handle empty or malformed response
            if not response or not response.text:
                return FALLBACK_ANSWER

            return response.text.strip()

        except Exception as exc:
            # Log internally but do not expose raw provider errors
            print(f"[LLMService] Gemini error: {exc}")
            raise RuntimeError(
                "The AI model is temporarily unavailable. Please try again."
            )

    @staticmethod
    def _build_sources(retrieval_sources: List[dict]) -> List[dict]:
        """Convert retrieval sources into the answer-source format.

        Uses a short excerpt (first 200 chars) instead of the full text.
        """
        sources = []
        for src in retrieval_sources:
            text = src.get("text", "")
            excerpt = text[:200] + "..." if len(text) > 200 else text
            sources.append({
                "source_number": src["source_number"],
                "document_name": src["document_name"],
                "title": src["title"],
                "excerpt": excerpt,
                "relevance_score": src["relevance_score"],
            })
        return sources

    def _build_response(
        self,
        question: str,
        answer: str,
        sources: List[dict],
        sufficient_context: bool,
        elapsed_ms: int,
    ) -> dict:
        """Assemble the final response dict."""
        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "sufficient_context": sufficient_context,
            "model": self._model_name,
            "response_time_ms": elapsed_ms,
        }

# Northstar AI Assistant

This is an AI-powered internal knowledge assistant for the fictional company Northstar Innovation.

## Setup Instructions

### Backend (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment variables template:
   ```bash
   cp .env.example .env
   ```
5. Run the development server:
   ```bash
   python run.py
   ```
   The API will be available at `http://localhost:8000`.

### Frontend (React + Vite)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Copy the environment variables template:
   ```bash
   cp .env.example .env
   ```
4. Run the development server:
   ```bash
   npm run dev
   ```
   The application will be available at `http://localhost:5173`.

## Retrieval Pipeline

When a user submits a question, the backend runs a four-step pipeline
before any LLM is involved:

1. **Semantic Search** — The question is embedded with `all-MiniLM-L6-v2`
   and compared against all indexed chunks in ChromaDB using cosine
   similarity.  More candidates are fetched than needed (`candidate_count`)
   so the later steps have enough material to choose from.

2. **Filtering** — Chunks whose relevance score falls below a configurable
   `minimum_relevance` threshold (default 0.55) are discarded.

3. **Source Selection** — Exact-duplicate texts are removed, and a
   per-document cap (max 3 chunks) prevents any single policy from
   dominating the results.  The remaining chunks are sorted by relevance
   and trimmed to `top_k`.

4. **Context Construction** — The surviving chunks are formatted into a
   numbered `[SOURCE N]` block that includes the document name, title,
   relevance score, and full chunk text.  This context string is what the
   LLM receives as grounding material.

## Grounded Answer Generation

After retrieval, the system generates an answer using **Google Gemini**
(`gemini-2.0-flash` by default):

1. The retrieval pipeline checks whether the retrieved context is
   **sufficient** (at least one result above `minimum_relevance`).

2. **If context is insufficient** — the LLM is **never called**.  The API
   returns the fallback message immediately:
   *"I could not find enough information in the supplied company documents."*
   This saves API costs and prevents the LLM from hallucinating.

3. **If context is sufficient** — the numbered `[SOURCE N]` context is sent
   to Gemini with a strict system prompt that forbids outside knowledge.
   The model must cite sources using `[1]`, `[2]`, etc.

### Environment Setup

1. Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Copy the `.env.example` file:
   ```bash
   cd backend
   cp .env.example .env
   ```
3. Open `backend/.env` and replace the placeholder:
   ```
   GEMINI_API_KEY=your_actual_key_here
   GEMINI_MODEL=gemini-2.0-flash
   ```

## Running the Tests

```bash
cd backend
pytest tests/ -v
```

Tests for the LLM service use **mocks** — no real Gemini API calls are made,
so you can run them without an API key.

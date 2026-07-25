"""
Vector Store Service

Generates embeddings for document chunks using sentence-transformers
and stores them in a local ChromaDB database for semantic search.

Does NOT use LangChain.  All logic is self-contained.
"""

import pathlib
from typing import List

# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
# pyrefly: ignore [missing-import]
import chromadb

from app.services.document_loader import DocumentLoader, DocumentChunker


# ── Configuration ─────────────────────────────────────────────────────

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "northstar_documents"
CHROMA_DB_DIR = pathlib.Path(__file__).parent.parent.parent / "chroma_db"
KNOWLEDGE_BASE_DIR = pathlib.Path(__file__).parent.parent / "knowledge_base"


class VectorStoreService:
    """Manages embedding generation, ChromaDB storage, and semantic search.

    Usage:
        service = VectorStoreService()
        service.index()                         # embed & store all chunks
        results = service.search("my query")    # semantic search
    """

    def __init__(self):
        # Load the embedding model once
        self._model = SentenceTransformer(EMBEDDING_MODEL)

        # Create a persistent ChromaDB client
        CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index(self) -> dict:
        """Load documents, chunk them, embed, and store in ChromaDB.

        Duplicate chunks (same chunk_id) are skipped automatically so
        calling this multiple times is safe.

        Returns:
            A summary dict with documents_processed, chunks_indexed, etc.
        """
        # Reuse existing document loader and chunker
        loader = DocumentLoader(KNOWLEDGE_BASE_DIR)
        chunker = DocumentChunker(chunk_size=600, overlap=100)

        documents = loader.load_all()
        chunks = chunker.chunk_all(documents)

        if not chunks:
            return {
                "status": "success",
                "documents_processed": 0,
                "chunks_indexed": 0,
                "collection": COLLECTION_NAME,
            }

        # Get or create the collection
        collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        # Filter out chunks that are already indexed (prevent duplicates)
        new_ids = [c["chunk_id"] for c in chunks]
        existing = collection.get(ids=new_ids, include=[])
        existing_ids = set(existing["ids"]) if existing["ids"] else set()

        to_add = [c for c in chunks if c["chunk_id"] not in existing_ids]

        if to_add:
            texts = [c["text"] for c in to_add]
            ids = [c["chunk_id"] for c in to_add]
            metadatas = [
                {
                    "chunk_id": c["chunk_id"],
                    "document_name": c["document_name"],
                    "title": c["title"],
                    "chunk_index": c["chunk_index"],
                    "start_character": c["start_character"],
                    "end_character": c["end_character"],
                }
                for c in to_add
            ]

            # Generate embeddings
            embeddings = self._model.encode(texts).tolist()

            # Store in ChromaDB
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

        return {
            "status": "success",
            "documents_processed": len(documents),
            "chunks_indexed": len(to_add),
            "collection": COLLECTION_NAME,
        }

    def rebuild(self) -> dict:
        """Delete the existing collection and re-index from scratch.

        Returns:
            The same summary dict as index().
        """
        # Delete existing collection if it exists
        try:
            self._client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass  # Collection may not exist yet

        return self.index()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Return information about the vector store.

        Returns:
            A dict with collection name, path, count, model, and readiness.
        """
        try:
            collection = self._client.get_collection(name=COLLECTION_NAME)
            count = collection.count()
            ready = count > 0
        except Exception:
            count = 0
            ready = False

        return {
            "collection": COLLECTION_NAME,
            "vector_db_path": str(CHROMA_DB_DIR),
            "indexed_chunks": count,
            "embedding_model": EMBEDDING_MODEL,
            "ready": ready,
        }

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        """Perform semantic search against indexed chunks.

        Args:
            query: The user's natural-language question.
            top_k: Number of top results to return (1-10).

        Returns:
            A list of result dicts sorted by relevance_score descending.
        """
        if not query or not query.strip():
            return []

        try:
            collection = self._client.get_collection(name=COLLECTION_NAME)
        except Exception:
            return []

        if collection.count() == 0:
            return []

        # Generate embedding for the query
        query_embedding = self._model.encode(query).tolist()

        # Query ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        # Build response — convert cosine distance to a 0-1 relevance score.
        # ChromaDB cosine distance ranges from 0 (identical) to 2 (opposite).
        # relevance = 1 - (distance / 2) gives a score where 1 = perfect match.
        search_results = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            relevance_score = round(1 - (distance / 2), 4)

            search_results.append({
                "chunk_id": results["ids"][0][i],
                "document_name": results["metadatas"][0][i]["document_name"],
                "title": results["metadatas"][0][i]["title"],
                "text": results["documents"][0][i],
                "relevance_score": relevance_score,
            })

        return search_results

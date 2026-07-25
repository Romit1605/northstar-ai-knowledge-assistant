"""
Document Loading and Chunking Service

Reads Markdown files from the knowledge_base directory,
extracts metadata, and splits them into overlapping chunks
for future retrieval use.
"""

import pathlib
import re
from typing import List, Optional


# Path to the knowledge base directory
KNOWLEDGE_BASE_DIR = pathlib.Path(__file__).parent.parent / "knowledge_base"


class DocumentLoader:
    """Scans the knowledge_base folder and loads Markdown documents."""

    def __init__(self, directory: pathlib.Path = KNOWLEDGE_BASE_DIR):
        self.directory = directory

    def load_all(self) -> List[dict]:
        """Load every .md file in the knowledge_base directory.

        Returns:
            A list of dicts, each containing filename, title,
            content, size (bytes), and number_of_lines.
        """
        documents = []

        if not self.directory.exists() or not self.directory.is_dir():
            return documents

        for file_path in sorted(self.directory.glob("*.md")):
            doc = self._load_file(file_path)
            if doc is not None:
                documents.append(doc)

        return documents

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_file(self, file_path: pathlib.Path) -> Optional[dict]:
        """Read a single Markdown file and return its metadata.

        Skips the file and returns None if it is empty or unreadable.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            print(f"[DocumentLoader] Skipping {file_path.name}: {exc}")
            return None

        # Skip empty files
        if not content.strip():
            return None

        title = self._extract_title(content, file_path.name)

        return {
            "filename": file_path.name,
            "title": title,
            "content": content,
            "size": file_path.stat().st_size,
            "number_of_lines": content.count("\n") + 1,
        }

    @staticmethod
    def _extract_title(content: str, fallback: str) -> str:
        """Return the first Markdown heading, or the filename as fallback."""
        match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
        return match.group(1).strip() if match else fallback


class DocumentChunker:
    """Splits document text into overlapping chunks on paragraph boundaries.

    Does NOT use LangChain.  All logic is self-contained.
    """

    def __init__(self, chunk_size: int = 600, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, document: dict) -> List[dict]:
        """Split a single loaded document into chunks.

        Args:
            document: A dict returned by DocumentLoader (must contain
                      filename, title, and content keys).

        Returns:
            A list of chunk dicts.
        """
        text = document["content"]
        doc_name = document["filename"]
        title = document["title"]

        paragraphs = self._split_into_paragraphs(text)
        chunks = self._merge_paragraphs_into_chunks(paragraphs)

        result = []
        for index, (chunk_text, start_char, end_char) in enumerate(chunks):
            result.append({
                "chunk_id": f"{doc_name}__chunk_{index}",
                "document_name": doc_name,
                "title": title,
                "chunk_index": index,
                "text": chunk_text,
                "start_character": start_char,
                "end_character": end_char,
            })

        return result

    def chunk_all(self, documents: List[dict]) -> List[dict]:
        """Chunk every document in the list.

        Args:
            documents: A list of dicts from DocumentLoader.load_all().

        Returns:
            A flat list of all chunk dicts.
        """
        all_chunks = []
        for doc in documents:
            all_chunks.extend(self.chunk_document(doc))
        return all_chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_into_paragraphs(text: str) -> List[str]:
        """Split text on blank-line boundaries (paragraph breaks)."""
        paragraphs = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _merge_paragraphs_into_chunks(
        self, paragraphs: List[str]
    ) -> List[tuple]:
        """Merge paragraphs into chunks that respect chunk_size and overlap.

        Returns a list of (chunk_text, start_char, end_char) tuples.
        """
        if not paragraphs:
            return []

        # Reconstruct the running text with double-newline separators so we
        # can track accurate character offsets.
        full_text = "\n\n".join(paragraphs)

        # Build a list of (paragraph_text, start_offset, end_offset)
        para_spans = []
        offset = 0
        for para in paragraphs:
            start = full_text.index(para, offset)
            end = start + len(para)
            para_spans.append((para, start, end))
            offset = end

        chunks = []
        i = 0  # paragraph index

        while i < len(para_spans):
            chunk_parts = []
            chunk_start = para_spans[i][1]
            current_length = 0
            start_para_index = i

            # Greedily add paragraphs until we exceed chunk_size
            j = i
            while j < len(para_spans):
                para_text = para_spans[j][0]
                addition = len(para_text) + (2 if chunk_parts else 0)

                if current_length + addition > self.chunk_size and chunk_parts:
                    break

                chunk_parts.append(para_text)
                current_length += addition
                j += 1

            chunk_text = "\n\n".join(chunk_parts)
            chunk_end = chunk_start + len(chunk_text)
            chunks.append((chunk_text, chunk_start, chunk_end))

            # If we consumed every paragraph, we're done
            if j >= len(para_spans):
                break

            # Advance with overlap: step back so the next chunk starts
            # approximately `overlap` characters before the current end.
            overlap_target = chunk_end - self.overlap
            next_i = j  # default: start at the next unprocessed paragraph
            for k in range(j - 1, start_para_index, -1):
                if para_spans[k][1] <= overlap_target:
                    next_i = k
                    break

            # Safety: always advance by at least one paragraph
            if next_i <= start_para_index:
                next_i = start_para_index + 1

            i = next_i

        return chunks

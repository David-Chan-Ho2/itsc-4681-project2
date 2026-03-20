"""Document chunking utilities for the local RAG pipeline."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentChunk:
    """A chunk of source documentation."""

    chunk_id: str
    text: str
    source_path: str
    title: str
    chunk_index: int


class MarkdownChunker:
    """Chunk markdown or plaintext files into overlapping windows."""

    def __init__(self, chunk_size: int = 900, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, source_path: Path, text: str) -> list[DocumentChunk]:
        """Split a document into chunks while preserving section boundaries when possible."""
        normalized = text.replace("\r\n", "\n").strip()
        if not normalized:
            return []

        blocks = self._split_into_blocks(normalized)
        chunks: list[DocumentChunk] = []
        current = ""
        current_title = source_path.stem
        chunk_index = 0

        for block in blocks:
            if block.startswith("#"):
                current_title = block.lstrip("# ").strip() or source_path.stem

            candidate = f"{current}\n\n{block}".strip() if current else block
            if current and len(candidate) > self.chunk_size:
                chunks.append(
                    self._build_chunk(
                        source_path=source_path,
                        title=current_title,
                        text=current,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1
                overlap_tail = current[-self.overlap :] if self.overlap else ""
                current = f"{overlap_tail}\n\n{block}".strip() if overlap_tail else block
            else:
                current = candidate

        if current:
            chunks.append(
                self._build_chunk(
                    source_path=source_path,
                    title=current_title,
                    text=current,
                    chunk_index=chunk_index,
                )
            )

        return chunks

    def _split_into_blocks(self, text: str) -> list[str]:
        """Break text into paragraph-like blocks."""
        blocks: list[str] = []
        current_lines: list[str] = []

        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#"):
                if current_lines:
                    blocks.append("\n".join(current_lines).strip())
                    current_lines = []
                blocks.append(stripped)
                continue

            if not stripped:
                if current_lines:
                    blocks.append("\n".join(current_lines).strip())
                    current_lines = []
                continue

            current_lines.append(stripped)

        if current_lines:
            blocks.append("\n".join(current_lines).strip())

        return [block for block in blocks if block]

    def _build_chunk(
        self, source_path: Path, title: str, text: str, chunk_index: int
    ) -> DocumentChunk:
        """Create a stable chunk object."""
        chunk_id = f"{source_path.as_posix()}::{chunk_index}"
        return DocumentChunk(
            chunk_id=chunk_id,
            text=text.strip(),
            source_path=source_path.as_posix(),
            title=title,
            chunk_index=chunk_index,
        )

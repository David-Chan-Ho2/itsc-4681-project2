"""Service layer for indexing and querying local documentation."""

from pathlib import Path
from typing import Optional

from nexus.rag.chunker import DocumentChunk, MarkdownChunker
from nexus.rag.embeddings import HashEmbeddingModel
from nexus.rag.fusion import generate_query_variants, reciprocal_rank_fusion
from nexus.rag.store import ChromaRAGStore


class RAGService:
    """Build and query a persistent local documentation index."""

    def __init__(
        self,
        db_dir: str,
        collection_name: str,
        chunk_size: int = 900,
        overlap: int = 150,
        embedding_dimension: int = 256,
    ):
        self.collection_name = collection_name
        self.chunker = MarkdownChunker(chunk_size=chunk_size, overlap=overlap)
        self.embedder = HashEmbeddingModel(dimension=embedding_dimension)
        self.store = ChromaRAGStore(db_dir=db_dir, collection_name=collection_name)

    def build_index(
        self, source_dir: str, force_rebuild: bool = False
    ) -> dict:
        """Index a directory of documentation files into the persistent vector store."""
        base_path = Path(source_dir)
        if not base_path.exists():
            return {"success": False, "error": f"Source directory not found: {source_dir}"}

        chunks = self._load_chunks(base_path)
        if not chunks:
            return {
                "success": False,
                "error": f"No supported documentation files found in {source_dir}",
            }

        if force_rebuild:
            self.store.reset()

        embeddings = self.embedder.embed_documents([chunk.text for chunk in chunks])
        self.store.upsert(chunks, embeddings)

        return {
            "success": True,
            "collection_name": self.collection_name,
            "documents_indexed": len({chunk.source_path for chunk in chunks}),
            "chunks_indexed": len(chunks),
            "db_dir": str(self.store.db_dir),
        }

    def search(self, query: str, top_k: int = 4) -> dict:
        """Query the documentation index using fusion retrieval."""
        if self.store.count() == 0:
            return {
                "success": False,
                "error": (
                    f"Collection '{self.collection_name}' is empty. "
                    "Build the index before searching."
                ),
            }

        query_variants = generate_query_variants(query)
        rankings = []

        for variant in query_variants:
            query_embedding = self.embedder.embed_query(variant)
            ranking = self.store.query(query_embedding=query_embedding, top_k=top_k)
            rankings.append(ranking)

        fused_results = reciprocal_rank_fusion(rankings)[:top_k]
        for item in fused_results:
            metadata = item.get("metadata", {})
            item["source_path"] = metadata.get("source_path", "unknown")
            item["title"] = metadata.get("title", "Untitled")

        return {
            "success": True,
            "collection_name": self.collection_name,
            "technique": "fusion_retrieval",
            "query_variants": query_variants,
            "results": fused_results,
        }

    def status(self) -> dict:
        """Return the current collection status."""
        return {
            "collection_name": self.collection_name,
            "chunks_indexed": self.store.count(),
            "db_dir": str(self.store.db_dir),
        }

    def _load_chunks(self, source_dir: Path) -> list[DocumentChunk]:
        """Load supported documentation files and chunk them."""
        supported_suffixes = {".md", ".txt", ".rst"}
        chunks: list[DocumentChunk] = []

        for path in sorted(source_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in supported_suffixes:
                continue

            text = path.read_text(encoding="utf-8")
            chunks.extend(self.chunker.chunk_text(path, text))

        return chunks

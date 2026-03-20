"""Persistent vector storage for the local RAG pipeline."""

from pathlib import Path
from typing import Optional

from nexus.rag.chunker import DocumentChunk


class ChromaRAGStore:
    """Persist and query document embeddings with Chroma."""

    def __init__(self, db_dir: str, collection_name: str):
        self.db_dir = Path(db_dir)
        self.collection_name = collection_name
        self.db_dir.mkdir(parents=True, exist_ok=True)

    def reset(self) -> None:
        """Delete the current collection if it exists."""
        client = self._get_client()
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            return

    def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """Store chunks and embeddings."""
        if not chunks:
            return

        collection = self._get_collection(create=True)
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "source_path": chunk.source_path,
                    "title": chunk.title,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ],
            embeddings=embeddings,
        )

    def count(self) -> int:
        """Return the number of stored chunks."""
        collection = self._get_collection(create=False)
        if collection is None:
            return 0
        return int(collection.count())

    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """Query the collection and return normalized result objects."""
        collection = self._get_collection(create=False)
        if collection is None or collection.count() == 0:
            return []

        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]

        normalized = []
        for chunk_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            normalized.append(
                {
                    "chunk_id": chunk_id,
                    "document": document,
                    "metadata": metadata or {},
                    "distance": float(distance or 0.0),
                }
            )
        return normalized

    def _get_collection(self, create: bool) -> Optional[object]:
        """Get or create a collection."""
        client = self._get_client()
        if create:
            return client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "NEXUS local documentation index"},
            )

        try:
            return client.get_collection(self.collection_name)
        except Exception:
            return None

    def _get_client(self):
        """Create a persistent Chroma client."""
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "chromadb is not installed. Install project dependencies to use RAG."
            ) from exc

        return chromadb.PersistentClient(path=str(self.db_dir))

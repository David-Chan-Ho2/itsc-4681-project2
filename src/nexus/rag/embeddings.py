"""Local embedding helpers for the RAG pipeline."""

import hashlib
import math
import re


class HashEmbeddingModel:
    """A deterministic local embedding model based on hashed token frequencies."""

    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple documents."""
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query or document."""
        vector = [0.0] * self.dimension
        tokens = re.findall(r"\b[a-z0-9_]+\b", text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector

        return [value / norm for value in vector]

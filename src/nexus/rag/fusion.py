"""Advanced retrieval helpers for the local RAG server."""

import re


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}


def generate_query_variants(query: str) -> list[str]:
    """Generate lightweight query rewrites for fusion retrieval."""
    tokens = [token for token in re.findall(r"\b[a-z0-9_]+\b", query.lower()) if token not in STOPWORDS]
    keywords = " ".join(tokens[:8]).strip()

    variants = [
        query.strip(),
        keywords,
        f"{keywords} usage example".strip(),
        f"{keywords} concepts overview".strip(),
    ]

    deduped: list[str] = []
    for variant in variants:
        if variant and variant not in deduped:
            deduped.append(variant)
    return deduped


def reciprocal_rank_fusion(
    rankings: list[list[dict]], fusion_constant: int = 60
) -> list[dict]:
    """Combine multiple rankings with Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    merged: dict[str, dict] = {}

    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            chunk_id = item["chunk_id"]
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (
                fusion_constant + rank
            )
            if chunk_id not in merged:
                merged[chunk_id] = dict(item)

    for chunk_id, score in scores.items():
        merged[chunk_id]["fusion_score"] = score

    return sorted(
        merged.values(),
        key=lambda item: item.get("fusion_score", 0.0),
        reverse=True,
    )

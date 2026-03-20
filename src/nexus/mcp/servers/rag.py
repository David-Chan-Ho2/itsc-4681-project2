"""Local RAG MCP server for NEXUS."""

from typing import Optional

from fastmcp import FastMCP

from nexus.config.settings import settings
from nexus.rag.service import RAGService

rag_server = FastMCP("NEXUS Local RAG")


def _create_service(collection_name: Optional[str] = None) -> RAGService:
    """Create a RAG service using current settings."""
    return RAGService(
        db_dir=settings.RAG_DB_DIR,
        collection_name=collection_name or settings.RAG_COLLECTION_NAME,
        chunk_size=settings.RAG_CHUNK_SIZE,
        overlap=settings.RAG_CHUNK_OVERLAP,
        embedding_dimension=settings.RAG_EMBEDDING_DIMENSION,
    )


@rag_server.tool()
def build_rag_index(
    source_dir: str = "",
    collection_name: Optional[str] = None,
    force_rebuild: bool = False,
) -> str:
    """Index a local documentation directory into the persistent vector store."""
    target_dir = source_dir or settings.RAG_SOURCE_DIR
    if not target_dir:
        return "Error: No source directory provided for RAG indexing."

    result = _create_service(collection_name).build_index(
        source_dir=target_dir,
        force_rebuild=force_rebuild,
    )
    if not result["success"]:
        return f"Error: {result['error']}"

    return (
        f"Indexed {result['documents_indexed']} document(s) into "
        f"'{result['collection_name']}' with {result['chunks_indexed']} chunk(s). "
        f"Database: {result['db_dir']}"
    )


@rag_server.tool()
def rag_search(
    query: str,
    top_k: int = 4,
    collection_name: Optional[str] = None,
) -> str:
    """Search the local documentation index using fusion retrieval."""
    result = _create_service(collection_name).search(query=query, top_k=top_k)
    if not result["success"]:
        return f"Error: {result['error']}"

    lines = [
        f"Collection: {result['collection_name']}",
        f"Technique: {result['technique']}",
        f"Query variants: {', '.join(result['query_variants'])}",
        "",
    ]

    for index, item in enumerate(result["results"], start=1):
        preview = item["document"][:320].replace("\n", " ")
        lines.append(f"{index}. {item['title']} ({item['source_path']})")
        lines.append(f"   Fusion score: {item['fusion_score']:.4f}")
        lines.append(f"   {preview}")
        lines.append("")

    return "\n".join(lines).strip()


@rag_server.tool()
def rag_status(collection_name: Optional[str] = None) -> str:
    """Report whether the local RAG collection is ready."""
    status = _create_service(collection_name).status()
    return (
        f"Collection: {status['collection_name']}\n"
        f"Chunks indexed: {status['chunks_indexed']}\n"
        f"Database: {status['db_dir']}"
    )

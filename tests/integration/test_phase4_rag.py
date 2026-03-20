"""Integration tests for the phase 4 local RAG server."""

from pathlib import Path

import pytest
from fastmcp import Client

from nexus.rag.service import RAGService


def _write_docs(base_path: Path) -> Path:
    docs_dir = base_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "agents.md").write_text(
        (
            "# Agents\n\n"
            "Agents decide which tools to call and use the observations from those "
            "tools to continue reasoning.\n"
        ),
        encoding="utf-8",
    )
    (docs_dir / "vectorstores.md").write_text(
        (
            "# Vector Stores\n\n"
            "Vector stores persist embedded document chunks so the retrieval index "
            "can be reused across sessions.\n"
        ),
        encoding="utf-8",
    )
    return docs_dir


def test_rag_service_builds_persistent_index(tmp_path):
    """The RAG service can build an index and reuse it from disk."""
    docs_dir = _write_docs(tmp_path)
    db_dir = tmp_path / "chroma"

    first_service = RAGService(
        db_dir=str(db_dir),
        collection_name="test-docs",
    )
    build_result = first_service.build_index(str(docs_dir), force_rebuild=True)

    assert build_result["success"] is True
    assert build_result["documents_indexed"] == 2
    assert build_result["chunks_indexed"] >= 2

    second_service = RAGService(
        db_dir=str(db_dir),
        collection_name="test-docs",
    )
    search_result = second_service.search("How do agents use tools?", top_k=2)

    assert search_result["success"] is True
    assert search_result["technique"] == "fusion_retrieval"
    assert search_result["results"]
    assert "agents.md" in search_result["results"][0]["source_path"]


@pytest.mark.asyncio
async def test_rag_mcp_server_build_and_search(monkeypatch, tmp_path):
    """The local RAG MCP server can build an index and answer a query."""
    from nexus.config.settings import settings
    from nexus.mcp.servers.rag import rag_server

    docs_dir = _write_docs(tmp_path)
    db_dir = tmp_path / "rag-db"

    monkeypatch.setattr(settings, "RAG_DB_DIR", str(db_dir))
    monkeypatch.setattr(settings, "RAG_SOURCE_DIR", str(docs_dir))
    monkeypatch.setattr(settings, "RAG_COLLECTION_NAME", "integration-rag")
    monkeypatch.setattr(settings, "RAG_CHUNK_SIZE", 600)
    monkeypatch.setattr(settings, "RAG_CHUNK_OVERLAP", 100)
    monkeypatch.setattr(settings, "RAG_EMBEDDING_DIMENSION", 128)

    async with Client(rag_server) as client:
        build_result = await client.call_tool(
            "build_rag_index",
            {
                "source_dir": str(docs_dir),
                "collection_name": "integration-rag",
                "force_rebuild": True,
            },
        )
        search_result = await client.call_tool(
            "rag_search",
            {
                "query": "What do vector stores persist?",
                "collection_name": "integration-rag",
                "top_k": 2,
            },
        )

    build_output = build_result.content[0].text
    search_output = search_result.content[0].text

    assert "Indexed 2 document" in build_output
    assert "fusion_retrieval" in search_output
    assert "vectorstores.md" in search_output


@pytest.mark.asyncio
async def test_rag_stdio_path_transport_exposes_tools():
    """The path-based RAG server transport used by the app launches correctly."""
    from nexus.mcp.server_registry import get_local_rag_server_path

    async with Client(get_local_rag_server_path()) as client:
        tools = await client.list_tools()

    tool_names = [tool.name for tool in tools]

    assert "build_rag_index" in tool_names
    assert "rag_search" in tool_names
    assert "rag_status" in tool_names


def test_rag_service_requires_index_before_search(tmp_path):
    """Searching an empty collection returns a clear error."""
    service = RAGService(
        db_dir=str(tmp_path / "chroma"),
        collection_name="empty",
    )

    result = service.search("What is an agent?", top_k=2)

    assert result["success"] is False
    assert "empty" in result["error"].lower() or "build the index" in result["error"].lower()

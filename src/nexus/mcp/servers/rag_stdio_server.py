"""Stdio entrypoint for the local RAG MCP server."""

from nexus.mcp.servers.rag import rag_server


if __name__ == "__main__":
    rag_server.run(transport="stdio", show_banner=False)

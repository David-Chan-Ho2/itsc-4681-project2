"""Helpers for building MCP server transports used by the app."""

import os
from pathlib import Path
from typing import Any, Optional

from nexus.config.settings import settings


def build_official_filesystem_config(
    roots: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build a stdio MCP config for the official filesystem server."""
    allowed_roots = roots or _get_filesystem_roots()

    if os.name == "nt":
        command = "cmd"
        args = [
            "/c",
            "npx",
            "-y",
            "@modelcontextprotocol/server-filesystem",
            *allowed_roots,
        ]
    else:
        command = "npx"
        args = ["-y", "@modelcontextprotocol/server-filesystem", *allowed_roots]

    return {
        "mcpServers": {
            "filesystem": {
                "transport": "stdio",
                "command": command,
                "args": args,
                "cwd": str(Path.cwd()),
                "description": "Official MCP filesystem server",
            }
        }
    }


def build_tavily_transport(api_key: str) -> str:
    """Build the remote Tavily MCP endpoint URL."""
    return f"https://mcp.tavily.com/mcp/?tavilyApiKey={api_key}"


def get_local_rag_server_path() -> Path:
    """Return the stdio entrypoint for the local Python RAG server."""
    return Path(__file__).resolve().parent / "servers" / "rag_stdio_server.py"


def _get_filesystem_roots() -> list[str]:
    """Resolve filesystem roots from configuration."""
    raw = getattr(settings, "FILESYSTEM_ROOTS", "") or str(Path.cwd())
    return [part for part in raw.split(os.pathsep) if part]

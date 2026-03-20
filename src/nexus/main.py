"""NEXUS - Main entry point for the CLI coding assistant."""

import asyncio
import signal
import sys
from typing import Optional

import typer
from rich.console import Console

from nexus.cli.repl import create_repl
from nexus.config.settings import settings
from nexus.core.agent import Agent
from nexus.core.types import ExecutionMode
from nexus.mcp.client import MCPClientManager
from nexus.mcp.server_registry import (
    build_official_filesystem_config,
    build_tavily_transport,
    get_local_rag_server_path,
)
from nexus.mcp.servers.search import search_server
from nexus.persistence.store import SessionStore
from nexus.rag.service import RAGService
from nexus.tools.executor import MCPToolExecutor

console = Console()
app = typer.Typer(
    name="NEXUS",
    help="Autonomous CLI Coding Assistant",
    pretty_exceptions_enable=True,
    invoke_without_command=True,
)


def _handle_signal(signum, frame):
    """Handle signals for graceful shutdown."""
    console.print("\n[yellow]Received shutdown signal. Exiting...[/yellow]")
    sys.exit(0)


def _create_llm_provider():
    """Create the active LLM provider."""
    if settings.GROQ_API_KEY:
        from nexus.llm.groq_provider import GroqProvider

        return GroqProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
        )

    from nexus.llm.ollama_provider import OllamaProvider

    console.print(
        "[yellow]No GROQ_API_KEY found. Using Ollama. Tool calling depends on the model adapter.[/yellow]"
    )
    return OllamaProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
    )


def _build_mcp_manager() -> MCPClientManager:
    """Register the MCP servers required by the project."""
    manager = MCPClientManager()
    manager.register_server("filesystem", build_official_filesystem_config())

    if settings.TAVILY_API_KEY:
        manager.register_server("search", build_tavily_transport(settings.TAVILY_API_KEY))
    else:
        manager.register_server("search", search_server)

    manager.register_server("rag", get_local_rag_server_path())
    return manager


def _parse_execution_mode(mode: str) -> ExecutionMode:
    """Validate and parse the execution mode."""
    mode_map = {
        "auto": ExecutionMode.AUTO,
        "manual": ExecutionMode.MANUAL,
        "confirmation": ExecutionMode.CONFIRMATION,
    }

    execution_mode = mode_map.get(mode.lower())
    if execution_mode is None:
        console.print(f"[red]Invalid mode: {mode}[/red]")
        console.print("Available modes: auto, manual, confirmation")
        raise typer.Exit(1)

    return execution_mode


def main(
    session_id: Optional[str] = None,
    mode: str = "auto",
    debug: bool = False,
) -> None:
    """Start NEXUS - the autonomous CLI coding assistant."""
    settings.validate()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    execution_mode = _parse_execution_mode(mode)
    llm_provider = _create_llm_provider()

    mcp_manager = _build_mcp_manager()
    tool_executor = MCPToolExecutor(mcp_manager)

    store = SessionStore()
    existing_session = None
    if session_id and store.exists(session_id):
        try:
            existing_session = store.load(session_id)
            console.print(f"[green]Resuming session {session_id[:8]}...[/green]")
        except Exception as exc:
            console.print(
                f"[yellow]Could not load session: {exc}. Starting fresh.[/yellow]"
            )

    repl = create_repl()
    session = repl.start_session(
        session_id=session_id,
        execution_mode=execution_mode,
        existing_session=existing_session,
    )

    agent = Agent(
        llm_provider=llm_provider,
        session=session,
        tool_executor=tool_executor,
    )
    repl.set_agent(agent)

    try:
        asyncio.run(repl.run_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Exiting NEXUS.[/yellow]")
    except Exception as exc:
        console.print(f"[red]Fatal error: {exc}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        raise typer.Exit(1) from exc
    finally:
        if repl.session:
            store.save(repl.session)
            console.print(
                "[dim]Session saved "
                f"({repl.session.session_id[:8]}). Resume with --session "
                f"{repl.session.session_id}[/dim]"
            )


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Option(
        None,
        "--session",
        "-s",
        help="Resume existing session by ID",
    ),
    mode: str = typer.Option(
        "auto",
        "--mode",
        "-m",
        help="Execution mode: auto, manual, or confirmation",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug mode",
    ),
) -> None:
    """Launch the REPL when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        main(session_id=session_id, mode=mode, debug=debug)


@app.command("build-rag")
def build_rag(
    source_dir: str = typer.Option(
        settings.RAG_SOURCE_DIR,
        "--source",
        "-s",
        help="Directory containing documentation files to ingest",
    ),
    collection_name: str = typer.Option(
        settings.RAG_COLLECTION_NAME,
        "--collection",
        "-c",
        help="Persistent collection name for the local vector store",
    ),
    force_rebuild: bool = typer.Option(
        False,
        "--force",
        help="Delete the existing collection before re-indexing",
    ),
) -> None:
    """Build or refresh the persistent local RAG index."""
    settings.validate()
    service = RAGService(
        db_dir=settings.RAG_DB_DIR,
        collection_name=collection_name,
        chunk_size=settings.RAG_CHUNK_SIZE,
        overlap=settings.RAG_CHUNK_OVERLAP,
        embedding_dimension=settings.RAG_EMBEDDING_DIMENSION,
    )
    result = service.build_index(source_dir=source_dir, force_rebuild=force_rebuild)
    if not result["success"]:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    console.print(
        "[green]Indexed "
        f"{result['documents_indexed']} document(s) into "
        f"{result['collection_name']} with {result['chunks_indexed']} chunk(s).[/green]"
    )
    console.print(f"[dim]Vector store: {result['db_dir']}[/dim]")


if __name__ == "__main__":
    app()

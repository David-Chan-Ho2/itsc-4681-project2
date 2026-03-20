# NEXUS

NEXUS is an autonomous CLI coding assistant built for the ITSC 4681 course project. It accepts a natural-language development task, reasons over the local codebase, invokes MCP tools, observes the results, and continues until it reaches a final answer or a safe stopping point.

## Assignment Coverage

This repo now includes the full project architecture across the assignment phases:

- Agentic loop with iterative LLM -> tool -> observation execution
- Provider abstraction for Groq and Ollama
- CLI REPL with visible tool activity, execution modes, and session persistence
- Dynamic MCP tool discovery through a central client manager
- Official filesystem MCP server via `@modelcontextprotocol/server-filesystem`
- External resource MCP server via Tavily
- Custom local RAG MCP server with persistent ChromaDB storage
- Advanced RAG technique via fusion retrieval with query rewrites and reciprocal rank fusion
- Planning, architecture, sequence, state, and reflection docs in `docs/`

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+ with `npm` and `npx`
- A Groq API key for the strongest tool-calling demo path
- A Tavily API key for the required external MCP server demo
- Optional local Ollama instance for offline fallback

### Install

```bash
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
cmd /c npm install
```

### Configure

```bash
copy .env.example .env
```

Recommended variables to set in `.env`:

- `GROQ_API_KEY`
- `TAVILY_API_KEY`
- `FILESYSTEM_ROOTS`
- `RAG_SOURCE_DIR`

### Build the Local RAG Index

The local documentation server uses a persistent vector store, so the indexing step only has to be done once per documentation set.

```bash
nexus build-rag --source fixtures/rag_docs/langchain --force
```

### Run

```bash
nexus --mode confirmation
```

## MCP Servers

NEXUS registers three MCP servers:

1. `filesystem`
   Uses the official `@modelcontextprotocol/server-filesystem` package over stdio.
2. `search`
   Uses Tavily's remote MCP endpoint when `TAVILY_API_KEY` is configured.
3. `rag`
   Uses a local Python stdio MCP server backed by a persistent ChromaDB index.

If `TAVILY_API_KEY` is missing, the app falls back to a local search stub for offline development. For the assignment demo, set a real Tavily key so the external MCP server is visibly invoked.

## CLI Commands

- `/help` shows built-in commands
- `/mode auto` executes tools automatically
- `/mode manual` confirms every tool
- `/mode confirmation` confirms only higher-risk tools
- `/history` shows recent conversation turns
- `/context` shows the current model context window
- `/status` shows session metadata
- `/tools` lists discovered MCP tools
- `/exit` exits and saves the session

## Suggested Demo Tasks

Use prompts like these in the course video:

1. `Read README.md and add a short setup troubleshooting section.`
   Shows filesystem tool use and confirmation flow.
2. `Search the web for Tavily MCP setup steps and summarize them in bullets.`
   Shows the external Tavily MCP server.
3. `Using the local docs, explain how LangChain tools relate to agents.`
   Shows the custom RAG MCP server after `build-rag`.

## Testing

Run the full suite:

```bash
python -m pytest -q
```

Phase-focused verification:

```bash
python -m pytest -q tests/integration/test_phase3_mcp.py tests/integration/test_phase3_runtime.py tests/integration/test_phase4_rag.py tests/integration/test_agentic_loop.py
```

## Project Structure

```text
src/nexus/
  cli/            REPL interface and terminal UX
  config/         Runtime settings
  core/           Agent loop, session state, shared types
  llm/            Groq and Ollama providers
  mcp/            MCP client manager, registries, and servers
  persistence/    Session storage
  rag/            Chunking, embeddings, fusion retrieval, vector store
  tools/          MCP-backed tool executor
tests/integration/  Phase-oriented integration tests
docs/               Planning and deliverable artifacts
fixtures/rag_docs/  Sample documentation corpus for the local RAG server
```

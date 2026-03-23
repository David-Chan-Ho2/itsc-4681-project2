# CLI Coding Assistant - Implementation Plan

**Project Goal**: Build an autonomous command-line AI coding assistant that takes natural language instructions, reasons about a local codebase, and autonomously reads, edits, and executes code to complete tasks.

**Codename**: NEXUS (Neural Executive Xperiment for Unified Software automation)

**Team Size**: 4+ developers
**Primary LLM**: Groq
**Fallback LLM**: Ollama (local)
**RAG Technique**: HyDE (Hypothetical Document Embeddings)
**External Resource**: Tavily (web search)

---

## CONTEXT & RATIONALE

This project requires building a sophisticated agentic system with:
- **Autonomous reasoning**: An LLM that decides what actions to take
- **Multi-tool integration**: File operations, web search, semantic documentation retrieval
- **Real-time interaction**: Terminal REPL with streaming responses
- **Robust error recovery**: Automatic retry, provider failover, graceful degradation
- **Team coordination**: Multi-developer project with clear component boundaries

The architecture must support professional-grade features: session persistence, confirmation modes (auto vs manual execution), comprehensive error handling, and extensible tool system.

---

## SYSTEM ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────┐
│     NEXUS - CLI Coding Assistant (User Facing)         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Terminal REPL Interface (cli/repl.py)           │  │
│  │  - Command parsing & dispatch                    │  │
│  │  - Streaming response output                     │  │
│  │  - Execution mode toggle (auto/manual)           │  │
│  └────────────────┬─────────────────────────────────┘  │
│                   │                                     │
│  ┌────────────────▼─────────────────────────────────┐  │
│  │  Agentic Loop Engine (core/agent.py)             │  │
│  │  - Reason → Act → Observe → Iterate              │  │
│  │  - LLM invocation with context management        │  │
│  │  - Tool call parsing & validation                │  │
│  └────────────────┬─────────────────────────────────┘  │
│                   │                                     │
│  ┌────────┬───────┴────────┬────────────────────────┐  │
│  │        │                │                        │   │
│  │    ┌───▼───┐      ┌──────▼──────┐      ┌───────▼──┐ │
│  │    │LLM    │      │Tool         │      │MCP Client│ │
│  │    │Abstraction   │Executor     │      │Pool      │ │
│  │    └───────┘      └─────────────┘      └──────────┘ │
│  │                                                     │
│  └─────────────────────────────────────────────────────┘
│                                                         │
└─────────────────────────────────────────────────────────┘

         External Services Layer (via MCP Clients)
┌─────────────────────────────────────────────────────────┐
│ Filesystem Server | Tavily Server | Custom RAG Server  │
│ (file ops)        | (web search)   | (LangChain docs)  │
└─────────────────────────────────────────────────────────┘
```

**Key Insight**: The assistant is a CLI-first application that internally acts as an MCP *client* to connect to the 3 required MCP servers. It does NOT need to expose itself as an MCP server.

---

## COMPONENT BREAKDOWN & OWNERSHIP

### Team A: Core Infrastructure (2 developers)
**Responsibilities**: CLI, session management, configuration, persistence

- **cli/repl.py** - Terminal interface
  - Command loop with async input
  - Rich-formatted output with streaming
  - `/help`, `/clear`, `/history`, `/mode` commands
  - Signal handling for Ctrl+C

- **core/session.py** - Session management
  - Message history (user/assistant/tool results)
  - Execution mode tracking (AUTO/MANUAL/CONFIRMATION)
  - Context window management
  - JSON serialization for persistence

- **core/types.py** - Shared type definitions
  - Message, ToolCall, ExecutionResult dataclasses
  - Execution mode enums
  - Error categories

- **persistence/session_db.py** - SQLite session storage
  - Save/load conversation history
  - Cross-session resumption
  - Query execution logs

### Team B: Agentic Loop & LLM Integration (2 developers)
**Responsibilities**: Agent reasoning, LLM abstraction, error handling

- **core/agent.py** - Agentic loop orchestrator
  - Main loop: reason → select tools → execute → observe
  - Stop condition evaluation
  - Context window sliding window (keep last N messages)
  - Iteration counter to prevent infinite loops

- **llm/provider.py** - LLM provider abstraction
  - Abstract base class with `invoke()` method
  - Tool calling support (function schemas to JSON)
  - Token counting
  - Streaming response handling

- **llm/groq_provider.py** - Groq API integration
  - API key management
  - Request formatting for Groq API
  - Tool schema translation

- **llm/ollama_provider.py** - Local Ollama integration
  - Connection to local Ollama instance
  - Model selection and fallback

- **core/error_handler.py** - Error handling & retry logic
  - Error classification (transient vs permanent)
  - Exponential backoff with jitter
  - Circuit breaker for repeated failures
  - Provider failover (Groq → Ollama)

### Team C: Tools & MCP Integration (1-2 developers)
**Responsibilities**: Tool system, MCP client management

- **tools/registry.py** - Tool registration & schema generation
  - Define available tools with parameters
  - Generate JSON schemas for LLM tool calling
  - Tool metadata (risk_level, description, etc.)

- **tools/executor.py** - Tool execution engine
  - Parallel execution with DAG dependency tracking
  - Sandbox execution for file/shell operations
  - Tool output formatting

- **mcp/client_manager.py** - MCP client lifecycle
  - Initialize connections to 3 servers at startup
  - Connection pooling (2-3 connections per server)
  - Automatic reconnection on failure
  - Request routing to appropriate server

- **mcp/servers/filesystem_server.py** - Filesystem MCP client
  - Wrapper around @modelcontextprotocol/server-filesystem
  - read_file, write_file, list_dir operations
  - Path sandboxing to project root

- **mcp/servers/tavily_server.py** - Tavily MCP client
  - Wrapper around Tavily web search MCP
  - search(query) → top results with URLs
  - Result caching to reduce API calls

### Team D: RAG Server & Vector DB (1-2 developers)
**Responsibilities**: Custom RAG implementation, LangChain doc indexing

- **rag/server.py** - Custom RAG MCP server
  - Runs as separate FastMCP process
  - semantic_search(query) endpoint
  - HyDE query expansion before search
  - Returns top-3 results with relevance scores

- **rag/hyde.py** - HyDE implementation
  - Generate 3-5 hypothetical documents from user query
  - Semantic similarity between hypotheticals and documents
  - Re-rank actual documents based on hypothetical similarity
  - Results merged with BM25 keyword search

- **rag/document_loader.py** - LangChain documentation loader
  - Download LangChain docs from GitHub
  - Semantic chunking (split at logical boundaries)
  - Metadata extraction (section, file, url)

- **rag/vector_db.py** - Chroma vector DB interface
  - Load/save Chroma collections
  - Store embeddings with metadata
  - Hybrid search (vector + keyword)
  - Persistent storage at `rag/chroma_db/`

---

## DEVELOPMENT PHASES

### Phase 1: Foundation (Weeks 1-2)
**Deliverables**: Project structure, CLI skeleton, session management

Team A:
- [x] Create project structure with `/src` directory
- [x] Implement basic REPL loop with Rich formatting
- [x] Session context + in-memory message history
- [x] Command parsing (`/help`, `/exit`, `/mode`)
- [x] Signal handler for Ctrl+C

All teams:
- [x] Add `pyproject.toml` dependencies
- [x] Setup GitHub Actions CI/CD (lint, test, build)
- [x] Create `.gitignore`
- [x] Write setup instructions in README.md

**Critical File**: `src/main.py` - Entry point

### Phase 2: Core Loop (Weeks 3-4)
**Deliverables**: Agentic loop functional, LLM integration working

Team B:
- [ ] Implement LLM provider abstraction (base class)
- [ ] Groq provider integration (API calls)
- [ ] Ollama provider integration (local fallback)
- [ ] Agentic loop orchestrator (main reasoning loop)
- [ ] Error handler with retry logic
- [ ] Circuit breaker for provider failover

All teams:
- [ ] Integration tests: Full loop with mock tools
- [ ] End-to-end test: Simple task completion

**Critical Files**:
- `src/core/agent.py` - Agentic loop
- `src/llm/provider.py` - LLM abstraction

### Phase 3: Tools & MCP (Weeks 5-6)
**Deliverables**: All 3 MCP servers connected, tools working

Team C:
- [ ] Tool registry + schema generation
- [ ] Tool executor with error handling
- [ ] MCP client manager (lifecycle, connection pooling)
- [ ] Filesystem server integration (read/write/search files)
- [ ] Tavily server integration (web search)
- [ ] Tool sandboxing for safe execution

Team A (support):
- [ ] Session persistence to SQLite

All teams:
- [ ] Integration tests: MCP connections stable
- [ ] Tool execution tests (parallel + serial)

**Critical Files**:
- `src/tools/registry.py` - Tool definitions
- `src/mcp/client_manager.py` - MCP management

### Phase 4: RAG Server (Weeks 7-8)
**Deliverables**: RAG server running, LangChain docs indexed, HyDE implemented

Team D:
- [ ] Chroma vector DB setup
- [ ] LangChain documentation loader
- [ ] Semantic chunking implementation
- [ ] HyDE query expansion algorithm
- [ ] Custom RAG MCP server (FastMCP) with semantic_search endpoint
- [ ] Embedding model selection (OpenAI vs sentence-transformers)

Team C (support):
- [ ] Integrate RAG MCP client into client_manager

All teams:
- [ ] Integration test: RAG server responds to queries
- [ ] Quality validation: Relevant results returned

**Critical Files**:
- `src/rag/server.py` - RAG endpoints
- `src/rag/hyde.py` - HyDE algorithm
- `scripts/setup_rag_db.py` - One-time setup script

### Phase 5: Polish & Testing (Weeks 9-10)
**Deliverables**: Comprehensive tests, signal handling, cross-session support

All teams:
- [ ] Unit tests (80%+ coverage on core modules)
- [ ] Integration tests (all components together)
- [ ] E2E tests (real user workflows)
- [ ] Signal handling (clean shutdown, state persistence)
- [ ] Confirmation/auto-execute mode refinement
- [ ] Error recovery validation

Team A:
- [ ] Cross-session resumption logic
- [ ] CLI help text and documentation

**Minimum Test Coverage**:
- `core/agent.py` - 85% (critical loop logic)
- `llm/provider.py` - 80% (failover scenarios)
- `tools/executor.py` - 80% (parallel execution)
- `mcp/client_manager.py` - 75% (connection handling)

### Phase 6: Deployment & Demo (Weeks 11+)
**Deliverables**: README, video demo, reflection

All teams:
- [ ] Write comprehensive README with setup instructions
- [ ] Docker image + docker-compose.yml
- [ ] Dependencies frozen in requirements.txt
- [ ] .env.example file for configuration

Lead:
- [ ] Record video demo (10-15 min)
  - Show 2 non-trivial coding tasks
  - All 3 MCP servers visibly invoked
  - Agent reasoning and tool calls on screen
- [ ] Write reflection (~2-3 pages)
  - Design decisions and trade-offs
  - LLM comparison (Groq vs Ollama on same task)
  - HyDE technique analysis and impact
  - What would you do differently

---

## CRITICAL FILE PATHS & OWNERSHIP MATRIX

| Component | File | Team | Weeks |
|-----------|------|------|-------|
| CLI REPL | `src/cli/repl.py` | A | 1-2 |
| Session Mgmt | `src/core/session.py` | A | 1-2 |
| Persistence | `src/persistence/session_db.py` | A | 4 |
| Agent Loop | `src/core/agent.py` | B | 3-4 |
| LLM Abstract | `src/llm/provider.py` | B | 3-4 |
| Error Handler | `src/core/error_handler.py` | B | 3-4 |
| Tool Registry | `src/tools/registry.py` | C | 5-6 |
| Tool Executor | `src/tools/executor.py` | C | 5-6 |
| MCP Manager | `src/mcp/client_manager.py` | C | 5-6 |
| RAG Server | `src/rag/server.py` | D | 7-8 |
| HyDE Impl | `src/rag/hyde.py` | D | 7-8 |
| Doc Loader | `src/rag/document_loader.py` | D | 7-8 |

---

## KEY ARCHITECTURAL DECISIONS

### 1. LLM Failover: Sequential (not parallel)
- **Choice**: Groq primary, switch to Ollama on failure
- **Rationale**: Simpler state management, predictable user experience
- **Trade-off**: Slower failover (~5s detection + reconnect) vs simpler code
- **Optimization**: Could parallelize in Phase 5 with race-condition winner

### 2. Tool Execution: Parallel with DAG dependencies
- **Choice**: Execute independent tools in parallel, respect dependencies
- **Rationale**: Better UX, faster task completion
- **Implementation**: Topological sort of tool calls, concurrent execution

### 3. Session Persistence: Multi-layer (in-memory + SQLite + file backup)
- **Choice**: Fast in-memory cache, durable SQLite index, JSON file backup
- **Rationale**: Balance speed (in-memory), durability (SQLite), portability (JSON)
- **Sync**: Async background writes to avoid blocking user interaction

### 4. Vector DB: Chroma (embedded, persistent)
- **Choice**: Chroma over Pinecone/Weaviate/Qdrant
- **Rationale**: Lightweight, Python-first, zero external dependency, good for education
- **Alternative**: Design DB abstraction for future migration to Qdrant

### 5. RAG: HyDE + BM25 hybrid search
- **Choice**: HyDE for semantic expansion, BM25 for keyword fallback
- **Rationale**: Better coverage than pure semantic, prevents hallucination
- **Relevance threshold**: Only return results with cosine_similarity > 0.7

### 6. Confirmation Modes: Tool-level risk detection
- **Choice**: Auto-execute low-risk tools, manual approval for high-risk
- **Rationale**: Better UX, safety trade-off
- **Implementation**: Tool schema includes `risk_level` (low/medium/high)

### 7. Error Recovery: Automatic for transient, user-prompted for permanent
- **Choice**: Auto-retry (max 3x) transient errors, inform user of permanent failures
- **Rationale**: Less friction vs safety
- **Transparency**: Always log error details for debugging

---

## INTEGRATION POINTS - CRITICAL SEQUENCES

### Sequence 1: Simple Coding Task Completion
```
1. User: "write a python hello world script"
2. CLI REPL: Parse command, create new session context
3. Agent: Invoke LLM with prompt + tools
4. LLM: Returns tool_calls: [{"name": "write_file", "args": {...}}]
5. Tool Registry: Validate tool (exists, schema valid)
6. Manual Mode?: Prompt user for confirmation
7. Tool Executor: Execute in sandbox
8. MCP Client: Route to Filesystem server
9. Filesystem Server: Write file, return result
10. Agent: Add result to context, check completion
11. LLM: Respond "Done! Created hello_world.py"
12. CLI: Display response, save session
```

### Sequence 2: Error Recovery During Execution
```
1. Agent: Send prompt to Groq API
2. Error: Timeout (transient)
3. Error Handler: Classify as TRANSIENT
4. Retry: Backoff 1s, retry #1 (fails again)
5. Retry: Backoff 2s, retry #2 (succeeds)
6. Continue: Resume execution with result
7. User: Sees brief delay, no interruption
```

### Sequence 3: Provider Failover
```
1. Agent: Send prompt to Groq API
2. Error: 500 Internal Server Error (persistent)
3. Circuit Breaker: Opens after 3 failures
4. Fallback: Switch provider to Ollama
5. Agent: Retry prompt with Ollama
6. Recovery Scheduled: Try Groq again in 30s
7. User: Informed "Using Ollama (Groq unavailable)"
```

### Sequence 4: RAG Query for Documentation
```
1. Tool Call: {"name": "search_docs", "query": "how to use langchain"}
2. Tool Executor: Route to RAG MCP server
3. RAG Server: Accept semantic_search request
4. HyDE: Expand query to 3 hypotheticals
   - "A LangChain tutorial..."
   - "How to initialize chains..."
   - "LangChain best practices..."
5. Embeddings: Convert to vectors
6. Chroma: Search vector DB (top-5 vector + top-3 BM25)
7. Re-rank & Merge: Combine results, score
8. Return: Top-3 with > 0.7 similarity + cite sources
9. Agent: Format results in LLM context
10. LLM: Use docs to inform response
```

---

## TESTING STRATEGY

### Unit Tests (40% of effort)
- **Location**: `tests/unit/`
- **Coverage Target**: 80%+ on core modules
- **Fixtures**: Mock LLM, mock MCP servers, test sessions

Examples:
```python
# Test LLM provider failover
async def test_groq_timeout_fallback_to_ollama()
    # Groq times out, should switch to Ollama

# Test tool registry schema generation
def test_tool_schema_validation()
    # Tool schema matches JSON schema spec

# Test error categorization
def test_error_classification_transient_vs_permanent()

# Test HyDE query expansion
def test_hyde_generates_three_hypotheticals()
```

### Integration Tests (30% of effort)
- **Location**: `tests/integration/`
- **Scenarios**: Full agentic loop, MCP connections, RAG queries

Examples:
```python
# Full loop test
async def test_complete_coding_task_end_to_end()
    # User query → agent loop → tool execution → response

# MCP connection test
async def test_mcp_server_reconnection_on_failure()
    # Kill server, verify agent continues after reconnect

# RAG integration test
async def test_semantic_search_returns_relevant_results()
    # Query with no exact match → HyDE finds relevant doc
```

### E2E Tests (20% of effort)
- **Location**: `tests/e2e/`
- **Hardware**: Real file system, optional real Groq/Ollama API

Examples:
```python
# CLI interaction test
def test_cli_repl_processes_user_commands()
    # Simulate terminal input, verify output

# Task completion test
async def test_agent_autonomously_completes_two_different_tasks()
    # Task 1: Write code
    # Task 2: Modify existing file

# Session resumption test
def test_cross_session_context_recovery()
    # Save session, load in new process, confirm state
```

### Test Infrastructure
- **Framework**: pytest + pytest-asyncio
- **Mocking**: pytest fixtures, unittest.mock
- **Coverage**: pytest-cov (generate HTML reports)
- **CI/CD**: GitHub Actions (run on every PR)

---

## VERIFICATION & VALIDATION

### Pre-Implementation Checklist
- [ ] All team members have Python 3.12+ installed
- [ ] Project structure created (`src/`, `tests/`, `docs/`, `scripts/`)
- [ ] `pyproject.toml` updated with all dependencies
- [ ] GitHub Actions CI/CD pipeline configured
- [ ] Team assignments finalized (who's on which team)
- [ ] Communication channels established (Slack/Discord for daily sync)

### Mid-Project Checkpoints (Weeks 4, 8, 10)
- [ ] **Week 4**: Agentic loop with mock tools functional
- [ ] **Week 8**: All 3 MCP servers connected and tested
- [ ] **Week 10**: RAG queries working with HyDE, test coverage > 75%

### Pre-Demo Requirements
- [ ] Agent completes 2+ non-trivial coding tasks autonomously
- [ ] All 3 MCP servers visibly invoked during demo
- [ ] Error recovery demonstrated (LLM timeout → Ollama fallback)
- [ ] Session persistence working (save → exit → resume)
- [ ] Code clean (linted, type-checked, documented)
- [ ] README has setup instructions + requirements.txt

### Post-Implementation Tasks
1. **Record video demo** (10-15 min)
   - Show agent + terminal window side-by-side
   - Display tool calls being executed
   - Narrate what's happening

2. **Write reflection** (2-3 pages)
   - Design decisions: Why this architecture?
   - LLM comparison: Run same task on Groq vs Ollama
   - RAG analysis: How well did HyDE work?
   - Lessons learned & future improvements

3. **Create architecture diagrams**
   - Original plan diagram
   - Final architecture (if changed)
   - Data flow diagrams for critical sequences

---

## DEPENDENCIES & TECH STACK

### Core Dependencies (add to pyproject.toml)
```toml
fastmcp = ">=3.1.0"              # MCP framework
groq = ">=0.4.0"                 # Groq LLM API
ollama = ">=0.1.0"               # Local LLM
rich = ">=13.0.0"                # CLI formatting
typer = ">=0.9.0"                # CLI framework
pydantic = ">=2.0.0"             # Data validation

# Async & concurrency
aiofiles = ">=23.0.0"            # Async file ops
tenacity = ">=8.2.0"             # Retry logic

# Vector DB & embeddings
chroma-db = ">=0.3.0"            # Vector store
sentence-transformers = ">=2.2.0" # Embeddings

# Documentation & data
langchain = ">=0.0.300"          # LLM frameworks
requests = ">=2.31.0"            # HTTP client

# Database
sqlalchemy = ">=2.0.0"           # ORM

# HTTP
httpx = ">=0.24.0"               # Async HTTP

# Logging
python-json-logger = ">=2.0.0"   # JSON logs
```

### Dev Dependencies
```toml
pytest = ">=7.4.0"
pytest-asyncio = ">=0.21.0"
pytest-cov = ">=4.1.0"
black = ">=23.0.0"          # Code formatting
ruff = ">=0.1.0"            # Linting
mypy = ">=1.5.0"            # Type checking
pre-commit = ">=3.4.0"      # Git hooks
```

---

## ASSISTANT BRANDING: NEXUS

**Full Name**: NEXUS (Neural Executive Xperiment for Unified Software automation)

**Tagline**: "Autonomous code execution, intelligent reasoning, persistent context"

**Features to Highlight**:
- ⚡ Real-time agentic reasoning
- 🛠️ Multi-tool integration (filesystem, web search, documentation)
- 🔄 Automatic error recovery and provider failover
- 💾 Cross-session context preservation
- 🎯 HyDE-powered semantic documentation retrieval

**Branding in Code**:
- App name: "NEXUS" (used in help text, headers)
- User messages: "→ You" or "⚡ User"
- Agent responses: "⟳ NEXUS" or "🤖 Agent"
- Tool execution: "🔧 [Tool Name]"
- Errors: "⚠️ Error" with recovery strategy

---

## TEAM COLLABORATION & AGREEMENTS

### Code Review Process
1. All PRs require 1 cross-team review before merge
2. Breaking changes to shared interfaces (types.py, provider.py) require 2 reviews
3. Use conventional commits: `feat:`, `fix:`, `refactor:`, `test:`

### Shared Owned Code
- **src/core/types.py** - All teams contribute
- **src/config/settings.py** - All teams contribute
- **tests/integration/** - Cross-team responsibility
- **pyproject.toml** - Lead developers manage

### Weekly Sync Structure
- **Monday**: Planning (this week's tasks, blockers)
- **Wednesday**: Progress check (integration points)
- **Friday**: Demo + retrospective (what shipped, what changed)

### Communication Norms
- Async updates in shared #nexus-coding Slack channel
- Real-time sync for blockers via voice/video
- Documentation in shared Wiki for decisions

---

## FINAL CHECKLIST - READY TO IMPLEMENT

- [x] Architecture decided and documented
- [x] Components assigned to teams
- [x] Critical file paths identified
- [x] Technology stack finalized
- [x] Phases with clear deliverables
- [x] Integration points detailed
- [x] Testing strategy defined
- [x] Team structure for 4+ developers
- [x] Error handling strategies documented
- [x] Verification/validation checklist created

**Status**: ✅ READY FOR IMPLEMENTATION

**Next Steps**:
1. Create GitHub issues for each phase/component
2. Set up project board with phases as columns
3. Begin Phase 1 (Foundation) with Team A
4. Weekly syncs starting Monday

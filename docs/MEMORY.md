# NEXUS Project Memory

## Project Overview

- **Name**: NEXUS (Neural Executive Xperiment for Unified Software automation)
- **Type**: CLI-based autonomous coding assistant
- **Team**: 4+ developers (Teams A-D)
- **Status**: Phase 2 Core Loop ✅ Complete

## Architecture

- **Primary LLM**: Groq (API-based)
- **Fallback LLM**: Ollama (local)
- **MCP Integration**: 3 required servers
  1. Filesystem (official @modelcontextprotocol/server-filesystem)
  2. Tavily (web search)
  3. Custom RAG with HyDE technique
- **RAG DB**: Chroma (local SQLite + persistence)
- **Embedding Model**: sentence-transformers (all-MiniLM-L6-v2)

## Phase 1 Implementation Details

### Completed Components

- **CLI REPL** (`src/nexus/cli/repl.py`): Terminal interface with Rich formatting
  - Commands: `/help`, `/exit`, `/clear`, `/history`, `/mode`, `/context`, `/status`
  - Streaming responses with async I/O
- **Session Management** (`src/nexus/core/session.py`): Conversation persistence
  - Message history with roles (USER, ASSISTANT, SYSTEM, TOOL)
  - Execution mode tracking (AUTO, MANUAL, CONFIRMATION)
  - Context window sliding (last 20 messages to LLM)
  - Iteration counter (max 10) to prevent infinite loops
- **Type System** (`src/nexus/core/types.py`): Shared data types
  - ToolCall, ToolResult, Message, ExecutionResult, SessionMetadata
  - ExecutionMode, ErrorCategory, MessageRole, RiskLevel enums
- **Configuration** (`src/nexus/config/settings.py`): Environment-based settings
  - LLM configs (Groq API key, Ollama URL, models)
  - Execution settings (timeouts, max iterations, retry policy)
  - Path configs (sessions, RAG DB, logs)
- **Main Entry Point** (`src/nexus/main.py`): Typer CLI application
  - Signal handling for graceful shutdown
  - Mode selection (auto/manual/confirmation)
  - Session resumption by ID

### Project Structure

```
src/nexus/
├── cli/          # Terminal interface ✅ Phase 1
├── core/         # Session, types, error handling, agent ✅ Phase 1-2
├── llm/          # Provider abstraction ✅ Phase 2
├── tools/        # (Phase 3) Registry & executor
├── mcp/          # (Phase 3) Client management
├── rag/          # (Phase 4) Custom RAG server
├── persistence/  # (Phase 4) Session DB
└── config/       # Settings & logging ✅ Phase 1
```

## Phase 2 Implementation Details

### LLM Provider Abstraction
- **Base Class** (`src/nexus/llm/provider.py`):
  - Unified interface: `invoke()`, `health_check()`, tool conversion
  - Generic LLMResponse model with tool_calls support
  - Models: ToolSchema, ToolCall, LLMResponse

- **GroqProvider** (`src/nexus/llm/groq_provider.py`):
  - Cloud-based inference with Groq API
  - Supports tool calling with function schema translation
  - Timeout handling and error categorization
  - Token counting from API responses

- **OllamaProvider** (`src/nexus/llm/ollama_provider.py`):
  - Local inference fallback for offline work
  - HTTP-based communication (async)
  - Note: Ollama doesn't support tool calling yet
  - Longer timeout for local inference (120s default)

### Agentic Loop Engine
- **Agent Class** (`src/nexus/core/agent.py`):
  - Main loop: invoke LLM → parse tool calls → execute → observe → repeat
  - Iteration counter (respects max_iterations from session)
  - Stop condition: no tool calls or max iterations reached
  - Integration with session context for message history
  - System prompt management

### Error Handling & Resilience
- **CircuitBreaker** (`src/nexus/core/error_handler.py`):
  - States: CLOSED → OPEN → HALF_OPEN
  - Failure threshold: 3 consecutive failures
  - Recovery timeout: 30 seconds
  - Prevents cascading failures

- **RetryManager**:
  - Max retries: 3 (configurable)
  - Exponential backoff with jitter
  - Error categorization for retry decisions
  - Rate limit handling with longer backoff

### Testing Coverage
- Unit tests: 7 (Phase 1 session tests still passing)
- Integration tests: 21 new tests
  - Agent creation and execution
  - Circuit breaker functionality
  - Retry manager with exponential backoff
  - LLM provider interfaces
  - Tool call extraction
  - Error classification and backoff calculation
- Total: **28 tests passing**, 50% code coverage
- CI/CD: GitHub Actions running on every push

### Phase 2 Deliverables
- ✅ LLM provider abstraction working
- ✅ Groq+Ollama multi-provider support
- ✅ Agentic loop orchestrator
- ✅ Error handling with retry logic
- ✅ Circuit breaker for resilience
- ✅ Integration tests (21 tests)
- ✅ All Phase 1 tests still passing

### Testing Infrastructure

- Framework: pytest + pytest-asyncio
- Fixtures in `tests/conftest.py` for mocks
- Unit tests: `tests/unit/test_session.py` (7 tests)
- Integration tests: `tests/integration/test_agentic_loop.py` (11 tests)
- Integration tests: `tests/integration/test_llm_providers.py` (10 tests)
- CI/CD: GitHub Actions with lint, test, build stages
- Coverage: pytest-cov tracking enabled (50% overall)

### Key Dependencies (Phase 1-3)

- `fastmcp>=3.1.0` - MCP framework
- `groq>=0.4.0`, `ollama>=0.1.0` - LLM providers
- `rich>=13.0.0`, `typer>=0.9.0` - CLI & formatting
- `pydantic>=2.0.0` - Data validation
- `tenacity>=8.2.0` - Retry logic
- `httpx>=0.24.0` - Async HTTP

### Notes for Future Phases

- **Phase 4 Dependencies** (RAG setup): Commented out in pyproject.toml
  - `chroma-db>=0.3.0` - Vector DB
  - `sentence-transformers>=2.2.0` - Embeddings
  - `langchain>=0.0.300` - Doc loading
  - `sqlalchemy>=2.0.0` - ORM
- **Python Version**: Using Python 3.14 (venv created with 3.14)
  - Some packages may have compatibility issues on 3.14
  - Project requires Python >=3.12

## Key Design Decisions

1. **Execution Modes**: Tool-level risk detection (LOW/MEDIUM/HIGH)
2. **LLM Failover**: Sequential (Groq → Ollama) not parallel
3. **Session Persistence**: Multi-layer (in-memory + future SQLite)
4. **Context Window**: Sliding window of last 20 messages
5. **Error Handling**: Transient auto-retry, permanent user notification

## Team Assignment (from plan)

- **Team A**: CLI, session, persistence ✅ Phase 1 done
- **Team B**: Agent loop, LLM providers ✅ Phase 2 done
- **Team C**: Tools, MCP clients → Phase 3
- **Team D**: RAG server, HyDE, vector DB → Phase 4

## Repository Info

- GitHub: https://github.com/David-Chan-Ho2/itsc-4681-project2.git
- Branch: main
- Latest commit: `0a83bfa feat: Phase 2 - Agentic loop and LLM integration`
- Tests: 28 passing (7 Phase 1 + 21 Phase 2)
- Coverage: 50% overall, 83% error_handler, 80% session, 81% provider base

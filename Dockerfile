# ── Stage 1: build wheel ───────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --upgrade pip build \
 && python -m build --wheel --outdir /dist


# ── Stage 2: runtime ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install the wheel and its runtime dependencies
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Persistent data directories (mounted as volumes at runtime)
RUN mkdir -p /app/nexus_sessions /app/logs /app/rag/chroma_db

# Default env — overridden by docker-compose / --env-file
ENV SESSION_DIR=/app/nexus_sessions \
    LOG_DIR=/app/logs \
    RAG_DB_DIR=/app/rag/chroma_db \
    OLLAMA_BASE_URL=http://ollama:11434 \
    EXECUTION_MODE=auto \
    MAX_ITERATIONS=10 \
    MAX_CONTEXT_MESSAGES=20 \
    LLM_TIMEOUT=30.0 \
    TOOL_TIMEOUT=60.0 \
    MCP_TIMEOUT=10.0 \
    MAX_RETRIES=3 \
    RETRY_BACKOFF_BASE=1.0 \
    DEBUG=false

ENTRYPOINT ["nexus"]
CMD ["--help"]

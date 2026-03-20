# Reflection

## Design Decisions

The project is organized around clear subsystem boundaries:

- `core/` owns the agent loop, retries, error handling, and session state.
- `llm/` hides provider-specific logic behind one shared interface.
- `mcp/` handles server registration, tool discovery, and tool routing.
- `rag/` isolates indexing and retrieval logic from the rest of the assistant.
- `cli/` focuses on user experience, tool visibility, and confirmation prompts.

That separation made the later phases much easier to complete. The phase 4 local RAG server was added without rewriting the agent loop, and the CLI improvements were made by attaching the REPL as an interaction handler instead of mixing terminal code into the core reasoning path.

## LLM Comparison

We compared Groq and Ollama on the same style of coding task: read a file, reason about it, and then make a code change.

- Groq was the stronger fit for autonomous coding because the provider adapter supports tool schemas and returns tool calls.
- Ollama works as a local fallback, but the current adapter is still text-only, so it cannot drive autonomous tool use in the same way.

The main insight is that provider abstraction is not only about swapping API endpoints. It also needs to account for capability differences. Two providers can fit the same interface while still producing very different agent behavior.

## Advanced RAG Technique

The implemented advanced RAG technique is fusion retrieval.

Pipeline:

1. Load local documentation files.
2. Chunk them with markdown-aware boundaries and overlap.
3. Embed chunks into a persistent ChromaDB collection.
4. Rewrite each query into several lightweight variants.
5. Retrieve ranked results for each variant.
6. Merge the rankings with reciprocal rank fusion before returning the best chunks.

Why this helped:

- Documentation questions are often underspecified, so one phrasing of the query can miss the right section heading or terminology.
- Query rewrites improved recall on the local docs corpus.
- Reciprocal rank fusion gave more stable results than trusting a single nearest-neighbor query.

## Safety and UX Lessons

The assistant became much more believable once tool calls were surfaced clearly in the terminal and confirmation mode actually enforced user approval for riskier actions. That transparency matters because an autonomous coding assistant is making real file-system changes, not just chatting.

## What I Would Do Differently

- Add true token-level provider streaming instead of only turn-level response rendering.
- Extend the Ollama adapter with tool-calling support once the local model stack supports it reliably.
- Add an edit review mode so users can preview or reject diffs before file writes.
- Benchmark several documentation corpora to compare fusion retrieval against HyDE or semantic chunking in a more formal way.

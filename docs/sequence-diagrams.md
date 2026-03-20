# Sequence Diagrams

These diagrams show the interactions the assignment asks us to document between the user, CLI, agent loop, LLM, MCP client, and MCP servers.

## Scenario 1: Read and Edit a File

```mermaid
sequenceDiagram
    participant U as User
    participant C as CLI Interface
    participant A as Agentic Loop
    participant L as LLM Provider
    participant M as MCP Client
    participant F as Filesystem MCP Server

    U->>C: "Inspect app.py and add a TODO comment"
    C->>A: execute(task)
    A->>L: invoke(messages, tools)
    L-->>A: tool_call(read_file)
    A->>C: show tool call
    A->>M: call_tool(read_file)
    M->>F: read_file(path)
    F-->>M: file contents
    M-->>A: ToolResult(success)
    A->>L: invoke(updated context)
    L-->>A: tool_call(write_file)
    A->>C: prompt for confirmation if mode requires it
    A->>M: call_tool(write_file)
    M->>F: write_file(path, content)
    F-->>M: write success
    M-->>A: ToolResult(success)
    A->>L: invoke(updated context)
    L-->>A: final answer
    A-->>C: final response
    C-->>U: render completion
```

## Scenario 2: Search the Web and Produce a Plan

```mermaid
sequenceDiagram
    participant U as User
    participant C as CLI Interface
    participant A as Agentic Loop
    participant L as LLM Provider
    participant M as MCP Client
    participant S as External Search MCP Server

    U->>C: "Research Tavily MCP setup and outline a plan"
    C->>A: execute(task)
    A->>L: invoke(messages, tools)
    L-->>A: tool_call(web_search)
    A->>C: show tool call
    A->>M: call_tool(web_search)
    M->>S: web_search(query)
    S-->>M: search results
    M-->>A: ToolResult(success)
    A->>L: invoke(updated context)
    L-->>A: final implementation plan
    A-->>C: final response
    C-->>U: render plan
```

## Scenario 3: Build and Use the Local Documentation Index

```mermaid
sequenceDiagram
    participant U as User
    participant C as CLI Interface
    participant A as Agentic Loop
    participant L as LLM Provider
    participant M as MCP Client
    participant R as Local RAG MCP Server
    participant V as Chroma Vector DB

    U->>C: "Using the local docs, explain how LangChain tools work"
    C->>A: execute(task)
    A->>L: invoke(messages, tools)
    L-->>A: tool_call(rag_search)
    A->>C: show tool call
    A->>M: call_tool(rag_search)
    M->>R: rag_search(query)
    R->>V: query multiple rewritten variants
    V-->>R: ranked chunk matches
    R-->>M: fused results with source paths
    M-->>A: ToolResult(success)
    A->>L: invoke(updated context)
    L-->>A: grounded answer
    A-->>C: final response
    C-->>U: render documentation answer
```

## Scenario 4: Initial RAG Index Build

```mermaid
sequenceDiagram
    participant U as User
    participant C as CLI Command
    participant R as RAGService
    participant D as Documentation Files
    participant V as Chroma Vector DB

    U->>C: "nexus build-rag --force"
    C->>R: build_index(source_dir)
    R->>D: load markdown/text files
    R->>R: chunk documents and embed chunks
    R->>V: upsert vectors and metadata
    V-->>R: persistent collection ready
    R-->>C: index summary
    C-->>U: show indexed document and chunk counts
```

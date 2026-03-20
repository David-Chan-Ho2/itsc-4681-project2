"""Generate PNG diagram files for the NEXUS deliverables."""

import graphviz
import os

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")


# ---------------------------------------------------------------------------
# State Diagram
# ---------------------------------------------------------------------------

def make_state_diagram():
    d = graphviz.Digraph(
        "nexus_state",
        comment="NEXUS Runtime State Machine",
        graph_attr={
            "rankdir": "LR",
            "bgcolor": "#1e1e2e",
            "fontname": "Helvetica",
            "fontsize": "14",
            "pad": "0.5",
            "nodesep": "0.6",
            "ranksep": "1.2",
            "label": "NEXUS Runtime State Machine",
            "labelloc": "t",
            "fontcolor": "#cdd6f4",
        },
        node_attr={
            "fontname": "Helvetica",
            "fontsize": "12",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "10",
            "color": "#89b4fa",
            "fontcolor": "#a6e3a1",
        },
    )

    def state(name, label=None, shape="rectangle", fillcolor="#313244", fontcolor="#cdd6f4"):
        d.node(
            name,
            label=label or name,
            shape=shape,
            style="filled,rounded",
            fillcolor=fillcolor,
            fontcolor=fontcolor,
            color="#89b4fa",
        )

    # Special nodes
    d.node("START", label="", shape="circle", width="0.3", style="filled",
           fillcolor="#a6e3a1", color="#a6e3a1")
    d.node("END", label="", shape="doublecircle", width="0.3", style="filled",
           fillcolor="#f38ba8", color="#f38ba8")

    # States
    state("Idle", "Idle\n(REPL waiting)")
    state("AcceptingInput", "Accepting\nInput")
    state("Reasoning", "Reasoning\n(LLM invoke)", fillcolor="#45475a")
    state("ToolSelection", "Tool\nSelection")
    state("AwaitingConfirmation", "Awaiting\nConfirmation", fillcolor="#fab387")
    state("ExecutingTools", "Executing\nTools\n(MCP call)")
    state("ObservingResults", "Observing\nResults")
    state("LLMFallback", "LLM\nFallback\n(Ollama)", fillcolor="#45475a")
    state("Completed", "Completed", fillcolor="#a6e3a1", fontcolor="#1e1e2e")
    state("Failed", "Failed\n(exceeded limits)", fillcolor="#f38ba8", fontcolor="#1e1e2e")
    state("PersistingSession", "Persisting\nSession")

    # Transitions
    d.edge("START", "Idle")
    d.edge("Idle", "AcceptingInput", label="user enters task")
    d.edge("AcceptingInput", "Reasoning", label="agent invokes LLM")
    d.edge("Reasoning", "Completed", label="final answer")
    d.edge("Reasoning", "ToolSelection", label="tool call emitted")
    d.edge("Reasoning", "LLMFallback", label="Groq error")
    d.edge("LLMFallback", "ToolSelection", label="Ollama answer\n(text only)")
    d.edge("LLMFallback", "Failed", label="Ollama also fails")
    d.edge("ToolSelection", "AwaitingConfirmation", label="manual / high-risk")
    d.edge("ToolSelection", "ExecutingTools", label="auto-approved")
    d.edge("AwaitingConfirmation", "ExecutingTools", label="user approves")
    d.edge("AwaitingConfirmation", "ObservingResults", label="user declines")
    d.edge("ExecutingTools", "ObservingResults", label="MCP returns result")
    d.edge("ObservingResults", "Reasoning", label="result added to context")
    d.edge("Reasoning", "Failed", label="max iterations\nor unrecoverable error")
    d.edge("Completed", "PersistingSession")
    d.edge("Failed", "PersistingSession")
    d.edge("PersistingSession", "Idle", label="ready for next task")
    d.edge("Idle", "END", label="/exit")

    return d


# ---------------------------------------------------------------------------
# Architecture Diagram (component view)
# ---------------------------------------------------------------------------

def make_architecture_diagram():
    d = graphviz.Digraph(
        "nexus_architecture",
        comment="NEXUS Component Architecture",
        graph_attr={
            "rankdir": "LR",
            "bgcolor": "#1e1e2e",
            "fontname": "Helvetica",
            "fontsize": "14",
            "pad": "0.6",
            "nodesep": "0.5",
            "ranksep": "1.4",
            "label": "NEXUS Component Architecture",
            "labelloc": "t",
            "fontcolor": "#cdd6f4",
            "splines": "ortho",
        },
        node_attr={
            "fontname": "Helvetica",
            "fontsize": "11",
            "shape": "rectangle",
            "style": "filled,rounded",
            "color": "#89b4fa",
            "fontcolor": "#cdd6f4",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "9",
            "color": "#6c7086",
        },
    )

    def node(name, label=None, fillcolor="#313244"):
        d.node(name, label=label or name, fillcolor=fillcolor)

    # User
    node("User", "User", fillcolor="#a6e3a1")

    with d.subgraph(name="cluster_cli") as s:
        s.attr(label="CLI Layer", color="#585b70", fontcolor="#cdd6f4",
               style="rounded", bgcolor="#181825")
        node("REPL", "REPLInterface")
        node("SessionStore", "SessionStore\n(JSON files)")

    with d.subgraph(name="cluster_core") as s:
        s.attr(label="Core Layer", color="#585b70", fontcolor="#cdd6f4",
               style="rounded", bgcolor="#181825")
        node("Agent", "Agent\n(execute loop)")
        node("Session", "SessionContext")
        node("Retry", "RetryManager\n+ CircuitBreaker")

    with d.subgraph(name="cluster_llm") as s:
        s.attr(label="LLM Providers", color="#585b70", fontcolor="#cdd6f4",
               style="rounded", bgcolor="#181825")
        node("Provider", "LLMProvider\n(abstract)")
        node("Groq", "GroqProvider\n(cloud)", fillcolor="#89dceb")
        node("Ollama", "OllamaProvider\n(local)", fillcolor="#89dceb")

    with d.subgraph(name="cluster_mcp") as s:
        s.attr(label="MCP Layer", color="#585b70", fontcolor="#cdd6f4",
               style="rounded", bgcolor="#181825")
        node("Executor", "MCPToolExecutor")
        node("MCPMgr", "MCPClientManager")
        node("FS", "Filesystem MCP\n(official stdio)", fillcolor="#cba6f7")
        node("Search", "Tavily MCP\n(remote)", fillcolor="#cba6f7")
        node("RAG", "Local RAG MCP\n(custom stdio)", fillcolor="#cba6f7")

    with d.subgraph(name="cluster_rag") as s:
        s.attr(label="RAG Subsystem", color="#585b70", fontcolor="#cdd6f4",
               style="rounded", bgcolor="#181825")
        node("RAGSvc", "RAGService")
        node("Chunker", "MarkdownChunker")
        node("Embed", "HashEmbeddingModel")
        node("Fusion", "FusionRetrieval\n(query rewrites\n+ RRF)")
        node("Chroma", "ChromaDB\n(persistent)", fillcolor="#f9e2af")

    # Edges
    d.edge("User", "REPL")
    d.edge("REPL", "Agent")
    d.edge("REPL", "SessionStore")
    d.edge("Agent", "Session")
    d.edge("Agent", "Provider")
    d.edge("Agent", "Executor")
    d.edge("Agent", "Retry")
    d.edge("Provider", "Groq")
    d.edge("Provider", "Ollama")
    d.edge("Executor", "MCPMgr")
    d.edge("MCPMgr", "FS")
    d.edge("MCPMgr", "Search")
    d.edge("MCPMgr", "RAG")
    d.edge("RAG", "RAGSvc")
    d.edge("RAGSvc", "Chunker")
    d.edge("RAGSvc", "Embed")
    d.edge("RAGSvc", "Fusion")
    d.edge("RAGSvc", "Chroma")

    return d


# ---------------------------------------------------------------------------
# Sequence diagrams — rendered as DOT graphs (activity-style)
# Each "sequence" is a ranked DOT digraph that approximates a sequence diagram
# ---------------------------------------------------------------------------

def _seq_graph(name, title):
    """Return a Digraph configured as a sequence diagram canvas."""
    return graphviz.Digraph(
        name,
        graph_attr={
            "rankdir": "TB",
            "bgcolor": "#1e1e2e",
            "fontname": "Helvetica",
            "fontsize": "12",
            "label": title,
            "labelloc": "t",
            "fontcolor": "#cdd6f4",
            "pad": "0.5",
            "nodesep": "0.8",
            "ranksep": "0.5",
            "splines": "false",
        },
        node_attr={
            "fontname": "Helvetica",
            "fontsize": "11",
            "shape": "rectangle",
            "style": "filled,rounded",
            "color": "#89b4fa",
            "fontcolor": "#cdd6f4",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "9",
            "color": "#89b4fa",
            "fontcolor": "#a6e3a1",
        },
    )


def make_seq_file_edit():
    """Scenario 1: Read and Edit a File."""
    d = _seq_graph("seq_file_edit", "Scenario 1: Read and Edit a File")

    actors = ["User", "CLI", "AgentLoop", "LLM", "MCPClient", "FilesystemMCP"]
    colors = ["#a6e3a1", "#89dceb", "#cba6f7", "#f9e2af", "#fab387", "#f38ba8"]
    label_map = {
        "User": "User",
        "CLI": "CLI\nInterface",
        "AgentLoop": "Agentic\nLoop",
        "LLM": "LLM\nProvider",
        "MCPClient": "MCP\nClient",
        "FilesystemMCP": "Filesystem\nMCP Server",
    }

    for actor, color in zip(actors, colors):
        d.node(actor + "_head", label=label_map[actor], shape="rectangle",
               fillcolor=color, fontcolor="#1e1e2e", style="filled,rounded",
               width="1.4")

    steps = [
        ("User", "CLI", "1. Read app.py and add TODO comment"),
        ("CLI", "AgentLoop", "2. execute(task)"),
        ("AgentLoop", "LLM", "3. invoke(messages, tools)"),
        ("LLM", "AgentLoop", "4. tool_call: read_file"),
        ("AgentLoop", "CLI", "5. display tool call"),
        ("AgentLoop", "MCPClient", "6. call_tool(read_file)"),
        ("MCPClient", "FilesystemMCP", "7. read_file(path)"),
        ("FilesystemMCP", "MCPClient", "8. file contents"),
        ("MCPClient", "AgentLoop", "9. ToolResult(success)"),
        ("AgentLoop", "LLM", "10. invoke(updated context)"),
        ("LLM", "AgentLoop", "11. tool_call: write_file"),
        ("AgentLoop", "CLI", "12. [confirmation] approve?"),
        ("CLI", "AgentLoop", "13. user approves"),
        ("AgentLoop", "MCPClient", "14. call_tool(write_file)"),
        ("MCPClient", "FilesystemMCP", "15. write_file(path, content)"),
        ("FilesystemMCP", "MCPClient", "16. write success"),
        ("MCPClient", "AgentLoop", "17. ToolResult(success)"),
        ("AgentLoop", "LLM", "18. invoke(updated context)"),
        ("LLM", "AgentLoop", "19. final answer"),
        ("AgentLoop", "CLI", "20. final response"),
        ("CLI", "User", "21. render completion"),
    ]

    prev_nodes = {}
    for i, (src, dst, label) in enumerate(steps):
        node_id = f"step_{i}"
        d.node(node_id, label=label, shape="rectangle",
               fillcolor="#313244", fontcolor="#cdd6f4",
               style="filled,rounded", width="3.5")

        # Invisible rank constraint to keep steps ordered vertically
        if i > 0:
            d.edge(f"step_{i-1}", node_id, style="invis")

        # Source actor to step
        col = actors.index(src)
        d.edge(src + "_head", node_id, style="dashed", constraint="false",
               weight="0")

    return d


def make_seq_web_research():
    """Scenario 2: Search the Web and Produce a Plan."""
    d = _seq_graph("seq_web_research",
                   "Scenario 2: Web Research via Tavily MCP")

    steps = [
        "1. User → CLI\n\"Research Tavily MCP setup and outline a plan\"",
        "2. CLI → AgentLoop\nexecute(task)",
        "3. AgentLoop → LLM\ninvoke(messages, tools=[web_search, ...])",
        "4. LLM → AgentLoop\ntool_call: web_search(query)",
        "5. AgentLoop → CLI\ndisplay tool call",
        "6. AgentLoop → MCPClient\ncall_tool(web_search)",
        "7. MCPClient → Tavily MCP Server\nweb_search(query)",
        "8. Tavily MCP Server → MCPClient\nsearch results JSON",
        "9. MCPClient → AgentLoop\nToolResult(success, results)",
        "10. AgentLoop → LLM\ninvoke(updated context + results)",
        "11. LLM → AgentLoop\nfinal implementation plan",
        "12. AgentLoop → CLI\nfinal response",
        "13. CLI → User\nrender plan with source citations",
    ]

    for i, step in enumerate(steps):
        color = "#a6e3a1" if i == 0 or i == len(steps) - 1 else "#313244"
        font = "#1e1e2e" if i == 0 or i == len(steps) - 1 else "#cdd6f4"
        d.node(f"s{i}", label=step, shape="rectangle",
               fillcolor=color, fontcolor=font,
               style="filled,rounded", width="4.0")
        if i > 0:
            d.edge(f"s{i-1}", f"s{i}", color="#89b4fa")

    return d


def make_seq_rag_query():
    """Scenario 3: Local RAG Documentation Query."""
    d = _seq_graph("seq_rag_query",
                   "Scenario 3: Local RAG Documentation Query")

    steps = [
        "1. User → CLI\n\"Using local docs, explain how LangChain tools work\"",
        "2. CLI → AgentLoop\nexecute(task)",
        "3. AgentLoop → LLM\ninvoke(messages, tools=[rag_search, ...])",
        "4. LLM → AgentLoop\ntool_call: rag_search(query)",
        "5. AgentLoop → CLI\ndisplay tool call",
        "6. AgentLoop → MCPClient\ncall_tool(rag_search)",
        "7. MCPClient → Local RAG MCP Server\nrag_search(query)",
        "8. Local RAG MCP Server → RAGService\nrewrite query into N variants",
        "9. RAGService → ChromaDB\nembedding search (N queries)",
        "10. ChromaDB → RAGService\nranked chunk candidates",
        "11. RAGService → RAGService\nreciprocal rank fusion",
        "12. RAGService → Local RAG MCP Server\nbest chunks + source paths",
        "13. Local RAG MCP Server → MCPClient\nToolResult(fused results)",
        "14. MCPClient → AgentLoop\nToolResult(success)",
        "15. AgentLoop → LLM\ninvoke(updated context + doc chunks)",
        "16. LLM → AgentLoop\ngrounded answer referencing docs",
        "17. AgentLoop → CLI\nfinal response",
        "18. CLI → User\nrender documentation answer",
    ]

    for i, step in enumerate(steps):
        color = "#a6e3a1" if i == 0 or i == len(steps) - 1 else "#313244"
        font = "#1e1e2e" if i == 0 or i == len(steps) - 1 else "#cdd6f4"
        d.node(f"s{i}", label=step, shape="rectangle",
               fillcolor=color, fontcolor=font,
               style="filled,rounded", width="4.5")
        if i > 0:
            d.edge(f"s{i-1}", f"s{i}", color="#89b4fa")

    return d


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(DOCS_DIR, exist_ok=True)

    items = [
        (make_state_diagram(), "state-diagram"),
        (make_architecture_diagram(), "architecture-diagram"),
        (make_seq_web_research(), "seq-web-research"),
        (make_seq_rag_query(), "seq-rag-query"),
    ]

    for diagram, name in items:
        out_path = os.path.join(DOCS_DIR, name)
        diagram.render(out_path, format="png", cleanup=True)
        print(f"  wrote {out_path}.png")

    print("Done — diagram PNGs written to docs/")


if __name__ == "__main__":
    main()

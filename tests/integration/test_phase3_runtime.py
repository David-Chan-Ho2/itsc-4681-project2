"""Deeper runtime verification for the application runtime."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import typer

from nexus.core.agent import Agent
from nexus.core.session import SessionContext
from nexus.core.types import ExecutionMode
from nexus.llm.provider import LLMResponse, ToolCall, ToolSchema
from nexus.mcp.client import MCPClientManager
from nexus.mcp.servers.filesystem import filesystem_server
from nexus.tools.executor import MCPToolExecutor


@pytest.mark.asyncio
async def test_agent_executes_real_filesystem_tool_round_trip(tmp_path):
    """The agent can drive the MCP executor end to end for a real file write."""
    session = SessionContext()
    target = tmp_path / "generated.py"

    provider = AsyncMock()
    provider.invoke = AsyncMock(
        side_effect=[
            LLMResponse(
                content="I'll create the file.",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="write_file",
                        arguments={"path": str(target), "content": "print('phase3')"},
                    )
                ],
                stop_reason="tool_use",
            ),
            LLMResponse(
                content="The file has been created successfully.",
                tool_calls=[],
                stop_reason="end_turn",
            ),
        ]
    )

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)
    executor = MCPToolExecutor(manager)
    await executor.initialize()

    agent = Agent(llm_provider=provider, session=session, tool_executor=executor)
    result = await agent.execute("Create generated.py that prints phase3")

    assert result.success is True
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "print('phase3')"
    assert session.messages[1].tool_results[0].success is True
    assert session.messages[1].tool_results[0].tool_name == "write_file"


@pytest.mark.asyncio
async def test_repl_run_loop_initializes_executor_before_processing(monkeypatch):
    """The REPL initializes tools before entering the input loop."""
    from nexus.cli.repl import REPLInterface

    repl = REPLInterface()
    repl.start_session()

    tool_executor = SimpleNamespace(initialize=AsyncMock())
    agent = SimpleNamespace(tool_executor=tool_executor, execute=AsyncMock())
    repl.set_agent(agent)

    prompts = iter(["/exit"])
    monkeypatch.setattr("nexus.cli.repl.console.input", lambda _: next(prompts))
    monkeypatch.setattr("nexus.cli.repl.console.print", lambda *args, **kwargs: None)

    await repl.run_loop()

    tool_executor.initialize.assert_awaited_once()


def test_repl_set_agent_registers_itself_as_interaction_handler():
    """Attaching the agent wires the REPL into tool feedback callbacks."""
    from nexus.cli.repl import REPLInterface

    repl = REPLInterface()
    session = repl.start_session()
    provider = AsyncMock()
    agent = Agent(llm_provider=provider, session=session)

    repl.set_agent(agent)

    assert repl.agent is agent
    assert agent.interaction_handler is repl


def test_repl_tools_command_lists_discovered_tools(monkeypatch):
    """The /tools view exposes the tool schemas discovered by MCP."""
    from nexus.cli.repl import REPLInterface

    repl = REPLInterface()
    repl.start_session()

    fake_executor = SimpleNamespace(
        get_tool_schemas=lambda: [
            ToolSchema(
                name="read_file",
                description="Read a file",
                parameters={"type": "object"},
            ),
            ToolSchema(
                name="web_search",
                description="Search the web",
                parameters={"type": "object"},
            ),
        ]
    )
    repl.agent = SimpleNamespace(tool_executor=fake_executor)

    printed: list[str] = []

    def capture(*args, **kwargs):
        printed.append(" ".join(str(arg) for arg in args))

    monkeypatch.setattr("nexus.cli.repl.console.print", capture)

    repl._show_tools()

    output = "\n".join(printed)
    assert "read_file" in output
    assert "web_search" in output


def test_main_invalid_mode_exits(monkeypatch):
    """The CLI rejects invalid execution modes."""
    from nexus import main as nexus_main

    monkeypatch.setattr(nexus_main.settings, "validate", lambda: None)
    monkeypatch.setattr(nexus_main.signal, "signal", lambda *args, **kwargs: None)

    with pytest.raises(typer.Exit) as exc:
        nexus_main.main(mode="danger-zone")

    assert exc.value.exit_code == 1


def test_main_wires_ollama_phase3_stack(monkeypatch):
    """The main entrypoint wires the full MCP stack when running with Ollama."""
    from nexus import main as nexus_main

    captured = {}
    session = SessionContext()

    class FakeStore:
        def exists(self, session_id):
            return False

        def save(self, stored_session):
            captured["saved_session"] = stored_session

    class FakeREPL:
        def __init__(self):
            self.session = session
            self.agent = None

        def start_session(self, session_id=None, execution_mode=None, existing_session=None):
            captured["start_session"] = {
                "session_id": session_id,
                "execution_mode": execution_mode,
                "existing_session": existing_session,
            }
            return session

        def set_agent(self, agent):
            self.agent = agent
            captured["agent"] = agent

        async def run_loop(self):
            captured["run_loop_called"] = True

    monkeypatch.setattr(nexus_main.settings, "validate", lambda: None)
    monkeypatch.setattr(nexus_main.settings, "GROQ_API_KEY", None)
    monkeypatch.setattr(nexus_main.settings, "TAVILY_API_KEY", None)
    monkeypatch.setattr(nexus_main.settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(nexus_main.settings, "OLLAMA_MODEL", "mistral")
    monkeypatch.setattr(nexus_main.signal, "signal", lambda *args, **kwargs: None)
    monkeypatch.setattr(nexus_main, "SessionStore", FakeStore)
    monkeypatch.setattr(nexus_main, "create_repl", lambda: FakeREPL())
    monkeypatch.setattr(
        "nexus.llm.ollama_provider.OllamaProvider",
        lambda base_url, model: SimpleNamespace(
            base_url=base_url,
            model=model,
            invoke=AsyncMock(),
        ),
    )
    monkeypatch.setattr(
        nexus_main.asyncio,
        "run",
        lambda coro: (coro.close(), captured.setdefault("run_loop_called", True))[1],
    )
    monkeypatch.setattr(nexus_main.console, "print", lambda *args, **kwargs: None)

    nexus_main.main(mode="confirmation")

    agent = captured["agent"]
    assert isinstance(agent.tool_executor, MCPToolExecutor)
    assert set(agent.tool_executor.mcp_manager._servers) == {
        "filesystem",
        "search",
        "rag",
    }
    assert captured["start_session"]["execution_mode"] == ExecutionMode.CONFIRMATION
    assert captured["saved_session"] is session


def test_main_wires_groq_when_api_key_is_present(monkeypatch):
    """The main entrypoint prefers the cloud provider when a Groq key exists."""
    from nexus import main as nexus_main

    captured = {}
    session = SessionContext()

    class FakeStore:
        def exists(self, session_id):
            return False

        def save(self, stored_session):
            captured["saved_session"] = stored_session

    class FakeREPL:
        def __init__(self):
            self.session = session

        def start_session(self, session_id=None, execution_mode=None, existing_session=None):
            return session

        def set_agent(self, agent):
            captured["agent"] = agent

        async def run_loop(self):
            captured["run_loop_called"] = True

    fake_provider = SimpleNamespace(invoke=AsyncMock(), model="mixtral")

    monkeypatch.setattr(nexus_main.settings, "validate", lambda: None)
    monkeypatch.setattr(nexus_main.settings, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(nexus_main.settings, "TAVILY_API_KEY", None)
    monkeypatch.setattr(nexus_main.settings, "GROQ_MODEL", "mixtral-test")
    monkeypatch.setattr(nexus_main.signal, "signal", lambda *args, **kwargs: None)
    monkeypatch.setattr(nexus_main, "SessionStore", FakeStore)
    monkeypatch.setattr(nexus_main, "create_repl", lambda: FakeREPL())
    monkeypatch.setattr(
        "nexus.llm.groq_provider.GroqProvider",
        lambda api_key, model: fake_provider,
    )
    monkeypatch.setattr(
        nexus_main.asyncio,
        "run",
        lambda coro: (coro.close(), captured.setdefault("run_loop_called", True))[1],
    )
    monkeypatch.setattr(nexus_main.console, "print", lambda *args, **kwargs: None)

    nexus_main.main(mode="auto")

    assert captured["agent"].llm_provider is fake_provider
    assert isinstance(captured["agent"].tool_executor, MCPToolExecutor)
    assert set(captured["agent"].tool_executor.mcp_manager._servers) == {
        "filesystem",
        "search",
        "rag",
    }

"""Integration tests for Phase 2 - Agentic loop and LLM providers."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from nexus.core.agent import Agent
from nexus.core.session import SessionContext
from nexus.core.types import ExecutionMode, RiskLevel, ToolResult
from nexus.core.error_handler import CircuitBreaker, RetryManager, ErrorCategory
from nexus.llm.provider import LLMProvider, LLMResponse, ToolCall


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, model: str = "test-model"):
        """Initialize mock provider."""
        super().__init__(model=model)
        self.call_count = 0
        self.last_prompt = None

    async def invoke(
        self,
        prompt,
        system=None,
        tools=None,
        temperature=0.7,
        max_tokens=None,
        conversation_history=None,
    ):
        """Mock invoke."""
        self.call_count += 1
        self.last_prompt = prompt

        # Return a simple response
        return LLMResponse(
            content="I'll help you with that.",
            tool_calls=[],
            stop_reason="end_turn",
            input_tokens=10,
            output_tokens=5,
        )

    async def health_check(self):
        """Mock health check."""
        return True


@pytest.mark.asyncio
async def test_agent_creation():
    """Test that an agent can be created."""
    session = SessionContext()
    provider = MockLLMProvider()
    agent = Agent(llm_provider=provider, session=session)

    assert agent.llm_provider is provider
    assert agent.session is session


@pytest.mark.asyncio
async def test_agent_simple_execution():
    """Test simple agent execution without tools."""
    session = SessionContext()

    # Create mock provider
    provider = AsyncMock(spec=LLMProvider)
    provider.invoke = AsyncMock(
        return_value=LLMResponse(
            content="Task completed.",
            tool_calls=[],
            stop_reason="end_turn",
        )
    )

    agent = Agent(llm_provider=provider, session=session)

    # Execute
    result = await agent.execute("Write a simple script")

    assert result.success is True
    assert "Task completed" in result.message
    assert result.iterations >= 1


@pytest.mark.asyncio
async def test_agent_with_tool_calls():
    """Test agent execution with tool calls."""
    session = SessionContext()

    # Create mock provider that returns tool calls
    provider = AsyncMock(spec=LLMProvider)

    # First call: LLM requests tool
    provider.invoke = AsyncMock(
        return_value=LLMResponse(
            content="I'll write a file for you.",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="write_file",
                    arguments={"path": "test.py", "content": "print('hello')"},
                )
            ],
            stop_reason="tool_use",
        )
    )

    # Create agent
    agent = Agent(llm_provider=provider, session=session)

    # Execute
    result = await agent.execute("Write a Python script")

    # Should attempt to execute but fail (no tool executor)
    # and still return some result
    assert result.iterations >= 1


@pytest.mark.asyncio
async def test_circuit_breaker():
    """Test circuit breaker functionality."""

    async def failing_func():
        raise Exception("Test error")

    async def recovering_func():
        recovering_func.call_count += 1
        if recovering_func.call_count < 3:
            raise Exception("Still failing")
        return "Success"

    recovering_func.call_count = 0

    breaker = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)

    # Test: failures open the breaker
    with pytest.raises(Exception):
        await breaker.call(failing_func)

    with pytest.raises(Exception):
        await breaker.call(failing_func)

    # Circuit should be open now
    with pytest.raises(Exception):
        await breaker.call(failing_func)


@pytest.mark.asyncio
async def test_retry_manager():
    """Test retry manager with exponential backoff."""

    async def flaky_func():
        flaky_func.attempts += 1
        if flaky_func.attempts < 2:
            raise TimeoutError("Timeout")
        return "Success"

    flaky_func.attempts = 0

    manager = RetryManager(max_retries=3, backoff_base=0.01)

    result = await manager.execute_with_retry(flaky_func)
    assert result == "Success"
    assert flaky_func.attempts == 2


@pytest.mark.asyncio
async def test_retry_manager_exhaustion():
    """Test retry manager exhausts retries."""

    async def always_failing():
        raise ValueError("Always fails")

    manager = RetryManager(max_retries=2, backoff_base=0.01)

    with pytest.raises(ValueError):
        await manager.execute_with_retry(always_failing)


def test_error_categorization():
    """Test error categorization."""
    manager = RetryManager()

    # Timeout errors
    timeout_error = TimeoutError("Request timed out")
    category = manager._infer_category(timeout_error)
    assert category == ErrorCategory.TRANSIENT

    # Rate limit errors
    rate_limit_error = Exception("429 Too Many Requests")
    category = manager._infer_category(rate_limit_error)
    assert category == ErrorCategory.RATE_LIMIT

    # Validation errors
    validation_error = Exception("Invalid input validation")
    category = manager._infer_category(validation_error)
    assert category == ErrorCategory.VALIDATION_ERROR


def test_backoff_calculation():
    """Test exponential backoff calculation."""
    manager = RetryManager(backoff_base=1.0, backoff_max=60.0)

    # Should increase exponentially
    backoff1 = manager._calculate_backoff(1, ErrorCategory.TRANSIENT)
    backoff2 = manager._calculate_backoff(2, ErrorCategory.TRANSIENT)
    backoff3 = manager._calculate_backoff(3, ErrorCategory.TRANSIENT)

    # Rough checks (allowing for jitter)
    assert 0.5 < backoff1 < 2.0  # Around 1.0 ±50%
    assert 1.0 < backoff2 < 4.0  # Around 2.0 ±50%
    assert 2.0 < backoff3 < 8.0  # Around 4.0 ±50%


def test_session_context_system_prompt():
    """Test session provides system prompt."""
    session = SessionContext()
    prompt = session.get_system_prompt()

    assert "NEXUS" in prompt
    assert "autonomous" in prompt.lower()
    assert len(prompt) > 50


@pytest.mark.asyncio
async def test_agent_respects_max_iterations():
    """Test agent respects max iterations."""
    session = SessionContext()
    session.max_iterations = 2

    # Create provider that always returns tool calls
    provider = AsyncMock(spec=LLMProvider)
    provider.invoke = AsyncMock(
        return_value=LLMResponse(
            content="Continuing...",
            tool_calls=[
                ToolCall(
                    id=f"call-{i}",
                    name="dummy_tool",
                    arguments={},
                )
                for i in range(1)
            ],
            stop_reason="tool_use",
        )
    )

    agent = Agent(llm_provider=provider, session=session)

    # Execute - should stop at max iterations
    result = await agent.execute("Do something")

    # Should reach max iterations
    assert result.iterations >= session.max_iterations


@pytest.mark.asyncio
async def test_session_message_history_in_context():
    """Test session message history is used in LLM context."""
    session = SessionContext()

    # Add some messages
    session.add_user_message("First question")
    session.add_assistant_message("First answer")
    session.add_user_message("Second question")

    # Create provider to check context
    provider = AsyncMock(spec=LLMProvider)
    provider.invoke = AsyncMock(
        return_value=LLMResponse(
            content="Response",
            tool_calls=[],
            stop_reason="end_turn",
        )
    )

    agent = Agent(llm_provider=provider, session=session)

    await agent.execute("Final question")

    # Check that invoke was called with context
    assert provider.invoke.called


@pytest.mark.asyncio
async def test_agent_reports_tool_events_to_interaction_handler():
    """Tool start and result events are surfaced to the attached UI handler."""
    session = SessionContext()
    provider = AsyncMock(spec=LLMProvider)
    provider.invoke = AsyncMock(
        side_effect=[
            LLMResponse(
                content="I'll inspect the file first.",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="read_file",
                        arguments={"path": "main.py"},
                    )
                ],
                stop_reason="tool_use",
            ),
            LLMResponse(
                content="The file has been read.",
                tool_calls=[],
                stop_reason="end_turn",
            ),
        ]
    )

    tool_executor = AsyncMock()
    tool_executor.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="call-1",
            tool_name="read_file",
            output="print('hello')",
            success=True,
        )
    )
    tool_executor.get_tool_schemas = MagicMock(return_value=[])

    handler = MagicMock()

    agent = Agent(
        llm_provider=provider,
        session=session,
        tool_executor=tool_executor,
        interaction_handler=handler,
    )

    result = await agent.execute("Read main.py")

    assert result.success is True
    handler.show_tool_call.assert_called_once_with("read_file", {"path": "main.py"})
    handler.show_tool_result.assert_called_once()
    assert session.messages[1].tool_calls[0].risk_level == RiskLevel.LOW


@pytest.mark.asyncio
async def test_agent_respects_confirmation_handler_for_high_risk_tools():
    """Confirmation mode asks before high-risk tool execution and can block it."""
    session = SessionContext(execution_mode=ExecutionMode.CONFIRMATION)
    provider = AsyncMock(spec=LLMProvider)
    provider.invoke = AsyncMock(
        side_effect=[
            LLMResponse(
                content="I need to delete the file.",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="delete_file",
                        arguments={"path": "scratch.txt"},
                    )
                ],
                stop_reason="tool_use",
            ),
            LLMResponse(
                content="I skipped the deletion after the confirmation prompt.",
                tool_calls=[],
                stop_reason="end_turn",
            ),
        ]
    )

    tool_executor = AsyncMock()
    tool_executor.execute = AsyncMock()
    tool_executor.get_tool_schemas = MagicMock(return_value=[])

    handler = MagicMock()
    handler.prompt_confirmation.return_value = False

    agent = Agent(
        llm_provider=provider,
        session=session,
        tool_executor=tool_executor,
        interaction_handler=handler,
    )

    result = await agent.execute("Delete scratch.txt")

    assert result.success is True
    handler.prompt_confirmation.assert_called_once()
    tool_executor.execute.assert_not_called()
    assert session.messages[1].tool_calls[0].risk_level == RiskLevel.HIGH
    assert session.messages[1].tool_results[0].error == "User did not confirm"

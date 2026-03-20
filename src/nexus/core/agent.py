"""Agentic loop orchestrator for NEXUS."""

import json
from typing import Any, Optional, Protocol

from nexus.core.error_handler import CircuitBreaker, ErrorCategory, RetryManager
from nexus.core.session import SessionContext
from nexus.core.types import ExecutionResult, RiskLevel, ToolCall, ToolResult
from nexus.llm.provider import LLMProvider, LLMResponse, ToolSchema


class AgentInteractionHandler(Protocol):
    """UI hooks used by the agent during tool execution."""

    def show_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Display that a tool is about to be executed."""

    def show_tool_result(self, tool_name: str, success: bool, output: str) -> None:
        """Display the result of a tool execution."""

    def prompt_confirmation(self, message: str) -> bool:
        """Request user confirmation before a tool runs."""


class Agent:
    """Autonomous agent orchestrator."""

    DEFAULT_TOOL_RISKS = {
        "list_allowed_directories": RiskLevel.LOW,
        "read_file": RiskLevel.LOW,
        "list_directory": RiskLevel.LOW,
        "search_files": RiskLevel.LOW,
        "web_search": RiskLevel.LOW,
        "rag_search": RiskLevel.LOW,
        "rag_status": RiskLevel.LOW,
        "create_directory": RiskLevel.MEDIUM,
        "write_file": RiskLevel.MEDIUM,
        "build_rag_index": RiskLevel.MEDIUM,
        "move_file": RiskLevel.MEDIUM,
        "delete_file": RiskLevel.HIGH,
    }

    def __init__(
        self,
        llm_provider: LLMProvider,
        session: SessionContext,
        tool_executor: Optional["ToolExecutor"] = None,
        interaction_handler: Optional[AgentInteractionHandler] = None,
        max_iterations: Optional[int] = None,
    ):
        """Initialize agent.

        Args:
            llm_provider: LLM provider for reasoning.
            session: Session context for conversation.
            tool_executor: Optional tool executor.
            interaction_handler: Optional CLI/UI handler for tool feedback.
            max_iterations: Max iterations (overrides session default).
        """
        self.llm_provider = llm_provider
        self.session = session
        self.tool_executor = tool_executor
        self.interaction_handler = interaction_handler

        if max_iterations:
            self.session.max_iterations = max_iterations

        # Error handling
        self.retry_manager = RetryManager(max_retries=3, backoff_base=1.0)
        self.circuit_breaker = CircuitBreaker("llm_provider", failure_threshold=3)

    def set_interaction_handler(
        self, interaction_handler: Optional[AgentInteractionHandler]
    ) -> None:
        """Attach or replace the interaction handler used during execution."""
        self.interaction_handler = interaction_handler

    async def execute(self, user_input: str) -> ExecutionResult:
        """Execute agent loop until completion.

        Args:
            user_input: The user's instruction.

        Returns:
            ExecutionResult with final response and metadata.
        """
        self.session.add_user_message(user_input)

        result = ExecutionResult(
            success=False,
            message="",
            iterations=0,
            tool_calls_made=0,
            error=None,
            error_category=None,
        )

        try:
            while not self.session.reached_max_iterations():
                self.session.increment_iteration()
                result.iterations += 1

                llm_response = await self._invoke_llm()

                if llm_response.tool_calls:
                    result.tool_calls_made += len(llm_response.tool_calls)

                    core_tool_calls = self._normalize_tool_calls(llm_response.tool_calls)
                    self.session.add_assistant_message(llm_response.content, core_tool_calls)

                    tool_results = await self._execute_tool_calls(core_tool_calls)

                    for tool_result in tool_results:
                        self.session.add_tool_result(tool_result.tool_call_id, tool_result)

                    continue

                self.session.add_assistant_message(llm_response.content)
                result.success = True
                result.message = llm_response.content
                result.final_response = llm_response.content
                break

            if not result.success and self.session.reached_max_iterations():
                result.success = False
                result.message = (
                    f"Agent reached max iterations ({self.session.max_iterations}). "
                    "Task may be incomplete."
                )
                result.error = result.message
                result.error_category = ErrorCategory.UNKNOWN

            return result

        except Exception as e:
            result.success = False
            result.message = f"Agent execution failed: {str(e)}"
            result.error = str(e)
            result.error_category = ErrorCategory.UNKNOWN
            return result

    async def _invoke_llm(self) -> LLMResponse:
        """Invoke the LLM with current context.

        Returns:
            LLM response.

        Raises:
            Exception: If LLM invocation fails.
        """
        try:
            context_messages = []
            for msg in self.session.get_context_messages():
                if msg.role.value == "user":
                    context_messages.append({"role": "user", "content": msg.content})
                elif msg.role.value == "assistant":
                    if msg.tool_calls:
                        context_messages.append(
                            {
                                "role": "assistant",
                                "content": msg.content or "",
                                "tool_calls": [
                                    {
                                        "id": tc.id,
                                        "type": "function",
                                        "function": {
                                            "name": tc.name,
                                            "arguments": json.dumps(tc.arguments),
                                        },
                                    }
                                    for tc in msg.tool_calls
                                ],
                            }
                        )
                        for tr in msg.tool_results:
                            context_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tr.tool_call_id,
                                    "content": tr.output,
                                }
                            )
                    else:
                        context_messages.append(
                            {
                                "role": "assistant",
                                "content": msg.content,
                            }
                        )

            tool_schemas: list[ToolSchema] = []
            if self.tool_executor:
                tool_schemas = self.tool_executor.get_tool_schemas()

            response = await self.circuit_breaker.call(
                self.retry_manager.execute_with_retry,
                self.llm_provider.invoke,
                categorize_error=self._categorize_llm_error,
                prompt="",
                system=self.session.get_system_prompt(),
                tools=tool_schemas if tool_schemas else None,
                temperature=0.7,
                conversation_history=context_messages,
            )

            return response

        except Exception as e:
            print(f"LLM invocation failed: {e}")
            raise

    async def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute tool calls.

        Args:
            tool_calls: List of tool calls from the LLM.

        Returns:
            List of tool results.
        """
        results: list[ToolResult] = []

        for tool_call in tool_calls:
            self._notify_tool_call(tool_call)

            try:
                if not self.tool_executor:
                    result = ToolResult(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        output="Tool executor not available",
                        success=False,
                        error="No tool executor configured",
                    )
                    results.append(result)
                    self._notify_tool_result(result)
                    continue

                should_confirm = self.session.should_confirm_tool(
                    tool_call.name, tool_call.risk_level.value
                )
                confirmed = self._request_confirmation(tool_call) if should_confirm else True

                if not confirmed:
                    result = ToolResult(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        output="User declined execution",
                        success=False,
                        error="User did not confirm",
                    )
                else:
                    result = await self.tool_executor.execute(tool_call)

                results.append(result)
                self._notify_tool_result(result)

            except Exception as e:
                result = ToolResult(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    output=str(e),
                    success=False,
                    error=str(e),
                )
                results.append(result)
                self._notify_tool_result(result)

        return results

    def _normalize_tool_calls(self, tool_calls: list[Any]) -> list[ToolCall]:
        """Convert provider tool calls into the core risk-aware ToolCall type."""
        return [self._normalize_tool_call(tool_call) for tool_call in tool_calls]

    def _normalize_tool_call(self, tool_call: Any) -> ToolCall:
        """Normalize a provider tool call into the core tool call representation."""
        if isinstance(tool_call, ToolCall):
            return tool_call

        return ToolCall(
            id=tool_call.id,
            name=tool_call.name,
            arguments=tool_call.arguments,
            risk_level=self._get_tool_risk(tool_call.name),
        )

    def _get_tool_risk(self, tool_name: str) -> RiskLevel:
        """Return the default risk level for a known tool."""
        return self.DEFAULT_TOOL_RISKS.get(tool_name, RiskLevel.MEDIUM)

    def _request_confirmation(self, tool_call: ToolCall) -> bool:
        """Ask the user to confirm a tool call when the session mode requires it."""
        if not self.interaction_handler:
            print(
                f"Tool '{tool_call.name}' requires confirmation "
                f"(risk: {tool_call.risk_level.value}). Auto-approving because "
                "no interaction handler is attached."
            )
            return True

        arguments = json.dumps(tool_call.arguments, default=str)
        message = (
            f"Allow {tool_call.name} (risk: {tool_call.risk_level.value}) "
            f"with arguments {arguments}?"
        )
        return self.interaction_handler.prompt_confirmation(message)

    def _notify_tool_call(self, tool_call: ToolCall) -> None:
        """Send a tool start event to the interaction handler, if present."""
        if self.interaction_handler:
            self.interaction_handler.show_tool_call(tool_call.name, tool_call.arguments)

    def _notify_tool_result(self, result: ToolResult) -> None:
        """Send a tool result event to the interaction handler, if present."""
        if self.interaction_handler:
            summary = result.error or result.output
            self.interaction_handler.show_tool_result(result.tool_name, result.success, summary)

    def _categorize_llm_error(self, exception: Exception) -> ErrorCategory:
        """Categorize LLM errors for retry logic.

        Args:
            exception: The exception.

        Returns:
            Error category.
        """
        error_str = str(exception).lower()

        if "timeout" in error_str:
            return ErrorCategory.TRANSIENT

        if "429" in error_str or "rate limit" in error_str:
            return ErrorCategory.RATE_LIMIT

        if "api_error" in error_str or "authentication" in error_str:
            return ErrorCategory.VALIDATION_ERROR

        if "unavailable" in error_str or "connection" in error_str:
            return ErrorCategory.PROVIDER_UNAVAILABLE

        return ErrorCategory.UNKNOWN


class ToolExecutor:
    """Executor for tool calls (stub for Phase 3)."""

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call.

        Args:
            tool_call: The tool call to execute.

        Returns:
            Tool result.
        """
        raise NotImplementedError("Tool executor not implemented in Phase 2")

    def get_tool_schemas(self) -> list[ToolSchema]:
        """Get available tool schemas.

        Returns:
            List of tool schemas.
        """
        return []

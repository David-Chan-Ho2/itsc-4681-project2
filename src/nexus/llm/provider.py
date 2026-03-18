"""Abstract base class for LLM providers."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from pydantic import BaseModel


class ToolSchema(BaseModel):
    """Schema for a tool available to the LLM."""

    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    """A tool call made by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str
    tool_calls: list[ToolCall] = []
    stop_reason: str = "end_turn"  # end_turn, tool_use, max_tokens, etc.
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: str, timeout: float = 30.0):
        """Initialize provider.

        Args:
            model: Model name/identifier.
            timeout: Request timeout in seconds.
        """
        self.model = model
        self.timeout = timeout

    @abstractmethod
    async def invoke(
        self,
        prompt: str,
        system: Optional[str] = None,
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> LLMResponse:
        """Invoke the LLM with a prompt.

        Args:
            prompt: The user's prompt/query.
            system: System prompt/instructions.
            tools: Available tools the LLM can call.
            temperature: Sampling temperature (higher = more diverse).
            max_tokens: Maximum response tokens.
            conversation_history: Previous messages for context.

        Returns:
            LLMResponse with content, tool calls, and metadata.

        Raises:
            TimeoutError: If request times out.
            ValueError: If invalid parameters.
            Exception: Provider-specific errors.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available.

        Returns:
            True if provider is healthy, False otherwise.
        """
        pass

    def convert_tool_schema(self, tools: list[ToolSchema]) -> Any:
        """Convert tool schemas to provider-specific format.

        Args:
            tools: Generic tool schemas.

        Returns:
            Provider-specific tool format.
        """
        # Override in subclasses if needed
        return tools

    def extract_tool_calls(self, response: Any) -> list[ToolCall]:
        """Extract tool calls from provider response.

        Args:
            response: Raw provider response.

        Returns:
            List of tool calls.
        """
        # Override in subclasses
        return []

    async def __call__(
        self,
        prompt: str,
        system: Optional[str] = None,
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Allow provider to be called directly."""
        return await self.invoke(
            prompt=prompt,
            system=system,
            tools=tools,
            temperature=temperature,
        )

"""Terminal REPL interface for NEXUS."""

import json
import time
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from nexus.core.session import SessionContext
from nexus.core.types import ExecutionMode

console = Console()


class REPLInterface:
    """Terminal-based REPL for user interaction."""

    def __init__(self):
        """Initialize the REPL interface."""
        self.session: Optional[SessionContext] = None
        self.running = False
        self.agent = None

    def set_agent(self, agent) -> None:
        """Attach an agent to the REPL."""
        self.agent = agent
        if hasattr(agent, "set_interaction_handler"):
            agent.set_interaction_handler(self)

    def start_session(
        self,
        session_id: Optional[str] = None,
        execution_mode: ExecutionMode = ExecutionMode.AUTO,
        existing_session: Optional[SessionContext] = None,
    ) -> SessionContext:
        """Start or resume a session."""
        if existing_session:
            self.session = existing_session
            self.session.set_execution_mode(execution_mode)
        else:
            self.session = SessionContext(
                session_id=session_id,
                execution_mode=execution_mode,
            )

        self._print_welcome()
        return self.session

    def _print_welcome(self) -> None:
        """Print welcome message."""
        if not self.session:
            return

        panel = Panel.fit(
            (
                "NEXUS - Autonomous Code Assistant\n"
                "Neural Executive Xperiment for Unified Software automation\n\n"
                f"Session: {self.session.session_id[:8]}\n"
                "Type /help for commands, then describe the coding task."
            ),
            border_style="cyan",
            title="Ready",
        )
        console.print(panel)

    async def run_loop(self) -> None:
        """Run the main REPL loop."""
        if not self.session:
            console.print("[red]Error: No session started[/red]")
            return

        if self.agent and getattr(self.agent, "tool_executor", None):
            if hasattr(self.agent.tool_executor, "initialize"):
                console.print("[dim]Initializing MCP tools...[/dim]")
                await self.agent.tool_executor.initialize()

        self.running = True
        try:
            while self.running:
                try:
                    user_input = console.input("\n[bold cyan]> You:[/bold cyan] ").strip()

                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        await self._handle_command(user_input)
                        continue

                    if self.agent:
                        result = await self.agent.execute(user_input)
                        if result.success:
                            self.stream_response(result.final_response or result.message)
                        else:
                            self.show_error(result.error or result.message)
                    else:
                        self.session.add_user_message(user_input)
                        console.print("\n[dim][No agent connected][/dim]")

                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrupted. Type /exit to quit cleanly.[/yellow]")

        except EOFError:
            console.print("\n[yellow]Exiting NEXUS...[/yellow]")
            self.running = False

    async def _handle_command(self, command: str) -> None:
        """Handle a command typed into the REPL."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            self._show_help()
        elif cmd == "/exit":
            self.running = False
            console.print("[yellow]Exiting NEXUS. Goodbye![/yellow]")
        elif cmd == "/clear":
            self._clear_history()
        elif cmd == "/history":
            self._show_history()
        elif cmd == "/mode":
            self._set_mode(arg)
        elif cmd == "/context":
            self._show_context()
        elif cmd == "/status":
            self._show_status()
        elif cmd == "/tools":
            self._show_tools()
        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
            console.print("Type [bold]/help[/bold] for available commands.")

    def _show_help(self) -> None:
        """Show help message."""
        help_text = """
# NEXUS Commands

## Execution
- **Type your task** - Give a natural language coding instruction

## Session Management
- `/clear` - Clear conversation history
- `/history` - Show recent conversation history
- `/context` - Show the current context window
- `/status` - Show session status

## Settings
- `/mode [auto|manual|confirmation]` - Change execution mode
- `/tools` - List the currently available MCP tools

## Utility
- `/help` - Show this help message
- `/exit` - Exit NEXUS
"""
        console.print(Markdown(help_text))

    def _clear_history(self) -> None:
        """Clear conversation history."""
        if self.session:
            msg_count = len(self.session.messages)
            self.session.messages = []
            self.session.reset_iteration()
            console.print(f"[green]Cleared {msg_count} messages from history.[/green]")

    def _show_history(self) -> None:
        """Show conversation history."""
        if not self.session or not self.session.messages:
            console.print("[yellow]No messages in history yet.[/yellow]")
            return

        console.print("\n[bold]Conversation History[/bold]")
        console.print(
            f"[dim]Showing the last {min(len(self.session.messages), 10)} messages[/dim]\n"
        )

        for message in self.session.messages[-10:]:
            if message.role.value == "user":
                console.print(f"[bold cyan]> You:[/bold cyan] {message.content}")
            elif message.role.value == "assistant":
                console.print(f"[bold green]NEXUS:[/bold green] {message.content}")
                if message.tool_calls:
                    console.print(
                        f"[dim]  Used {len(message.tool_calls)} tool(s) in this turn.[/dim]"
                    )

    def _set_mode(self, mode_str: str) -> None:
        """Set execution mode."""
        if not self.session:
            return

        mode_map = {
            "auto": ExecutionMode.AUTO,
            "manual": ExecutionMode.MANUAL,
            "confirmation": ExecutionMode.CONFIRMATION,
        }

        mode = mode_map.get(mode_str.lower())
        if mode:
            self.session.set_execution_mode(mode)
            console.print(f"[green]Execution mode set to [bold]{mode.value}[/bold].[/green]")
        else:
            console.print(f"[red]Invalid mode: {mode_str}[/red]")
            console.print("Available modes: auto, manual, confirmation")

    def _show_context(self) -> None:
        """Show current context window."""
        if not self.session:
            return

        context_msgs = self.session.get_context_messages()
        console.print(f"\n[bold]Context Window ({len(context_msgs)} messages)[/bold]\n")

        for msg in context_msgs:
            role_label = "> You" if msg.role.value == "user" else "NEXUS"
            color = "cyan" if msg.role.value == "user" else "green"
            console.print(f"[{color}]{role_label}[/{color}]")
            preview = msg.content[:100]
            suffix = "..." if len(msg.content) > 100 else ""
            console.print(f"  {preview}{suffix}")
            console.print()

    def _show_status(self) -> None:
        """Show session status."""
        if not self.session:
            return

        meta = self.session.metadata
        console.print("\n[bold]Session Status[/bold]\n")
        console.print(f"Session ID: [cyan]{meta.session_id}[/cyan]")
        console.print(f"Created: {meta.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"Updated: {meta.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"Mode: [bold]{meta.execution_mode.value}[/bold]")
        console.print(f"LLM: {meta.llm_model}")
        console.print(f"Messages: {len(self.session.messages)}")
        console.print(f"Tool calls: {meta.tool_calls_count}")
        console.print(f"Iterations: {self.session.iteration_count}/{self.session.max_iterations}")
        console.print()

    def _show_tools(self) -> None:
        """Show available MCP tools discovered by the executor."""
        if not self.agent or not getattr(self.agent, "tool_executor", None):
            console.print("[yellow]No tool executor is attached yet.[/yellow]")
            return

        schemas = self.agent.tool_executor.get_tool_schemas()
        if not schemas:
            console.print(
                "[yellow]No tools have been discovered yet. Start the loop first.[/yellow]"
            )
            return

        console.print("\n[bold]Available Tools[/bold]\n")
        for schema in schemas:
            console.print(f"[cyan]{schema.name}[/cyan] - {schema.description}")

    def stream_response(self, response: str) -> None:
        """Render the assistant response incrementally in the terminal."""
        console.print("\n[bold green]NEXUS:[/bold green] ", end="")
        for chunk in self._response_chunks(response):
            console.print(chunk, end="", highlight=False, soft_wrap=True)
            time.sleep(0.005)
        console.print()

    def _response_chunks(self, response: str, chunk_size: int = 24) -> list[str]:
        """Split a response into small pieces for terminal streaming."""
        return [response[index : index + chunk_size] for index in range(0, len(response), chunk_size)]

    def show_tool_call(self, tool_name: str, arguments: dict) -> None:
        """Show that a tool is being called."""
        pretty_args = json.dumps(arguments, indent=2, default=str)
        console.print(f"\n[bold blue]Tool[/bold blue] [cyan]{tool_name}[/cyan]")
        console.print(Panel(pretty_args, border_style="blue", title="Arguments"))

    def show_tool_result(self, tool_name: str, success: bool, output: str) -> None:
        """Show a tool execution result."""
        status = "[green]SUCCESS[/green]" if success else "[red]FAILED[/red]"
        preview = output[:400]
        suffix = "..." if len(output) > 400 else ""
        console.print(f"{status} {tool_name}")
        console.print(f"[dim]{preview}{suffix}[/dim]")

    def prompt_confirmation(self, message: str) -> bool:
        """Prompt for user confirmation."""
        console.print(f"[yellow]{message}[/yellow]")
        return typer.confirm("Proceed?", default=False)

    def show_error(self, error_message: str) -> None:
        """Show an error message."""
        console.print(f"[red]Error: {error_message}[/red]")


def create_repl() -> REPLInterface:
    """Create a REPL interface instance."""
    return REPLInterface()

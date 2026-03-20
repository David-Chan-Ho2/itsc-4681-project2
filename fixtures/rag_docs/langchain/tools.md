# LangChain Tools

Tools are callable actions exposed to an agent. Each tool should include a clear name, description, and argument schema so the model can decide when and how to use it.

Good tool design matters because vague descriptions make it harder for the model to select the right action. For coding assistants, typical tools include file reads, file writes, shell commands, and documentation lookup.

Tool execution should be observable in the user interface so the developer can trust what the agent is doing.

# LangChain Agents

LangChain agents decide which tools to call based on the user request and the intermediate observations they receive back from the runtime.

Agents are useful when a workflow cannot be expressed as a single deterministic chain. They combine model reasoning, tool invocation, and iteration.

A common pattern is:

1. read the user goal
2. choose a tool
3. observe the tool result
4. decide whether to stop or continue

This makes agents a strong fit for coding assistants, especially when filesystem access and documentation retrieval are involved.

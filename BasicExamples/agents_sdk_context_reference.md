# OpenAI Agents SDK: `RunContextWrapper` & `AgentHookContext`

This document describes **what lives inside** the context objects you receive in tools, `handoff(..., on_handoff=...)` callbacks, and hook methods. It is based on the installed `agents` package (`run_context.py`, `usage.py`).

**Important:** Context objects are **not sent to the LLM**. They are for **your code**: tools, hooks, and handoff callbacks—dependency injection and bookkeeping.

---

## 1. `RunContextWrapper[TContext]`

Defined in `agents.run_context`. A **generic** wrapper: `TContext` is the type of **your** `context` object (often a Pydantic model or a plain dict) that you pass into `Runner.run(..., context=RunContextWrapper(...))`.

### 1.1 Public fields (attributes you read/write)

| Attribute | Type | Meaning |
|-----------|------|---------|
| **`context`** | `TContext` | **Your** application state. Whatever you wrapped when creating `RunContextWrapper(context=...)`. Tools and hooks can read/update it (e.g. `ctx.context.status = "done"`). |
| **`usage`** | `Usage` | Running totals for the **agent run** so far (tokens, request counts). Updated by the SDK as turns complete. For streaming, values may lag until the stream finishes. |
| **`turn_input`** | `list[TResponseInputItem]` | Conversation / input items for the **current turn**, as the SDK sees them (OpenAI Responses-style items). Useful for advanced logging; shape follows the SDK’s input item types. |
| **`tool_input`** | `Any \| None` | When the run is inside an **agent-as-tool** or structured tool-input path, this holds the **structured input** for that tool run; otherwise often `None`. |

### 1.2 “Private” but present on the instance

| Attribute | Notes |
|-----------|--------|
| **`_approvals`** | Internal dict backing tool **approval** state. **Do not use directly.** Use the public methods below. |

### 1.3 Public methods (tool approval flow)

Used when tools require human approval (when you wire approval into your run):

- **`is_tool_approved(tool_name, call_id) -> bool | None`**
- **`get_approval_status(...)`** — resolves keys/namespaces; returns approval status.
- **`get_rejection_message(...)`** — message if a call was rejected.
- **`approve_tool(approval_item, always_approve=False)`**
- **`reject_tool(approval_item, always_reject=False, rejection_message=None)`**

For a minimal demo without approvals, you rarely touch these.

---

## 2. `Usage` (inside `wrapper.usage`)

From `agents.usage`. Typical fields you log in hooks:

| Field | Meaning |
|-------|--------|
| **`requests`** | Number of LLM API requests aggregated into this usage object. |
| **`input_tokens`**, **`output_tokens`**, **`total_tokens`** | Aggregated token counts. |
| **`input_tokens_details`**, **`output_tokens_details`** | Nested details (e.g. cached input tokens, reasoning output tokens)—provider-dependent. |
| **`request_usage_entries`** | `list[RequestUsage]` — per-request breakdown when the SDK records it (good for cost / window analysis). |
| **`add(other: Usage)`** | Mutates this usage by adding another `Usage` (used internally; you mostly **read** fields in hooks). |

---

## 3. `AgentHookContext[TContext]`

Also in `agents.run_context`:

```python
class AgentHookContext(RunContextWrapper[TContext]):
    """Context passed to agent hooks (on_start, on_end)."""
```

There are **no extra fields** on `AgentHookContext`—it **inherits everything** from `RunContextWrapper`.

**Naming:** The SDK does **not** define a type called `AgentContext`. The hook type for `on_start` / `on_end` on **`AgentHooks`** is **`AgentHookContext`**, which is a **subclass** of `RunContextWrapper`, so you can use **`context.context`**, **`context.usage`**, **`context.turn_input`**, etc., the same way.

---

## 4. Where each type appears (what you can access)

### 4.1 `AgentHooks` (per-agent, `Agent(..., hooks=...)`)

| Hook | First argument type | What you can use |
|------|---------------------|------------------|
| `on_start` | **`AgentHookContext`** | `context.context`, `usage`, `turn_input`, `tool_input`, approval APIs. |
| `on_end` | **`AgentHookContext`** | Same as above; **`usage`** is commonly read here for token totals after the agent’s work. |
| `on_handoff` | **`RunContextWrapper`** | Same fields (receiver’s wrapper during handoff). |
| `on_tool_start` / `on_tool_end` | **`RunContextWrapper`** | Same. |
| `on_llm_start` / `on_llm_end` | **`RunContextWrapper`** | Same. |

So: for **agent start/end**, the type is explicitly **`AgentHookContext`** (still a `RunContextWrapper` under the hood).

### 4.2 `RunHooks` (`Runner.run(..., hooks=...)`)

| Hook | Context type | Same accessible fields |
|------|----------------|------------------------|
| `on_agent_start` / `on_agent_end` | **`AgentHookContext`** | `context`, `usage`, `turn_input`, … |
| `on_handoff` | **`RunContextWrapper`** | Same. |
| `on_tool_start` / `on_tool_end` | **`RunContextWrapper`** | Same. |
| `on_llm_start` / `on_llm_end` | **`RunContextWrapper`** | Same (plus LLM-specific args on those methods). |

### 4.3 `@function_tool` and `handoff(on_handoff=...)`

| Callback | Typical first arg | Access |
|----------|-------------------|--------|
| Tool with `RunContextWrapper` as first parameter | **`RunContextWrapper`** | `ctx.context`, `ctx.usage`, … |
| `on_handoff(ctx, input_data)` | **`RunContextWrapper`** | Same; use **`ctx.context`** to update shared app state. |

---

## 5. Quick mental model

```
Runner.run(..., context=RunContextWrapper(context=my_app_state))
                         │
                         ▼
              ┌──────────────────────┐
              │  RunContextWrapper    │
              │  .context  ← your T   │
              │  .usage    ← Usage      │
              │  .turn_input            │
              │  .tool_input            │
              │  + approval helpers     │
              └──────────┬─────────────┘
                         │ subclass
                         ▼
              ┌──────────────────────┐
              │  AgentHookContext     │  ← only used for AgentHooks.on_start / on_end
              │  (same fields)        │
              └──────────────────────┘
```

---

## 6. Version note

Field names and hook signatures follow the **`agents`** package installed in your environment. If you upgrade the package, re-check `agents/run_context.py` for any new fields or methods.

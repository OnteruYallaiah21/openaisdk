
---

# AI Agent Guardrails: Technical Documentation

## 1. Overview
Guardrails are safety and validation mechanisms that act as **tripwires**. They monitor the flow of information into and out of an agent. If a guardrail "triggers," it halts execution immediately to prevent unsafe or irrelevant processing.

## 2. Core Components
| Class / Attribute | Purpose |
| :--- | :--- |
| **`GuardrailFunctionOutput`** | The return object of any guardrail. Contains `tripwire_triggered` (bool). |
| **`InputGuardrail`** | Checks performed on user input **before or during** agent execution. |
| **`OutputGuardrail`** | Checks performed on the agent's response **after** it is generated. |
| **`output_info`** | A metadata field (Any) used to store granular results or logs about the check. |

---

## 3. Input Guardrails: Execution Modes
The system provides two ways to run input checks. Choosing the right one depends on your resource and latency requirements.

### A. Parallel Execution (Default)
* **Setting:** `@input_guardrail(run_in_parallel=True)`
* **Behavior:** The guardrail and the Agent start at the **same time**.
* **Best For:** Network-bound tasks (API calls, external safety services).
* **Trade-off:** * **Pro:** Lowest latency; the user doesn't wait for the guardrail to finish before the agent starts.
    * **Con:** If the guardrail triggers, any compute/tokens used by the agent in that time are **wasted**.

### B. Sequential Execution (Gatekeeper)
* **Setting:** `@input_guardrail(run_in_parallel=False)`
* **Behavior:** The guardrail must return a "Pass" **before** the agent is allowed to start.
* **Best For:** CPU-bound tasks (Regex, local keyword filtering, complex math validation).
* **Trade-off:**
    * **Pro:** **Cost-efficient**. It prevents expensive Agent/LLM calls if the input is already invalid.
    * **Con:** Higher latency; the total response time is `Guardrail Time + Agent Time`.

---

## 4. Implementation Reference

### Input Guardrail Example
```python
@input_guardrail(name="sensitive_data_filter", run_in_parallel=False)
def filter_pii(context, agent, user_input):
    # Perform CPU-heavy regex check
    has_pii = "123-45-678" in user_input 
    
    return GuardrailFunctionOutput(
        tripwire_triggered=has_pii,
        output_info={"reason": "PII detected"} if has_pii else None
    )
```

### Output Guardrail Example
```python
@output_guardrail(name="format_checker")
async def check_json_format(context, agent, agent_output):
    # Ensure the agent actually returned valid JSON
    is_valid = validate_json(agent_output)
    
    return GuardrailFunctionOutput(
        tripwire_triggered=not is_valid,
        output_info="Invalid JSON format in response"
    )
```

---

## 5. Key Observations for Your Notes
* **Tripwire Exception:** When `tripwire_triggered` is `True`, the system raises an `InputGuardrailTripwireTriggered` or `OutputGuardrailTripwireTriggered` exception.
* **Naming:** Use the `name` parameter in decorators for better tracing in logs; otherwise, it defaults to the function name.
* **Flexibility:** Guardrails can be either **Sync** or **Async**; the system handles the `await` logic automatically based on the function type.




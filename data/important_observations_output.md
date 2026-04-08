Here’s a clean, structured Markdown note file based on your execution logs and observations:

---

# 🧠 Agent Execution Notes (Deterministic Behavior + Guardrails)

## 1. RunContextWrapper Behavior

1. **Initial Context is Empty**

   * `context=None`, `turn_input=[]`, `usage=0`
   * ➤ The context is initialized fresh for every run unless explicitly persisted.
   * ⚠️ Trade-off: Stateless by default → safer but no memory retention.

2. **turn_input gets populated before LLM call**

   * Contains user message: `{'role': 'user', 'content': ...}`
   * ➤ This is the actual payload sent to the LLM.
   * ⚠️ Important: Any preprocessing must happen before this stage.

3. **Usage Metrics Update After LLM Call**

   * Tokens tracked: `input_tokens`, `output_tokens`, `reasoning_tokens`
   * ➤ Useful for cost + performance monitoring.
   * ⚠️ Trade-off: Extra logging overhead but critical for optimization.

---

## 2. Input Guardrails Execution

4. **Multiple Guardrails Supported**

   * Example:

     * `user_inpout_check`
     * `llm_user_input_guraddrail`
   * ➤ Enables layered validation.

5. **Parallel Execution by Default**

   * `run_in_parallel=True`
   * ➤ Improves speed when multiple guardrails exist.
   * ⚠️ Trade-off: Higher CPU usage.

6. **Sequential Execution Control**

   * `run_in_parallel=False`
   * ➤ Ensures deterministic order.
   * ⚠️ Trade-off: Slight latency increase.

7. **Guardrail Output Structure**

   * Returns:

     * `tripwire_triggered=False`
     * `output_info=None`
   * ➤ Acts like a validation checkpoint.

8. **LLM-based Guardrail Adds Token Cost**

   * `llm_user_input_guraddrail` makes an LLM call
   * ➤ Improves semantic validation.
   * ⚠️ Trade-off: Extra latency + cost.

---

## 3. Agent Configuration

9. **Agent Instructions Drive Output**

   * `"Extract item name, value, damage description"`
   * ➤ Strongly influences structured output.

10. **No Tools Used**

* `tools=[]`
* ➤ Pure LLM-based processing.
* ⚠️ Trade-off: No external validation or enrichment.

11. **Model Settings Default to None**

* `temperature=None`, `top_p=None`
* ➤ Uses model defaults.
* ⚠️ Recommendation: Set explicitly for deterministic behavior.

12. **tool_use_behavior = 'run_llm_again'**

* ➤ If tools exist, LLM re-runs after tool execution.
* ⚠️ Not relevant here but important for tool pipelines.

---

## 4. LLM Execution Flow

13. **Guardrail Runs Before Main LLM**

* Input → Guardrail → LLM
* ➤ Ensures safe and clean input.

14. **LLM Produces Structured Markdown Output**

* Table + summary format
* ➤ Good for readability and downstream parsing.

15. **Raw Response Stored Separately**

* Stored in `raw_responses`
* ➤ Useful for debugging and replay.

---

## 5. RunResult Object Insights

16. **final_output Contains Clean Result**

* ➤ Ready for downstream usage.

17. **new_items Stores Response Objects**

* ➤ Tracks incremental outputs.

18. **input_guardrail_results Captured**

* ➤ Helps debug validation issues.

19. **No Interruptions**

* `interruptions=[]`
* ➤ Flow executed smoothly.

---

## 6. Business Logic Layer (Post-LLM)

20. **Triage Decision Logic**

* `Risk: Low → Claim Approved`
* ➤ Deterministic rule-based decision after LLM.

21. **Separation of Concerns**

* LLM → Extraction
* Backend → Decision
* ➤ Best practice for reliability.

---

## 7. Output Document Generation

22. **Dynamic Document Creation**

* Uses extracted fields:

  * Item
  * Value
  * Damage
* ➤ Clean template-based generation.

23. **No Hallucination Risk in Final Step**

* ➤ Uses structured data, not raw LLM text.

24. **Deterministic Refund Logic**

* Refund = `$250`
* ➤ Direct mapping from extracted value.

---

## 8. Key Design Patterns Observed

25. **LLM for Extraction Only**

* ➤ Keeps LLM role minimal and controlled.

26. **Guardrails for Safety + Validation**

* ➤ Prevents bad input propagation.

27. **Backend Logic for Decisions**

* ➤ Avoids relying on LLM reasoning for critical steps.

28. **Structured Output → Template Rendering**

* ➤ Enables automation (documents, emails, etc.)

---

## 9. Important Defaults to Remember

29. **Context is Stateless by Default**
30. **Guardrails run in parallel unless disabled**
31. **Model settings are unset unless specified**
32. **No tool execution unless explicitly configured**
33. **LLM output stored in multiple layers (final_output, raw_responses)**

---

## 10. Optimization Opportunities

34. **Reduce LLM Guardrail Calls**

* ➤ Replace with rule-based checks if possible.

35. **Set Deterministic Parameters**

* Example:

  * `temperature=0`
* ➤ Ensures consistent outputs.

36. **Add Output Guardrails**

* ➤ Validate LLM output before business logic.

37. **Enable Context Persistence**

* ➤ For multi-turn workflows.

---

## 🔑 Key Takeaways

* Use LLMs **only where needed (extraction, NLP tasks)**
* Keep **decision-making deterministic (backend logic)**
* Guardrails are powerful but **can increase cost if overused**
* Always monitor **token usage for scalability**
* Structure outputs early → makes automation easier

---

If you want, I can next convert this into a **reusable template for all your agent experiments** or align it with your **resume analyzer / multi-agent system design**.

# Agents SDK Execution Flow with Guardrails

## Flow Diagram

```mermaid
graph TD
    User([User Input]) -->|1. Intercept| Guard{Step 1: Input Guardrail}
    
    Guard -->|tripwire_triggered=True| Abort[STOP: Raise Exception]
    Guard -->|tripwire_triggered=False| Init[Step 2: Dynamic Init]

    Init -->|Inject RunContextWrapper| LLM{Step 3: LLM Brain}

    LLM -->|Call Tool| Tool[Step 4: Python Function]
    Tool -->|Return Result| LLM
    
    LLM -->|Handoff| NewAgent[Switch Active Agent]
    NewAgent -->|Restart Flow| Guard

    LLM -->|Produce Response| Validate{Step 5: Output Validation}
    Validate -->|Schema PASS| End([User Receives Output])
    Validate -->|Schema FAIL| Retry[Retry/Error Handling]

    style Guard fill:#f96,stroke:#333,stroke-width:2px
    style LLM fill:#bbf,stroke:#333
    style Abort fill:#f66,stroke:#000
    style End fill:#9f9,stroke:#333
    style Retry fill:#ff9,stroke:#333
    style Tool fill:#9cf,stroke:#333
    style NewAgent fill:#9cf,stroke:#333
    style Validate fill:#fc9,stroke:#333
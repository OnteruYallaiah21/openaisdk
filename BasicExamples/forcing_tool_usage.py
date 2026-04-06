from __future__ import annotations

import asyncio
import time
from typing import Any, Literal
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime
import sys

# ------------------ MODEL CONFIG ------------------
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

try:
    from llm_model_config.llm_model_config import ModelSingleton
    model = ModelSingleton.get_instance()
    print(f"✅ [debug-control {Path(__file__).name}] Model loaded from config")
except ImportError:
    model = None
    print(f"⚠️ [debug-control {Path(__file__).name}] Model config not found, using None")

# ------------------ AGENT IMPORTS ------------------
from agents import (
    Agent,
    FunctionToolResult,
    ModelSettings,
    RunContextWrapper,
    Runner,
    ToolsToFinalOutputFunction,
    ToolsToFinalOutputResult,
    function_tool,
)

# ------------------ DATA MODELS ------------------
class LeaveBalance(BaseModel):
    employee_id: str
    remaining_leaves: int
    last_updated: datetime

# ------------------ TOOLS ------------------
@function_tool
def HRDatabaseTool(employee_id: str) -> LeaveBalance:
    """
    Dummy HR database tool.
    In a real system, this would query the HR database for leave balances.
    """
    print(f"[debug-control {Path(__file__).name}] HRDatabaseTool called for employee_id={employee_id}")
    time.sleep(0.5)  # simulate database latency
    return LeaveBalance(
        employee_id=employee_id,
        remaining_leaves=12,
        last_updated=datetime.now(),
    )

# ------------------ CUSTOM TOOL USAGE ------------------
async def custom_tool_use_behavior(
    context: RunContextWrapper[Any], results: list[FunctionToolResult]
) -> ToolsToFinalOutputResult:
    """
    Always uses the tool result to generate the final output.
    Enforces tool usage: AI cannot bypass the database.
    """
    print(f"[debug-control {Path(__file__).name}] custom_tool_use_behavior called")
    tool_result: LeaveBalance = results[0].output
    final_response = (
        f"Employee {tool_result.employee_id} has {tool_result.remaining_leaves} leaves remaining "
        f"(last updated: {tool_result.last_updated.strftime('%Y-%m-%d %H:%M:%S')})."
    )
    return ToolsToFinalOutputResult(
        is_final_output=True,
        final_output=final_response
    )

# ------------------ AGENT EXECUTION ------------------
async def run_hr_agent(employee_id: str, tool_use_behavior: Literal["default", "first_tool", "custom"] = "custom"):
    """
    Runs the HR agent to check leave balances.
    Uses RunContextWrapper for tracking and debugging.
    """
    start_time = time.time()

    if tool_use_behavior == "default":
        behavior: Literal["run_llm_again", "stop_on_first_tool"] | ToolsToFinalOutputFunction = "run_llm_again"
    elif tool_use_behavior == "first_tool":
        behavior = "stop_on_first_tool"
    else:
        behavior = custom_tool_use_behavior

    agent = Agent(
        name="HR Leave Balance Agent",
        instructions="You are a corporate HR assistant. You must always fetch leave balances from the HR database tool.",
        tools=[HRDatabaseTool],
        tool_use_behavior=behavior,
        model_settings=ModelSettings(tool_choice="required"),
        model=model,
    )

    # Wrap agent for observation and token tracking
    run_context = RunContextWrapper(agent)
    print(f"[debug-control {Path(__file__).name}] Starting agent run for employee_id={employee_id}")

    # Execute agent normally via Runner.run()
    result = await Runner.run(agent, input=f"Check leave balance for employee {employee_id}")

    end_time = time.time()
    print(f"[debug-control {Path(__file__).name}] Agent run completed in {end_time - start_time:.2f} seconds")
    print(f"[debug-control {Path(__file__).name}] Final output:\n{result.final_output}\n")

# ------------------ DEMO / CLI ------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--employee_id", type=str, help="Employee ID to check leave balance")
    parser.add_argument(
        "--behavior",
        type=str,
        default="custom",
        choices=["default", "first_tool", "custom"],
        help="Tool use behavior for the agent"
    )
    args = parser.parse_args()

    # Interactive fallback if employee_id not provided
    if not args.employee_id:
        print("Please type your question (e.g., 'Check leave balance for employee E12345'):")
        user_input = input(">> ")
        # naive parsing: extract last word as employee_id
        employee_id = user_input.strip().split()[-1]
        print(f"[debug-control {Path(__file__).name}] Parsed employee_id='{employee_id}' from input")
    else:
        employee_id = args.employee_id

    asyncio.run(run_hr_agent(employee_id, args.behavior))

"""
================== SAMPLE USE CASES ==================

# Example 1:
Command line:
$ python forcing_tool_usage.py --employee_id E12345
Output:
Employee E12345 has 12 leaves remaining (last updated: 2026-04-05 17:45:12).

# Example 2:
Interactive input:
$ python forcing_tool_usage.py
Please type your question:
>> Check leave balance for employee E67890
Parsed employee_id='E67890' from input
Employee E67890 has 12 leaves remaining (last updated: 2026-04-05 17:46:05).

Observations / Learnings:
- Only the HRDatabaseTool is used to fetch leave balances.
- Direct AI responses without tool are prevented via tool_choice="required".
- Debug prints show execution progress using just the filename.
- RunContextWrapper can track agent execution and tokens for analysis.
- Agent enforces business rules: accurate leave data, compliance, and tool usage.

"""
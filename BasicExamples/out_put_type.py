import os
import asyncio
import json
from pathlib import Path

from dataclasses import dataclass
from typing import Any
from pydantic import TypeAdapter

from agents import Agent, AgentOutputSchema, AgentOutputSchemaBase, Runner

# Setup model (Assuming your ModelSingleton is configured)
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()

@dataclass
class OutputType:
    # LLMs prefer string keys. 
    # Use dict[str, str] to avoid 'int_parsing' errors.
    jokes: dict[str, str]

class CustomOutputSchema(AgentOutputSchemaBase):
    def is_plain_text(self) -> bool:
        return False

    def name(self) -> str:
        return "CustomJokeSchema"

    def json_schema(self) -> dict[str, Any]:
        # Simple schema that matches the expected output
        return {
            "type": "object",
            "properties": {
                "jokes": {
                    "type": "object",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["jokes"]
        }

    def is_strict_json_schema(self) -> bool:
        return False

    def validate_json(self, json_str: str) -> Any:
        data = json.loads(json_str)
        # Ensure we look inside the 'response' wrapper if the SDK adds it
        actual_data = data.get("response", data)
        return list(actual_data["jokes"].values())

async def main():
    # 1. This will fail if OutputType isn't "Strict Compatible" 
    # (OpenAI strict mode doesn't like some dict configurations)
    agent = Agent(
        name="Assistant",
        instructions="Return 3 jokes in the specified format.",
        model=model,
        output_type=OutputType,
    )

    input_text = "Tell me 3 short jokes."

    print("--- Strategy 1: Non-Strict AgentOutputSchema ---")
    # Wrap with strict_json_schema=False to allow more flexible JSON
    agent.output_type = AgentOutputSchema(OutputType, strict_json_schema=False)
    try:
        result = await Runner.run(agent, input_text)
        print(f"Result: {result.final_output}")
    except Exception as e:
        print(f"Error in Strategy 1: {e}")

    print("\n--- Strategy 2: Custom Output Schema ---")
    agent.output_type = CustomOutputSchema()
    try:
        result = await Runner.run(agent, input_text)
        print(f"Result (List of jokes): {result.final_output}")
    except Exception as e:
        print(f"Error in Strategy 2: {e}")

if __name__ == "__main__":
    asyncio.run(main())
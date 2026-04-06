import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# workspace root (parent of this file's folder)
rootpath = Path(__file__).resolve().parent.parent
sys.path.append(str(rootpath))

from llm_model_config.llm_model_config import ModelSingleton
from agents import Agent, Runner, RunContextWrapper

model = ModelSingleton.get_instance()


class CustomContext(BaseModel):
    style: Literal["formal", "casual", "veryformal"] = Field(
        description="The style of the response"
    )


def custom_Instructions(run_context: RunContextWrapper[CustomContext], agent: Agent[CustomContext]) -> str:
    """Load a style-based instruction from the prompt registry at the workspace root.

    Behavior:
    - Looks for versions under `<workspace_root>/prompt_registry/custom_instructions`.
    - Loads the latest `vN.json` file (highest N).
    - Reads the `styles` mapping and returns the value for the current context style.
    - Falls back to a `default` entry or a generated instruction if not found.
    """
    context = run_context.context
    print(f"[DEBUG] Agent: {agent.name}")
    print(f"the instructions are==>> {agent.instructions}")
    print(f"[DEBUG] Full wrapper: {run_context}")
    print(f"[DEBUG] Context: {context}")

    registry_dir = rootpath / "prompt_registry" / "custom_instructions"
    registry_dir.mkdir(parents=True, exist_ok=True)

    def _find_latest_version_file() -> Path | None:
        files = list(registry_dir.glob("v*.json"))
        if not files:
            return None

        def _vernum(p: Path) -> int:
            try:
                return int(p.stem.lstrip("vV"))
            except Exception:
                return 0

        files.sort(key=_vernum, reverse=True)
        return files[0]

    latest = _find_latest_version_file()

    if latest is None:
        default = {
            "version": 1,
            "description": "Default custom_instructions mapping.",
            "styles": {
                "formal": "Please respond in a formal tone.",
                "casual": "Please respond in a casual tone.",
                "veryformal": "Please respond in a very formal tone.",
            },
            "default": "Please respond in a clear and helpful tone.",
            "guidelines": [
                "Be concise",
                "Use appropriate tone",
                "Avoid slang unless requested",
            ],
        }
        out = registry_dir / "v1.json"
        out.write_text(json.dumps(default, indent=2), encoding="utf-8")
        latest = out

    try:
        prompt_def = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Failed to load prompt definition {latest}: {e}")
        prompt_def = {}

    styles_map = prompt_def.get("styles", {}) if isinstance(prompt_def, dict) else {}
    instruction = styles_map.get(context.style)

    if instruction is None:
        instruction = prompt_def.get("default") if isinstance(prompt_def, dict) else None
    if instruction is None:
        tone = getattr(context, "style", "neutral")
        instruction = f"Please respond in a {tone} tone, be concise and helpful."

    print(f"[DEBUG] Returning instruction (from {latest.name}): {instruction}")
    return instruction


agent = Agent(name="Custom Context Agent", instructions=custom_Instructions, model=model)


async def main():
    style = random.choice(["formal", "casual", "veryformal", "funny", "serious", "sarcastic"])
    context = CustomContext(style=style)
    print("***************the context is==>> ", context)
    print("****************I am just dummy response to check the context wrapper functionality****************")
    result = await Runner.run(agent, "how to do you feel now if your are human?", context=context)
    print(f"Context style: {style}")
    print(f"Agent response: {result.final_output}")


if __name__ == "__main__":
    print(f"I am inside file called => {Path(__file__).resolve()}")
    asyncio.run(main())
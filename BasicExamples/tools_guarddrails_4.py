import asyncio
import json
import sys
import os
from pathlib import Path
root_path= Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
from pydantic import BaseModel, Field
from typing import Annotated
from agents import (Agent, Runner,ToolGuardrailFunctionOutput, ToolInputGuardrailData, ToolOutputGuardrailData, ToolOutputGuardrailTripwireTriggered, function_tool, tool_input_guardrail, tool_output_guardrail)

@function_tool
def send_whatsapp_message(to:Annotated[str, Field(description="Phone number to send the message to")], message: Annotated[str, Field(description="Message content to send")]) -> str:
    """Send a WhatsApp message to the specified recipient."""
    print("******************************I am inside send_whatsapp_message *******************************")
    print(f"Simulating sending WhatsApp message to {to} with content '{message}'")
    return f"WhatsApp message sent to {to} with content '{message}'"

@tool_input_guardrail
def reject_sensitive_words(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
    """Reject tool calls that contain sensitive words in arguments."""
    print("****************************** I am inside (tool_input_guardrail.reject_sensitive_words) *******************************")
    print(f"Tool input data: {data}")
    print(f"Checking tool input: {data}")
    print("========================after printing the data =======================================")
    args = json.loads(data.context.tool_arguments) if data.context.tool_arguments else {}
    print(f"Guardrail checking tool arguments: {args}")
    print("================================after printing the args ===============================")
    # Example check for sensitive words
    sensitive_words = ["password", "ssn", "secret","yagna"]
    for word in sensitive_words:
        if word in json.dumps(args).lower():
            return ToolGuardrailFunctionOutput.reject_content(
                message=f"Tool call rejected due to presence of sensitive word: {word}"
            )
    return ToolGuardrailFunctionOutput.allow()

async def main():
    agent = Agent(
        name="WhatsApp Messaging Agent",
        instructions="You send WhatsApp messages to users.",
        model=model,
        tools=[send_whatsapp_message],
        tool_input_guardrails=[reject_sensitive_words],
    )
    result = await Runner.run(agent, "Send a WhatsApp message to 555-1234 with the content 'Hello, this is a test message!'")
    print(result.final_output)

if __name__ == "__main__":
    import asyncio
    import json
    import sys
    import os
    from pathlib import Path
    root_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(root_path))
    from llm_model_config.llm_model_config import ModelSingleton
    model = ModelSingleton.get_instance()
    from pydantic import BaseModel, Field
    from typing import Annotated
    from agents import (
        Agent,
        Runner,
        ToolGuardrailFunctionOutput,
        ToolInputGuardrailData,
        ToolOutputGuardrailData,
        ToolOutputGuardrailTripwireTriggered,
        function_tool,
        tool_input_guardrail,
        tool_output_guardrail,
    )


    @function_tool
    def send_whatsapp_message(to: Annotated[str, Field(description="Phone number to send the message to")], message: Annotated[str, Field(description="Message content to send")]) -> str:
        """Send a WhatsApp message to the specified recipient."""
        print("******************************I am inside send_whatsapp_message *******************************")
        print(f"Simulating sending WhatsApp message to {to} with content '{message}'")
        return f"WhatsApp message sent to {to} with content '{message}'"


    @tool_input_guardrail
    def reject_sensitive_words(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
        """Reject tool calls that contain sensitive words in arguments."""
        print("****************************** I am inside (tool_input_guardrail.reject_sensitive_words) *******************************")
        print(f"Tool input data: {data}")
        print(f"Checking tool input: {data}")
        print("========================after printing the data =======================================")
        args = json.loads(data.context.tool_arguments) if data.context.tool_arguments else {}
        print(f"Guardrail checking tool arguments: {args}")
        print("================================after printing the args ===============================")
        # Example check for sensitive words
        sensitive_words = ["password", "ssn", "secret", "yagna", "555-1234", "9985416448"]
        for word in sensitive_words:
            if word in json.dumps(args).lower():
                return ToolGuardrailFunctionOutput.reject_content(
                    message=f"Tool call rejected due to presence of sensitive word: {word}"
                )
        return ToolGuardrailFunctionOutput.allow()

    agent= Agent(
    name="Support agent",
    instructions="Handle tickets and ask for approval when needed.",
    model= model
    )
    async def main():
        # Attach guardrails to the tool itself (Agent doesn't accept tool_input_guardrails)
        send_whatsapp_message.tool_input_guardrails = [reject_sensitive_words]

        agent = Agent(
            name="WhatsApp Messaging Agent",
            instructions="You send WhatsApp messages to users.",
            model=model,
            tools=[send_whatsapp_message],
        )
        result = await Runner.run(agent, "Send a WhatsApp message to yagna and this is here phone number 9985416448 with the content 'Hello, this is a test message!'")
        print(result.final_output)


    if __name__ == "__main__":
        asyncio.run(main())
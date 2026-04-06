import asyncio
import json
import asyncio
from pathlib import Path
import sys
import asyncio
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()


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
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to the specified recipient."""
    print("******************************I am inside send_email *******************************")   
    print(f"Simulating sending email to {to} with subject '{subject}' and body '{body}'")
    return f"Email sent to {to} with subject '{subject}'"


@function_tool
def get_user_data(user_id: str) -> dict[str, str]:
    """Get user data by ID."""
    print("******************************I am inside get_user_data *******************************")
    print(f"Simulating retrieving user data for ID: {user_id}")
    # Simulate returning sensitive data
    return {
        "user_id": user_id,
        "name": "John Doe",
        "email": "john@example.com",
        "ssn": "123-45-6789",  # Sensitive data that should be blocked!
        "phone": "555-1234",
    }


@function_tool
def get_contact_info(user_id: str) -> dict[str, str]:
    """Get contact info by ID."""
    print("******************************I am inside get_contact_info *******************************")
    print(f"Simulating retrieving contact info for ID: {user_id}")
    return {
        "user_id": user_id,
        "name": "Jane Smith",
        "email": "jane@example.com",
        "phone": "555-1234",
    }



# --- Guardrail functions ---

@tool_input_guardrail
def reject_sensitive_words(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
    """Reject tool calls that contain sensitive words in arguments."""
    try:
        print("****************************** I am inside (tool_input_guardrail.reject_sensitive_words) *******************************")
        print(f"Tool input data: {data[:20]}")
        print(f"Checking tool input: {data[:20]}")
        print("========================after printing the data =======================================")
        args = json.loads(data.context.tool_arguments) if data.context.tool_arguments else {}
        print
        print(f"Guardrail checking tool arguments: {args[:20]}")
        print("================================after printing the args ===============================")
    except json.JSONDecodeError:
        return ToolGuardrailFunctionOutput(output_info="Invalid JSON arguments")

    # Check for suspicious content
    sensitive_words = [
        "password",
        "hack",
        "exploit",
        "malware",
        "ACME",
    ]
    for key, value in args.items():
        value_str = str(value).lower()
        for word in sensitive_words:
            if word.lower() in value_str:
                # Reject tool call and inform the model the function was not called
                return ToolGuardrailFunctionOutput.reject_content(
                    message=f"🚨 Tool call blocked: contains '{word}'",
                    output_info={"blocked_word": word, "argument": key},
                )

    return ToolGuardrailFunctionOutput(output_info="Input validated")


@tool_output_guardrail
def block_sensitive_output(data: ToolOutputGuardrailData) -> ToolGuardrailFunctionOutput:
    """Block tool outputs that contain sensitive data."""
    print("******************************I am inside tool_output_guardrail.block_sensitive_output *******************************")
    print(f"Checking tool output: {data.output[:20]}")
    output_str = str(data.output).lower()
    print(f"Guardrail checking tool output: {output_str[:20]}")
    # Check for sensitive data patterns
    if "ssn" in output_str or "123-45-6789" in output_str:
        # Use raise_exception to halt execution completely for sensitive data
        return ToolGuardrailFunctionOutput.raise_exception(
            output_info={"blocked_pattern": "SSN", "tool": data.context.tool_name},
        )

    return ToolGuardrailFunctionOutput(output_info="Output validated")


@tool_output_guardrail
def reject_phone_numbers(data: ToolOutputGuardrailData) -> ToolGuardrailFunctionOutput:
    """Reject function output containing phone numbers."""
    print("******************************I am inside tool_output_guardrail.reject_phone_numbers *******************************")
    print(f"Checking tool output for phone numbers: {data.output[:20]}")
    output_str = str(data.output)
    print(f"Guardrail checking tool output for phone numbers: {output_str[:20]}")
    if "555-1234" in output_str:
        return ToolGuardrailFunctionOutput.reject_content(
            message="User data not retrieved as it contains a phone number which is restricted.",
            output_info={"redacted": "phone_number"},
        )
    return ToolGuardrailFunctionOutput(output_info="Phone number check passed")


# Apply guardrails to tools
send_email.tool_input_guardrails = [reject_sensitive_words]
get_user_data.tool_output_guardrails = [block_sensitive_output]
get_contact_info.tool_output_guardrails = [reject_phone_numbers]


# agent configuration

agent = Agent(
    name="Secure Assistant",
    instructions="You are a helpful assistant with access to email and user data tools.",
    tools=[send_email, get_user_data, get_contact_info],
    model=model
)


async def main():
    print("=== Tool Guardrails Example ===\n")

    try:
        # Example 1: Normal operation - should work fine
        print("1. Normal email sending:")
        print("================================before printing the result ===============================")
        result = await Runner.run(agent, "Send a welcome email to john@example.com")
        print("================================after printing the result ===============================")
        print(f"✅ Successful tool execution: {result.final_output}\n")
    except Exception as e:
        print(f"Error: {e}\n")



if __name__ == "__main__":
    asyncio.run(main())

"""
Example output:

=== Tool Guardrails Example ===

1. Normal email sending: 
✅ Successful tool execution: I've sent a welcome email to john@example.com with an appropriate subject and greeting message.

2. Attempting to send email with suspicious content:
❌ Guardrail rejected function tool call: I'm unable to send the email as mentioning ACME Corp. is restricted.

3. Attempting to get user data (contains SSN). Execution blocked:
🚨 Output guardrail triggered: Execution halted for sensitive data
   Details: {'blocked_pattern': 'SSN', 'tool': 'get_user_data'}

4. Rejecting function tool output containing sensitive data:
❌ Guardrail rejected function tool output: I'm unable to retrieve the contact info for user456 because it contains restricted information.
"""
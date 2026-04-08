import asyncio
import logging
import random
import time
from typing import Callable, Any
from dataclasses import dataclass

# -------------------- LOGGER SETUP --------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("agent_system")

# -------------------- RETRY CONFIG --------------------
@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 10.0

DEFAULT_RETRY_CONFIG = RetryConfig()

# -------------------- ERROR CLASSIFIER --------------------
class ErrorClassifier:
    @staticmethod
    def is_rate_limit_error(e: Exception) -> bool:
        return "rate_limit" in str(e).lower()

    @staticmethod
    def is_network_error(e: Exception) -> bool:
        return "network" in str(e).lower()

# -------------------- RETRY HELPER --------------------
async def run_with_retry(
    func: Callable,
    *args,
    retry_config: RetryConfig = DEFAULT_RETRY_CONFIG,
    context_info: str = "",
    retry_on_network_errors: bool = True,
    **kwargs
) -> Any:

    for attempt in range(retry_config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            is_rate_limit = ErrorClassifier.is_rate_limit_error(e)
            is_network = ErrorClassifier.is_network_error(e) if retry_on_network_errors else False

            # ❌ Not retryable
            if not (is_rate_limit or is_network):
                log.error(f"[FAIL_FAST] {e}")
                raise

            # ❌ Max retries reached
            if attempt >= retry_config.max_retries:
                log.error(f"[MAX_RETRIES] Failed after {attempt} attempts | {context_info}")
                raise

            # ⏳ Exponential backoff + jitter
            delay = min(
                retry_config.initial_delay * (retry_config.backoff_factor ** attempt),
                retry_config.max_delay
            )
            delay += random.uniform(0, 0.5)

            error_type = "RateLimit" if is_rate_limit else "Network"
            log.warning(f"{error_type} error → Retry {attempt+1}/{retry_config.max_retries} in {delay:.2f}s")

            await asyncio.sleep(delay)

# -------------------- MOCK TRACER --------------------
class DummySpan:
    def __init__(self):
        self.trace_id = random.randint(1, 10**10)

    def get_span_context(self):
        return self

class DummyTracer:
    def start_as_current_span(self, name):
        return self

    def __enter__(self):
        self.span = DummySpan()
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

openai_tracer = DummyTracer()

# -------------------- AGENT --------------------
class Agent:
    def __init__(self, name):
        self.name = name

# -------------------- MOCK RUNNER --------------------
class Runner:
    @staticmethod
    async def run(*, starting_agent, input, run_config, context, hooks):
        log.info(f"Running agent: {starting_agent.name}")

        # Simulate random failures
        rand = random.random()

        if rand < 0.3:
            raise Exception("rate_limit exceeded")
        elif rand < 0.6:
            raise Exception("network timeout")

        await asyncio.sleep(1)  # simulate processing
        return f"✅ Success from {starting_agent.name} | Input: {input}"

# -------------------- AGENT EXECUTOR --------------------
class AgentExecutor:

    def __init__(self):
        self.hooks = None

    def _set_span_attributes(self, span, request_id):
        log.info(f"[TRACE] request_id={request_id} trace_id={span.trace_id}")

    async def execute_agent_workflow(
        self,
        resolved_agent,
        conversation_input,
        run_config,
        agent_context,
        request_id
    ):
        with openai_tracer.start_as_current_span("agent_workflow_root") as root_span:
            self._set_span_attributes(root_span, request_id)

            try:
                result = await run_with_retry(
                    Runner.run,
                    starting_agent=resolved_agent,
                    input=conversation_input,
                    run_config=run_config,
                    context=agent_context,
                    hooks=self.hooks,
                    context_info=f"request_id={request_id}"
                )

                log.info(f"[SUCCESS] request_id={request_id}")
                trace_id = format(root_span.get_span_context().trace_id, "032x")

                return {
                    "result": result,
                    "trace_id": trace_id
                }

            except Exception as e:
                log.error(f"[FAILED] request_id={request_id} error={e}")
                raise

# -------------------- MAIN --------------------
async def main():
    agent = Agent("Router-Agent")
    executor = AgentExecutor()

    try:
        response = await executor.execute_agent_workflow(
            resolved_agent=agent,
            conversation_input="Transfer $100",
            run_config={},
            agent_context={},
            request_id="REQ-123"
        )

        print("\nFINAL RESPONSE:")
        print(response)

    except Exception as e:
        print("\nFINAL FAILURE:", e)

# -------------------- RUN --------------------
if __name__ == "__main__":
    asyncio.run(main())
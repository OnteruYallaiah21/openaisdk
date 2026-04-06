import os
import threading
from pathlib import Path
from load_dotenv import load_dotenv
from agents import AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled

# Disable internal tracing
set_tracing_disabled(disabled=True)

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path)

class ModelSingleton:
    _instance = None
    _lock = threading.Lock()  # Thread-safe for multi-threaded apps

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    try:
                        api_key = os.getenv("GROQ_API_KEY")
                        model_name = os.getenv("model_name")
                        if not api_key or not model_name:
                            raise ValueError("GROQ_API_KEY or model_name missing in env")

                        client = AsyncOpenAI(
                            api_key=api_key,
                            base_url="https://api.groq.com/openai/v1"
                        )
                        cls._instance = OpenAIChatCompletionsModel(
                            model=model_name,
                            openai_client=client
                        )
                    except Exception as e:
                        print(f"[ModelSingleton] Error initializing model: {e}")
                        cls._instance = None
        return cls._instance
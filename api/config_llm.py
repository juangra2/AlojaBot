# api/config_llm.py
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Modelo para AlojaBot
LLM_MODEL = "gpt-4o-mini"

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY no está definida. "
        "Configúrala como variable de entorno antes de usar el LLM."
    )

# api/config_llm.py
import os

OPENAI_API_KEY = "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"

# Modelo para AlojaBot
LLM_MODEL = "gpt-4o-mini"

if not OPENAI_API_KEY:
    # Esto nos ayudará a detectar si se nos ha olvidado configurar la key
    raise RuntimeError(
        "OPENAI_API_KEY no está definida. "
        "Configúrala como variable de entorno antes de usar el LLM."
    )

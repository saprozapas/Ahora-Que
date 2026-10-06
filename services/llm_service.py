"""Integración con Groq (modelo configurable con GROQ_MODEL).

El cliente se crea recién la primera vez que se usa, así la app levanta
aunque falte GROQ_API_KEY o la librería groq: solo falla el chatbot.
"""
import os

MODELO = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

_client = None


class LLMNoConfigurado(RuntimeError):
    pass


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY", "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").strip()
        if not api_key:
            raise LLMNoConfigurado("Falta la variable de entorno GROQ_API_KEY.")
        from groq import Groq
        _client = Groq(api_key=api_key, timeout=20, max_retries=1)
    return _client


def chat_completion(messages, tools=None, temperature=0.5, tool_choice="auto"):
    payload = {
        "model": MODELO,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    response = _get_client().chat.completions.create(**payload)
    return response.choices[0].message
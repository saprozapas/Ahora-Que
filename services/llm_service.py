"""Integración con Groq (modelo configurable con GROQ_MODEL).

El cliente se crea recién la primera vez que se usa, así la app levanta
aunque falte GROQ_API_KEY o la librería groq: solo falla el chatbot.
"""
import os
from types import SimpleNamespace

MODELO = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# Los modelos gpt-oss "razonan" antes de contestar, y el bot hace varias
# llamadas seguidas (buscar, buscar, proponer, redactar): con el razonamiento
# por defecto (medium) esa espera se multiplica. "low" la acorta mucho y para
# esta tarea alcanza. Valores: low | medium | high. Vacío = no mandar nada.
RAZONAMIENTO = os.environ.get("GROQ_REASONING_EFFORT", "low").strip().lower()

# Si está activo, el modelo manda su razonamiento mientras piensa y la página lo
# va mostrando en vivo (ver static/chatbot.js). No cuesta tokens de más: el
# modelo razona igual, solo se decide si se recibe o se descarta.
# Poner CHATBOT_MOSTRAR_RAZONAMIENTO=0 en el .env para ocultarlo.
MOSTRAR_RAZONAMIENTO = os.environ.get("CHATBOT_MOSTRAR_RAZONAMIENTO", "1").strip().lower() not in ("0", "false", "no")

_client = None


class LLMNoConfigurado(RuntimeError):
    pass


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise LLMNoConfigurado("Falta la variable de entorno GROQ_API_KEY.")
        from groq import Groq
        _client = Groq(api_key=api_key, timeout=20, max_retries=1)
    return _client


def _opciones_razonamiento():
    """Parámetros extra para los modelos gpt-oss (los otros modelos de Groq
    rechazan estos campos). Van en extra_body para no depender de la versión
    instalada de la librería groq."""
    if "gpt-oss" not in MODELO.lower() or RAZONAMIENTO not in ("low", "medium", "high"):
        return {}
    return {"extra_body": {"reasoning_effort": RAZONAMIENTO, "include_reasoning": MOSTRAR_RAZONAMIENTO}}


def chat_completion(messages, tools=None, temperature=0.5, tool_choice="auto"):
    payload = {
        "model": MODELO,
        "messages": messages,
        "temperature": temperature,
        **_opciones_razonamiento(),
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    response = _get_client().chat.completions.create(**payload)
    return response.choices[0].message


def chat_completion_stream(messages, tools=None, temperature=0.5, tool_choice="auto"):
    """Igual que chat_completion, pero con streaming.

    Es un generador: va emitiendo (yield) cada fragmento apenas lo genera el
    modelo, como una tupla (tipo, texto):
      ("razonamiento", "...")   lo que el modelo "piensa" antes de contestar
      ("texto", "...")          la respuesta en sí
    Al terminar devuelve (return) un mensaje con la misma forma que
    chat_completion: `.content` y `.tool_calls` (None si no hubo), cada tool
    call con `.id`, `.function.name` y `.function.arguments`.
    El razonamiento NO va en `.content` ni se vuelve a mandar al modelo.
    Se usa con `mensaje = yield from chat_completion_stream(...)`.
    """
    payload = {
        "model": MODELO,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        **_opciones_razonamiento(),
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    partes = []
    tool_calls = {}  # index -> {"id", "name", "arguments"}: llegan en pedazos

    for chunk in _get_client().chat.completions.create(**payload):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        # El campo `reasoning` solo viene con modelos gpt-oss e include_reasoning=True.
        razonamiento = getattr(delta, "reasoning", None)
        if razonamiento:
            yield ("razonamiento", razonamiento)
        if delta.content:
            partes.append(delta.content)
            yield ("texto", delta.content)
        for tc in delta.tool_calls or []:
            acumulado = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
            if tc.id:
                acumulado["id"] = tc.id
            if tc.function:
                if tc.function.name:
                    acumulado["name"] = tc.function.name
                if tc.function.arguments:
                    acumulado["arguments"] += tc.function.arguments

    llamadas = [
        SimpleNamespace(
            id=datos["id"] or f"call_{indice}",
            function=SimpleNamespace(name=datos["name"], arguments=datos["arguments"]),
        )
        for indice, datos in sorted(tool_calls.items())
    ]
    return SimpleNamespace(content="".join(partes), tool_calls=llamadas or None)
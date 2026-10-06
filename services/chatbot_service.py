"""Lógica del chatbot para armar ideas de plan (Tool Calling).

El modelo tiene dos herramientas:

  buscar_lugares      usa LugarService.buscar con los mismos filtros que
                      el formulario (services/lugar_filtros.py). Si se
                      agrega un filtro ahí, el bot lo recibe solo.
  proponer_borrador   el modelo arma la idea con ids de lugares. Acá se
                      verifican contra la tabla "Lugar": el borrador que
                      llega al usuario solo tiene lugares reales, con el
                      nombre y el precio que dice la base (no el modelo).

No hay memoria entre conversaciones: todo lo que el bot sabe del usuario
sale de los mensajes de la conversación activa.
"""
import json
import re

import ia_bridge
from services import plan_reglas
from services.llm_service import chat_completion
from services.lugar_filtros import FILTROS_LUGAR
from services.lugar_service import LugarService
from services.precio_lugar import RANGOS_POR_NIVEL

lugar_service = LugarService()

MAX_ITERACIONES = 8
MAX_RESULTADOS_BUSQUEDA = 10
MAX_LUGARES_BORRADOR = 5
MAX_NOMBRE = 120
MAX_DESCRIPCION = 600
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_PRECIOS = "; ".join(
    f"nivel {nivel} = ${minimo}-{maximo}" for nivel, (minimo, maximo) in RANGOS_POR_NIVEL.items() if nivel
)

SYSTEM_PROMPT = (
    "Sos el asistente de 'Ahora Qué', una app para armar planes y salidas en Montevideo. "
    "Hablás en español rioplatense, con tono cercano y respuestas cortas.\n"
    "Tu trabajo es armar una IDEA de plan: qué hacer y por qué lugares pasar (la fecha se elige "
    "después, en el grupo).\n"
    "\n"
    "Cómo trabajás:\n"
    "1. Apenas el usuario te cuenta qué quiere, aunque falten datos, armá el plan EN ESE MISMO TURNO: "
    "usá buscar_lugares (una búsqueda por cada parada) y después llamá a proponer_borrador. "
    "No hagas preguntas antes de proponer.\n"
    "2. Lo que falte lo asumís con criterio (una salida común, zona céntrica, presupuesto medio, "
    "sin restricciones) y lo aclarás en una frase, por ejemplo: \"Asumí un presupuesto medio\".\n"
    "3. Terminá SIEMPRE tu respuesta preguntando si le cierra o si quiere cambiar algo "
    "(presupuesto, zona, tipo de lugar, restricciones de comida).\n"
    "4. Si pide cambios, buscá de nuevo y proponé un borrador nuevo y completo.\n"
    "5. Solo si el mensaje no da ninguna pista (un saludo, por ejemplo), hacé UNA pregunta corta "
    "en lugar de proponer.\n"
    "\n"
    "Reglas del plan:\n"
    "- Usá SIEMPRE buscar_lugares. Nunca inventes lugares, direcciones ni precios: solo podés "
    "mencionar lugares que devolvió la herramienta. Si una búsqueda no trae resultados, probá con "
    "menos filtros o con otra palabra clave.\n"
    "- Un plan tiene de 1 a 3 paradas y tiene que tener sentido: como máximo UN lugar para comer "
    "(restaurante, parrilla, pizzería...), un café y un postre. Para armar una salida completa "
    "combiná comida con bar, paseo, actividad o postre. Cada lugar trae su 'rol' para que lo controles.\n"
    "- Todos los lugares de la base están en Montevideo: NUNCA pongas 'Montevideo' en el parámetro texto. \n"
    "Usá una sola palabra clave corta (ej: 'restaurante', 'parrilla', 'bar'), no frases.\n"
    "- Si el usuario dice cuánto quiere gastar por persona, pasalo en pesos uruguayos en "
    "presupuesto_por_persona (ej: 430). El servidor lo convierte al nivel de precio (" + _PRECIOS + "); "
    "no uses nivel_precio.\n"
    "- No uses el filtro 'ambiente' salvo que el usuario pida un ambiente concreto: es texto libre y "
    "casi siempre devuelve 0 resultados.\n"
    "- Si el usuario pide algo tranquilo, proponé 1 o 2 paradas (no hace falta llegar a 3).\n"
    "- Si te dicen la cantidad de personas o el grupo, tenelo en cuenta.\n"
    "- Al proponer, elegí los lugares que mejor cumplan lo que pidió el usuario.\n"
    "- Nunca muestres ids, JSON ni detalles técnicos al usuario. Después de proponer el borrador, "
    "contá en una o dos frases qué armaste y avisá que puede guardarlo con el botón."
)

EMPUJON = (
    "[Instrucción interna] El usuario ya dio información suficiente y todavía no armaste el "
    "borrador. No hagas más preguntas: buscá lugares con buscar_lugares y llamá a proponer_borrador "
    "ahora, asumiendo lo que falte (y decilo en tu respuesta). Terminá preguntando si le cierra "
    "o quiere cambiar algo."
)

_tipos_cache = None


def tipos_disponibles():
    """Nombres de los Tipos que existen en la base (se cachean). El modelo
    tiene que buscar con ESTOS nombres: si busca 'restaurante' y la base
    dice 'Comida', la búsqueda da 0 y se queda dando vueltas."""
    global _tipos_cache
    if _tipos_cache is None:
        try:
            _tipos_cache = [t["nombre"] for t in lugar_service.listar_tipos()]
        except Exception as e:
            print("[chatbot] no pude leer los tipos:", e, flush=True)
            return []
    return _tipos_cache


PREGUNTA_FINAL = "¿Te cierra así o querés cambiar algo?"


# --- Herramientas ------------------------------------------------------------

def schema_tools():
    props = {"texto": {"type": "string", "description": "Palabra clave: nombre o tipo de lugar (ej: 'bar', 'parrilla', 'café')."}}
    for filtro in FILTROS_LUGAR:
        if filtro["id"] == "nivel_precio":
            continue  # el bot manda presupuesto_por_persona; el servidor calcula el nivel
        if filtro["tipo"] == "checkbox":
            props[filtro["id"]] = {"type": "boolean", "description": filtro["etiqueta"]}
        elif filtro["tipo"] == "select":
            opciones = [(valor, etiqueta) for valor, etiqueta in filtro["opciones"] if valor]
            props[filtro["id"]] = {
                "type": "string",
                "enum": [valor for valor, _ in opciones],
                "description": filtro["etiqueta"] + " (" + ", ".join(f"{v} = {e}" for v, e in opciones) + ")",
            }
        elif filtro["tipo"] == "numero":
            props[filtro["id"]] = {"type": "number", "description": filtro["etiqueta"]}
        else:
            props[filtro["id"]] = {"type": "string", "description": filtro["etiqueta"]}

    props["presupuesto_por_persona"] = {
        "type": "number",
        "description": "Cuánto quiere gastar cada persona, en pesos uruguayos (ej: 430).",
    }

    return [
        {
            "type": "function",
            "function": {
                "name": "buscar_lugares",
                "description": "Busca lugares reales de Montevideo en la base de datos de la app. "
                               "Todos los parámetros son opcionales; usá solo los que el usuario pidió.",
                "parameters": {"type": "object", "properties": props},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "proponer_borrador",
                "description": "Arma el borrador de la idea de plan para que el usuario lo pueda guardar. "
                               "Los lugares tienen que ser ids devueltos por buscar_lugares, en el orden del recorrido.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string", "description": "Nombre corto de la idea (ej: 'Cena y pool')."},
                        "descripcion": {"type": "string", "description": "De qué se trata la idea, en una o dos frases."},
                        "lugares": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id_lugar": {"type": "string", "description": "id exacto devuelto por buscar_lugares."},
                                    "hora": {"type": "string", "description": "Hora sugerida HH:MM (opcional)."},
                                },
                                "required": ["id_lugar"],
                            },
                        },
                    },
                    "required": ["nombre", "lugares"],
                },
            },
        },
    ]


def _buscar_con_texto(texto, filtros):
    return lugar_service.buscar(texto=texto, tipo_id="", filtros=filtros, limite=MAX_RESULTADOS_BUSQUEDA, aleatorio=True)


def nivel_para_presupuesto(pesos):
    """Nivel de precio máximo que entra en el presupuesto por persona: el
    más alto cuyo mínimo (RANGOS_POR_NIVEL) no supera lo que quiere gastar.
    Devuelve None si el valor no es un número válido."""
    try:
        pesos = float(pesos)
    except (TypeError, ValueError):
        return None
    if pesos < 0:
        return None
    return max(nivel for nivel, (minimo, _) in RANGOS_POR_NIVEL.items() if minimo <= pesos)


def ejecutar_buscar_lugares(args):
    filtros = {}
    for clave, valor in args.items():
        if clave in ("texto", "presupuesto_por_persona", "nivel_precio") or valor in (None, False, ""):
            continue
        filtros[clave] = "1" if valor is True else str(valor)

    nivel = nivel_para_presupuesto(args.get("presupuesto_por_persona"))
    if nivel is not None:
        filtros["nivel_precio"] = str(nivel)

    # "Montevideo" no filtra nada (todo está ahí) y rompe la búsqueda por
    # nombre/tipo. Además la base busca el texto como una sola cadena, así
    # que una frase ("restaurante italiano") casi nunca matchea: si la frase
    # entera no trae nada, se prueba palabra por palabra.
    palabras = [p for p in re.findall(r"\w+", str(args.get("texto") or "")) if p.lower() != "montevideo"]
    lugares = _buscar_con_texto(" ".join(palabras), filtros)
    if not lugares and len(palabras) > 1:
        vistos = {}
        for palabra in palabras:
            for lugar in _buscar_con_texto(palabra, filtros):
                vistos.setdefault(lugar["id"], lugar)
        lugares = list(vistos.values())[:MAX_RESULTADOS_BUSQUEDA]

    # Se le pasa al modelo el tipo y el rol de cada lugar, para que pueda
    # evitar por su cuenta, por ejemplo, dos lugares para comer.
    tipos = ia_bridge.tipos_por_lugar([lugar["id"] for lugar in lugares])
    for lugar in lugares:
        lugar["tipos"] = tipos.get(lugar["id"], [])
        lugar["rol"] = plan_reglas.roles_de(lugar["nombre"], lugar["tipos"])
    return lugares


def ejecutar_proponer_borrador(args):
    """Valida el borrador del modelo. Devuelve (borrador o None, respuesta_para_el_modelo)."""
    nombre = str(args.get("nombre") or "").strip()[:MAX_NOMBRE]
    descripcion = str(args.get("descripcion") or "").strip()[:MAX_DESCRIPCION]
    pedidos = args.get("lugares") or []
    if not isinstance(pedidos, list):
        pedidos = []

    if not nombre:
        return None, {"ok": False, "error": "El borrador necesita un nombre."}

    ids_pedidos = []
    horas = {}
    for pedido in pedidos:
        if not isinstance(pedido, dict):
            continue
        id_lugar = str(pedido.get("id_lugar") or "").strip()
        if not id_lugar or id_lugar in ids_pedidos:
            continue
        ids_pedidos.append(id_lugar)
        hora = str(pedido.get("hora") or "").strip()
        horas[id_lugar] = hora if _HORA.match(hora) else None

    if not ids_pedidos:
        return None, {"ok": False, "error": "El borrador necesita al menos un lugar devuelto por buscar_lugares."}
    if len(ids_pedidos) > MAX_LUGARES_BORRADOR:
        return None, {"ok": False, "error": f"Máximo {MAX_LUGARES_BORRADOR} lugares por idea."}

    existentes = ia_bridge.lugares_por_ids(ids_pedidos)
    invalidos = [i for i in ids_pedidos if i not in existentes]
    if invalidos:
        return None, {
            "ok": False,
            "error": "Estos id_lugar no existen. Volvé a usar buscar_lugares y usá los ids exactos.",
            "ids_invalidos": invalidos,
        }

    tipos = ia_bridge.tipos_por_lugar(ids_pedidos)
    errores = plan_reglas.validar([
        {"nombre": existentes[i]["nombre"], "roles": plan_reglas.roles_de(existentes[i]["nombre"], tipos.get(i, []))}
        for i in ids_pedidos
    ])
    if errores:
        return None, {"ok": False, "error": " ".join(errores)}

    borrador = {
        "nombre": nombre,
        "descripcion": descripcion,
        "lugares": [
            {
                "id_lugar": id_lugar,
                "nombre": existentes[id_lugar]["nombre"],
                "nivel_precio": existentes[id_lugar]["nivel_precio"],
                "direccion": existentes[id_lugar]["direccion"],
                "hora": horas[id_lugar],
            }
            for id_lugar in ids_pedidos
        ],
    }
    return borrador, {"ok": True, "mensaje": "Borrador listo: el usuario ya lo ve con un botón para guardarlo."}


# --- Conversación ------------------------------------------------------------

def historial_para_llm(historial, grupo=None):
    """Convierte el historial guardado al formato del modelo. Los borradores
    se le pasan como texto (con los ids), así puede ajustarlos si el
    usuario pide cambios. `grupo` ({"nombre", "integrantes"}) es el grupo
    para el que se arma el plan, si el chat se usa desde un grupo."""
    prompt = SYSTEM_PROMPT
    if grupo:
        prompt += (
            f"\n\nContexto: este plan es para el grupo «{grupo['nombre']}», que tiene "
            f"{grupo['integrantes']} integrantes. Si el usuario no dice otra cosa, "
            f"asumí que van {grupo['integrantes']} personas."
        )
    tipos = tipos_disponibles()
    if tipos:
        prompt += (
            "\n\nTipos de lugar que existen en la base (el parámetro texto de buscar_lugares "
            "busca por el nombre del lugar o por estos tipos; usá estos nombres, no sinónimos): "
            + ", ".join(tipos) + "."
        )
    mensajes = [{"role": "system", "content": prompt}]
    for mensaje in historial:
        if mensaje["tipo"] == "borrador":
            contenido = "[Borrador propuesto al usuario] " + mensaje["content"]
        else:
            contenido = mensaje["content"]
        mensajes.append({"role": mensaje["role"], "content": contenido})
    return mensajes


def _tool_call_a_dict(tool_call):
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments},
    }


def _ejecutar_tool(tool_call):
    """Devuelve (borrador o None, contenido_para_el_modelo)."""
    nombre = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments or "{}")
        if not isinstance(args, dict):
            raise ValueError
    except ValueError:
        return None, {"ok": False, "error": "Argumentos inválidos: tienen que ser un objeto JSON."}

    if nombre == "buscar_lugares":
        resultados = ejecutar_buscar_lugares(args)
        respuesta = {"cantidad": len(resultados), "lugares": resultados}
        if not resultados:
            respuesta["aviso"] = ("Sin resultados. Probá con otro de estos tipos o sin filtros: "
                                  + ", ".join(tipos_disponibles()) + ". No repitas la misma búsqueda.")
        return None, respuesta
    if nombre == "proponer_borrador":
        return ejecutar_proponer_borrador(args)
    return None, {"ok": False, "error": f"Herramienta desconocida: {nombre}"}


def _cerrar_respuesta(texto, borrador):
    """Si se armó un borrador, la respuesta termina siempre preguntando si
    le cierra (aunque el modelo se haya olvidado)."""
    if not borrador:
        return texto or "¿Me contás un poco más qué tenés ganas de hacer?"
    if not texto:
        texto = "Te armé este plan."
    if "?" not in texto[-200:]:
        texto = texto.rstrip() + "\n\n" + PREGUNTA_FINAL
    return texto


def _log(*partes):
    print("[chatbot]", *partes, flush=True)


def _llamar_modelo(mensajes, tools, tool_choice):
    """Groq a veces rechaza (400 tool_use_failed) cuando el modelo llama a una
    herramienta distinta de la que se le forzó, o genera mal la llamada.
    En ese caso se reintenta una vez dejando que elija solo."""
    try:
        return chat_completion(mensajes, tools=tools, tool_choice=tool_choice)
    except Exception as e:
        if "tool_use_failed" not in str(e):
            raise
        _log("tool_use_failed, reintento con tool_choice=auto:", str(e)[:200])
        return chat_completion(mensajes, tools=tools, tool_choice="auto")


def procesar_mensaje_bot(mensajes, forzar_plan=False):
    """Corre el ciclo de Tool Calling. `mensajes` ya incluye el system
    prompt y el último mensaje del usuario (ver historial_para_llm).

    forzar_plan: si el modelo contesta sin armar un borrador (por ejemplo,
    porque se puso a preguntar), se le pide una vez que lo arme ya.

    Devuelve (texto_respuesta, borrador o None).
    """
    tools = schema_tools()
    borrador = None
    empujado = False
    cierre_forzado = False

    for i in range(MAX_ITERACIONES):
        tool_choice = "auto"
        # Si ya se gastaron casi todas las vueltas sin borrador, se lo obliga
        # a llamar a proponer_borrador con lo que ya encontró.
        if borrador is None and i >= MAX_ITERACIONES - 2:
            if not cierre_forzado:
                cierre_forzado = True
                mensajes.append({"role": "user", "content": (
                    "[Instrucción interna] Ya buscaste suficiente. Llamá a proponer_borrador ahora "
                    "con los lugares que ya encontraste (ids exactos).")})
            tool_choice = {"type": "function", "function": {"name": "proponer_borrador"}}

        msg = _llamar_modelo(mensajes, tools, tool_choice)
        if not msg.tool_calls:
            if forzar_plan and borrador is None and not empujado:
                empujado = True
                mensajes.append({"role": "user", "content": EMPUJON})
                continue
            return _cerrar_respuesta((msg.content or "").strip(), borrador), borrador

        mensajes.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [_tool_call_a_dict(tc) for tc in msg.tool_calls],
        })
        for tool_call in msg.tool_calls:
            nuevo_borrador, resultado = _ejecutar_tool(tool_call)
            if nuevo_borrador:
                borrador = nuevo_borrador
            _log(f"vuelta {i + 1}:", tool_call.function.name, tool_call.function.arguments,
                 "->", (resultado.get("cantidad") if isinstance(resultado, dict) and "cantidad" in resultado
                        else resultado.get("error") or resultado.get("mensaje") if isinstance(resultado, dict) else ""))
            mensajes.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })
        if borrador:
            # Ya hay borrador: una vuelta más, sin permitir más herramientas,
            # para que redacte la respuesta final.
            try:
                msg = chat_completion(mensajes, tools=tools, tool_choice="none")
                return _cerrar_respuesta((msg.content or "").strip(), borrador), borrador
            except Exception as e:  # el modelo insistió con una tool: igual hay borrador
                _log("cierre sin herramientas falló:", e)
                return _cerrar_respuesta("", borrador), borrador

    # Se pasó de iteraciones sin borrador. Nunca se llama al modelo sin
    # `tools` con historial de tool calls: Groq rechaza (400) si intenta usar una.
    _log("se agotaron las vueltas sin borrador")
    return ("Perdón, no logré armar el plan con los lugares que encontré. "
            "¿Me das un poco más de detalle (tipo de comida, zona o presupuesto)?"), None
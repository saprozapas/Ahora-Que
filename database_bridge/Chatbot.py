# import json 
# import sys 
# import os 
# from groq import Groq 
# 
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 
# from database import get_db_connection 
# import psycopg2 
# import psycopg2.extras 
# 
# # Reemplaza por tu clave de Groq 
# GROQ_API_KEY = "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" 
# 
# client = Groq(api_key=GROQ_API_KEY) 
# 
# # Campos del JSON del LLM que NO tienen correspondencia en buscar_lugares hoy. 
# CAMPOS_SIN_MAPEO = ["cant_personas", "Distancia_max_km", "es_techado"] 
# 
# 
# def extraer_filtros(texto_usuario: str) -> dict: 
#     prompt = f""" 
#     Sos un asistente para la app 'Ahora Qué' en Montevideo. 
#     Analizá el texto del usuario y extraé los filtros para buscar lugares. 
# 
#     Reglas de interpretación: 
#     - Modismos uruguayos/argentinos: "un montón", "una banda", "bocha" -> 10 personas. "Un par" -> 2 personas. 
#     - Lluvia, frío, "adentro" -> 'es_techado': true. 
#     - Perros, mascotas -> 'pet_friendly': true. 
#     - "Barato", "económico" -> asigná un 'precio_max' estimado (ej: 500). 
# 
#     Texto del usuario: "{texto_usuario}" 
# 
#     Responde ÚNICAMENTE un JSON válido con estas claves: 
#     {{ 
#         "cant_personas": int | null, 
#         "precio_max": float | null, 
#         "opcion_celiacos": bool | null, 
#         "opcion_vegana": bool | null, 
#         "Distancia_max_km": float | null, 
#         "Apto_menores": bool | null, 
#         "es_techado": bool | null 
#     }} 
#     """ 
# 
#     completion = client.chat.completions.create( 
#         messages=[{"role": "user", "content": prompt}], 
#         model="groq/compound-mini", 
#         response_format={"type": "json_object"}, 
#         temperature=0.1 
#     ) 
# 
#     return json.loads(completion.choices[0].message.content) 
# 
# 
# def json_a_parametros_lugares(filtros: dict) -> dict: 
#     """ 
#     Convierte el JSON del chatbot (claves del prompt de Groq) a los 
#     parámetros reales de la función SQL buscar_lugares. 
# 
#     Firma real de buscar_lugares en Postgres: 
#         p_texto, p_tipo_id, p_nivel_precio_max, p_solo_vegano, 
#         p_solo_celiaco, p_apto_menores, p_dia_semana, p_hora, 
#         p_limite, p_offset 
#     """ 
#     ignorados = {k: v for k, v in filtros.items() if k in CAMPOS_SIN_MAPEO and v is not None} 
#     if ignorados: 
#         print(f"⚠️  Campos sin parámetro correspondiente en buscar_lugares (se ignoran): {ignorados}") 
# 
#     return { 
#         "texto": None, 
#         "tipo_id": None, 
#         "nivel_precio_max": filtros.get("precio_max"), 
#         "solo_vegano": bool(filtros.get("opcion_vegana")) if filtros.get("opcion_vegana") is not None else False, 
#         "solo_celiaco": bool(filtros.get("opcion_celiacos")) if filtros.get("opcion_celiacos") is not None else False, 
#         "apto_menores": bool(filtros.get("Apto_menores")) if filtros.get("Apto_menores") is not None else False, 
#         "dia_semana": None, 
#         "hora": None, 
#         "limite": 10, 
#         "offset": 0, 
#     } 
# 
# 
# def buscar_lugares( 
#     texto=None, 
#     tipo_id=None, 
#     nivel_precio_max=None, 
#     solo_vegano=False, 
#     solo_celiaco=False, 
#     apto_menores=False, 
#     dia_semana=None, 
#     hora=None, 
#     limite=10, 
#     offset=0, 
# ): 
#     connection = get_db_connection() 
#     try: 
#         with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor: 
#             cursor.execute( 
#                 """ 
#                 SELECT * FROM buscar_lugares(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
#                 """, 
#                 ( 
#                     texto, tipo_id, nivel_precio_max, solo_vegano, 
#                     solo_celiaco, apto_menores, dia_semana, hora, 
#                     limite, offset, 
#                 ), 
#             ) 
#             return cursor.fetchall() 
#     except psycopg2.Error: 
#         raise 
#     finally: 
#         connection.close() 
# 
# 
# def buscar_lugares_desde_json(filtros_json: dict): 
#     parametros = json_a_parametros_lugares(filtros_json) 
#     return buscar_lugares(**parametros) 
# 
# 
# print("=" * 50, flush=True) 
# print("  CHATBOT AHORA QUÉ - búsqueda real en la base de datos", flush=True) 
# print("  Escribí lo que buscás. Escribí 'salir' para terminar.", flush=True) 
# print("=" * 50, flush=True) 
# 
# while True: 
#     try: 
#         entrada = input("\nVos: ") 
#     except (KeyboardInterrupt, EOFError): 
#         print("\n¡Hasta luego!") 
#         sys.exit() 
# 
#     if entrada.lower().strip() in ["salir", "exit", "quit"]: 
#         print("¡Hasta luego!") 
#         break 
# 
#     if not entrada.strip(): 
#         continue 
# 
#     try: 
#         filtros = extraer_filtros(entrada) 
#         print("\n🤖 Filtros extraídos:", flush=True) 
#         print(json.dumps(filtros, indent=2, ensure_ascii=False), flush=True) 
# 
#         lugares = buscar_lugares_desde_json(filtros) 
#         print(f"\n📍 Lugares encontrados ({len(lugares)}):", flush=True) 
#         if not lugares: 
#             print("  (ninguno con esos filtros)") 
#         for lugar in lugares: 
#             print(f"  - {lugar}") 
# 
#     except Exception as e: 
#         print(f"\n❌ Error: {e}", flush=True)
"""Resume las mediciones de sesion-main: una fila por ruta (375 y 1440) y los
fallos de contraste, objetivos tactiles y texto chico mas repetidos."""
import collections, glob, json, os, re, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "redesign-screens/audit/sesion-main"


def cargar(d, w, t):
    f = f"{BASE}/{d}/medicion__{w}__{t}.json"
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else None


print("ruta | url final | scrollH(320/375/768/1440) | tact<44 @375 | contraste claro/noche @375 | contraste claro @1440 | texto<12 @375 | fuentes @375 | h1 | sin nombre")
agg_c, agg_cn, agg_t, agg_x = (collections.Counter() for _ in range(4))
for d in sorted(x for x in os.listdir(BASE) if os.path.isdir(f"{BASE}/{x}")):
    j = cargar(d, 375, "claro"); n = cargar(d, 375, "noche"); g = cargar(d, 1440, "claro")
    if not j:
        continue
    sh = [w for w in (320, 375, 768, 1440) if (cargar(d, w, "claro") or {}).get("scrollW", 0) > w]
    a = j["a11y"]; h = j["hist"]
    print(f"{j['ruta'][:46]:46s} | {j['urlFinal'][:30]:30s} | {sh or '-'} | {len(j['tactiles']):3d} | "
          f"{j['contraste']['totalFallos']}/{j['contraste']['evaluados']} - {(n or {}).get('contraste', {}).get('totalFallos', '?')} | "
          f"{(g or {}).get('contraste', {}).get('totalFallos', '?')} | {len(j['textoChico'])} | {len(h['fontSize'])} | "
          f"h1={a['h1']} {a['saltosTitulos'] or ''} | {a['botonesSinNombre'][:2]} {a['inputsSinEtiqueta'][:2]} imgSinAlt={a['imgSinAlt'][:2]}")
    for x in j["contraste"]["fallos"]:
        agg_c[(re.sub(r"#.*", "", x["el"])[:40], x["ratio"])] += 1
    for x in (n or {"contraste": {"fallos": []}})["contraste"]["fallos"]:
        agg_cn[(re.sub(r"#.*", "", x["el"])[:40], x["ratio"])] += 1
    for t in j["tactiles"]:
        agg_t[re.sub(r" \d+x\d+.*", "", t)[:50]] += 1
    for t in j["textoChico"]:
        agg_x[re.sub(r" [\d.]+px/.*", "", t)[:50]] += 1
print("\ncontraste claro:", agg_c.most_common(20))
print("\ncontraste noche:", agg_cn.most_common(14))
print("\ntactiles <44:", agg_t.most_common(24))
print("\ntexto <12px:", agg_x.most_common(14))

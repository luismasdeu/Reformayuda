#!/usr/bin/env python3
"""Escribe con IA nuevos guiones de reels y carruseles de consejos cuando quedan pocos.

Lo lanza .github/workflows/redes-generar.yml cada semana. Si quedan menos de MIN_REELS reels
o MIN_CARRUSELES carruseles sin publicar (y no hay ya propuestas esperando), pide a Claude
una tanda nueva y la deja en revision/redes-propuestas.json con estado «pendiente».
Se aprueban o descartan en obrayuda.es/revisar/; las aprobadas pasan a docs/redes/ con
`python scripts/redes/redes.py incorporar` (lo hace solo el workflow de redes).

Usa el mismo tope mensual de gasto que el resto de la IA (revision/gasto-ia.json).
"""
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import redes  # noqa: E402

PROPUESTAS = RAIZ / "revision" / "redes-propuestas.json"
GASTO = RAIZ / "revision" / "gasto-ia.json"
MODELO = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5"
PRECIO = {"claude-opus-5-5": (4, 20), "claude-sonnet-5-5": (2, 10), "claude-haiku-5-5": (0.10, 0.50)}
MIN_REELS, MIN_CARRUSELES = 10, 6
TANDA_REELS, TANDA_CARRUSELES = 14, 6

INSTRUCCIONES = """Eres el responsable de redes sociales de Obrayuda, una app gratuita (no oficial) que reúne las ayudas públicas españolas para reformar, rehabilitar, mejorar la eficiencia o la accesibilidad, o construir una vivienda o un edificio de viviendas. Revisa cada mañana el BOE y los boletines oficiales. Web: obrayuda.es. Canal de Telegram: t.me/obrayuda.

Escribes en español de España, cercano y claro, para personas de 30 a 65 años que van a hacer obra en casa o en su comunidad. Sin tecnicismos.

Reglas que no se pueden saltar:
- Solo datos verdaderos y generales que se puedan comprobar en fuentes oficiales (leyes, Agencia Tributaria, BOE, convocatorias). Si no estás seguro de una cifra, no la pongas. Nada de prometer dinero a todo el mundo: di «puede», «muchas», «según la convocatoria».
- Contenido ATEMPORAL: consejos, errores, trámites, mitos, tipos de obra. NO hagas piezas sobre una ayuda concreta con plazo (esas se publican solas en otro formato) y no pongas fechas de cierre: se pueden publicar semanas después.
- No te inventes cifras, normas ni plazos. No cites números de leyes o reales decretos. Las únicas cifras permitidas son las de la lista de datos fiables que te paso.
- Nada sobre comprar una casa ya construida, alquiler, recibos o ayudas sociales: Obrayuda es solo de obras.
- No repitas temas ni ganchos de la lista de ya publicados o preparados.
- Cada pieza acaba invitando a comentar una PALABRA en mayúsculas (AYUDA, EDIFICIO, PLACAS, BAÑO, CONSTRUIR, MAYORES, ICIO, PUEBLO…).

Reels (vídeos verticales de 20-30 s con voz y texto grande):
- Gancho en la primera escena: frase corta que pare el scroll (pregunta directa, error que te hace perder dinero, «nadie te lo dice», dato sorprendente). Resalta la parte clave entre **dobles asteriscos**.
- 3 escenas de desarrollo, cada una con una idea. «texto» es lo que se ve (máximo 90 caracteres, con **resaltado**); «voz» es lo que se dice (natural, máximo 160 caracteres; escribe los números como se dicen si son porcentajes o cifras grandes).
- Escena final de llamada a la acción.
- «texto_publicacion»: el texto que acompaña al reel en Instagram: primera línea gancho con un emoji, 3 viñetas, una línea «Cada ayuda tiene sus bases: revisa siempre la convocatoria oficial.», la llamada a comentar, «🔎 Busca las ayudas de tu zona en obrayuda.es (enlace en el perfil)» y como máximo 5 hashtags en una línea.

Estilos de reel (reparte la tanda entre todos, y haz más de los que mejor funcionen según las métricas que te paso):
- "subtitulos": consejo directo. Gancho fuerte y 3 escenas.
- "noticia": algo que la gente debe saber ya (un plazo general, una norma, un error muy común). Banner de 2-3 palabras en "banner" (por ejemplo «⚠️ OJO», «🚨 IMPORTANTE»). Nunca inventes noticias ni fechas.
- "mito": 3 escenas, cada una una creencia falsa o verdadera sobre ayudas u obras; pon en "veredicto" MITO o VERDAD y explica por qué en la voz.
- "lista": «3 cosas que…», cuenta atrás: pon "n" = 3, 2, 1 en las escenas.
- "pov": el gancho es una situación con la que la gente se identifica («POV: te enteras de la ayuda el día después de que cierre»). Texto del gancho en primera persona y corto.
- "error": escenas alternas del error y de lo correcto; pon "marca" = "mal" o "bien".
En los campos que no apliquen al estilo, deja cadena vacía ("") o 0.

Carruseles (4-6 imágenes): portada con gancho, 2-4 diapositivas de lista (3 puntos cada una, máximo 90 caracteres) o de texto (máximo 300 caracteres), y llamada final. «texto_publicacion» como en los reels.
"""

TEXTO = {"type": "string"}
ESQUEMA = {
    "type": "object", "additionalProperties": False, "required": ["reels", "carruseles"],
    "properties": {
        "reels": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["nombre", "estilo", "banner", "emoji", "gancho", "voz_gancho", "escenas", "palabra", "cta", "voz_cta", "texto_publicacion"],
            "properties": {
                "nombre": {"type": "string", "description": "slug corto en minúsculas con guiones"},
                "emoji": TEXTO, "gancho": TEXTO, "voz_gancho": TEXTO,
                "estilo": {"type": "string", "enum": ["subtitulos", "noticia", "mito", "lista", "pov", "error"]},
                "banner": TEXTO,
                "escenas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                            "required": ["texto", "voz", "emoji", "veredicto", "marca", "n"],
                            "properties": {"texto": TEXTO, "voz": TEXTO, "emoji": TEXTO, "veredicto": TEXTO, "marca": TEXTO, "n": {"type": "integer"}}}},
                "palabra": TEXTO, "cta": TEXTO, "voz_cta": TEXTO, "texto_publicacion": TEXTO}}},
        "carruseles": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["nombre", "ceja", "titulo", "subtitulo", "diapositivas", "cta", "texto_publicacion"],
            "properties": {
                "nombre": TEXTO, "ceja": TEXTO, "titulo": TEXTO, "subtitulo": TEXTO,
                "diapositivas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                 "required": ["tipo", "ceja", "titulo", "puntos", "texto"],
                                 "properties": {"tipo": {"type": "string", "enum": ["lista", "texto"]}, "ceja": TEXTO, "titulo": TEXTO,
                                                "puntos": {"type": "array", "items": TEXTO}, "texto": TEXTO}}},
                "cta": TEXTO, "texto_publicacion": TEXTO}}},
    },
}


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "pieza"


def existentes():
    """Ganchos y títulos ya preparados o publicados, para no repetir."""
    out = []
    for f in sorted(redes.REELS.glob("*.json")):
        out.append("REEL: " + json.loads(f.read_text(encoding="utf-8"))["escenas"][0]["texto"].replace("**", ""))
    for f in sorted(redes.BANCO.glob("*.json")):
        out.append("CARRUSEL: " + json.loads(f.read_text(encoding="utf-8"))["slides"][0]["titulo"].replace("**", "").replace("\n", " "))
    return out


def pendientes_de_publicar():
    reg = redes.leer_registro()
    hechos_r = {p["nombre"] for p in redes.hechas(reg, "reel") if p.get("tipo") == "guion"}
    hechos_c = {p["nombre"] for p in redes.hechas(reg, "carrusel") if p.get("tipo") == "consejo"}
    reels = [f for f in redes.REELS.glob("*.json") if f.stem not in hechos_r]
    carr = [f for f in redes.BANCO.glob("*.json") if f.stem not in hechos_c]
    return len(reels), len(carr)


def a_guion(r):
    gancho = {"tipo": "gancho", "emoji": r["emoji"], "texto": r["gancho"], "voz": r["voz_gancho"]}
    if r.get("banner"):
        gancho["banner"] = r["banner"]
    esc = [gancho]
    for e in r["escenas"][:4]:
        x = {"tipo": "punto", "emoji": e["emoji"], "texto": e["texto"], "voz": e["voz"]}
        for k in ("veredicto", "marca"):
            if e.get(k):
                x[k] = e[k]
        if e.get("n"):
            x["n"] = e["n"]
        esc.append(x)
    esc.append({"tipo": "cta", "texto": r["cta"], "voz": r["voz_cta"], "palabra": r["palabra"].upper()})
    return {"voz": "es-ES-XimenaNeural", "estilo": r.get("estilo", "subtitulos"), "escenas": esc, "texto": r["texto_publicacion"]}


def metricas():
    """Visualizaciones, alcance, guardados y compartidos de cada publicación (Instagram), para aprender qué funciona."""
    token = os.environ.get("META_PAGE_TOKEN", "").strip()
    if not token:
        return []
    out = []
    for p in redes.leer_registro()["publicadas"]:
        if not p.get("instagram") or p["fecha"] < (dt.date.today() - dt.timedelta(days=60)).isoformat():
            continue
        try:
            datos = redes.graph("GET", f"{p['instagram']}/insights", token, metric="views,reach,saved,shares,comments,likes").get("data", [])
        except RuntimeError:
            continue
        m = {d["name"]: (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value", 0)) for d in datos}
        out.append({"fecha": p["fecha"], "formato": p.get("formato", "carrusel"), "nombre": p["nombre"], **m})
    return out


def resumen_metricas(ms):
    if not ms:
        return "Aún no hay métricas: reparte la tanda entre todos los estilos para probar."
    estilos = {}
    for f in list(redes.REELS.glob("*.json")) + list(redes.BANCO.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        estilos[f.stem] = (d.get("estilo") or ("carrusel" if "slides" in d else "subtitulos"),
                           (d.get("escenas") or d.get("slides"))[0].get("texto") or d["slides"][0].get("titulo", ""))
    filas = []
    for m in sorted(ms, key=lambda x: -(x.get("shares", 0) * 3 + x.get("saved", 0) * 2 + x.get("views", 0) / 100)):
        est, gancho = estilos.get(m["nombre"], ("ayuda concreta", m["nombre"]))
        filas.append(f"{m['formato']} · estilo {est} · vistas {m.get('views', 0)} · guardados {m.get('saved', 0)} · "
                     f"compartidos {m.get('shares', 0)} · «{str(gancho).replace('**', '')[:90]}»")
    return "Métricas de lo publicado (de mejor a peor):\n" + "\n".join(filas[:25])


def a_carrusel(c):
    s = [{"tipo": "portada", "ceja": c["ceja"], "titulo": c["titulo"], "sub": c["subtitulo"]}]
    for d in c["diapositivas"][:4]:
        if d["tipo"] == "lista":
            s.append({"tipo": "lista", "ceja": d["ceja"], "titulo": d["titulo"], "marcas": "check", "puntos": d["puntos"][:4]})
        else:
            s.append({"tipo": "texto", "ceja": d["ceja"], "titulo": d["titulo"], "texto": d["texto"]})
    s.append({"tipo": "cta", "titulo": c["cta"], "sub": "Guárdalo para cuando vayas a hacer obra."})
    return {"slides": s, "texto": c["texto_publicacion"]}


def main():
    forzar = "--forzar" in sys.argv
    props = json.loads(PROPUESTAS.read_text(encoding="utf-8")) if PROPUESTAS.exists() else {"propuestas": []}
    esperando = [p for p in props["propuestas"] if p.get("estado", "pendiente") == "pendiente"]
    n_reels, n_carr = pendientes_de_publicar()
    print(f"Sin publicar: {n_reels} reels y {n_carr} carruseles. Propuestas esperando revisión: {len(esperando)}.")
    if not forzar and (esperando or (n_reels >= MIN_REELS and n_carr >= MIN_CARRUSELES)):
        print("No hace falta generar contenido nuevo.")
        return
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("Sin ANTHROPIC_API_KEY: no genero contenido.")
        return
    mes = dt.date.today().strftime("%Y-%m")
    gasto = json.loads(GASTO.read_text(encoding="utf-8")) if GASTO.exists() else {"limite_usd": 20, "meses": {}}
    if gasto["meses"].get(mes, 0) > float(gasto.get("limite_usd", 20)) - 1:
        print("Tope mensual de IA casi alcanzado: no genero contenido este mes.")
        return

    ms = metricas()
    if ms:
        (RAIZ / "revision" / "redes-metricas.json").write_text(json.dumps({"fecha": dt.date.today().isoformat(), "publicaciones": ms},
                                                                         ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pedir_r = TANDA_REELS if n_reels < MIN_REELS or forzar else 0
    pedir_c = TANDA_CARRUSELES if n_carr < MIN_CARRUSELES or forzar else 0
    peticion = (f"Escribe {pedir_r} reels y {pedir_c} carruseles nuevos.\n\n"
                "Ya publicados o preparados (no repitas tema ni gancho):\n" + "\n".join(existentes()) +
                "\n\n" + resumen_metricas(ms) +
                "\n\nDatos fiables que puedes usar: deducción del IRPF por obras de eficiencia energética en vivienda del 20 % "
                "(hasta 1.000 € al año) o del 40 % (hasta 3.000 € al año), y del 60 % en obras del edificio (hasta 9.000 € en total); "
                "exige certificado energético antes y después, factura a tu nombre y pago no en efectivo. Bonificaciones municipales: "
                "IBI hasta el 50 % por placas solares e ICIO hasta el 95 % en obras de eficiencia, renovables o accesibilidad, según cada ayuntamiento." +
                "\n\nVaría los temas: tipos de obra (ventanas, aislamiento, cubierta, aerotermia, placas, baño, cocina adaptada, ascensor, fachada, humedades, autoconstrucción), "
                "trámites (certificados, licencias, plazos, justificación), errores frecuentes, mitos, comunidades de vecinos, casas de pueblo y zonas rurales.")

    import anthropic
    cliente = anthropic.Anthropic()
    with cliente.beta.messages.stream(
        model=MODELO, max_tokens=32000, system=INSTRUCCIONES,
        messages=[{"role": "user", "content": peticion}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ESQUEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    ) as flujo:
        r = flujo.get_final_message()
    if r.stop_reason in ("refusal", "max_tokens"):
        raise SystemExit(f"Respuesta incompleta ({r.stop_reason})")
    texto = [b.text for b in r.content if b.type == "text"][-1]
    datos = json.loads(texto[texto.index("{"):texto.rindex("}") + 1])
    entrada, salida = PRECIO.get(MODELO, (2, 10))
    coste = round((r.usage.input_tokens * entrada + r.usage.output_tokens * salida) / 1e6, 3)
    gasto["meses"][mes] = round(gasto["meses"].get(mes, 0) + coste, 3)
    GASTO.write_text(json.dumps(gasto, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    hoy = dt.date.today().isoformat()
    nuevas = []
    for x in datos.get("reels", [])[:pedir_r]:
        nuevas.append({"id": f"{hoy}-r-{slug(x['nombre'])}", "formato": "reel", "nombre": slug(x["nombre"]),
                       "estado": "pendiente", "fecha": hoy, "contenido": a_guion(x)})
    for x in datos.get("carruseles", [])[:pedir_c]:
        nuevas.append({"id": f"{hoy}-c-{slug(x['nombre'])}", "formato": "carrusel", "nombre": slug(x["nombre"]),
                       "estado": "pendiente", "fecha": hoy, "contenido": a_carrusel(x)})
    props["propuestas"] += nuevas
    PROPUESTAS.write_text(json.dumps(props, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Propuestas nuevas: {len(nuevas)} · coste {coste} $ · gasto del mes {gasto['meses'][mes]} $")


if __name__ == "__main__":
    main()

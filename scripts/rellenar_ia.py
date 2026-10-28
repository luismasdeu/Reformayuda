#!/usr/bin/env python3
"""Rellena las candidatas con la API de Claude leyendo la ficha de la BDNS y las bases oficiales.

Para cada candidata pendiente que aún no se ha procesado:
  1. Descarga la ficha de la BDNS y el documento de bases (PDF o página web).
  2. Pide a Claude que extraiga título claro, importe, plazo, requisitos, documentos, pasos,
     tipo de obra, edad, etc., y que diga si de verdad es una ayuda para obras en una vivienda.
  3. Lo guarda en la candidata, con lo que no ha podido confirmar en «_revisar.confirmar».
Tú sigues decidiendo: en reformayuda.es/revisar/ ves su recomendación y pulsas Publicar o Descartar.

Uso:
  python scripts/rellenar_ia.py                       candidatas pendientes (máx. IA_MAX, 15 por defecto)
                                                      y ayudas publicadas que aún tienen datos genéricos
  python scripts/rellenar_ia.py --publicadas id1,id2  corrige ayudas ya publicadas con datos genéricos

Necesita el secreto ANTHROPIC_API_KEY. Si no está, no hace nada.
"""
import base64
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from actualizar import BDNS_BASES, USER_AGENT, pedir_json  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CANDIDATAS = RAIZ / "revision" / "candidatas.json"
AYUDAS = RAIZ / "web" / "data" / "ayudas.json"
DIAGNOSTICO = RAIZ / "revision" / "diagnostico-ia.json"
GASTO = RAIZ / "revision" / "gasto-ia.json"  # gasto por mes y tope mensual (limite_usd)
MARGEN_POR_AYUDA = 0.60  # lo máximo que suele costar una ayuda: no se empieza otra si no cabe en el tope
MODELO = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5"
PRECIO = {"claude-opus-5-5": (4, 20), "claude-sonnet-5-5": (2, 10), "claude-haiku-5-5": (0.10, 0.50)}  # $ por millón (entrada, salida)
MAX_PDF_PAGINAS = 40      # más páginas (p. ej. un boletín entero): solo se envía el texto de las páginas que hablan de la ayuda
MAX_TEXTO = 120_000       # caracteres
TIPOS = ["eficiencia", "solar", "aerotermia", "ventanas", "accesibilidad", "rehabilitacion", "construccion"]

INSTRUCCIONES = """Ayudas a Reformayuda, una web gratuita que explica en lenguaje sencillo las ayudas públicas españolas para reformar o construir una vivienda. Recibes la ficha de la Base de Datos Nacional de Subvenciones (BDNS) de una convocatoria y, si se ha podido descargar, el texto de sus bases o del anuncio oficial.

Extrae los datos para una ficha que leerán particulares sin conocimientos legales:
- Usa solo lo que dicen los documentos. Si un dato no aparece, deja el texto vacío (o 0 en los números) y apúntalo en «dudas». Nunca inventes importes, fechas ni requisitos.
- Escribe en español claro, frases cortas, tuteando («Vivir en…», «Presenta…»). Nada de jerga administrativa.
- «es_ayuda_para_obras_en_vivienda»: true SOLO si la ayuda paga obras de reforma, rehabilitación, mejora, eficiencia energética, energía renovable, accesibilidad o construcción en una vivienda o en un edificio de viviendas (comunidad de propietarios), o si es una rebaja de impuestos (IBI, ICIO) por hacer esas obras. Es false en todo lo demás: pagar el alquiler, la hipoteca, recibos, suministros, el IBI u otros gastos de la vivienda; comprar una casa; ayudas sociales para vivir; ayudas solo para empresas, entidades o ayuntamientos; y ayudas para un edificio o beneficiario concreto ya decidido (no abiertas al público). Ante la duda, false. Explica el motivo en una frase.
- «title»: máximo 70 caracteres, que diga qué se paga y dónde (p. ej. «Rehabilitación de viviendas en Tazacorte»).
- «imp»: cuánto da a cada persona o vivienda, en palabras (p. ej. «Hasta 6.000 € por vivienda (el 50 % de la obra)»). «importe»: ese máximo en euros, o 0 si no hay cifra por vivienda.
- Fechas en formato AAAA-MM-DD. «cierra» vacío si no hay fecha final (por ejemplo, hasta agotar fondos) y explícalo en «plazo».
- «req», «docs», «pasos»: listas de 3 a 7 frases cortas. En «pasos», el último suele ser justificar la obra.
- «tipo»: elige entre """ + ", ".join(TIPOS) + """. «dest»: «vivienda» (particulares), «edificio» (comunidades de propietarios) o ambos.
- «edad_min», «edad_max», «max_habitantes»: 0 si no hay límite.
- «url_solicitud»: dirección de la sede electrónica o del trámite, solo si aparece en los documentos.
- «dudas»: lo que la persona que revisa debe comprobar en las bases (máximo 4 frases).
- «referencia_bases»: si el documento es solo un extracto que remite a las bases publicadas en otro sitio (p. ej. «texto íntegro en el BOP nº 126 de 16/10/2026»), escribe dónde están (boletín, número y fecha). Si no, vacío.
- «documento_corresponde»: false si el documento adjunto no contiene las bases ni la convocatoria de ESTA ayuda (por ejemplo, un boletín que solo nombra al municipio por otro asunto). En ese caso no saques datos de él.
- «claridad»: «clara» solo si has leído las bases o la convocatoria oficial y en ellas constan el importe por vivienda (o el porcentaje con su máximo), el plazo (fecha final o «hasta agotar fondos»), los requisitos y cómo se pide, y no hay nada importante que dudar. Si te falta cualquiera de esas cosas o has tenido que suponer algo, «dudosa». Las claras se publican sin revisión humana: ante la duda, «dudosa»."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "es_ayuda_para_obras_en_vivienda": {"type": "boolean"},
        "motivo": {"type": "string"},
        "title": {"type": "string"},
        "resumen": {"type": "string"},
        "imp": {"type": "string"},
        "importe": {"type": "integer"},
        "abre": {"type": "string"},
        "cierra": {"type": "string"},
        "plazo": {"type": "string"},
        "req": {"type": "array", "items": {"type": "string"}},
        "docs": {"type": "array", "items": {"type": "string"}},
        "pasos": {"type": "array", "items": {"type": "string"}},
        "tipo": {"type": "array", "items": {"type": "string", "enum": TIPOS}},
        "dest": {"type": "array", "items": {"type": "string", "enum": ["vivienda", "edificio"]}},
        "edad_min": {"type": "integer"},
        "edad_max": {"type": "integer"},
        "max_habitantes": {"type": "integer"},
        "irpf": {"type": "boolean"},
        "url_solicitud": {"type": "string"},
        "dudas": {"type": "array", "items": {"type": "string"}},
        "claridad": {"type": "string", "enum": ["clara", "dudosa"]},
        "documento_corresponde": {"type": "boolean"},
        "referencia_bases": {"type": "string"},
    },
    "required": ["es_ayuda_para_obras_en_vivienda", "motivo", "title", "resumen", "imp", "importe", "abre", "cierra",
                 "plazo", "req", "docs", "pasos", "tipo", "dest", "edad_min", "edad_max", "max_habitantes", "irpf",
                 "url_solicitud", "dudas", "claridad", "documento_corresponde", "referencia_bases"],
    "additionalProperties": False,
}


def descargar(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(25_000_000)


def texto_html(datos):
    t = datos.decode("utf-8", "ignore")
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Muchas fichas de la BDNS ponen como «bases» un enlace que no lo es: una ley general, una ordenanza
# general de subvenciones, el presupuesto municipal o la portada de una sede o boletín.
GENERICOS = re.compile(r"boe\.es/eli/es/(l|rd|lo)/|BOE-A-2003-20977|BOE-A-2006-13371|BOE-A-2015-1056[56]|"
                       r"pressupost|presupuesto[-+ _]general|ordenanza[-+ _]general|reguladora\+de\+subvenciones|"
                       r"index\.php$|/info\.0$|BOP\.jsp$|becas-y-subvenciones/?$", re.I)


def enlace_generico(url):
    from urllib.parse import urlparse
    u = urlparse(url or "")
    return bool(GENERICOS.search(url or "")) or u.path.strip("/") == ""


def bloques_documento(url, pistas):
    """Contenido de las bases para el mensaje: el PDF entero si es corto; si no, solo las páginas útiles."""
    if not url or not url.startswith("http"):
        return [], "sin enlace a las bases"
    if enlace_generico(url):
        return [], "el enlace de bases de la BDNS es genérico (ley, ordenanza general o portada)"
    try:
        datos = descargar(url)
    except Exception as e:
        return [], f"no se pudo descargar ({e})"
    if datos[:4] != b"%PDF":
        texto = texto_html(datos)[:MAX_TEXTO]
        return ([{"type": "text", "text": f"Texto de la página de las bases ({url}):\n\n{texto}"}] if len(texto) > 200 else []), "página web"
    from pypdf import PdfReader
    pdf = PdfReader(io.BytesIO(datos))
    if len(pdf.pages) <= MAX_PDF_PAGINAS and len(datos) < 20_000_000:
        return [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                "data": base64.standard_b64encode(datos).decode()}}], f"PDF de {len(pdf.pages)} páginas"
    # Boletín entero: se buscan las páginas que nombran al organismo o al municipio (y la siguiente).
    paginas = [(p.extract_text() or "") for p in pdf.pages]
    claves = [k.lower() for k in pistas if k and len(k) > 3]
    tema = re.compile(r"subvenci|ayuda|rehabilit|vivienda|bases reguladoras|convocatoria", re.I)
    elegidas = sorted({j for i, t in enumerate(paginas) if any(k in t.lower() for k in claves) and tema.search(t)
                       for j in (i, i + 1) if j < len(paginas)})
    texto = "\n\n".join(f"[Página {i + 1}]\n{paginas[i]}" for i in elegidas)[:MAX_TEXTO]
    if not texto:
        return [], f"PDF de {len(pdf.pages)} páginas sin texto útil"
    return [{"type": "text", "text": f"Páginas del boletín ({url}) que mencionan la convocatoria:\n\n{texto}"}], f"{len(elegidas)} de {len(pdf.pages)} páginas"


def ficha_bdns(c):
    m = re.search(r"(\d{5,})", c.get("fuente", "") + " " + c.get("url", ""))
    if not m:
        return None
    for base in BDNS_BASES:
        try:
            return pedir_json(f"{base}/convocatorias", {"vpd": "GE", "numConv": m.group(1)}, intentos=2)
        except Exception:
            continue
    return None


# Si las bases descargadas no bastan (enlace a una portada, web que no se deja leer…), la IA puede
# buscar la convocatoria oficial en internet. Se limita el número de búsquedas para controlar el coste.
# Solo se ofrece cuando no se han podido leer bases útiles, porque es lo que más encarece cada ayuda.
HERRAMIENTAS = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 2},
                {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 3}]


def bases_utiles(bloques):
    return any(b["type"] == "document" or len(b.get("text", "")) > 4000 for b in bloques)


def preguntar(cliente, c, ficha, bloques, buscar=None, pista=""):
    if buscar is None:
        buscar = not bases_utiles(bloques)
    contexto = {k: c.get(k) for k in ("title", "org", "ccaa", "prov", "muni", "abre", "cierra", "url")}
    mensajes = [{"role": "user", "content": bloques + [{"type": "text", "text": (
        "Datos que ya tenemos de la convocatoria:\n" + json.dumps(contexto, ensure_ascii=False) +
        "\n\nFicha de la BDNS:\n" + json.dumps(ficha or {}, ensure_ascii=False)[:15_000] +
        ("\n\nNo se han podido leer las bases. Busca en internet la convocatoria o las bases oficiales (boletín "
         "oficial o sede del organismo) y léelas; usa solo fuentes oficiales y busca lo justo." if buscar else "") +
        (f"\n\nSegún el extracto, las bases completas están en: {pista}. Búscalas y léelas; complementa con ellas "
         "lo que ya sabes del extracto." if pista else "") +
        "\n\nExtrae los datos de la ficha de Reformayuda.")}]}]
    uso = {"entrada": 0, "salida": 0, "busquedas": 0}
    for _ in range(4):
        r = cliente.beta.messages.create(
            model=MODELO, max_tokens=16000, system=INSTRUCCIONES, messages=mensajes, **({"tools": HERRAMIENTAS} if buscar else {}),
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ESQUEMA}},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        uso["entrada"] += r.usage.input_tokens
        uso["salida"] += r.usage.output_tokens
        stu = getattr(r.usage, "server_tool_use", None)
        uso["busquedas"] += getattr(stu, "web_search_requests", 0) or 0
        if r.stop_reason != "pause_turn":
            break
        mensajes.append({"role": "assistant", "content": r.content})  # la búsqueda sigue en el servidor
    if r.stop_reason == "refusal":
        raise RuntimeError("la API rechazó la petición")
    if r.stop_reason in ("max_tokens", "pause_turn"):
        raise RuntimeError(f"respuesta incompleta ({r.stop_reason})")
    texto = [b.text for b in r.content if b.type == "text"][-1]
    return json.loads(texto[texto.index("{"):texto.rindex("}") + 1]), uso


def fecha_ok(v):
    try:
        return dt.date.fromisoformat(v).isoformat()
    except (TypeError, ValueError):
        return None


def aplicar(c, d, completa):
    """Pasa los datos extraídos a la ayuda. Con completa=False (ayudas ya publicadas) se mantienen título,
    resumen, tipo y destinatarios, y el resto se sustituye por lo que diga la convocatoria."""
    for k in ("title", "resumen") if completa else ():
        if d.get(k):
            c[k] = d[k].strip()
    for k in ("imp", "plazo"):
        if d.get(k):
            c[k] = d[k].strip()
    if d.get("importe"):
        c["importe"] = int(d["importe"])
    for k in ("abre", "cierra"):
        f = fecha_ok(d.get(k))
        if f:
            c[k] = f
    for k in ("req", "docs", "pasos"):
        lista = [x.strip() for x in d.get(k) or [] if x.strip()]
        if len(lista) >= 2:
            c[k] = lista[:8]
    if completa:
        if d.get("tipo"):
            c["tipo"] = [t for t in TIPOS if t in d["tipo"]]
        if d.get("dest"):
            c["dest"] = d["dest"]
        c["irpf"] = bool(d.get("irpf"))
    edad = {k: v for k, v in (("min", d.get("edad_min")), ("max", d.get("edad_max"))) if v}
    if edad:
        c["edad"] = edad
    if d.get("max_habitantes"):
        c["maxHab"] = int(d["max_habitantes"])
    if d.get("url_solicitud", "").startswith("http"):
        c["sede"] = d["url_solicitud"]


def muy_clara(c, d, bloques):
    """Solo se publica sin revisión si la IA la ve clara y además están todos los datos importantes."""
    hoy = dt.date.today().isoformat()
    return (d.get("claridad") == "clara" and (bloques or d.get("url_solicitud")) and c.get("importe", 0) > 0
            and not str(c.get("imp", "")).startswith(("Consulta", "No consta"))
            and (not c.get("cierra") or c["cierra"] >= hoy) and c.get("tipo")
            and all(len(c.get(k) or []) >= 2 for k in ("req", "docs", "pasos")))


def procesar(cliente, c, completa, informe):
    r = c.get("_revisar") or {}
    ficha = ficha_bdns(c)
    url_bases = r.get("bases_reguladoras") or (ficha or {}).get("urlBasesReguladoras") or ""
    bloques, como = bloques_documento(url_bases, [c.get("muni"), c.get("org", "").split("·")[0].strip(), c.get("title", "")[:40]])
    if enlace_generico(url_bases):
        r["bases_no_corresponden"] = True
    d, uso = preguntar(cliente, c, ficha, bloques)
    if bloques and not d.get("documento_corresponde", True):
        # El enlace de bases de la BDNS lleva a otro documento: se busca la convocatoria buena.
        como += " (no eran las bases de esta ayuda: buscada en internet)"
        r["bases_no_corresponden"] = True
        d, uso2 = preguntar(cliente, c, ficha, [], buscar=True)
        uso = {k: uso[k] + uso2[k] for k in uso}
    elif d.get("referencia_bases") and not d.get("importe"):
        # Era solo el extracto: las bases están en otro boletín. Se buscan una vez para sacar importe y requisitos.
        r["referencia_bases"] = d["referencia_bases"]
        como += f" (extracto; bases en {d['referencia_bases']})"
        d2, uso2 = preguntar(cliente, c, ficha, bloques, buscar=True, pista=d["referencia_bases"])
        uso = {k: uso[k] + uso2[k] for k in uso}
        if d2.get("importe") or len(d2.get("req") or []) >= len(d.get("req") or []):
            d = d2
    entrada, salida = PRECIO.get(MODELO, (2, 10))
    coste = (uso["entrada"] * entrada + uso["salida"] * salida) / 1e6 + uso["busquedas"] * 0.01  # 10 $ por 1.000 búsquedas
    informe["coste_usd"] += coste
    aplicar(c, d, completa)
    if completa:
        r["ia"] = {"fecha": dt.date.today().isoformat(), "documento": como,
                   "recomendacion": "publicar" if d["es_ayuda_para_obras_en_vivienda"] else "descartar",
                   "motivo": d.get("motivo", "")}
        r["confirmar"] = [x for x in d.get("dudas") or [] if x.strip()][:4]
        c["_revisar"] = r
        if not d["es_ayuda_para_obras_en_vivienda"]:
            c["estado"] = "descartada"  # no es de obras: no llega a tu lista (se puede recuperar en /revisar/)
        elif not r.get("no_auto") and muy_clara(c, d, bloques):
            c["estado"] = "aprobada"  # se publica sola; se puede retirar desde /revisar/
            r["ia"]["recomendacion"] = "publicada sola"
    else:
        c["ia"] = dt.date.today().isoformat()
    informe["procesadas"].append({"id": c["id"], "documento": como, "coste_usd": round(coste, 4),
                                  "recomendacion": (r.get("ia") or {}).get("recomendacion") if completa else "corregida"})
    print(f"  {c['id']}: {como} · {informe['procesadas'][-1]['recomendacion']} · {coste:.3f} $")


def main():
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("Sin ANTHROPIC_API_KEY: no se rellenan las candidatas con IA.")
        return
    import anthropic
    cliente = anthropic.Anthropic()
    mes = dt.date.today().strftime("%Y-%m")
    gasto = json.loads(GASTO.read_text(encoding="utf-8")) if GASTO.exists() else {"limite_usd": 15, "meses": {}}
    limite = float(os.environ.get("IA_LIMITE_MES") or gasto.get("limite_usd", 15))
    ya = gasto["meses"].get(mes, 0.0)
    informe = {"fecha": dt.datetime.now().isoformat(timespec="minutes"), "modelo": MODELO,
               "procesadas": [], "errores": [], "coste_usd": 0.0, "pendientes_por_tope": 0}

    def cabe():
        """Tope mensual: si no cabe una ayuda más, se deja para el mes siguiente (o para revisar a mano)."""
        return ya + informe["coste_usd"] + MARGEN_POR_AYUDA <= limite

    if "--publicadas" in sys.argv:
        ids = sys.argv[sys.argv.index("--publicadas") + 1].split(",")
        datos = json.loads(AYUDAS.read_text(encoding="utf-8"))
        for a in datos["ayudas"]:
            if a["id"] in ids and cabe():
                try:
                    procesar(cliente, a, False, informe)
                except Exception as e:
                    informe["errores"].append(f"{a['id']}: {type(e).__name__}: {str(e)[:200]}")
        AYUDAS.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    else:
        # Ayudas publicadas con datos genéricos («Consulta…», «confírmalo…»): se completan una vez.
        datos = json.loads(AYUDAS.read_text(encoding="utf-8"))
        incompletas = [a for a in datos["ayudas"] if a["id"].startswith("bdns-") and not a.get("ia")
                       and any(str(v).startswith("Consulta") or "confírma" in str(v).lower() for v in [a.get("imp")] + a.get("req", []))]
        for a in incompletas[:5]:
            if not cabe():
                informe["pendientes_por_tope"] += 1
                continue
            try:
                procesar(cliente, a, False, informe)
            except Exception as e:
                informe["errores"].append(f"{a['id']}: {type(e).__name__}: {str(e)[:200]}")
        if incompletas:
            AYUDAS.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        rev = json.loads(CANDIDATAS.read_text(encoding="utf-8"))
        cola = [c for c in rev["candidatas"] if c.get("estado", "pendiente") == "pendiente"
                and not (c.get("_revisar") or {}).get("ia") and not (c.get("_revisar") or {}).get("confirmar")]
        for c in cola[:int(os.environ.get("IA_MAX", "15"))]:
            if not cabe():
                informe["pendientes_por_tope"] += 1
                continue
            try:
                procesar(cliente, c, True, informe)
            except Exception as e:
                informe["errores"].append(f"{c['id']}: {type(e).__name__}: {str(e)[:200]}")
            CANDIDATAS.write_text(json.dumps(rev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    informe["coste_usd"] = round(informe["coste_usd"], 3)
    gasto["meses"][mes] = round(ya + informe["coste_usd"], 3)
    gasto["limite_usd"] = gasto.get("limite_usd", 15)
    GASTO.write_text(json.dumps(gasto, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    informe["gasto_mes_usd"], informe["limite_mes_usd"] = gasto["meses"][mes], limite
    if informe["pendientes_por_tope"]:
        print(f"Tope mensual de {limite} $ alcanzado: {informe['pendientes_por_tope']} se quedan sin rellenar (revísalas a mano).")
    DIAGNOSTICO.write_text(json.dumps(informe, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Procesadas: {len(informe['procesadas'])}. Errores: {len(informe['errores'])}. Coste aproximado: {informe['coste_usd']} $")
    for e in informe["errores"]:
        print("  error", e, file=sys.stderr)


if __name__ == "__main__":
    main()

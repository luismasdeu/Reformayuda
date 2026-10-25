#!/usr/bin/env python3
"""Busca ayudas nuevas de vivienda en el BOE y en la Base de Datos Nacional de
Subvenciones (BDNS) y las deja en revision/candidatas.json para revisarlas.

No publica nada: solo propone. Una persona revisa cada candidata y la aprueba
o la descarta (ver README.md). Solo usa la biblioteca estándar de Python.

Uso:
  python scripts/actualizar.py            # busca en los últimos 3 días
  python scripts/actualizar.py --dias 30  # primera carga o recuperación
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AYUDAS = RAIZ / "web" / "data" / "ayudas.json"
CANDIDATAS = RAIZ / "revision" / "candidatas.json"
DESCARTADAS = RAIZ / "revision" / "descartadas.json"

USER_AGENT = "Reformayuda/1.0 (+https://reformayuda.es; busqueda diaria de ayudas de vivienda)"
BOE_SUMARIO = "https://www.boe.es/datosabiertos/api/boe/sumario/{fecha}"
BDNS_BASES = ["https://www.infosubvenciones.es/bdnstrans/api", "https://www.pap.hacienda.gob.es/bdnstrans/api"]
BDNS_FICHA = "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/{codigo}"

# Búsquedas en la BDNS. Cada una es una consulta; se juntan y se quitan duplicados.
BDNS_BUSQUEDAS = ["vivienda", "rehabilitación", "eficiencia energética", "accesibilidad", "autoconsumo", "fachada", "ascensor"]
MAX_FICHAS_BDNS = 80  # fichas de detalle por ejecución, para no cargar el servicio

# Palabras que indican que una convocatoria nos interesa (se comparan sin tildes y en minúsculas).
TEMA = ["vivienda", "eficiencia energetica", "accesibilidad", "ascensor", "fachada", "cubierta",
        "aislamiento", "autoconsumo", "fotovoltaic", "aerotermia", "bomba de calor", "biomasa", "amianto",
        "edificio residencial", "comunidad de propietarios", "renovacion urbana", "regeneracion urbana"]
AYUDA = ["ayuda", "subvencion", "convocatoria", "bases reguladoras", "programa de", "plan de"]
EXCLUIR = ["alquiler", "arrendatari", "desahucio", "personal funcionario", "oposicion", "contratacion", "licitacion",
           "nombramiento", "empresa", "pyme", "industria", "agrari", "ganader", "universidad", "plan de estudios",
           # subvenciones a entidades concretas, no abiertas a particulares
           "nominativa", "nominada", "subvencion directa a", "convenio", "fundacio", "asociacio", "a ayuntamientos",
           "subvenciones ayuntamientos", "entidades locales",
           # «rehabilitación» en otros sentidos u obras públicas
           "fisioterap", "salud mental", "saude mental", "rehabilitacion fisica", "drogodependencia",
           "cementerio", "casa consistorial", "parque infantil", "gastos basicos", "notaria"]

# Tipo de obra a partir de palabras clave.
TIPOS = {
    "solar": ["fotovoltaic", "autoconsumo", "placas solares", "solar termica", "renovable"],
    "aerotermia": ["aerotermia", "bomba de calor", "biomasa", "calefaccion", "climatizacion"],
    "ventanas": ["ventana", "carpinteria", "cerramiento"],
    "accesibilidad": ["accesibilidad", "ascensor", "barreras", "discapacidad", "salvaescaleras"],
    "construccion": ["construccion de vivienda", "nueva construccion", "obra nueva", "adquisicion o construccion"],
    "eficiencia": ["eficiencia energetica", "aislamiento", "envolvente", "rehabilitacion energetica", "fachada", "cubierta"],
    "rehabilitacion": ["rehabilit", "conservacion", "renovacion", "regeneracion", "reforma"],
}

# Códigos NUTS (los usa la BDNS en "regiones") → comunidad autónoma y provincia.
NUTS2 = {"ES11": "Galicia", "ES12": "Asturias", "ES13": "Cantabria", "ES21": "País Vasco", "ES22": "Navarra",
         "ES23": "La Rioja", "ES24": "Aragón", "ES30": "Comunidad de Madrid", "ES41": "Castilla y León",
         "ES42": "Castilla-La Mancha", "ES43": "Extremadura", "ES51": "Cataluña", "ES52": "Comunitat Valenciana",
         "ES53": "Illes Balears", "ES61": "Andalucía", "ES62": "Región de Murcia", "ES63": "Ceuta",
         "ES64": "Melilla", "ES70": "Canarias"}
NUTS3 = {"ES111": "A Coruña", "ES112": "Lugo", "ES113": "Ourense", "ES114": "Pontevedra", "ES120": "Asturias",
         "ES130": "Cantabria", "ES211": "Álava", "ES212": "Gipuzkoa", "ES213": "Bizkaia", "ES220": "Navarra",
         "ES230": "La Rioja", "ES241": "Huesca", "ES242": "Teruel", "ES243": "Zaragoza", "ES300": "Madrid",
         "ES411": "Ávila", "ES412": "Burgos", "ES413": "León", "ES414": "Palencia", "ES415": "Salamanca",
         "ES416": "Segovia", "ES417": "Soria", "ES418": "Valladolid", "ES419": "Zamora", "ES421": "Albacete",
         "ES422": "Ciudad Real", "ES423": "Cuenca", "ES424": "Guadalajara", "ES425": "Toledo", "ES431": "Badajoz",
         "ES432": "Cáceres", "ES511": "Barcelona", "ES512": "Girona", "ES513": "Lleida", "ES514": "Tarragona",
         "ES521": "Alicante", "ES522": "Castellón", "ES523": "Valencia", "ES531": "Illes Balears",
         "ES532": "Illes Balears", "ES533": "Illes Balears", "ES611": "Almería", "ES612": "Cádiz",
         "ES613": "Córdoba", "ES614": "Granada", "ES615": "Huelva", "ES616": "Jaén", "ES617": "Málaga",
         "ES618": "Sevilla", "ES620": "Murcia", "ES630": "Ceuta", "ES640": "Melilla", "ES703": "Santa Cruz de Tenerife",
         "ES704": "Las Palmas", "ES705": "Las Palmas", "ES706": "Santa Cruz de Tenerife",
         "ES707": "Santa Cruz de Tenerife", "ES708": "Las Palmas", "ES709": "Santa Cruz de Tenerife"}


def sin_tildes(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def contiene(texto, palabras):
    return any(p in texto for p in palabras)


def es_de_vivienda(texto):
    t = sin_tildes(texto)
    # «rehabilitación» solo cuenta si habla de viviendas o edificios (no de fisioterapia ni de obras públicas)
    rehab = "rehabilit" in t and contiene(t, ["vivienda", "edific", "fachada", "inmueble"])
    return (contiene(t, TEMA) or rehab) and contiene(t, AYUDA) and not contiene(t, EXCLUIR)


def pedir_json(url, params=None, intentos=4):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    espera = 1.0
    for intento in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if intento == intentos - 1:
                raise
        except Exception:
            if intento == intentos - 1:
                raise
        time.sleep(espera)
        espera *= 2
    return None


def leer(ruta, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defecto


def guardar(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------- BOE ----------

def items_boe(nodo):
    """Recorre el sumario sin depender de su estructura exacta: devuelve todo lo que parezca una disposición."""
    if isinstance(nodo, dict):
        if "identificador" in nodo and "titulo" in nodo:
            yield nodo
        for v in nodo.values():
            yield from items_boe(v)
    elif isinstance(nodo, list):
        for v in nodo:
            yield from items_boe(v)


def url_de(valor):
    if isinstance(valor, dict):
        return valor.get("texto") or valor.get("url") or ""
    return valor or ""


def buscar_boe(dias):
    encontrados = []
    hoy = dt.date.today()
    for n in range(dias):
        fecha = hoy - dt.timedelta(days=n)
        try:
            datos = pedir_json(BOE_SUMARIO.format(fecha=fecha.strftime("%Y%m%d")))
        except Exception as e:
            print(f"  BOE {fecha}: error ({e})", file=sys.stderr)
            continue
        if not datos:
            continue  # domingo o festivo sin BOE
        for it in items_boe(datos):
            if es_de_vivienda(it["titulo"]):
                encontrados.append({
                    "id": it["identificador"],
                    "fecha": fecha.isoformat(),
                    "titulo": it["titulo"].strip(),
                    "url": url_de(it.get("url_html")) or url_de(it.get("url_pdf")),
                    "pdf": url_de(it.get("url_pdf")),
                })
    print(f"BOE: {len(encontrados)} disposiciones de vivienda en {dias} días")
    return encontrados


# ---------- BDNS ----------

def lista_de(respuesta):
    if isinstance(respuesta, list):
        return respuesta
    if isinstance(respuesta, dict):
        for clave in ("content", "convocatorias", "data", "items", "results"):
            if isinstance(respuesta.get(clave), list):
                return respuesta[clave]
    return []


def fecha_iso(valor):
    if not valor:
        return None
    valor = str(valor)[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(valor, formato).date().isoformat()
        except ValueError:
            pass
    return None


def texto_de(valor):
    if isinstance(valor, list):
        return " ".join(texto_de(v) for v in valor)
    if isinstance(valor, dict):
        return " ".join(texto_de(v) for v in valor.values())
    return str(valor or "")


def ambito_bdns(ficha):
    organo = ficha.get("organo") or {}
    n1 = sin_tildes(organo.get("nivel1") or ficha.get("nivel1"))
    n2 = organo.get("nivel2") or ficha.get("nivel2") or ""
    n3 = organo.get("nivel3") or ficha.get("nivel3") or ""
    regiones = re.findall(r"ES\d{2,3}", texto_de(ficha.get("regiones")))
    ccaa = next((NUTS2[r[:4]] for r in regiones if r[:4] in NUTS2), None)
    prov = next((NUTS3[r] for r in regiones if r in NUTS3), None)
    nombre_organo = " · ".join(x for x in (n2, n3) if x).strip() or "Organismo convocante"
    if "estado" in n1:
        return "estatal", "all", None, None, nombre_organo
    if "local" in n1:
        if contiene(sin_tildes(n2), ["diputaci", "cabildo", "consell", "diputacion foral"]):
            return "provincial", ccaa or "all", prov, None, nombre_organo
        m = re.search(r"ayuntamiento de (.+)", n2, re.I) or re.search(r"ayuntamiento de (.+)", n3, re.I)
        muni = m.group(1).strip().title() if m else None
        return "municipal", ccaa or "all", prov, muni, nombre_organo
    return "autonomica", ccaa or "all", None, None, nombre_organo


def tipos_de(texto):
    t = sin_tildes(texto)
    tipos = [k for k, palabras in TIPOS.items() if contiene(t, palabras)]
    return tipos or ["rehabilitacion"]


def destinatarios(t):
    edificio = contiene(t, ["comunidad de propietarios", "comunidades de propietarios", "edificio"])
    vivienda = contiene(t, ["vivienda", "persona fisica", "personas fisicas"]) or not edificio
    return [d for d, si in (("vivienda", vivienda), ("edificio", edificio)) if si]


def candidata_bdns(ficha):
    codigo = str(ficha.get("codigoBDNS") or ficha.get("numeroConvocatoria") or ficha.get("id"))
    titulo = (ficha.get("descripcion") or ficha.get("tituloConvocatoria") or "").strip()
    finalidad = (ficha.get("descripcionFinalidad") or "").strip()
    texto = f"{titulo} {finalidad} {texto_de(ficha.get('tiposBeneficiarios'))}"
    t = sin_tildes(texto)
    scope, ccaa, prov, muni, organo = ambito_bdns(ficha)
    importe = ficha.get("presupuestoTotal") or ficha.get("importeTotal") or ficha.get("importe") or 0
    c = {
        "id": f"bdns-{codigo}",
        "estado": "pendiente",
        "title": titulo[:160] or f"Convocatoria BDNS {codigo}",
        "org": organo,
        "scope": scope,
        "ccaa": ccaa,
        "tipo": tipos_de(texto),
        "dest": destinatarios(t),
        "importe": 0,
        "imp": "Consulta la convocatoria",
        "abre": fecha_iso(ficha.get("fechaInicioSolicitud") or ficha.get("fechaRecepcion")) or dt.date.today().isoformat(),
        "cierra": fecha_iso(ficha.get("fechaFinSolicitud")),
        "plazo": "Consulta el plazo en la convocatoria",
        "irpf": contiene(t, ["eficiencia energetica", "rehabilitacion energetica"]),
        "fuente": f"BDNS nº {codigo}",
        "url": BDNS_FICHA.format(codigo=codigo),
        "resumen": (finalidad or titulo)[:400],
        "req": ["Consulta los requisitos en la convocatoria oficial"],
        "docs": ["Consulta la documentación en la convocatoria oficial"],
        "pasos": ["Lee la convocatoria oficial", "Prepara la documentación", "Presenta la solicitud en la sede del organismo"],
        "_revisar": {
            "presupuesto_total": importe,
            "bases_reguladoras": ficha.get("urlBasesReguladoras") or ficha.get("sedeElectronica"),
            "abierta_segun_bdns": ficha.get("abierto"),
            "beneficiarios": texto_de(ficha.get("tiposBeneficiarios"))[:300],
            "nota": "Revisa importe por vivienda, requisitos, documentos y pasos antes de aprobar.",
        },
    }
    if prov:
        c["prov"] = prov
    if muni:
        c["muni"] = muni
    m = re.search(r"menos de ([\d\.]+) habitantes", t)
    if m:
        c["maxHab"] = int(m.group(1).replace(".", ""))
    if contiene(t, ["menores de 35", "jovenes", "joven "]):
        c["edad"] = {"max": 35}
    elif contiene(t, ["mayores de 65", "personas mayores"]):
        c["edad"] = {"min": 65}
    return c


def buscar_bdns(dias):
    base = None
    for b in BDNS_BASES:
        try:
            pedir_json(f"{b}/convocatorias/busqueda", {"vpd": "GE", "page": 0, "pageSize": 1}, intentos=2)
            base = b
            break
        except Exception as e:
            print(f"  BDNS {b}: no responde ({e})", file=sys.stderr)
    if not base:
        print("BDNS: sin conexión, se reintentará mañana")
        return []
    desde = (dt.date.today() - dt.timedelta(days=dias)).strftime("%d/%m/%Y")
    numeros = []
    for palabra in BDNS_BUSQUEDAS:
        try:
            r = pedir_json(f"{base}/convocatorias/busqueda",
                           {"vpd": "GE", "page": 0, "pageSize": 50, "fechaDesde": desde, "descripcion": palabra})
        except Exception as e:
            print(f"  BDNS '{palabra}': error ({e})", file=sys.stderr)
            continue
        for item in lista_de(r):
            num = item.get("numeroConvocatoria") or item.get("codigoBDNS") or item.get("id")
            if num and num not in numeros:
                numeros.append(num)
        time.sleep(0.5)
    candidatas = []
    for num in numeros[:MAX_FICHAS_BDNS]:
        try:
            ficha = pedir_json(f"{base}/convocatorias", {"vpd": "GE", "numConv": num})
        except Exception as e:
            print(f"  BDNS ficha {num}: error ({e})", file=sys.stderr)
            continue
        if not ficha:
            continue
        texto = f"{ficha.get('descripcion', '')} {ficha.get('descripcionFinalidad', '')}"
        benef = sin_tildes(texto_de(ficha.get("tiposBeneficiarios")))
        # Fuera las que son solo para empresas; dentro particulares y comunidades de propietarios.
        solo_empresas = contiene(benef, ["pyme", "empresa"]) and not contiene(benef, ["no desarrollan actividad", "personas fisicas que no", "comunidad"])
        if es_de_vivienda(texto) and not solo_empresas:
            c = candidata_bdns(ficha)
            if c["cierra"] and c["cierra"] < dt.date.today().isoformat():
                continue  # ya cerrada: no merece la pena revisarla
            candidatas.append(c)
        time.sleep(0.4)
    print(f"BDNS: {len(numeros)} convocatorias revisadas, {len(candidatas)} de vivienda")
    return candidatas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=3, help="días hacia atrás que se revisan")
    args = ap.parse_args()

    publicadas = {a["id"] for a in leer(AYUDAS, {"ayudas": []})["ayudas"]}
    descartadas = set(leer(DESCARTADAS, {"ids": []})["ids"])
    rev = leer(CANDIDATAS, {"candidatas": [], "boe": []})
    ya = publicadas | descartadas | {c["id"] for c in rev["candidatas"]} | {b["id"] for b in rev["boe"]}

    nuevas = [c for c in buscar_bdns(args.dias) if c["id"] not in ya]
    nuevas_boe = [b for b in buscar_boe(args.dias) if b["id"] not in ya]

    rev["candidatas"].extend(nuevas)
    rev["boe"].extend(nuevas_boe)
    rev["ultima_busqueda"] = dt.datetime.now().isoformat(timespec="minutes")
    guardar(CANDIDATAS, rev)

    pendientes = sum(1 for c in rev["candidatas"] if c.get("estado") == "pendiente")
    print(f"Nuevas: {len(nuevas)} de la BDNS y {len(nuevas_boe)} del BOE. Pendientes de revisar: {pendientes}.")
    # Resumen para el aviso de GitHub
    (RAIZ / "revision" / "resumen.md").write_text(resumen(nuevas, nuevas_boe, pendientes, rev["boe"]), encoding="utf-8")
    salida = os.environ.get("GITHUB_OUTPUT")
    if salida:
        with open(salida, "a", encoding="utf-8") as f:
            f.write(f"nuevas={len(nuevas) + len(nuevas_boe)}\n")


def resumen(nuevas, nuevas_boe, pendientes, boe_total):
    lineas = [f"Búsqueda del {dt.date.today().strftime('%d/%m/%Y')}.", "",
              f"**{len(nuevas)}** convocatorias nuevas de la BDNS y **{len(nuevas_boe)}** disposiciones del BOE.",
              f"Pendientes de revisar en total: **{pendientes}**.", ""]
    if nuevas:
        lineas.append("### Nuevas en la BDNS")
        lineas += [f"- [{c['title'][:110]}]({c['url']}) · {c['org'][:60]} · cierra {c['cierra'] or 'sin fecha'}" for c in nuevas]
        lineas.append("")
    if nuevas_boe:
        lineas.append("### Nuevas en el BOE (solo aviso: leer y, si es una ayuda, darla de alta a mano)")
        lineas += [f"- [{b['titulo'][:140]}]({b['url']})" for b in nuevas_boe]
        lineas.append("")
    lineas.append("Para revisar: abre `revision/candidatas.json`, cambia `\"estado\"` a `\"aprobada\"` o `\"descartada\"` y guarda. Mira el README.")
    return "\n".join(lineas) + "\n"


if __name__ == "__main__":
    main()

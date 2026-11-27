#!/usr/bin/env python3
"""Publicaciones automáticas de Obrayuda en Instagram y Facebook.

Lo lanza .github/workflows/redes.yml una vez al día:

  python scripts/redes/redes.py planificar   → decide qué toca hoy y deja su spec en
                                              docs/redes/publicadas/<fecha>-<nombre>/
  (node scripts/redes/carrusel.mjs genera las imágenes y el workflow las sube al repositorio)
  python scripts/redes/redes.py publicar DIR → publica ese carrusel en Instagram y Facebook

Calendario semanal:
  lunes, miércoles y viernes → una ayuda abierta (la mejor que aún no se haya publicado)
  martes, jueves y sábado    → un consejo del banco (docs/redes/banco/, en orden)
  domingo                    → descanso
Si un día no hay ayuda nueva, publica un consejo, y al revés.

Una ayuda puede tener un carrusel hecho a mano en docs/redes/ayudas/<id>.json; si no,
se genera solo con sus datos. Todo queda apuntado en revision/redes.json.

Necesita el secreto META_PAGE_TOKEN (token de la página de Facebook con permisos de
Instagram). Sin él no hace nada.
"""
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

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
from telegram import fecha, lugar  # noqa: E402

AYUDAS = RAIZ / "web" / "data" / "ayudas.json"
REGISTRO = RAIZ / "revision" / "redes.json"
BANCO = RAIZ / "docs" / "redes" / "banco"
HECHAS_A_MANO = RAIZ / "docs" / "redes" / "ayudas"
PUBLICADAS = RAIZ / "docs" / "redes" / "publicadas"
API = "https://graph.facebook.com/" + (os.environ.get("META_API_VERSION") or "v27.0")
DIAS_AYUDA, DIAS_CONSEJO = {0, 2, 4}, {1, 3, 5}
GENERICO = re.compile(r"^consulta (los|la) ", re.I)


def hoy():
    return dt.date.fromisoformat(os.environ["HOY"]) if os.environ.get("HOY") else dt.date.today()


def leer_registro():
    if REGISTRO.exists():
        return json.loads(REGISTRO.read_text(encoding="utf-8"))
    return {"publicadas": []}


def guardar_registro(r):
    REGISTRO.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def corta(texto, limite):
    texto = texto.strip().rstrip(".")
    return texto if len(texto) <= limite else texto[:limite].rsplit(" ", 1)[0] + "…"


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", t)


# ---------- qué toca hoy ----------

def completa(a):
    """En redes solo salen ayudas con los datos completos (sin «pendiente de las bases»)."""
    if a.get("pendiente_bases") or "pendiente" in a.get("imp", "").lower():
        return False
    return "no he podido" not in a.get("resumen", "").lower() and len(a.get("req", [])) >= 2


def candidatas(ayudas, ya, d):
    limite = (d + dt.timedelta(days=7)).isoformat()  # que dé tiempo a pedirla
    peso = {"estatal": 3, "autonomica": 2, "provincial": 1}
    out = [a for a in ayudas if a["id"] not in ya and a["abre"] <= d.isoformat()
           and (not a.get("cierra") or a["cierra"] >= limite) and completa(a)]
    out.sort(key=lambda a: ((HECHAS_A_MANO / f"{a['id']}.json").exists(), a.get("importe", 0) > 0,
                            peso.get(a.get("scope"), 0), a.get("importe", 0)), reverse=True)
    return out


def cifra(a):
    m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?\s?€", a.get("imp", ""))
    return f"Hasta {m.group(1)} €" if m else None


def plazo_texto(a, d):
    if a.get("cierra"):
        return f"Plazo hasta el {fecha(a['cierra'])}"
    return "Plazo abierto"


def hashtags(a):
    por_tipo = {"rehabilitacion": "#rehabilitacion", "eficiencia": "#eficienciaenergetica",
                "accesibilidad": "#accesibilidad", "solar": "#placassolares", "ventanas": "#ventanas",
                "aerotermia": "#aerotermia"}
    tags = ["#ayudasvivienda", "#subvenciones"]
    tags += [por_tipo[t] for t in a.get("tipo", []) if t in por_tipo][:1]
    zona = a.get("muni") or a.get("prov") or ("" if a["ccaa"] == "all" else a["ccaa"])
    if zona:
        tags.append("#" + slug(zona))
    tags.append("#reformas")
    return " ".join(list(dict.fromkeys(tags))[:5])


def spec_de_ayuda(a, d):
    """Carrusel generado con los datos de la ayuda."""
    sitio = lugar(a)
    zona = a.get("muni") or a.get("prov") or ("Toda España" if a["ccaa"] == "all" else a["ccaa"])
    portada = {"tipo": "portada", "ceja": corta(f"Ayuda abierta · {zona}", 48), "titulo": a["title"],
               "sub": plazo_texto(a, d)}
    if cifra(a):
        portada["cifra"] = cifra(a)
    else:
        portada["sub"] = corta(a.get("imp", ""), 90) + " · " + plazo_texto(a, d)
    slides = [portada]
    reqs = [r for r in a.get("req", []) if not GENERICO.match(r)]
    if len(reqs) >= 2:
        slides.append({"tipo": "lista", "ceja": "Quién puede pedirla", "titulo": "Requisitos", "marcas": "check",
                       "puntos": [corta(r, 110) for r in reqs[:4]]})
    elif a.get("resumen"):
        slides.append({"tipo": "texto", "ceja": "En qué consiste", "titulo": "Lo importante",
                       "texto": corta(a["resumen"], 330)})
    pasos = [p for p in a.get("pasos", []) if not GENERICO.match(p)]
    if pasos:
        slides.append({"tipo": "lista", "ceja": "Cómo pedirla", "titulo": "Paso a paso",
                       "puntos": [corta(p, 100) for p in pasos[:4]],
                       "nota": f"Fuente: {a.get('fuente', 'convocatoria oficial')}. Obrayuda no es un organismo público."})
    slides.append({"tipo": "cta", "titulo": "Comenta **AYUDA**\ny te paso el enlace oficial",
                   "sub": "Compártelo con quien vaya a hacer obra."})
    bloques = [
        f"🏠 {a['title']}",
        "\n".join(filter(None, [f"📍 {sitio}", f"💶 {a['imp']}" if a.get("imp") else "", f"📅 {plazo_texto(a, d)}"])),
        corta(a["resumen"], 600) + "." if a.get("resumen") else "",
        "💬 Comenta AYUDA y te paso el enlace oficial.\n🔎 Más ayudas de tu zona: obrayuda.es (enlace en el perfil)",
        f"Fuente: {a.get('fuente', 'convocatoria oficial')}. Obrayuda no es un organismo público.",
        hashtags(a)]
    texto = "\n\n".join(b for b in bloques if b)
    return {"slides": slides, "texto": texto}


def planificar():
    d = hoy()
    reg = leer_registro()
    if any(p["fecha"] == d.isoformat() and p.get("instagram") for p in reg["publicadas"]):
        print("Hoy ya se ha publicado.")
        return
    ya_ayudas = {p["ayuda"] for p in reg["publicadas"] if p.get("ayuda") and p.get("instagram")}
    ya_banco = {p["nombre"] for p in reg["publicadas"] if p.get("tipo") == "consejo" and p.get("instagram")}
    banco = [f for f in sorted(BANCO.glob("*.json")) if f.stem not in ya_banco]
    ayudas = candidatas(json.loads(AYUDAS.read_text(encoding="utf-8"))["ayudas"], ya_ayudas, d)

    eleccion = None
    if not any(p.get("instagram") for p in reg["publicadas"]) and banco:
        eleccion = ("consejo", banco[0])  # la primera publicación: qué es Obrayuda
    elif d.weekday() == 6 and not os.environ.get("FORZAR"):
        print("Domingo: descanso.")
        return
    elif d.weekday() in DIAS_AYUDA:
        eleccion = ("ayuda", ayudas[0]) if ayudas else (("consejo", banco[0]) if banco else None)
    else:
        eleccion = ("consejo", banco[0]) if banco else (("ayuda", ayudas[0]) if ayudas else None)
    if not eleccion:
        print("No hay nada nuevo que publicar.")
        return

    tipo, cosa = eleccion
    if tipo == "consejo":
        nombre, spec, ayuda = cosa.stem, json.loads(cosa.read_text(encoding="utf-8")), None
    else:
        nombre, ayuda = cosa["id"], cosa["id"]
        a_mano = HECHAS_A_MANO / f"{cosa['id']}.json"
        spec = json.loads(a_mano.read_text(encoding="utf-8")) if a_mano.exists() else spec_de_ayuda(cosa, d)
    carpeta = PUBLICADAS / f"{d.isoformat()}-{nombre}"
    carpeta.mkdir(parents=True, exist_ok=True)
    spec.update({"tipo": tipo, "nombre": nombre, "ayuda": ayuda, "fecha": d.isoformat()})
    (carpeta / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Hoy toca {tipo}: {nombre}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"carpeta={carpeta.relative_to(RAIZ)}\n")


# ---------- publicar en Meta ----------

def graph(metodo, ruta, token, **datos):
    datos["access_token"] = token
    if metodo == "GET":
        req = urllib.request.Request(f"{API}/{ruta}?{urllib.parse.urlencode(datos)}")
    else:
        req = urllib.request.Request(f"{API}/{ruta}", data=urllib.parse.urlencode(datos).encode())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as ex:
        raise RuntimeError(f"{ruta}: {ex.code} {ex.read().decode('utf-8', 'replace')[:400]}") from None


def esperar_url(url):
    for _ in range(20):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200:
                    return
        except urllib.error.URLError:
            pass
        time.sleep(6)
    raise RuntimeError(f"La imagen no está disponible: {url}")


def publicar_instagram(token, ig, urls, texto):
    hijos = [graph("POST", f"{ig}/media", token, image_url=u, is_carousel_item="true")["id"] for u in urls]
    contenedor = graph("POST", f"{ig}/media", token, media_type="CAROUSEL", children=",".join(hijos),
                       caption=texto)["id"]
    for _ in range(30):
        estado = graph("GET", contenedor, token, fields="status_code").get("status_code")
        if estado == "FINISHED":
            break
        if estado in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram no pudo preparar el carrusel ({estado})")
        time.sleep(5)
    return graph("POST", f"{ig}/media_publish", token, creation_id=contenedor)["id"]


def publicar_facebook(token, pagina, urls, texto):
    fotos = [graph("POST", f"{pagina}/photos", token, url=u, published="false")["id"] for u in urls]
    datos = {f"attached_media[{i}]": json.dumps({"media_fbid": f}) for i, f in enumerate(fotos)}
    return graph("POST", f"{pagina}/feed", token, message=texto, **datos)["id"]


def publicar(carpeta):
    token = os.environ.get("META_PAGE_TOKEN", "").strip()
    carpeta = RAIZ / carpeta
    spec = json.loads((carpeta / "spec.json").read_text(encoding="utf-8"))
    repo = os.environ.get("GITHUB_REPOSITORY", "luismasdeu/Reformayuda")
    base = f"https://raw.githubusercontent.com/{repo}/main/{carpeta.relative_to(RAIZ).as_posix()}"
    urls = [f"{base}/{f.name}" for f in sorted(carpeta.glob("slide-*.jpg"))]
    for u in urls:
        esperar_url(u)
    pagina = graph("GET", "me", token, fields="id,name")["id"]
    ig = graph("GET", pagina, token, fields="instagram_business_account").get("instagram_business_account", {}).get("id")
    entrada = {"fecha": spec["fecha"], "nombre": spec["nombre"], "tipo": spec["tipo"]}
    if spec.get("ayuda"):
        entrada["ayuda"] = spec["ayuda"]
    errores = []
    if ig:
        try:
            entrada["instagram"] = publicar_instagram(token, ig, urls, spec["texto"])
            print("Publicado en Instagram:", entrada["instagram"])
        except RuntimeError as ex:
            errores.append(f"Instagram: {ex}")
    else:
        errores.append("Instagram: la página no tiene una cuenta de Instagram vinculada")
    try:
        entrada["facebook"] = publicar_facebook(token, pagina, urls, spec["texto"])
        print("Publicado en Facebook:", entrada["facebook"])
    except RuntimeError as ex:
        errores.append(f"Facebook: {ex}")
    if errores:
        entrada["error"] = " | ".join(errores)
    reg = leer_registro()
    reg["publicadas"].append(entrada)
    guardar_registro(reg)
    if errores:
        print("\n".join(errores))
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "planificar":
        planificar()
    elif len(sys.argv) >= 3 and sys.argv[1] == "publicar":
        publicar(sys.argv[2])
    else:
        sys.exit(__doc__)

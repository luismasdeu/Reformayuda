#!/usr/bin/env python3
"""Genera páginas estáticas para Google y las inteligencias artificiales.

La app (web/index.html) se rellena con JavaScript y vive en una sola dirección.
Este script crea, a partir de los mismos datos, páginas con el texto ya escrito:

  web/ayudas/<ayuda>/            una página por ayuda publicada
  web/subvenciones/              índice de todas las ayudas
  web/subvenciones/<tipo>/       por tipo de obra (placas solares, ventanas…)
  web/subvenciones/<comunidad>/  por comunidad autónoma (y por tipo dentro de ella)
  web/preguntas/                 las preguntas frecuentes del asistente
  web/llms.txt                   resumen para inteligencias artificiales
  web/sitemap.xml                todas las direcciones

Se ejecuta en GitHub antes de cada publicación. Las páginas no se guardan en el
repositorio (están en .gitignore): se regeneran siempre desde los datos.
"""
import datetime as dt
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"
DOMINIO = "https://reformayuda.es"
HOY = dt.date.today()

TIPOS = {
    "eficiencia": ("Eficiencia energética y aislamiento", "eficiencia-energetica", "mejorar la eficiencia energética y el aislamiento de tu casa"),
    "solar": ("Placas solares y autoconsumo", "placas-solares", "instalar placas solares en casa"),
    "aerotermia": ("Aerotermia y calefacción", "aerotermia", "aerotermia y calefacción eficiente"),
    "ventanas": ("Ventanas y cerramientos", "ventanas", "cambiar las ventanas de casa"),
    "accesibilidad": ("Ascensor y accesibilidad", "accesibilidad", "ascensores y accesibilidad en viviendas"),
    "rehabilitacion": ("Rehabilitar o reformar", "rehabilitacion-y-reforma", "rehabilitar o reformar tu casa"),
    "construccion": ("Construir vivienda", "construir-vivienda", "construir una vivienda"),
}
CCAA = ["Andalucía", "Aragón", "Asturias", "Illes Balears", "Canarias", "Cantabria", "Castilla y León",
        "Castilla-La Mancha", "Cataluña", "Comunitat Valenciana", "Extremadura", "Galicia", "Comunidad de Madrid",
        "Región de Murcia", "Navarra", "País Vasco", "La Rioja", "Ceuta", "Melilla"]
PERMISO = {
    "eficiencia": ("Depende de la obra", "Aislar por dentro: declaración responsable. Aislar la fachada o el tejado por fuera: licencia en muchos municipios."),
    "solar": ("Declaración responsable", "En la mayoría de comunidades basta con declaración responsable o comunicación previa. En edificios protegidos o suelo rústico, licencia."),
    "aerotermia": ("Declaración responsable", "Declaración responsable. Si la máquina exterior va en la fachada o en el tejado común, avisa también a la comunidad."),
    "ventanas": ("Declaración responsable", "Declaración responsable si mantienes el aspecto de la fachada. Si lo cambias, licencia y permiso de la comunidad."),
    "accesibilidad": ("Depende de la obra", "Rampas, baño adaptado o salvaescaleras: declaración responsable. Ascensor nuevo: licencia con proyecto."),
    "rehabilitacion": ("Licencia de obra", "Si tocas estructura, fachada o tejado: licencia. Si solo son acabados interiores: declaración responsable."),
    "construccion": ("Licencia de obra", "Siempre licencia de obra mayor, con proyecto de arquitecto."),
}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
AVISO = ("Reformayuda no es una web oficial ni está vinculada a ninguna administración. La información es orientativa "
         "y procede de fuentes oficiales; antes de solicitar una ayuda, consulta siempre la convocatoria original.")

e = lambda t: html.escape(str(t or ""), quote=True)


def slug(texto):
    t = unicodedata.normalize("NFD", str(texto).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def fecha(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def estado(a):
    if dt.date.fromisoformat(a["abre"]) > HOY:
        return "proxima", f"Abre el {fecha(a['abre'])}"
    if not a.get("cierra"):
        return "abierta", a.get("plazo") or "Abierta"
    if dt.date.fromisoformat(a["cierra"]) < HOY:
        return "cerrada", f"Plazo cerrado el {fecha(a['cierra'])}"
    return "abierta", f"Abierta hasta el {fecha(a['cierra'])}"


def ambito(a):
    if a["scope"] == "estatal":
        return "Toda España"
    if a["scope"] == "autonomica":
        return a["ccaa"]
    if a["scope"] == "provincial":
        return f"Provincia de {a.get('prov')}"
    return f"Municipio de {a['muni']}" if a.get("muni") else "Tu ayuntamiento"


def texto_plano(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


# ---------- plantilla ----------

def pagina(ruta, titulo, descripcion, cuerpo, migas, jsonld=None, indexar=True):
    url = f"{DOMINIO}{ruta}"
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": f"{DOMINIO}{u}"} for i, (n, u) in enumerate(migas)]}
    datos = [bc] + ([jsonld] if jsonld else [])
    nav = " › ".join(f'<a href="{u}">{e(n)}</a>' if i < len(migas) - 1 else f"<span>{e(n)}</span>" for i, (n, u) in enumerate(migas))
    doc = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descripcion)}">
<link rel="canonical" href="{url}">{"" if indexar else chr(10) + '<meta name="robots" content="noindex, follow">'}
<meta name="theme-color" content="#0D7A63">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descripcion)}">
<meta property="og:image" content="{DOMINIO}/og.png">
<meta property="og:locale" content="es_ES">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/icons/icon.svg" type="image/svg+xml">
<link rel="icon" href="/icons/icon-96.png" type="image/png" sizes="96x96">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="stylesheet" href="/estatico.css">
<script type="application/ld+json">{json.dumps(datos, ensure_ascii=False)}</script>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="logo" href="/"><img src="/icons/icon.svg" width="32" height="32" alt=""><span>Reform<b>ayuda</b></span></a>
  <a class="btn" href="/">Abrir la app</a>
</div></header>
<main class="wrap">
<nav class="migas" aria-label="Estás en">{nav}</nav>
{cuerpo}
<p class="aviso">{e(AVISO)}</p>
</main>
<footer class="pie"><div class="wrap">
  <p><b>Reformayuda</b> · Buscador gratuito de ayudas y subvenciones para reformar o construir tu casa. Sin registro y sin anuncios. Contacto: <a href="mailto:contacto@reformayuda.es">contacto@reformayuda.es</a></p>
  <p><a href="/subvenciones/">Todas las ayudas</a> · <a href="/preguntas/">Preguntas frecuentes</a> · <a href="/que-es-reformayuda/">Qué es Reformayuda</a> · <a href="/#aviso">Aviso legal</a> · <a href="/#privacidad">Privacidad</a> · <a href="/#cookies">Cookies</a></p>
</div></footer>
</body>
</html>
"""
    destino = WEB / ruta.strip("/") / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(doc, encoding="utf-8")
    return ruta if indexar else None


def tarjeta(a):
    est, txt = estado(a)
    return f"""<li class="ayuda">
  <a href="{a['_ruta']}"><h3>{e(a['title'])}</h3></a>
  <p class="org">{e(a['org'])} · {e(ambito(a))}</p>
  <p><b>{e(a['imp'])}</b> · <span class="estado {est}">{e(txt)}</span>{' · <span class="chip">Desgrava IRPF</span>' if a.get('irpf') else ''}</p>
</li>"""


def lista(ayudas, vacio):
    if not ayudas:
        return f'<p class="vacio">{e(vacio)}</p>'
    orden = {"abierta": 0, "proxima": 1, "cerrada": 2}
    ayudas = sorted(ayudas, key=lambda a: (orden[estado(a)[0]], a.get("cierra") or "9999"))
    return '<ul class="ayudas">' + "".join(tarjeta(a) for a in ayudas) + "</ul>"


# ---------- páginas ----------

def pagina_ayuda(a, todas):
    est, txt = estado(a)
    tipos = ", ".join(TIPOS[t][0] for t in a["tipo"])
    para = " y ".join({"vivienda": "particulares (tu casa o piso)", "edificio": "comunidades de propietarios"}[d] for d in a["dest"])
    filas = [("Quién la da", a["org"]), ("Dónde", ambito(a)), ("Cuánto", a["imp"]), ("Plazo", txt),
             ("Para", para), ("Tipo de obra", tipos)]
    if a.get("maxHab"):
        filas.append(("Solo en municipios de", f"menos de {a['maxHab']:,} habitantes".replace(",", ".")))
    if a.get("edad"):
        filas.append(("Edad", f"menores de {a['edad']['max']} años" if a["edad"].get("max") else f"{a['edad']['min']} años o más"))
    filas.append(("¿Desgrava en el IRPF?", "Sí, si la obra mejora la eficiencia energética" if a.get("irpf") else "No de forma directa"))
    tabla = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in filas)
    permisos = "".join(f"<li><b>{e(TIPOS[t][0])}:</b> {e(PERMISO[t][1])}</li>" for t in a["tipo"])
    relacionadas = [b for b in todas if b is not a and estado(b)[0] != "cerrada" and
                    (set(b["tipo"]) & set(a["tipo"])) and (b["ccaa"] in ("all", a["ccaa"]) or a["ccaa"] == "all")][:5]
    cierre = f" Plazo: {txt.lower()}." if est != "abierta" or a.get("cierra") else ""
    desc = f"{a['title']}. {a['imp']}.{cierre} Requisitos, documentos y cómo pedirla, explicado fácil."
    cuerpo = f"""<article>
<p class="eyebrow">{e(ambito(a))} · {e(a['fuente'])}</p>
<h1>{e(a['title'])}</h1>
<p class="lead">{e(a['resumen'])}</p>
{'<p class="alerta">El plazo de esta ayuda ya ha terminado. Te dejamos la información por si vuelve a convocarse.</p>' if est == 'cerrada' else ''}
<div class="tabla"><table>{tabla}</table></div>
<p><a class="btn grande" href="/?ayuda={e(a['id'])}">Prepárala paso a paso en la app</a> <a class="btn alt" href="{e(a['url'])}" rel="noopener" target="_blank">Ver la convocatoria oficial</a></p>
<h2>Requisitos</h2><ul>{''.join(f'<li>{e(r)}</li>' for r in a['req'])}</ul>
<h2>Documentos que necesitas</h2><ul>{''.join(f'<li>{e(r)}</li>' for r in a['docs'])}</ul>
<h2>Cómo se pide</h2><ol>{''.join(f'<li>{e(r)}</li>' for r in a['pasos'])}</ol>
<h2>¿Necesitas licencia o basta con declaración responsable?</h2><ul>{permisos}</ul>
<p class="nota">Lo decide cada ayuntamiento: confírmalo antes de empezar la obra.</p>
{f'<p class="nota">Información revisada el {fecha(a["revisada"])}.</p>' if a.get('revisada') else ''}
</article>
{'<h2>Otras ayudas parecidas</h2>' + lista(relacionadas, '') if relacionadas else ''}"""
    grant = {"@context": "https://schema.org", "@type": "MonetaryGrant", "name": a["title"], "description": a["resumen"],
             "url": f"{DOMINIO}{a['_ruta']}", "sameAs": a["url"],
             "funder": {"@type": "GovernmentOrganization", "name": a["org"]}}
    if a.get("importe"):
        grant["amount"] = {"@type": "MonetaryAmount", "currency": "EUR", "maxValue": a["importe"]}
    migas = [("Inicio", "/"), ("Ayudas", "/subvenciones/")]
    if a["ccaa"] != "all":
        migas.append((a["ccaa"], f"/subvenciones/{slug(a['ccaa'])}/"))
    migas.append((a["title"], a["_ruta"]))
    return pagina(a["_ruta"], f"{a['title']} | Reformayuda", desc[:300], cuerpo, migas, grant)


def pagina_listado(ruta, h1, intro, ayudas, migas, enlaces="", indexar=True):
    abiertas = sum(1 for a in ayudas if estado(a)[0] != "cerrada")
    desc = f"{h1}: {abiertas} ayudas y subvenciones con importes, plazos y requisitos, actualizadas cada día. Gratis y sin registro."
    cuerpo = f"""<h1>{e(h1)}</h1>
<p class="lead">{e(intro)}</p>
{lista(ayudas, 'Ahora mismo no hay ayudas publicadas aquí. Las revisamos cada día: vuelve pronto o activa los avisos en la app.')}
{enlaces}"""
    return pagina(ruta, f"{h1} | Reformayuda", desc, cuerpo, migas, indexar=indexar)


def enlaces_tipos(base):
    return "<h2>Por tipo de obra</h2><ul class=\"enlaces\">" + "".join(
        f'<li><a href="{base}{s}/">{e(n)}</a></li>' for n, s, _ in TIPOS.values()) + "</ul>"


def pagina_preguntas(faq):
    cats, preguntas = faq["categorias"], faq["preguntas"]
    secciones, entidades = [], []
    for k, nombre in cats.items():
        items = []
        for i, p in enumerate(preguntas):
            if p["cat"] != k:
                continue
            resp = re.sub(r"<p>Ahora mismo estás viendo.*?</p>", "", p["a"])
            items.append(f'<div class="pregunta" id="p{i}"><h3>{e(p["q"])}</h3>{resp}'
                         f'<p class="nota"><a href="/?pregunta={i}">Pregúntalo en la app</a></p></div>')
            entidades.append({"@type": "Question", "name": p["q"],
                              "acceptedAnswer": {"@type": "Answer", "text": texto_plano(resp)}})
        if items:
            secciones.append(f'<section id="{slug(nombre)}"><h2>{e(nombre)}</h2>{"".join(items)}</section>')
    indice = "<ul class=\"enlaces\">" + "".join(f'<li><a href="#{slug(n)}">{e(n)}</a></li>' for n in cats.values()) + "</ul>"
    cuerpo = f"""<h1>Preguntas frecuentes sobre ayudas para reformar o construir tu casa</h1>
<p class="lead">{len(preguntas)} respuestas en lenguaje sencillo sobre subvenciones, deducciones del IRPF, licencias, comunidades de vecinos y casas de campo.</p>
{indice}
{''.join(secciones)}"""
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entidades}
    return pagina("/preguntas/", "Preguntas frecuentes sobre ayudas y subvenciones para tu casa | Reformayuda",
                  "Respuestas sencillas sobre subvenciones para reformar la casa, deducciones del IRPF, licencias de obra, "
                  "declaración responsable, comunidades de vecinos y casas de campo.",
                  cuerpo, [("Inicio", "/"), ("Preguntas frecuentes", "/preguntas/")], ld)


def pagina_que_es(ayudas, faq):
    cuerpo = f"""<h1>¿Qué es Reformayuda?</h1>
<p class="lead"><b>Reformayuda</b> es un buscador gratuito y sin registro de <b>ayudas y subvenciones públicas para reformar, rehabilitar o construir vivienda en España</b>.</p>
<h2>Qué hace</h2>
<ul>
<li>Reúne las ayudas del Estado, de las comunidades autónomas, de las diputaciones y de los ayuntamientos para obras en viviendas y edificios: aislamiento, ventanas, placas solares, aerotermia, ascensores y accesibilidad, rehabilitación y construcción.</li>
<li>Explica en lenguaje sencillo quién puede pedir cada ayuda, cuánto da, hasta cuándo y qué documentos hacen falta, con enlace a la convocatoria oficial.</li>
<li>Filtra por comunidad, provincia, municipio y tamaño del pueblo, por tipo de obra y por edad.</li>
<li>Calcula la deducción del IRPF por obras de mejora de la eficiencia energética (20 %, 40 % y 60 %).</li>
<li>Indica si una obra suele necesitar licencia o basta con declaración responsable.</li>
<li>Avisa de los plazos y permite añadirlos al calendario.</li>
<li>Responde {len(faq['preguntas'])} preguntas frecuentes sobre subvenciones, impuestos, licencias, comunidades de vecinos y casas de campo.</li>
</ul>
<h2>Qué no es</h2>
<ul>
<li><b>No es una empresa de reformas</b> ni un <b>directorio de profesionales</b>: no pone en contacto con empresas ni pide presupuestos.</li>
<li><b>No es un organismo oficial</b> ni está vinculada a ninguna administración.</li>
<li><b>No presenta solicitudes</b> en nombre de nadie: lleva a la sede oficial para que cada persona la presente.</li>
</ul>
<h2>De dónde salen los datos</h2>
<p>Cada día se revisan el Boletín Oficial del Estado (BOE) y la Base de Datos Nacional de Subvenciones (BDNS), donde las administraciones publican sus convocatorias. Cada ayuda se comprueba antes de publicarla y enlaza a su fuente oficial. Ahora mismo hay {len(ayudas)} ayudas publicadas.</p>
<h2>Cómo se usa</h2>
<p>Es gratis, sin registro, sin anuncios y sin recoger datos personales: todo se guarda en el propio dispositivo. Funciona en el navegador y se puede instalar como app en el móvil.</p>
<p><a class="btn grande" href="/">Abrir Reformayuda</a> <a class="btn alt" href="/subvenciones/">Ver todas las ayudas</a></p>
<h2>Quién está detrás</h2>
<p>Reformayuda es un proyecto personal de Luis Eduardo Masdeu Cano. Contacto: <a href="mailto:contacto@reformayuda.es">contacto@reformayuda.es</a>.</p>"""
    ld = {"@context": "https://schema.org", "@type": "AboutPage", "name": "Qué es Reformayuda", "url": f"{DOMINIO}/que-es-reformayuda/",
          "about": {"@type": "WebApplication", "name": "Reformayuda", "url": f"{DOMINIO}/", "applicationCategory": "FinanceApplication",
                    "isAccessibleForFree": True, "description": "Buscador gratuito de ayudas y subvenciones públicas para reformar, rehabilitar o construir vivienda en España. No es una empresa de reformas ni un directorio de profesionales."}}
    return pagina("/que-es-reformayuda/", "¿Qué es Reformayuda? Buscador gratuito de ayudas y subvenciones para tu casa",
                  "Reformayuda es un buscador gratuito y sin registro de ayudas y subvenciones públicas para reformar, rehabilitar o "
                  "construir vivienda en España. No es una empresa de reformas ni un directorio de profesionales.",
                  cuerpo, [("Inicio", "/"), ("Qué es Reformayuda", "/que-es-reformayuda/")], ld)


def llms_txt(ayudas, faq, rutas_tipo, rutas_ccaa):
    abiertas = [a for a in ayudas if estado(a)[0] != "cerrada"]
    lineas = ["# Reformayuda", "",
              "> Buscador gratuito y sin registro de ayudas y subvenciones para reformar, rehabilitar o construir vivienda en España "
              "(estatales, autonómicas, provinciales y municipales), con calculadora de la deducción del IRPF por obras de eficiencia "
              "energética y respuestas sobre licencias de obra, comunidades de vecinos y casas de campo. "
              "Las convocatorias se revisan cada día a partir del BOE y la Base de Datos Nacional de Subvenciones.", "",
              AVISO, "",
              "## Páginas principales", "",
              f"- [Qué es Reformayuda]({DOMINIO}/que-es-reformayuda/): qué hace y qué no hace (no es una empresa de reformas ni un directorio de profesionales)",
              f"- [App de Reformayuda]({DOMINIO}/): buscador, asistente de solicitud, calculadora del IRPF y avisos de plazos",
              f"- [Todas las ayudas]({DOMINIO}/subvenciones/): listado con importes y plazos",
              f"- [Preguntas frecuentes]({DOMINIO}/preguntas/): {len(faq['preguntas'])} respuestas sobre subvenciones, IRPF, licencias y comunidades", "",
              "## Ayudas por tipo de obra", ""]
    lineas += [f"- [{n}]({DOMINIO}{r})" for n, r in rutas_tipo]
    if rutas_ccaa:
        lineas += ["", "## Ayudas por comunidad autónoma", ""]
        lineas += [f"- [{n}]({DOMINIO}{r})" for n, r in rutas_ccaa]
    lineas += ["", f"## Ayudas abiertas o próximas ({len(abiertas)})", ""]
    lineas += [f"- [{a['title']}]({DOMINIO}{a['_ruta']}): {a['imp']}. {estado(a)[1]}. {ambito(a)}." for a in abiertas]
    (WEB / "llms.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def sitemap(rutas, fecha_datos):
    urls = "".join(f"  <url><loc>{DOMINIO}{r}</loc><lastmod>{fecha_datos}</lastmod></url>\n" for r in rutas)
    (WEB / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n',
        encoding="utf-8")


def main():
    datos = json.loads((WEB / "data" / "ayudas.json").read_text(encoding="utf-8"))
    faq = json.loads((WEB / "data" / "preguntas.json").read_text(encoding="utf-8"))
    ayudas = datos["ayudas"]
    for carpeta in ("ayudas", "subvenciones", "preguntas", "que-es-reformayuda"):
        shutil.rmtree(WEB / carpeta, ignore_errors=True)

    usadas = set()
    for a in ayudas:
        base = a.get("slug") or slug(a["title"])[:70].strip("-")
        s = base if base not in usadas else f"{base}-{slug(a['id'])}"
        usadas.add(s)
        a["_ruta"] = f"/ayudas/{s}/"

    rutas = ["/"]
    rutas += [pagina_ayuda(a, ayudas) for a in ayudas]

    rutas_tipo = []
    for t, (nombre, s, frase) in TIPOS.items():
        sel = [a for a in ayudas if t in a["tipo"]]
        h1 = f"Ayudas y subvenciones para {frase} ({HOY.year})"
        r = pagina_listado(f"/subvenciones/{s}/", h1,
                           f"Ayudas estatales, autonómicas y municipales para {frase}, con importes, plazos y requisitos. "
                           "Para ver solo las de tu zona, abre la app y pon tu comunidad y tu municipio.",
                           sel, [("Inicio", "/"), ("Ayudas", "/subvenciones/"), (nombre, f"/subvenciones/{s}/")],
                           indexar=bool(sel))
        rutas.append(r)
        if sel:
            rutas_tipo.append((nombre, r))

    rutas_ccaa = []
    for c in CCAA:
        cs = slug(c)
        sel = [a for a in ayudas if a["ccaa"] in ("all", c)]
        propias = [a for a in sel if a["ccaa"] == c]
        tipos_con_propias = [t for t in TIPOS if any(t in a["tipo"] for a in propias)]
        enlaces = ""
        if tipos_con_propias:
            enlaces = "<h2>Por tipo de obra en " + e(c) + "</h2><ul class=\"enlaces\">" + "".join(
                f'<li><a href="/subvenciones/{cs}/{TIPOS[t][1]}/">{e(TIPOS[t][0])}</a></li>' for t in tipos_con_propias) + "</ul>"
        r = pagina_listado(f"/subvenciones/{cs}/", f"Ayudas y subvenciones para reformar tu casa en {c} ({HOY.year})",
                           f"Ayudas para reformar, rehabilitar o construir vivienda en {c}: las de toda España y las de la comunidad, "
                           "las diputaciones y los ayuntamientos. En la app puedes filtrar por tu municipio.",
                           sel, [("Inicio", "/"), ("Ayudas", "/subvenciones/"), (c, f"/subvenciones/{cs}/")], enlaces,
                           indexar=bool(propias))
        rutas.append(r)
        if propias:
            rutas_ccaa.append((c, r))
        for t in tipos_con_propias:
            nombre, ts, frase = TIPOS[t]
            sub = [a for a in sel if t in a["tipo"]]
            rutas.append(pagina_listado(f"/subvenciones/{cs}/{ts}/", f"Subvenciones para {frase} en {c} ({HOY.year})",
                                        f"Ayudas para {frase} en {c}, con importes, plazos y requisitos.",
                                        sub, [("Inicio", "/"), ("Ayudas", "/subvenciones/"), (c, f"/subvenciones/{cs}/"),
                                              (nombre, f"/subvenciones/{cs}/{ts}/")]))

    enlaces_ccaa = "<h2>Por comunidad autónoma</h2><ul class=\"enlaces\">" + "".join(
        f'<li><a href="/subvenciones/{slug(c)}/">{e(c)}</a></li>' for c in CCAA) + "</ul>"
    rutas.append(pagina_listado("/subvenciones/", f"Ayudas y subvenciones para reformar o construir tu casa ({HOY.year})",
                                "Todas las ayudas publicadas en Reformayuda: estatales, autonómicas, provinciales y municipales, "
                                "para particulares y comunidades de vecinos. Revisamos los boletines oficiales cada día.",
                                ayudas, [("Inicio", "/"), ("Ayudas", "/subvenciones/")],
                                enlaces_tipos("/subvenciones/") + enlaces_ccaa))
    rutas.append(pagina_preguntas(faq))
    rutas.append(pagina_que_es(ayudas, faq))

    llms_txt(ayudas, faq, rutas_tipo, rutas_ccaa)
    rutas = [r for r in rutas if r]
    sitemap(rutas, datos.get("actualizado") or HOY.isoformat())
    print(f"Generadas las páginas: {len(rutas) - 1} en el sitemap ({len(ayudas)} de ayudas), llms.txt y sitemap.xml.")


if __name__ == "__main__":
    main()

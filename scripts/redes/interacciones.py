#!/usr/bin/env python3
"""Comentarios y mensajes de Instagram y Facebook de Obrayuda.

Lo lanza .github/workflows/redes-interacciones.yml cada 15 minutos.

Comentarios nuevos (de publicaciones de Obrayuda):
  · Con la palabra clave (AYUDA, EDIFICIO, PLACAS…):
      Instagram → respuesta pública «te lo mandamos por privado» + mensaje privado que invita a
                  seguir la cuenta con un botón «Ya os sigo ✅». Al pulsarlo (o contestar) se
                  comprueba si sigue la cuenta y se le envían los enlaces (si no sigue, se le
                  recuerda con amabilidad y se le envían igualmente: Meta no permite obligar).
      Facebook  → respuesta pública con los enlaces.
  · Agradecimientos y emojis → respuesta corta automática.
  · Spam (enlaces ajenos, cripto, insultos) → se oculta.
  · Preguntas → la IA prepara una respuesta y espera tu aprobación en obrayuda.es/revisar/.
Mensajes privados nuevos (Instagram) → la IA contesta sola (información general, máximo 3 por persona y día);
  si no puede, deja un borrador para aprobar.
Las respuestas aprobadas en /revisar/ se envían en la siguiente pasada.

Estado en revision/redes-interacciones.json y borradores en revision/redes-respuestas.json.
Necesita META_PAGE_TOKEN; ANTHROPIC_API_KEY para los borradores; FIREBASE_SERVICE_ACCOUNT para
avisarte al móvil.
"""
import datetime as dt
import json
import os
import random
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redes  # noqa: E402
from redes import graph, RAIZ  # noqa: E402

ESTADO = RAIZ / "revision" / "redes-interacciones.json"
RESPUESTAS = RAIZ / "revision" / "redes-respuestas.json"
ADMIN = RAIZ / "revision" / "admin.json"
GASTO = RAIZ / "revision" / "gasto-ia.json"
DOMINIO = "https://obrayuda.es"
TELEGRAM = "https://t.me/obrayuda"
MODELO = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5"
PRECIO = {"claude-opus-5-5": (4, 20), "claude-sonnet-5-5": (2, 10), "claude-haiku-5-5": (0.10, 0.50)}

PALABRAS_BASE = {"AYUDA", "AYUDAS", "EDIFICIO", "PLACAS", "BAÑO", "BANO", "CONSTRUIR", "MAYORES", "ICIO", "IBI",
                 "PUEBLO", "DANA", "VERDAD", "TELEGRAM", "INFO", "QUIERO", "LINK", "ENLACE"}
GRACIAS = re.compile(r"^\W*(gracias|muchas gracias|genial|top|buen[oa]? ?(info|dato|post)?|qué útil|que util|útil|util|"
                     r"me sirve|interesante|bravo|perfecto|ok|👏|🙌|❤️?|🔥|💪|👍|😍|🙏)+\W*$", re.I)
SPAM = re.compile(r"(https?://|www\.|\.com\b|\.net\b|bit\.ly|bitcoin|cripto|crypto|forex|invierte|inversi[oó]n|"
                  r"gana dinero|ganar dinero|follow ?back|sígueme|sigueme|promo|dm me|whatsapp \+?\d|"
                  r"gilipollas|imb[eé]cil|subnormal|hijo de puta|mierda|estafa)", re.I)
SIGO = re.compile(r"ya (os|te) sigo|ya sigo|os sigo|te sigo|^sigo|hecho|listo|seguido", re.I)


def norm(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", norm(t)).strip("-")


def leer(ruta, defecto):
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else defecto


def guardar(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def provincias():
    """Provincias por comunidad, sacadas de la propia app (web/index.html)."""
    h = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const\s+PROV\s*=\s*(\{.*?\})\s*;", h, re.S)
    return json.loads(m.group(1)) if m else {}


PROV = provincias()


def zona_de(texto):
    """Comunidad mencionada en el comentario (por su nombre o por el de una provincia)."""
    t = " " + norm(texto) + " "
    for ccaa, provs in PROV.items():
        for nombre in [ccaa] + provs:
            n = norm(nombre)
            if len(n) > 3 and re.search(r"[^a-z]" + re.escape(n) + r"[^a-z]", t):
                return ccaa
    return None


def palabras_clave():
    out = set(PALABRAS_BASE)
    for carpeta in (redes.REELS, redes.BANCO):
        for f in carpeta.glob("*.json"):
            for m in re.finditer(r"[Cc]omenta \*{0,2}([A-ZÁÉÍÓÚÑ]{3,})", f.read_text(encoding="utf-8")):
                out.add(m.group(1))
            for m in re.finditer(r'"palabra":\s*"([^"]+)"', f.read_text(encoding="utf-8")):
                out.add(m.group(1).upper())
    return out


def es_palabra(texto, claves):
    if len(texto) > 60:
        return False
    palabras = set(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", texto.upper()))
    return bool(palabras & claves)


# ---------- contenido de los mensajes ----------

def publicacion(media_id):
    """La publicación de Obrayuda (y su ayuda, si es de una ayuda concreta) a partir del id de Meta."""
    for p in redes.leer_registro()["publicadas"]:
        if media_id in (p.get("instagram"), p.get("facebook")):
            return p
    return {}


def enlaces(texto_comentario, media_id):
    lineas = []
    pub = publicacion(media_id)
    if pub.get("ayuda"):
        a = next((x for x in json.loads(redes.AYUDAS.read_text(encoding="utf-8"))["ayudas"] if x["id"] == pub["ayuda"]), None)
        if a:
            lineas.append(f"📄 {a['title']}: {DOMINIO}/?ayuda={a['id']}")
            if a.get("sede") or a.get("url"):
                lineas.append(f"🏛️ Convocatoria oficial: {a.get('sede') or a['url']}")
    ccaa = zona_de(texto_comentario)
    if ccaa:
        lineas.append(f"🔎 Ayudas en {ccaa}: {DOMINIO}/subvenciones/{slug(ccaa)}/")
    else:
        lineas.append(f"🔎 Las ayudas de tu zona: {DOMINIO} (elige tu provincia)")
    lineas.append(f"🔔 Avisos de ayudas nuevas en Telegram: {TELEGRAM}")
    return "\n".join(lineas)


def mensaje_seguir():
    return {"text": "¡Hola! 👋 Te lo mando ahora mismo.\n\nAntes, ¿nos sigues? Así te enteras de las ayudas nuevas "
                    "en cuanto salen. Cuando lo hagas, pulsa el botón 👇",
            "quick_replies": [{"content_type": "text", "title": "Ya os sigo ✅", "payload": "SIGO"}]}


def mensaje_enlaces(texto_comentario, media_id, sigue):
    inicio = ("¡Gracias por seguirnos! 🙌 Aquí lo tienes:" if sigue else
              "Parece que aún no nos sigues 🙂 Síguenos para no perderte las ayudas nuevas. ¡Aquí lo tienes igualmente!")
    return {"text": f"{inicio}\n\n{enlaces(texto_comentario, media_id)}\n\n"
                    "Cada ayuda tiene sus requisitos: revisa siempre la convocatoria oficial. Si tienes alguna duda, escríbenos por aquí."}


# ---------- borradores con IA ----------

INSTRUCCIONES = """Contestas comentarios y mensajes en las redes de Obrayuda, una app gratuita y no oficial que reúne las ayudas públicas españolas para obras en vivienda (reformar, rehabilitar, eficiencia, accesibilidad, construir). Web: obrayuda.es. Telegram: t.me/obrayuda.
Reglas:
- Español de España, cercano, breve (máximo 350 caracteres), sin tecnicismos. Tutea.
- Solo información general y verdadera. No des asesoramiento personal ni prometas que alguien cumple los requisitos o va a recibir dinero: di que depende de cada convocatoria y remite a las bases oficiales y a obrayuda.es.
- Si preguntan por una zona, invita a mirar obrayuda.es eligiendo su provincia.
- Si es una queja, responde con educación y ofrece ayuda por privado.
- Si no necesita respuesta (spam, conversación entre otros usuarios, algo sin sentido), marca necesita_respuesta=false.
- No inventes cifras, plazos ni ayudas. Usa solo los datos que te paso."""

ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["necesita_respuesta", "respuesta", "motivo"],
           "properties": {"necesita_respuesta": {"type": "boolean"}, "respuesta": {"type": "string"}, "motivo": {"type": "string"}}}


def borrador(cliente, texto, contexto, gasto):
    mes = dt.date.today().strftime("%Y-%m")
    if gasto["meses"].get(mes, 0) > float(gasto.get("limite_usd", 20)) - 0.5:
        return {"necesita_respuesta": True, "respuesta": "", "motivo": "Tope de IA del mes alcanzado: escribe tú la respuesta."}
    r = cliente.beta.messages.create(
        model=MODELO, max_tokens=2000, system=INSTRUCCIONES,
        messages=[{"role": "user", "content": f"Contexto:\n{contexto}\n\nComentario o mensaje recibido:\n{texto}"}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    )
    e, s = PRECIO.get(MODELO, (2, 10))
    gasto["meses"][mes] = round(gasto["meses"].get(mes, 0) + (r.usage.input_tokens * e + r.usage.output_tokens * s) / 1e6, 4)
    t = [b.text for b in r.content if b.type == "text"][-1]
    return json.loads(t[t.index("{"):t.rindex("}") + 1])


def contexto_de(media_id, caption):
    pub = publicacion(media_id)
    datos = [f"Publicación: {(caption or '')[:600]}"]
    if pub.get("ayuda"):
        a = next((x for x in json.loads(redes.AYUDAS.read_text(encoding="utf-8"))["ayudas"] if x["id"] == pub["ayuda"]), None)
        if a:
            datos.append("Ayuda de la publicación: " + json.dumps({k: a.get(k) for k in ("title", "imp", "plazo", "req", "url")}, ensure_ascii=False))
    return "\n".join(datos)


# ---------- aviso al móvil ----------

def avisar(n):
    cred = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    tokens = leer(ADMIN, {}).get("tokens", [])
    if not cred or not tokens or not n:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
        firebase_admin.initialize_app(credentials.Certificate(json.loads(cred)))
        for t in tokens:
            try:
                messaging.send(messaging.Message(token=t, data={
                    "title": f"Redes: {n} respuesta{'s' if n > 1 else ''} por aprobar",
                    "body": "Te han preguntado en Instagram o Facebook. Revisa la respuesta que ha preparado la IA.",
                    "url": f"{DOMINIO}/revisar/", "tag": "redes-respuestas"},
                    webpush=messaging.WebpushConfig(headers={"TTL": "3600", "Urgency": "high"})))
            except Exception as ex:  # noqa: BLE001
                print("Aviso no enviado:", ex)
    except Exception as ex:  # noqa: BLE001
        print("Firebase no disponible:", ex)


# ---------- pasada ----------

def main():
    token = os.environ.get("META_PAGE_TOKEN", "").strip()
    if not token:
        print("Sin META_PAGE_TOKEN.")
        return
    ahora = dt.datetime.now(dt.timezone.utc)
    est = leer(ESTADO, {})
    est.setdefault("desde", ahora.isoformat(timespec="seconds"))  # solo lo que llegue a partir de la primera pasada
    est.setdefault("vistos", [])
    est.setdefault("seguir", {})
    vistos = set(est["vistos"])
    resp = leer(RESPUESTAS, {"respuestas": []})
    gasto = leer(GASTO, {"limite_usd": 20, "meses": {}})
    claves = palabras_clave()
    desde = dt.datetime.fromisoformat(est["desde"])
    cliente = None
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        import anthropic
        cliente = anthropic.Anthropic()
    nuevos_borradores = 0

    yo = graph("GET", "me", token, fields="id,name")
    if "obrayuda" not in yo["name"].lower():
        sys.exit(f"El token es de «{yo['name']}», no de Obrayuda.")
    pagina = yo["id"]
    ig = graph("GET", pagina, token, fields="instagram_business_account{id,username}").get("instagram_business_account", {})

    def reciente(ts):
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+0000", "+00:00")) >= desde

    def nuevo_borrador(red, tipo, objetivo, autor, texto, contexto, extra=None):
        nonlocal nuevos_borradores
        b = borrador(cliente, texto, contexto, gasto) if cliente else {"necesita_respuesta": True, "respuesta": "", "motivo": "Sin IA"}
        if not b["necesita_respuesta"]:
            print("No necesita respuesta:", texto[:60], "·", b["motivo"])
            return
        resp["respuestas"].append({"id": f"{red}-{objetivo}", "red": red, "tipo": tipo, "objetivo": objetivo, "autor": autor,
                                   "texto": texto, "borrador": b["respuesta"], "estado": "pendiente",
                                   "fecha": ahora.isoformat(timespec="minutes"), **(extra or {})})
        nuevos_borradores += 1

    # 1) Enviar lo aprobado en /revisar/
    for r in resp["respuestas"]:
        if r.get("estado") != "aprobada":
            continue
        texto = (r.get("final") or r.get("borrador") or "").strip()
        try:
            if r["tipo"] == "comentario" and r["red"] == "instagram":
                graph("POST", f"{r['objetivo']}/replies", token, message=texto)
            elif r["tipo"] == "comentario":
                graph("POST", f"{r['objetivo']}/comments", token, message=texto)
            else:
                graph("POST", f"{pagina}/messages", token, recipient=json.dumps({"id": r["objetivo"]}),
                      message=json.dumps({"text": texto}), messaging_type="RESPONSE")
            r["estado"] = "enviada"
            print("Enviada respuesta aprobada:", r["id"])
        except RuntimeError as ex:
            r["estado"], r["error"] = "error", str(ex)[:300]
            print("No se pudo enviar", r["id"], ex)

    # 2) Comentarios de Instagram
    if ig.get("id"):
        for m in graph("GET", f"{ig['id']}/media", token, fields="id,caption,timestamp", limit=20).get("data", []):
            for c in graph("GET", f"{m['id']}/comments", token, fields="id,text,username,timestamp", limit=50).get("data", []):
                if c["id"] in vistos or c.get("username") == ig.get("username") or not reciente(c["timestamp"]):
                    continue
                vistos.add(c["id"])
                t = c.get("text", "")
                try:
                    if SPAM.search(t):
                        graph("POST", c["id"], token, hide="true")
                        print("Oculto (spam):", t[:60])
                    elif es_palabra(t, claves):
                        try:
                            graph("POST", f"{pagina}/messages", token, recipient=json.dumps({"comment_id": c["id"]}),
                                  message=json.dumps(mensaje_seguir()))
                            graph("POST", f"{c['id']}/replies", token, message=random.choice(
                                ["¡Te lo mandamos por privado! 📩", "¡Hecho! Mira tus mensajes 📩", "¡Te lo enviamos por privado! 📩"]))
                            est["seguir"][c["username"]] = {"texto": t, "media": m["id"], "fecha": ahora.isoformat(timespec="minutes")}
                            print("Palabra clave de", c["username"], ": privado enviado")
                        except RuntimeError as ex:
                            # Sin permiso para escribir por privado a esa persona: se contesta en público con los enlaces
                            graph("POST", f"{c['id']}/replies", token,
                                  message="¡Aquí lo tienes! 🙌\n" + enlaces(t, m["id"]) + "\nY síguenos para no perderte las nuevas 😉")
                            print("Palabra clave de", c["username"], ": respuesta pública (privado no permitido:", str(ex)[:120], ")")
                    elif GRACIAS.match(t):
                        graph("POST", f"{c['id']}/replies", token, message=random.choice(
                            ["¡Gracias! 🙌", "¡Gracias por comentar! 😊", "¡Nos alegra que te sirva! 🙌"]))
                    else:
                        nuevo_borrador("instagram", "comentario", c["id"], c.get("username"), t, contexto_de(m["id"], m.get("caption")))
                except RuntimeError as ex:
                    print("Error con el comentario", c["id"], ex)

        # 3) Mensajes privados de Instagram
        try:
            convs = graph("GET", f"{pagina}/conversations", token, platform="instagram",
                          fields="participants,messages.limit(5){id,message,from,created_time}", limit=20).get("data", [])
            est.pop("aviso_mensajes", None)
        except RuntimeError as ex:
            convs = []
            est["aviso_mensajes"] = "Activa en Instagram: Configuración → Mensajes y respuestas a historias → Herramientas conectadas → Permitir acceso a los mensajes."
            print("Mensajes de Instagram no disponibles:", str(ex)[:200])
        for conv in convs:
            for msg in reversed(conv.get("messages", {}).get("data", [])):
                de = msg.get("from", {})
                if msg["id"] in vistos or de.get("id") == ig["id"] or de.get("username") == ig.get("username") or not reciente(msg["created_time"]):
                    continue
                vistos.add(msg["id"])
                usuario, t = de.get("username"), msg.get("message", "")
                try:
                    pend = est["seguir"].get(usuario)
                    if pend and (SIGO.search(t) or es_palabra(t, claves) or not t.strip()):
                        sigue = bool(graph("GET", de["id"], token, fields="is_user_follow_business").get("is_user_follow_business"))
                        graph("POST", f"{pagina}/messages", token, recipient=json.dumps({"id": de["id"]}),
                              message=json.dumps(mensaje_enlaces(pend["texto"] + " " + t, pend["media"], sigue)), messaging_type="RESPONSE")
                        del est["seguir"][usuario]
                        print("Enlaces enviados a", usuario, "· sigue:", sigue)
                    elif es_palabra(t, claves):
                        graph("POST", f"{pagina}/messages", token, recipient=json.dumps({"id": de["id"]}),
                              message=json.dumps(mensaje_seguir()), messaging_type="RESPONSE")
                        est["seguir"][usuario] = {"texto": t, "media": "", "fecha": ahora.isoformat(timespec="minutes")}
                    elif t.strip():
                        hoy_ = ahora.date().isoformat()
                        cuenta = est.setdefault("auto_dm", {}).get(usuario, {})
                        n = cuenta.get("n", 0) if cuenta.get("dia") == hoy_ else 0
                        b = borrador(cliente, t, "Mensaje privado a la cuenta de Obrayuda.", gasto) if cliente and n < 3 else None
                        if b and b["necesita_respuesta"] and b["respuesta"].strip():
                            texto = b["respuesta"].strip() + "\n\n— Respuesta automática de Obrayuda"
                            graph("POST", f"{pagina}/messages", token, recipient=json.dumps({"id": de["id"]}),
                                  message=json.dumps({"text": texto}), messaging_type="RESPONSE")
                            est["auto_dm"][usuario] = {"dia": hoy_, "n": n + 1}
                            resp["respuestas"].append({"id": f"instagram-{msg['id']}", "red": "instagram", "tipo": "mensaje",
                                                       "objetivo": de["id"], "autor": usuario, "texto": t, "borrador": texto,
                                                       "estado": "enviada", "auto": True, "fecha": ahora.isoformat(timespec="minutes")})
                            print("Respuesta automática a", usuario)
                        elif not b or b["necesita_respuesta"]:
                            nuevo_borrador("instagram", "mensaje", de["id"], usuario, t, "Mensaje privado a la cuenta de Obrayuda.")
                except RuntimeError as ex:
                    print("Error con el mensaje", msg["id"], ex)

    # 4) Comentarios de Facebook
    for post in graph("GET", f"{pagina}/posts", token, fields="id,message", limit=15).get("data", []):
        for c in graph("GET", f"{post['id']}/comments", token, fields="id,message,from,created_time", limit=50).get("data", []):
            if c["id"] in vistos or c.get("from", {}).get("id") == pagina or not reciente(c["created_time"]):
                continue
            vistos.add(c["id"])
            t = c.get("message", "")
            try:
                if SPAM.search(t):
                    graph("POST", c["id"], token, is_hidden="true")
                elif es_palabra(t, claves):
                    graph("POST", f"{c['id']}/comments", token,
                          message="¡Aquí lo tienes! 🙌\n" + enlaces(t, post["id"]) + "\nY síguenos para no perderte las nuevas 😉")
                elif GRACIAS.match(t):
                    graph("POST", f"{c['id']}/comments", token, message="¡Gracias! 🙌")
                else:
                    nuevo_borrador("facebook", "comentario", c["id"], c.get("from", {}).get("name"), t, contexto_de(post["id"], post.get("message")))
            except RuntimeError as ex:
                print("Error con el comentario de Facebook", c["id"], ex)

    # Guardar (los pendientes de seguir caducan a los 7 días; se guardan los últimos 3.000 ids vistos)
    limite = (ahora - dt.timedelta(days=7)).isoformat(timespec="minutes")
    est["seguir"] = {u: v for u, v in est["seguir"].items() if v["fecha"] >= limite}
    est["auto_dm"] = {u: v for u, v in est.get("auto_dm", {}).items() if v.get("dia") == ahora.date().isoformat()}
    est["vistos"] = list(vistos)[-3000:]
    est["actualizado"] = ahora.isoformat(timespec="minutes")
    resp["respuestas"] = [r for r in resp["respuestas"] if r["estado"] in ("pendiente", "aprobada", "error")] + \
                         [r for r in resp["respuestas"] if r["estado"] in ("enviada", "descartada")][-50:]
    guardar(ESTADO, est)
    guardar(RESPUESTAS, resp)
    guardar(GASTO, gasto)
    avisar(nuevos_borradores)
    print(f"Pasada hecha · borradores nuevos: {nuevos_borradores}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Envía las notificaciones push de Reformayuda.

Se ejecuta en GitHub después de cada publicación (y por tanto cada mañana). Para cada
persona suscrita (colección «suscripciones» de Firestore) decide si tiene algo que contarle:

  1. Plazos: una ayuda que guardó cierra dentro de 7 días o mañana.
  2. Ayudas nuevas en su comunidad o provincia que encajan con sus tipos de obra.

Como mucho envía una notificación por persona y día. Las ayudas ya avisadas se apuntan
en revision/notificadas.json para no repetirlas. La primera vez solo apunta las que ya
existen, sin enviar nada, para no avisar de golpe de ayudas antiguas.

Necesita el secreto FIREBASE_SERVICE_ACCOUNT (el JSON de la cuenta de servicio). Si no
está, no hace nada: así la publicación funciona antes de configurar Firebase.
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AYUDAS = RAIZ / "web" / "data" / "ayudas.json"
NOTIFICADAS = RAIZ / "revision" / "notificadas.json"
DOMINIO = "https://reformayuda.es"


def estado_abierto(a, hoy):
    if a.get("cierra") and a["cierra"] < hoy.isoformat():
        return False
    return dt.date.fromisoformat(a["abre"]) <= hoy + dt.timedelta(days=30)


def zona(sub):
    return sub.get("prov") or sub.get("ccaa") or "tu zona"


def encaja(a, sub):
    if a["ccaa"] not in ("all", sub.get("ccaa")):
        return False
    if a.get("prov") and sub.get("prov") and a["prov"] != sub["prov"]:
        return False
    tipos = sub.get("tipos") or []
    return not tipos or bool(set(tipos) & set(a["tipo"]))


def planificar(ayudas, subs, avisadas, hoy):
    """Devuelve (envíos, ids_nuevas_avisadas). Cada envío: (id_doc, token, datos)."""
    nuevas = [a for a in ayudas if a["id"] not in avisadas and estado_abierto(a, hoy)]
    por_id = {a["id"]: a for a in ayudas}
    en7, en1 = (hoy + dt.timedelta(days=7)).isoformat(), (hoy + dt.timedelta(days=1)).isoformat()
    envios = []
    for doc_id, sub in subs:
        token = sub.get("token")
        if not token:
            continue
        datos = None
        if sub.get("plazos", True):
            for gid in sub.get("guardadas") or []:
                a = por_id.get(gid)
                if a and a.get("cierra") in (en7, en1):
                    dias = 7 if a["cierra"] == en7 else 1
                    datos = {"title": f"Queda{'n 7 días' if dias == 7 else ' 1 día'}: {a['title']}"[:110],
                             "body": f"{a['imp']}. Plazo hasta el {dt.date.fromisoformat(a['cierra']).strftime('%d/%m/%Y')}.",
                             "url": f"{DOMINIO}/?ayuda={a['id']}", "tag": f"plazo-{a['id']}"}
                    break
        if not datos and sub.get("nuevas", True):
            suyas = [a for a in nuevas if encaja(a, sub)]
            if len(suyas) == 1:
                a = suyas[0]
                datos = {"title": f"Nueva ayuda en {zona(sub)}"[:110],
                         "body": f"{a['title']} · {a['imp']}"[:180],
                         "url": f"{DOMINIO}/?ayuda={a['id']}", "tag": "nuevas"}
            elif suyas:
                datos = {"title": f"{len(suyas)} ayudas nuevas en {zona(sub)}"[:110],
                         "body": " · ".join(a["title"] for a in suyas[:2])[:180] + ("…" if len(suyas) > 2 else ""),
                         "url": f"{DOMINIO}/#ayudas", "tag": "nuevas"}
        if datos:
            envios.append((doc_id, token, datos))
    return envios, [a["id"] for a in nuevas]


def main():
    hoy = dt.date.today()
    ayudas = json.loads(AYUDAS.read_text(encoding="utf-8"))["ayudas"]
    registro = json.loads(NOTIFICADAS.read_text(encoding="utf-8")) if NOTIFICADAS.exists() else None

    if registro is None:
        NOTIFICADAS.write_text(json.dumps({"_leeme": "Ayudas de las que ya se ha avisado por notificación.",
                                           "ids": sorted(a["id"] for a in ayudas)}, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
        print("Primera ejecución: apuntadas las ayudas actuales sin enviar nada.")
        return

    credenciales = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not credenciales:
        print("Firebase sin configurar (falta FIREBASE_SERVICE_ACCOUNT): no se envían notificaciones.")
        return

    import firebase_admin
    from firebase_admin import credentials, firestore, messaging

    firebase_admin.initialize_app(credentials.Certificate(json.loads(credenciales)))
    db = firestore.client()
    subs = [(d.id, d.to_dict()) for d in db.collection("suscripciones").stream()]
    envios, avisadas = planificar(ayudas, subs, set(registro["ids"]), hoy)

    ok = borradas = 0
    for doc_id, token, datos in envios:
        msg = messaging.Message(token=token, data=datos,
                                webpush=messaging.WebpushConfig(headers={"TTL": "86400", "Urgency": "normal"}))
        try:
            messaging.send(msg)
            ok += 1
        except (messaging.UnregisteredError, messaging.SenderIdMismatchError):
            db.collection("suscripciones").document(doc_id).delete()
            borradas += 1
        except Exception as e:  # un fallo con una persona no para el resto
            print(f"  error con {doc_id[:8]}…: {e}", file=sys.stderr)

    registro["ids"] = sorted(set(registro["ids"]) | set(avisadas))
    NOTIFICADAS.write_text(json.dumps(registro, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Suscripciones: {len(subs)}. Notificaciones enviadas: {ok}. Suscripciones caducadas borradas: {borradas}.")


if __name__ == "__main__":
    main()

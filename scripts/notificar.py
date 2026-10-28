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
CANDIDATAS = RAIZ / "revision" / "candidatas.json"
ADMIN = RAIZ / "revision" / "admin.json"  # móviles del responsable, añadidos desde /revisar/
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


def aviso_revision(registro):
    """Aviso al responsable cuando la búsqueda diaria deja candidatas nuevas por revisar."""
    if not ADMIN.exists() or not CANDIDATAS.exists():
        return []
    tokens = json.loads(ADMIN.read_text(encoding="utf-8")).get("tokens", [])
    pend = [c for c in json.loads(CANDIDATAS.read_text(encoding="utf-8")).get("candidatas", [])
            if c.get("estado", "pendiente") == "pendiente"]
    ya = set(registro.get("revision_avisadas", []))
    registro["revision_avisadas"] = sorted(c["id"] for c in pend)
    nuevas = [c for c in pend if c["id"] not in ya]
    if not nuevas or not tokens:
        return []
    n = len(nuevas)
    datos = {"title": f"{n} ayuda{'s' if n > 1 else ''} nueva{'s' if n > 1 else ''} por revisar",
             "body": " · ".join(c.get("muni") or c.get("ccaa") or c["title"][:40] for c in nuevas[:4])[:180]
                     + (f" y {n - 4} más" if n > 4 else "") + f". En total, {len(pend)} pendientes.",
             "url": f"{DOMINIO}/revisar/", "tag": "revisar"}
    return [(None, t, datos) for t in tokens]


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
    if "--prueba" in sys.argv:
        envios = [(i, s["token"], {"title": "Prueba de Reformayuda", "body": "Las notificaciones funcionan. Te avisaremos de las ayudas nuevas en tu zona.",
                                   "url": f"{DOMINIO}/", "tag": "prueba"}) for i, s in subs if s.get("token")]
        avisadas = []
    else:
        envios, avisadas = planificar(ayudas, subs, set(registro["ids"]), hoy)
        envios += aviso_revision(registro)

    ok = borradas = 0
    errores = []
    for doc_id, token, datos in envios:
        msg = messaging.Message(token=token, data=datos,
                                webpush=messaging.WebpushConfig(headers={"TTL": "86400", "Urgency": "normal"}))
        try:
            messaging.send(msg)
            ok += 1
        except (messaging.UnregisteredError, messaging.SenderIdMismatchError) as e:
            if doc_id:
                db.collection("suscripciones").document(doc_id).delete()
            borradas += 1
            errores.append(f"{type(e).__name__}: {str(e)[:200]}")
        except Exception as e:  # un fallo con una persona no para el resto
            print(f"  error con {doc_id[:8]}…: {e}", file=sys.stderr)
            errores.append(f"{type(e).__name__}: {str(e)[:300]}")

    registro["ids"] = sorted(set(registro["ids"]) | set(avisadas))
    NOTIFICADAS.write_text(json.dumps(registro, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Suscripciones: {len(subs)}. Notificaciones enviadas: {ok}. Suscripciones caducadas borradas: {borradas}.")
    # Informe sin datos personales, para revisar desde el repositorio si algo falla.
    (RAIZ / "revision" / "diagnostico-notificaciones.json").write_text(json.dumps({
        "fecha": dt.datetime.now().isoformat(timespec="minutes"), "modo": "prueba" if "--prueba" in sys.argv else "diario",
        "suscripciones": len(subs), "con_algo_que_enviar": len(envios), "enviadas": ok, "caducadas_borradas": borradas,
        "zonas": sorted({f"{s.get('ccaa')}/{s.get('prov')}" for _, s in subs}), "errores": errores[:10]},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

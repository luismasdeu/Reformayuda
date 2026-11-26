#!/usr/bin/env python3
"""Publica en el canal de Telegram de Obrayuda cada ayuda nueva que sale en la web.

Se ejecuta en GitHub después de cada publicación (y por tanto cada mañana). Publica las
ayudas publicadas que siguen abiertas (o abren pronto) y que aún no se han enviado al
canal, y las apunta en revision/telegram.json para no repetirlas.

Necesita el secreto TELEGRAM_BOT_TOKEN (el bot debe ser administrador del canal con
«Publicar mensajes»). El canal se puede cambiar con la variable TELEGRAM_CANAL
(por defecto @obrayuda). Si falta el token, no hace nada.
"""
import datetime as dt
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AYUDAS = RAIZ / "web" / "data" / "ayudas.json"
REGISTRO = RAIZ / "revision" / "telegram.json"
DOMINIO = "https://obrayuda.es"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
MAX_POR_DIA = 8  # si un día salen muchas, el resto va al día siguiente


def fecha(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]}"


def publicable(a, hoy):
    # Si cierra hoy o mañana ya no da tiempo a pedirla: no se anuncia
    if a.get("cierra") and a["cierra"] <= (hoy + dt.timedelta(days=1)).isoformat():
        return False
    return dt.date.fromisoformat(a["abre"]) <= hoy + dt.timedelta(days=30)


def lugar(a):
    if a.get("muni"):
        return f"{a['muni']} ({a['prov']})" if a.get("prov") and a["prov"] != a["muni"] else a["muni"]
    if a.get("prov"):
        return f"Provincia de {a['prov']}"
    return "Toda España" if a["ccaa"] == "all" else a["ccaa"]


def resumen_corto(texto, limite=280):
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    punto = corte.rfind(". ")
    return corte[:punto + 1] if punto > 80 else corte.rsplit(" ", 1)[0] + "…"


def mensaje(a, hoy):
    e = html.escape
    lineas = [f"🏠 <b>{e(a['title'])}</b>", "", f"📍 {e(lugar(a))}"]
    if a.get("imp"):
        lineas.append(f"💶 {e(a['imp'])}")
    if a["abre"] > hoy.isoformat():
        plazo = f"Abre el {fecha(a['abre'])}" + (f" y cierra el {fecha(a['cierra'])}" if a.get("cierra") else "")
    elif a.get("cierra"):
        plazo = f"Hasta el {fecha(a['cierra'])}"
    else:
        plazo = "Plazo abierto"
    lineas.append(f"📅 {plazo}")
    if a.get("resumen"):
        lineas += ["", e(resumen_corto(a["resumen"]))]
    lineas += ["", f"👉 <a href=\"{DOMINIO}/?ayuda={urllib.parse.quote(a['id'])}\">Requisitos y cómo pedirla</a>"]
    if a.get("url"):
        lineas.append(f"📄 <a href=\"{e(a['url'])}\">Convocatoria oficial</a> · {e(a.get('fuente', ''))}")
    return "\n".join(lineas)


def enviar(token, canal, texto):
    datos = urllib.parse.urlencode({"chat_id": canal, "text": texto, "parse_mode": "HTML",
                                    "link_preview_options": json.dumps({"is_disabled": True})}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=datos)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Falta el secreto TELEGRAM_BOT_TOKEN: no publico en Telegram.")
        return 0
    canal = os.environ.get("TELEGRAM_CANAL", "").strip() or "@obrayuda"
    hoy = dt.date.fromisoformat(os.environ["HOY"]) if os.environ.get("HOY") else dt.date.today()
    ayudas = json.loads(AYUDAS.read_text(encoding="utf-8"))["ayudas"]
    registro = json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.exists() else {"enviadas": []}
    hechas = set(registro["enviadas"])
    # Primero las que cierran antes
    pendientes = sorted((a for a in ayudas if a["id"] not in hechas and publicable(a, hoy)),
                        key=lambda a: a.get("cierra") or "9999")
    errores = 0
    for a in pendientes[:MAX_POR_DIA]:
        try:
            enviar(token, canal, mensaje(a, hoy))
            hechas.add(a["id"])
            print("Publicada en Telegram:", a["id"], a["title"])
        except urllib.error.HTTPError as ex:
            errores += 1
            print("Telegram rechazó", a["id"], ex.code, ex.read().decode("utf-8", "replace")[:300])
            if ex.code in (400, 401, 403):  # token o canal mal configurados: no sigue
                break
        time.sleep(3)
    registro["enviadas"] = sorted(hechas)
    registro["actualizado"] = hoy.isoformat()
    REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

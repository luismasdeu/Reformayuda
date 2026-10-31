#!/usr/bin/env python3
"""Pasa a la app las candidatas que has marcado como aprobadas y aparta las descartadas.

En revision/candidatas.json:
  "estado": "aprobada"   → se publica en web/data/ayudas.json
  "estado": "descartada" → no se publica y no se vuelve a proponer
  "estado": "pendiente"  → se queda esperando
En la lista "boe", pon "estado": "vista" cuando ya la hayas leído.

También archiva las ayudas que cerraron hace más de 180 días.
"""
import datetime as dt
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AYUDAS = RAIZ / "web" / "data" / "ayudas.json"
CANDIDATAS = RAIZ / "revision" / "candidatas.json"
DESCARTADAS = RAIZ / "revision" / "descartadas.json"
ARCHIVO = RAIZ / "revision" / "archivo.json"


def leer(ruta, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defecto


def guardar(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    hoy = dt.date.today()
    pub = leer(AYUDAS, {"ayudas": []})
    rev = leer(CANDIDATAS, {"candidatas": [], "boe": []})
    desc = leer(DESCARTADAS, {"ids": []})
    arch = leer(ARCHIVO, {"ayudas": []})
    por_id = {a["id"]: a for a in pub["ayudas"]}
    cambios = 0

    quedan = []
    for c in rev.get("candidatas", []):
        estado = str(c.get("estado", "pendiente")).strip().lower()  # admite «aprobadas», «Aprobada»…
        if estado.startswith("aprob") or estado == "publicar":
            limpia = {k: v for k, v in c.items() if k not in ("estado", "_revisar")}
            limpia["revisada"] = hoy.isoformat()
            if (c.get("_revisar") or {}).get("ia", {}).get("recomendacion", "").startswith("publicada sola"):
                limpia["auto"] = hoy.isoformat()  # publicada por la IA sin revisión (se puede retirar en /revisar/)
            por_id[limpia["id"]] = limpia
            cambios += 1
            print(f"Publicada: {limpia['id']} · {limpia['title'][:70]}")
        elif estado.startswith("descart"):
            desc["ids"].append(c["id"])
            if (c.get("_revisar") or {}).get("ia", {}).get("recomendacion") == "descartar":
                # Descartada por la IA: se guarda entera para poder recuperarla desde /revisar/.
                desc["ia"] = (desc.get("ia") or [])[-59:] + [c]
            print(f"Descartada: {c['id']}")
        else:
            quedan.append(c)
    rev["candidatas"] = quedan

    boe = []
    for b in rev.get("boe", []):
        if b.get("estado") == "vista":
            desc["ids"].append(b["id"])
        else:
            boe.append(b)
    rev["boe"] = boe

    # Archivar las que cerraron hace más de 180 días
    limite = (hoy - dt.timedelta(days=180)).isoformat()
    activas = []
    for a in por_id.values():
        if a.get("cierra") and a["cierra"] < limite:
            arch["ayudas"].append(a)
            cambios += 1
            print(f"Archivada (cerró el {a['cierra']}): {a['id']}")
        else:
            activas.append(a)

    if cambios:
        pub["ayudas"] = activas
        pub["actualizado"] = hoy.isoformat()
        guardar(AYUDAS, pub)
        guardar(ARCHIVO, arch)
    desc["ids"] = sorted(set(desc["ids"]))
    guardar(DESCARTADAS, desc)
    guardar(CANDIDATAS, rev)
    print(f"Hecho: {cambios} cambios en la app, {len(quedan)} candidatas pendientes.")


if __name__ == "__main__":
    main()

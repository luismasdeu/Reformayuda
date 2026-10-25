#!/usr/bin/env python3
"""Comprueba que web/data/ayudas.json está bien antes de publicar.

Si algo falla, explica qué ayuda y qué campo hay que corregir, y la publicación se para.
"""
import datetime as dt
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AYUDAS = RAIZ / "web" / "data" / "ayudas.json"

CCAA = {"all", "Andalucía", "Aragón", "Asturias", "Illes Balears", "Canarias", "Cantabria", "Castilla y León",
        "Castilla-La Mancha", "Cataluña", "Comunitat Valenciana", "Extremadura", "Galicia", "Comunidad de Madrid",
        "Región de Murcia", "Navarra", "País Vasco", "La Rioja", "Ceuta", "Melilla"}
TIPOS = {"eficiencia", "solar", "aerotermia", "ventanas", "accesibilidad", "rehabilitacion", "construccion"}
SCOPES = {"estatal", "autonomica", "provincial", "municipal"}
DEST = {"vivienda", "edificio"}
TEXTO = ["id", "title", "org", "imp", "fuente", "url", "resumen"]
LISTAS = ["req", "docs", "pasos"]


def fecha_ok(v):
    try:
        dt.date.fromisoformat(v)
        return True
    except (TypeError, ValueError):
        return False


def main():
    try:
        datos = json.loads(AYUDAS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ayudas.json no es un JSON válido (línea {e.lineno}, columna {e.colno}): {e.msg}")
        print("Pista: suele ser una coma de más o de menos, o unas comillas sin cerrar.")
        sys.exit(1)

    errores, ids = [], set()
    for n, a in enumerate(datos.get("ayudas", []), 1):
        quien = f"Ayuda {n} ({a.get('id', 'sin id')})"
        for campo in TEXTO:
            if not isinstance(a.get(campo), str) or not a[campo].strip():
                errores.append(f"{quien}: falta el texto «{campo}».")
        for campo in LISTAS:
            if not isinstance(a.get(campo), list) or not a[campo]:
                errores.append(f"{quien}: «{campo}» tiene que ser una lista con al menos un elemento.")
        if a.get("id") in ids:
            errores.append(f"{quien}: el id está repetido.")
        ids.add(a.get("id"))
        if a.get("scope") not in SCOPES:
            errores.append(f"{quien}: «scope» tiene que ser uno de {sorted(SCOPES)}.")
        if a.get("ccaa") not in CCAA:
            errores.append(f"{quien}: «ccaa» no es una comunidad válida (o «all» para toda España).")
        if a.get("scope") == "provincial" and not a.get("prov"):
            errores.append(f"{quien}: una ayuda provincial necesita «prov».")
        if not a.get("tipo") or not set(a["tipo"]) <= TIPOS:
            errores.append(f"{quien}: «tipo» tiene que usar solo {sorted(TIPOS)}.")
        if not a.get("dest") or not set(a["dest"]) <= DEST:
            errores.append(f"{quien}: «dest» tiene que usar solo {sorted(DEST)}.")
        if not fecha_ok(a.get("abre")):
            errores.append(f"{quien}: «abre» tiene que ser una fecha AAAA-MM-DD.")
        if a.get("cierra") is not None and not fecha_ok(a.get("cierra")):
            errores.append(f"{quien}: «cierra» tiene que ser una fecha AAAA-MM-DD o null.")
        if a.get("cierra") is None and not a.get("plazo"):
            errores.append(f"{quien}: sin fecha de cierre, explica el plazo en «plazo».")
        if fecha_ok(a.get("abre")) and fecha_ok(a.get("cierra")) and a["cierra"] < a["abre"]:
            errores.append(f"{quien}: «cierra» es anterior a «abre».")
        if not isinstance(a.get("importe"), (int, float)):
            errores.append(f"{quien}: «importe» tiene que ser un número (se usa para ordenar).")
        if "edad" in a and not (isinstance(a["edad"], dict) and ({"min", "max"} & a["edad"].keys())):
            errores.append(f"{quien}: «edad» tiene que ser {{\"max\": 35}} o {{\"min\": 65}}.")
        if not str(a.get("url", "")).startswith("https://"):
            errores.append(f"{quien}: «url» tiene que empezar por https://")

    if errores:
        print(f"Hay {len(errores)} problemas en ayudas.json:")
        print("\n".join(" - " + e for e in errores))
        sys.exit(1)
    print(f"ayudas.json correcto: {len(ids)} ayudas.")


if __name__ == "__main__":
    main()

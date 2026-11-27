#!/usr/bin/env python3
"""Reloj de Obrayuda: lanza cada tarea a su hora sin depender de los «cron» de GitHub,
que a veces se retrasan horas.

Lo ejecuta .github/workflows/reloj.yml. Se queda en marcha casi 6 horas (el máximo de GitHub)
y cada 15 minutos:
  · revisa comentarios y mensajes de Instagram y Facebook (scripts/redes/interacciones.py);
  · lanza, una vez al día y a partir de su hora (hora de España), las tareas de TAREAS.
Al terminar se vuelve a lanzar a sí mismo, así que nunca se para.

Lo ya lanzado cada día se apunta en revision/reloj.json.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "revision" / "reloj.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "luismasdeu/Reformayuda")
MADRID = ZoneInfo("Europe/Madrid")
DURACION = dt.timedelta(hours=5, minutes=40)
CADA = 15 * 60

# nombre, workflow, hora (España), días de la semana (0 = lunes), datos del lanzamiento
TAREAS = [
    ("buscar", "actualizar.yml", "06:17", range(7), {}),
    ("generar", "redes-generar.yml", "07:23", [0], {}),
    ("carrusel", "redes.yml", "12:17", range(6), {"formato": "carrusel"}),
    ("reel", "redes.yml", "19:43", range(7), {"formato": "reel"}),
]


def api(metodo, ruta, datos=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{ruta}", method=metodo,
                                 data=json.dumps(datos).encode() if datos is not None else None,
                                 headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        cuerpo = r.read()
        return json.loads(cuerpo) if cuerpo else {}


def lanzar(workflow, entradas):
    api("POST", f"actions/workflows/{workflow}/dispatches", {"ref": "main", "inputs": entradas})


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)


def actualizar_repo():
    git("pull", "--rebase", "-q", "origin", "main")


def guardar_cambios(mensaje, rutas):
    git("add", *rutas)
    if git("diff", "--cached", "--quiet").returncode != 0:
        git("commit", "-q", "-m", mensaje)
        for _ in range(3):
            if git("pull", "--rebase", "-q", "origin", "main").returncode == 0 and git("push", "-q", "origin", "main").returncode == 0:
                return
            git("rebase", "--abort")
            time.sleep(5)


def ya_publicado(formato, hoy):
    reg = RAIZ / "revision" / "redes.json"
    if not reg.exists():
        return False
    return any(p.get("fecha") == hoy and p.get("formato", "carrusel") == formato and p.get("instagram")
               for p in json.loads(reg.read_text(encoding="utf-8"))["publicadas"])


def tareas_del_dia(estado):
    ahora = dt.datetime.now(MADRID)
    hoy = ahora.date().isoformat()
    hechas = estado.setdefault(hoy, {})
    for nombre, workflow, hora, dias, entradas in TAREAS:
        if nombre in hechas or ahora.weekday() not in dias or ahora.strftime("%H:%M") < hora:
            continue
        if nombre in ("carrusel", "reel") and ya_publicado(nombre, hoy):
            hechas[nombre] = "ya publicado"
            continue
        try:
            lanzar(workflow, entradas)
            hechas[nombre] = ahora.strftime("%H:%M")
            print(f"{ahora:%H:%M} · lanzada la tarea «{nombre}» ({workflow})")
        except Exception as ex:  # noqa: BLE001 — se reintenta en la siguiente vuelta
            print(f"No se pudo lanzar «{nombre}»: {ex}")
    for d in [d for d in estado if d < (ahora.date() - dt.timedelta(days=7)).isoformat()]:
        del estado[d]


def main():
    fin = dt.datetime.now(dt.timezone.utc) + DURACION
    while True:
        actualizar_repo()
        estado = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
        tareas_del_dia(estado)
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if os.environ.get("META_PAGE_TOKEN"):
            r = subprocess.run([sys.executable, "scripts/redes/interacciones.py"], cwd=RAIZ, capture_output=True, text=True)
            print((r.stdout + r.stderr).strip()[-1500:])
        guardar_cambios("Reloj: tareas, comentarios y mensajes",
                        ["revision/reloj.json", "revision/redes-interacciones.json", "revision/redes-respuestas.json", "revision/gasto-ia.json"])
        if dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=CADA) > fin:
            break
        time.sleep(CADA)
    lanzar("reloj.yml", {})
    print("Relevo: lanzado el siguiente reloj.")


if __name__ == "__main__":
    main()

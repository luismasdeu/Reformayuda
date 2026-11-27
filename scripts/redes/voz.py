#!/usr/bin/env python3
"""Voz de los reels con edge-tts y el momento exacto de cada palabra (para los subtítulos).

Uso: python voz.py <guion.json> <carpeta>
Deja e0.mp3, e0.json (lista de {"w", "ini", "fin"} en segundos), e1.mp3… Sale con error si no hay voz.
"""
import asyncio
import json
import sys
from pathlib import Path

import edge_tts


async def una(texto, voz, mp3, palabras_json):
    com = edge_tts.Communicate(texto, voz, rate="+10%", boundary="WordBoundary")
    palabras = []
    with open(mp3, "wb") as f:
        async for trozo in com.stream():
            if trozo["type"] == "audio":
                f.write(trozo["data"])
            elif trozo["type"] == "WordBoundary":
                ini = trozo["offset"] / 1e7
                palabras.append({"w": trozo["text"], "ini": round(ini, 3), "fin": round(ini + trozo["duration"] / 1e7, 3)})
    Path(palabras_json).write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")


async def main():
    guion = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    carpeta = Path(sys.argv[2])
    voz = guion.get("voz") or "es-ES-XimenaNeural"
    for i, s in enumerate(guion["escenas"]):
        texto = s.get("voz") or s["texto"].replace("**", "")
        for intento in range(3):
            try:
                await una(texto, voz, carpeta / f"e{i}.mp3", carpeta / f"e{i}.json")
                break
            except Exception as ex:  # noqa: BLE001
                if intento == 2:
                    raise SystemExit(f"Sin voz: {ex}")
                await asyncio.sleep(3)


asyncio.run(main())

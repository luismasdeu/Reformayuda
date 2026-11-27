#!/usr/bin/env python3
"""Rehace con IA el gancho de los guiones de reels: «pregunta» (clip 1) + «golpe» (clip 2), según docs/redes/ganchos.md.
Solo toca los guiones que aún tienen una escena «gancho»."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generar_contenido as gc  # noqa: E402
import redes  # noqa: E402

ESQ = {"type": "object", "additionalProperties": False, "required": ["ganchos"], "properties": {"ganchos": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["nombre", "pregunta", "voz_pregunta", "golpe", "voz_golpe"],
    "properties": {k: {"type": "string"} for k in ["nombre", "pregunta", "voz_pregunta", "golpe", "voz_golpe"]}}}}}


def main():
    pend = {}
    for f in sorted(redes.REELS.glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        if g["escenas"][0]["tipo"] == "gancho":
            pend[f.stem] = {"gancho": g["escenas"][0]["texto"], "contenido": [e["texto"] for e in g["escenas"][1:]]}
    if not pend:
        return print("Nada que rehacer.")
    reglas = (redes.RAIZ / "docs" / "redes" / "ganchos.md").read_text(encoding="utf-8")
    import anthropic
    r = anthropic.Anthropic().beta.messages.create(
        model=gc.MODELO, max_tokens=16000, system=gc.INSTRUCCIONES + "\n\n" + reglas,
        messages=[{"role": "user", "content": "Rehaz el gancho de estos reels con la estructura pregunta + golpe. "
                   "Pregunta: máximo 80 caracteres, que la persona se reconozca en 1 segundo y sepa de qué va (obra, ventanas, comunidad…). "
                   "Golpe: máximo 55 caracteres, lo que se juega (dinero, perder la ayuda, un error); resalta 1-3 palabras con **dobles asteriscos**. "
                   "La voz dice lo mismo de forma natural. Solo datos verdaderos y coherentes con el contenido del reel.\n\n" +
                   json.dumps(pend, ensure_ascii=False)}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ESQ}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    t = [b.text for b in r.content if b.type == "text"][-1]
    for x in json.loads(t[t.index("{"):t.rindex("}") + 1])["ganchos"]:
        f = redes.REELS / f"{x['nombre']}.json"
        if not f.exists():
            continue
        g = json.loads(f.read_text(encoding="utf-8"))
        viejo = g["escenas"][0]
        nuevas = [{"tipo": "pregunta", "texto": x["pregunta"], "voz": x["voz_pregunta"]},
                  {"tipo": "golpe", "texto": x["golpe"], "voz": x["voz_golpe"]}]
        if viejo.get("banner"):
            nuevas[0]["banner"] = viejo["banner"]
        g["escenas"] = nuevas + g["escenas"][1:]
        f.write_text(json.dumps(g, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{x['nombre']}: {x['pregunta']} → {x['golpe']}")


if __name__ == "__main__":
    main()

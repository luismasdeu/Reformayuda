// Genera un reel vertical (1080x1920, MP4) a partir de un guion JSON.
// Uso: node scripts/redes/reel.mjs <guion.json> <carpeta-de-salida>
// Deja reel.mp4 y portada.jpg. La voz se hace con edge-tts (gratis, sin clave);
// si no está disponible, el reel sale sin voz y con la duración calculada por palabras.
//
// Guion: { "voz": "es-ES-ElviraNeural", "escenas": [
//   { "tipo": "gancho"|"punto"|"cifra"|"cta", "texto": "lo que se ve (**resaltado**)",
//     "voz": "lo que se dice", "emoji": "🪟", "n": 1, "cifra": "9.000 €" } ] }
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const { chromium } = createRequire(import.meta.url)("playwright");

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const FUENTES = path.join(RAIZ, "web", "fonts");
const fuente = (f) => `data:font/woff2;base64,${fs.readFileSync(path.join(FUENTES, f)).toString("base64")}`;
const ICONO = fs.readFileSync(path.join(RAIZ, "web", "icons", "icon.svg"), "utf8");
const esc = (s = "") => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const marca = (s = "") => esc(s).replace(/\*\*(.+?)\*\*/g, "<em>$1</em>").replace(/\n/g, "<br>");

// Zona segura: Instagram tapa abajo (texto y botones) y la columna derecha (me gusta, comentar…)
const CSS = `
@font-face{font-family:B;src:url(${fuente("bricolage-grotesque.woff2")})}
@font-face{font-family:N;src:url(${fuente("nunito-sans.woff2")})}
*{box-sizing:border-box}
body{margin:0;width:1080px;height:1920px;overflow:hidden;font-family:N}
.e{position:relative;width:1080px;height:1920px;padding:300px 170px 520px 90px;display:flex;flex-direction:column;justify-content:center;color:#fff;background:radial-gradient(circle at 80% 15%,#16A37F 0,#0D7A63 45%,#0A5E4C 100%)}
.e.cta{background:radial-gradient(circle at 80% 15%,#FFD56B 0,#FFC23D 50%,#F2A91E 100%);color:#11302A}
em{font-style:normal;color:#FFC23D}.cta em{color:#0D7A63}
.emoji{font-size:170px;line-height:1;margin-bottom:40px}
.t{font-family:B;font-weight:800;letter-spacing:-2px;line-height:1.04}
.gancho .t{font-size:112px}
.punto .t{font-size:86px}
.cifra .t{font-size:72px}
.cta .t{font-size:100px}
.e .t.largo{font-size:68px;letter-spacing:-1px}
.n{display:inline-flex;width:120px;height:120px;border-radius:50%;background:#FFC23D;color:#11302A;font-family:B;font-weight:800;font-size:68px;align-items:center;justify-content:center;margin-bottom:40px}
.num{font-family:B;font-weight:800;font-size:190px;letter-spacing:-6px;line-height:1;color:#FFC23D;margin:30px 0;white-space:nowrap}
.burbuja{margin-top:56px;display:inline-flex;align-items:center;gap:22px;align-self:flex-start;background:#fff;color:#11302A;border-radius:60px;padding:26px 44px;font-size:52px;font-weight:800;box-shadow:0 10px 30px rgba(0,0,0,.15)}
.marca{position:absolute;left:90px;top:150px;display:flex;align-items:center;gap:18px;font-size:38px;font-weight:800;opacity:.95}
.marca svg{width:72px;height:72px;border-radius:18px;box-shadow:0 0 0 3px rgba(255,255,255,.8)}
`;

function html(s) {
  let cuerpo = "";
  const largo = (s.texto || "").replace(/\*\*/g, "").length > 75 ? " largo" : "";
  if (s.tipo === "punto") cuerpo = `${s.n ? `<div class="n">${s.n}</div>` : s.emoji ? `<div class="emoji">${s.emoji}</div>` : ""}<div class="t${largo}">${marca(s.texto)}</div>`;
  else if (s.tipo === "cifra") cuerpo = `${s.emoji ? `<div class="emoji">${s.emoji}</div>` : ""}<div class="t">${marca(s.texto)}</div><div class="num">${esc(s.cifra)}</div>${s.pie ? `<div class="t" style="font-size:60px">${marca(s.pie)}</div>` : ""}`;
  else if (s.tipo === "cta") cuerpo = `<div class="t">${marca(s.texto)}</div><div class="burbuja">💬 ${esc(s.palabra || "AYUDA")}</div>`;
  else cuerpo = `${s.emoji ? `<div class="emoji">${s.emoji}</div>` : ""}<div class="t">${marca(s.texto)}</div>`;
  return `<html><head><meta charset="utf-8"><style>${CSS}</style></head><body>
    <div class="e ${s.tipo || "gancho"}"><div class="marca">${ICONO}<span>@obrayuda</span></div>${cuerpo}</div></body></html>`;
}

const duracion = (f) => parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).toString());

function voz(texto, voces, archivo) {
  try {
    execFileSync("edge-tts", ["--voice", voces, "--rate", "+8%", "--text", texto, "--write-media", archivo], { stdio: "pipe", timeout: 60000 });
    if (fs.statSync(archivo).size > 1000) return true;
  } catch (e) { console.error("Sin voz:", String(e.stderr || e).trim().split("\n").slice(-2).join(" ")); }
  return false;
}

const [guionArchivo, salida] = process.argv.slice(2);
if (!guionArchivo || !salida) { console.error("Uso: node scripts/redes/reel.mjs <guion.json> <carpeta>"); process.exit(1); }
const guion = JSON.parse(fs.readFileSync(guionArchivo, "utf8"));
fs.mkdirSync(salida, { recursive: true });
const tmp = fs.mkdtempSync(path.join(salida, ".tmp-"));

const navegador = await chromium.launch();
const pagina = await navegador.newPage({ viewport: { width: 1080, height: 1920 } });
const partes = [];
let conVoz = 0;
for (const [i, s] of guion.escenas.entries()) {
  const png = path.join(tmp, `e${i}.png`), mp3 = path.join(tmp, `e${i}.mp3`), mp4 = path.join(tmp, `e${i}.mp4`);
  await pagina.setContent(html(s));
  await pagina.evaluate(() => document.fonts.ready);
  await pagina.screenshot({ path: png });
  if (i === 0) await pagina.screenshot({ path: path.join(salida, "portada.jpg"), type: "jpeg", quality: 90 });
  const hablado = voz(s.voz || s.texto.replace(/\*\*/g, ""), guion.voz || "es-ES-ElviraNeural", mp3);
  conVoz += hablado ? 1 : 0;
  const palabras = (s.voz || s.texto).split(/\s+/).length;
  const d = Math.max(hablado ? duracion(mp3) + 0.35 : palabras / 2.6 + 0.6, s.tipo === "cta" ? 2.5 : 1.6);
  const fr = Math.round(d * 30);
  // Entrada con un pequeño «zoom» (más marcado en el gancho) para que no sea una imagen quieta
  const z0 = i === 0 ? 1.12 : 1.05;
  const filtro = `scale=1188:2112,zoompan=z='max(${z0}-(${z0}-1)*on/12,1)+0.02*on/${fr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${fr}:s=1080x1920:fps=30,format=yuv420p`;
  const audio = hablado ? ["-i", mp3] : ["-f", "lavfi", "-t", String(d), "-i", "anullsrc=r=44100:cl=stereo"];
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-loop", "1", "-t", String(d), "-i", png, ...audio,
    "-filter_complex", `[0:v]${filtro}[v];[1:a]apad,atrim=0:${d},aresample=44100[a]`, "-map", "[v]", "-map", "[a]",
    "-t", String(d), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", mp4]);
  partes.push({ mp4, d });
}
await navegador.close();

// Unir las escenas y añadir una barra de progreso arriba (ayuda a que vean el vídeo entero)
const lista = path.join(tmp, "lista.txt");
fs.writeFileSync(lista, partes.map((p) => `file '${path.resolve(p.mp4)}'`).join("\n"));
const total = partes.reduce((a, p) => a + p.d, 0);
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista,
  "-f", "lavfi", "-i", "color=c=0xFFC23D:s=1080x14:r=30",
  "-filter_complex", `[0:v]drawbox=x=0:y=0:w=iw:h=14:color=white@0.25:t=fill[b];[b][1:v]overlay=x='-W+W*t/${total.toFixed(2)}':y=0:shortest=1[v]`,
  "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
  path.join(salida, "reel.mp4")]);
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`Reel listo: ${path.join(salida, "reel.mp4")} · ${total.toFixed(1)} s · voz en ${conVoz}/${partes.length} escenas`);

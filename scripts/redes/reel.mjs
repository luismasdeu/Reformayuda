// Reel vertical (1080x1920, MP4) a partir de un guion JSON.
// Uso: node scripts/redes/reel.mjs <guion.json> <carpeta-de-salida>
// · Voz: edge-tts (voz.py) con el tiempo de cada palabra; si falla, Piper (PIPER_MODELO) con tiempos estimados.
// · Fondo: vídeo real de Pixabay según el tema de cada escena (PIXABAY_API_KEY); si no, degradado de marca.
// · Subtítulos grandes palabra a palabra, título del gancho, cifra destacada y llamada final.
// Deja reel.mp4 y portada.jpg.
// Guion: { "voz": "es-ES-XimenaNeural", "escenas": [ { "tipo": "gancho"|"punto"|"cifra"|"cta",
//   "texto": "lo que se ve (**resaltado**)", "voz": "lo que se dice", "cifra": "9.000 €", "palabra": "AYUDA", "fondo": "roof" } ] }
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const { chromium } = createRequire(import.meta.url)("playwright");

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, "../..");
const FUENTES = path.join(RAIZ, "web", "fonts");
const fuente = (f) => `data:font/woff2;base64,${fs.readFileSync(path.join(FUENTES, f)).toString("base64")}`;
const ICONO = fs.readFileSync(path.join(RAIZ, "web", "icons", "icon.svg"), "utf8");
const esc = (s = "") => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const marca = (s = "") => esc(s).replace(/\*\*(.+?)\*\*/g, "<em>$1</em>").replace(/\n/g, "<br>");
const FPS = 30;

// ---------- fondos de vídeo ----------
const TEMAS = [
  [/ventan/i, "window house"], [/tejad|cubierta|gotera/i, "roof tiles"], [/placa|solar|renovable/i, "solar panels roof"],
  [/aerotermia|caldera|calefacci|radiador/i, "heating radiator home"], [/aisla|fachada|envolvente/i, "building facade"],
  [/baño|ducha|bañera/i, "bathroom renovation"], [/cocina/i, "kitchen renovation"], [/ascensor|escaler|rampa/i, "elevator building"],
  [/comunidad|edificio|vecin|junta|acta/i, "apartment building"], [/humedad|pared|pintar/i, "painting wall"],
  [/construir|autoconstru|proyecto|licencia/i, "house construction"], [/mayor|padres|abuel/i, "elderly couple home"],
  [/pueblo|rural/i, "village house"], [/papel|certificad|factura|document|justific|bases|solicit|sede/i, "documents paperwork"],
  [/hacienda|renta|deduc|irpf|dinero|€|euros|pag/i, "money calculator"], [/ibi|icio|ayuntamiento|impuesto/i, "city hall"],
  [/inund|dana/i, "flood street"], [/telegram|móvil|avisos|enteras/i, "smartphone hand"],
];
const GENERICOS = ["home renovation", "construction worker", "house interior renovation", "builder tools", "modern house"];
const usados = new Set();

function tema(s, i) {
  if (s.fondo) return s.fondo;
  const t = `${s.texto || ""} ${s.voz || ""}`;
  for (const [re, q] of TEMAS) if (re.test(t)) return q;
  return GENERICOS[i % GENERICOS.length];
}

async function fondoVideo(q, minimo, tmp, i) {
  const clave = process.env.PIXABAY_API_KEY;
  if (!clave) return null;
  try {
    const r = await fetch(`https://pixabay.com/api/videos/?key=${clave}&q=${encodeURIComponent(q)}&per_page=30&safesearch=true&video_type=film&min_width=1280`);
    if (!r.ok) throw new Error(`Pixabay ${r.status}`);
    const hits = (await r.json()).hits || [];
    const buenos = hits.filter((h) => !usados.has(h.id) && h.duration >= Math.min(minimo, 8));
    const h = buenos[Math.floor(Math.random() * Math.min(buenos.length, 8))];
    if (!h) return null;
    usados.add(h.id);
    const v = h.videos.medium?.url ? h.videos.medium : h.videos.large || h.videos.small;
    const destino = path.join(tmp, `f${i}.mp4`);
    fs.writeFileSync(destino, Buffer.from(await (await fetch(v.url)).arrayBuffer()));
    return destino;
  } catch (e) {
    console.error(`Sin vídeo de fondo para «${q}»:`, String(e).slice(0, 120));
    return null;
  }
}

// ---------- voz ----------
const duracion = (f) => parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).toString());

function vozEdge(guionArchivo, tmp) {
  try {
    execFileSync("python3", [path.join(AQUI, "voz.py"), guionArchivo, tmp], { stdio: "pipe", timeout: 300000 });
    return true;
  } catch (e) {
    console.error("edge-tts no disponible:", String(e.stderr || e).trim().split("\n").pop().slice(0, 160));
    return false;
  }
}

function vozPiper(texto, wav) {
  if (!process.env.PIPER_MODELO) return false;
  try {
    execFileSync("piper", ["-m", process.env.PIPER_MODELO, "-f", wav, "--length-scale", "0.92"], { input: texto, stdio: ["pipe", "pipe", "pipe"], timeout: 120000 });
    return fs.statSync(wav).size > 1000;
  } catch { return false; }
}

// Si no hay tiempos reales, se reparten las palabras según su longitud
function estimar(texto, total) {
  const ws = texto.replace(/\*\*/g, "").split(/\s+/).filter(Boolean);
  const pesos = ws.map((w) => w.length + 2), suma = pesos.reduce((a, b) => a + b, 0);
  let t = 0.15;
  const util = Math.max(total - 0.4, 0.5);
  return ws.map((w, k) => { const d = (util * pesos[k]) / suma, x = { w, ini: t, fin: t + d * 0.9 }; t += d; return x; });
}

// ---------- subtítulos ----------
function trozos(palabras) {
  const grupos = [];
  let g = [];
  palabras.forEach((p, k) => {
    const pausa = k > 0 && p.ini - palabras[k - 1].fin > 0.28;
    if (g.length && (g.length >= 3 || pausa)) { grupos.push(g); g = []; }
    g.push(k);
  });
  if (g.length) grupos.push(g);
  return grupos;
}

const CSS = `
@font-face{font-family:B;src:url(${fuente("bricolage-grotesque.woff2")})}
@font-face{font-family:N;src:url(${fuente("nunito-sans.woff2")})}
*{box-sizing:border-box}html,body{margin:0;background:transparent}
.e{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:B;color:#fff}
.marca{position:absolute;left:70px;top:140px;display:flex;align-items:center;gap:16px;font:800 38px N;text-shadow:0 2px 10px rgba(0,0,0,.6)}
.marca svg{width:68px;height:68px;border-radius:16px;box-shadow:0 0 0 3px rgba(255,255,255,.85)}
.titulo{position:absolute;left:70px;right:150px;top:300px;font-weight:800;font-size:96px;line-height:1.02;letter-spacing:-2px;
  paint-order:stroke fill;-webkit-text-stroke:14px rgba(0,0,0,.85);text-shadow:0 6px 24px rgba(0,0,0,.5)}
.titulo em{font-style:normal;color:#FFC23D}
.cifra{position:absolute;left:70px;right:150px;top:420px;font-weight:800;font-size:200px;letter-spacing:-6px;line-height:1;color:#FFC23D;white-space:nowrap;
  paint-order:stroke fill;-webkit-text-stroke:16px rgba(0,0,0,.85)}
.subs{position:absolute;left:70px;right:150px;top:1060px;text-align:center;font-weight:800;font-size:104px;line-height:1.08;letter-spacing:-1px;text-transform:uppercase}
.subs span{display:inline-block;margin:0 .2em;paint-order:stroke fill;-webkit-text-stroke:16px #000;text-shadow:0 6px 18px rgba(0,0,0,.55)}
.subs span.on{color:#FFC23D}
.cta{position:absolute;left:70px;right:150px;top:330px;background:#FFC23D;color:#11302A;border-radius:44px;padding:56px 54px;box-shadow:0 20px 50px rgba(0,0,0,.35)}
.cta .t{font-weight:800;font-size:84px;line-height:1.05;letter-spacing:-1.5px}.cta em{font-style:normal;color:#0D7A63}
.cta .b{margin-top:34px;display:inline-flex;gap:18px;align-items:center;background:#fff;border-radius:60px;padding:22px 40px;font:800 52px N}
`;

function capa(s, grupo, palabras, activa) {
  let arriba = "";
  if (s.tipo === "gancho") arriba = `<div class="titulo">${marca(s.texto)}</div>`;
  else if (s.tipo === "cifra") arriba = `<div class="cifra">${esc(s.cifra || "")}</div>`;
  else if (s.tipo === "cta") arriba = `<div class="cta"><div class="t">${marca(s.texto)}</div><div class="b">💬 ${esc(s.palabra || "AYUDA")}</div></div>`;
  const subs = grupo ? `<div class="subs">${grupo.map((k) => `<span class="${k === activa ? "on" : ""}">${esc(palabras[k].w)}</span>`).join("")}</div>` : "";
  return `<html><head><meta charset="utf-8"><style>${CSS}</style></head><body><div class="e"><div class="marca">${ICONO}<span>@obrayuda</span></div>${arriba}${subs}</div></body></html>`;
}

const FONDO_MARCA = `<html><head><style>body{margin:0;width:1080px;height:1920px;background:radial-gradient(circle at 80% 15%,#16A37F 0,#0D7A63 45%,#0A5E4C 100%)}</style></head><body></body></html>`;

// ---------- principal ----------
const [guionArchivo, salida] = process.argv.slice(2);
if (!guionArchivo || !salida) { console.error("Uso: node scripts/redes/reel.mjs <guion.json> <carpeta>"); process.exit(1); }
const guion = JSON.parse(fs.readFileSync(guionArchivo, "utf8"));
if (!guion.voz || /Elvira/.test(guion.voz)) guion.voz = "es-ES-XimenaNeural";
fs.mkdirSync(salida, { recursive: true });
const tmp = fs.mkdtempSync(path.join(salida, ".tmp-"));
fs.writeFileSync(path.join(tmp, "guion.json"), JSON.stringify(guion));
const conEdge = vozEdge(path.join(tmp, "guion.json"), tmp);

const navegador = await chromium.launch();
const pagina = await navegador.newPage({ viewport: { width: 1080, height: 1920 } });
await pagina.setContent(FONDO_MARCA);
const fondoMarca = path.join(tmp, "marca.png");
await pagina.screenshot({ path: fondoMarca });

const partes = [];
let conVoz = 0, conVideo = 0;
for (const [i, s] of guion.escenas.entries()) {
  const texto = s.voz || s.texto.replace(/\*\*/g, "");
  let audio = path.join(tmp, `e${i}.mp3`), palabras = null;
  if (conEdge && fs.existsSync(audio) && fs.statSync(audio).size > 1000) {
    palabras = JSON.parse(fs.readFileSync(path.join(tmp, `e${i}.json`), "utf8"));
  } else if (vozPiper(texto, path.join(tmp, `e${i}.wav`))) {
    audio = path.join(tmp, `e${i}.wav`);
  } else audio = null;
  conVoz += audio ? 1 : 0;
  const d = Math.max(audio ? duracion(audio) + 0.25 : texto.split(/\s+/).length / 2.6 + 0.6, s.tipo === "cta" ? 2.5 : 1.5);
  if (!palabras || !palabras.length) palabras = estimar(texto, d);

  // Capas de subtítulos (una imagen por palabra) encadenadas con sus tiempos
  const grupos = trozos(palabras), lista = [];
  let n = 0;
  const imagen = async (grupo, activa) => {
    const f = path.join(tmp, `c${i}_${n++}.png`);
    await pagina.setContent(capa(s, grupo, palabras, activa));
    await pagina.evaluate(() => document.fonts.ready);
    await pagina.screenshot({ path: f, omitBackground: true });
    return f;
  };
  const primera = await imagen(grupos[0], -1);
  lista.push([primera, Math.max(palabras[0].ini, 0.04)]);
  if (i === 0) execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", primera, path.join(tmp, "capa0.png")]);
  for (const g of grupos) for (const k of g) {
    const fin = k + 1 < palabras.length ? palabras[k + 1].ini : d;
    lista.push([await imagen(g, k), Math.max(fin - palabras[k].ini, 0.04)]);
  }
  const caps = path.join(tmp, `caps${i}.txt`);
  fs.writeFileSync(caps, lista.map(([f, t]) => `file '${path.resolve(f)}'\nduration ${t.toFixed(3)}`).join("\n") + `\nfile '${path.resolve(lista.at(-1)[0])}'\n`);

  const video = await fondoVideo(tema(s, i), d, tmp, i);
  conVideo += video ? 1 : 0;
  const fondo = video ? ["-stream_loop", "-1", "-i", video] : ["-loop", "1", "-i", fondoMarca];
  const oscuro = s.tipo === "cta" ? "-0.22" : "-0.12";
  const sonido = audio ? ["-i", audio] : ["-f", "lavfi", "-t", String(d), "-i", "anullsrc=r=44100:cl=stereo"];
  const mp4 = path.join(tmp, `e${i}.mp4`);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...fondo, ...sonido, "-f", "concat", "-safe", "0", "-i", caps,
    "-filter_complex",
    `[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=${FPS},eq=brightness=${oscuro}:saturation=0.9[b];` +
    `[2:v]fps=${FPS},format=rgba[c];[b][c]overlay=0:0:format=auto,format=yuv420p[v];[1:a]apad,atrim=0:${d.toFixed(3)},aresample=44100[a]`,
    "-map", "[v]", "-map", "[a]", "-t", d.toFixed(3), "-r", String(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "21",
    "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", mp4]);
  partes.push({ mp4, d });
}
await navegador.close();

const lista = path.join(tmp, "lista.txt");
fs.writeFileSync(lista, partes.map((p) => `file '${path.resolve(p.mp4)}'`).join("\n"));
const total = partes.reduce((a, p) => a + p.d, 0);
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista,
  "-f", "lavfi", "-i", `color=c=0xFFC23D:s=1080x12:r=${FPS}`,
  "-filter_complex", `[0:v]drawbox=x=0:y=0:w=iw:h=12:color=white@0.25:t=fill[b];[b][1:v]overlay=x='-W+W*t/${total.toFixed(2)}':y=0:shortest=1[v]`,
  "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "aac", "-b:a", "128k",
  "-movflags", "+faststart", path.join(salida, "reel.mp4")]);
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-ss", "0.6", "-i", path.join(salida, "reel.mp4"), "-frames:v", "1", "-q:v", "3", path.join(salida, "portada.jpg")]);
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`Reel listo: ${path.join(salida, "reel.mp4")} · ${total.toFixed(1)} s · voz en ${conVoz}/${partes.length} · vídeo de fondo en ${conVideo}/${partes.length}`);

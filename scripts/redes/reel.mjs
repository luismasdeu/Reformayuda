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
// Cada tema: búsquedas (de más a menos concreta) y etiquetas de Pixabay de las que el clip debe tener al menos una.
const OBRA = ["renovation", "construction", "builder", "construction worker", "repair", "drill", "plaster", "brick", "tiles", "tiling", "paint", "painting", "carpenter", "contractor", "handyman", "tools", "remodeling", "renovate", "scaffolding", "workman", "craftsman"];
const CASA = ["house", "home", "apartment", "building", "facade", "residential", "interior", "room", "flat", "villa"];
const TEMAS = [
  [/ventan/i, ["window installation", "installing window", "window replacement", "window frame worker", "carpenter window"],
    ["window+installation", "window+install", "window+worker", "window+construction", "window+renovation", "window+carpenter", "window+repair", "window+builder", "window+frame", "windows+installation"]],
  [/tejad|cubierta|gotera|teja/i, ["roof repair", "roofer working", "roof tiles"], ["roof", "roofer", "roofing", "tiles"]],
  [/placa|solar|renovable|autoconsumo/i, ["solar panels installation", "solar panels roof"], ["solar", "photovoltaic", "panel"]],
  [/aerotermia|caldera|calefacci|radiador|bomba de calor/i, ["heat pump", "radiator heating", "boiler"], ["heating", "radiator", "heat", "boiler", "thermostat"]],
  [/aisla|envolvente|frío|frio|calor/i, ["wall insulation", "insulation installation", "thermal insulation"], ["insulation", "insulating", "wool", "facade"]],
  [/fachada/i, ["building facade renovation", "facade painting", "scaffolding building"], ["facade", "scaffolding", "building", "wall"]],
  [/baño|ducha|bañera|plato de ducha/i, ["bathroom renovation", "shower installation", "bathroom tiles"], ["bathroom", "shower", "bath", "toilet", "tiles"]],
  [/cocina/i, ["kitchen renovation", "kitchen installation"], ["kitchen"]],
  [/ascensor|escaler|rampa|salvaescal|accesib|silla de ruedas|movilidad/i, ["elevator building", "wheelchair ramp", "stairs building"], ["elevator", "lift", "wheelchair", "ramp", "stairs", "staircase"]],
  [/humedad|pared|pintar|pintura/i, ["painting wall", "wall repair", "plastering wall"], ["paint", "painting", "wall", "plaster"]],
  [/construir|autoconstru|primera vivienda|licencia|proyecto/i, ["house construction", "building a house", "construction site"], ["construction", "building", "house", "site", "builder"]],
  [/comunidad|edificio|vecin|junta|acta/i, ["apartment building", "residential building", "building facade"], ["building", "apartment", "residential", "facade"]],
  [/mayor|padres|abuel/i, ["elderly couple home", "senior home"], ["elderly", "senior", "old", "grandparents"]],
  [/pueblo|rural|campo/i, ["village house", "old stone house", "rural house"], ["village", "rural", "stone", "house", "countryside"]],
  [/papel|certificad|factura|document|justific|bases|solicit|sede|trámite|tramite|formulario/i, ["documents paperwork", "filling form", "signing document"], ["document", "documents", "paper", "paperwork", "form", "signing", "office", "contract"]],
  [/hacienda|renta|deduc|irpf|dinero|€|euros|devuelv|pag|ahorr|factura de la luz/i, ["euro coins", "euro banknotes", "euro money"], ["euro", "euros", "coins", "money", "banknotes", "cash"]],
  [/reforma|obra|albañil|empez|contrat|presupuesto|constructor|ladrillo/i, ["renovation worker", "construction worker house", "home renovation", "builder working", "plastering wall"], OBRA],
  [/ibi|icio|ayuntamiento|impuesto/i, ["city hall spain", "town hall building"], ["city hall", "town hall", "building", "government"]],
  [/inund|dana/i, ["flood street", "flooded house"], ["flood", "flooding", "water"]],
  [/telegram|móvil|movil|avisos|enteras|notifica/i, ["smartphone hand", "using phone"], ["phone", "smartphone", "mobile"]],
];
const GENERAL = [["home renovation", "house renovation", "renovation worker", "construction worker", "builder working"], [...OBRA, ...CASA]];
const PROHIBIDAS = ["yoga", "fitness", "sport", "exercise", "gym", "dance", "dancing", "running", "laboratory", "lab", "science", "scientist", "medical",
  "hospital", "doctor", "candle", "candles", "candlestick", "christmas", "fantasy", "abstract", "animation", "cartoon", "3d", "render", "space", "galaxy",
  "stars", "night sky", "fireworks", "beach", "sea", "ocean", "forest", "animal", "dog", "cat", "bird", "food", "cooking", "wedding", "party", "fashion",
  "model", "makeup", "beauty", "car", "cars", "factory", "industry", "industrial", "textile", "dollar", "dollars", "us dollar", "bitcoin", "crypto", "war",
  "fire", "smoke", "explosion", "rain", "raindrop", "raindrops", "rainy", "weather", "storm", "snow", "drops", "droplets", "antique", "vintage", "calligraphy", "typewriter", "dictionary", "encyclopedia", "book", "books", "piggy bank", "gambling", "casino", "bees", "bee", "insects", "insect", "flowers", "tulips", "field", "agriculture", "farm", "skyscraper", "vietnam", "india", "toy", "game", "gaming", "music", "concert", "church", "religion", "halloween", "horror", "drink", "alcohol", "bikini", "lingerie"];
const USADOS_F = path.join(RAIZ, "revision", "redes-videos-usados.json");
const usadosAntes = new Set(fs.existsSync(USADOS_F) ? JSON.parse(fs.readFileSync(USADOS_F, "utf8")).ids || [] : []);
const usados = new Set();

function temaDe(s, guion) {
  const t = `${s.texto || ""} ${s.voz || ""}`;
  for (const [re, q, tags] of TEMAS) if (re.test(t)) return [q, tags];
  // Gancho y escenas sin tema claro: el tema del reel entero
  const todo = guion.escenas.map((e) => `${e.texto || ""} ${e.voz || ""}`).join(" ");
  for (const [re, q, tags] of TEMAS) if (re.test(todo) && !/hacienda|papel/i.test(String(re))) return [q, tags];
  return GENERAL;
}

function encaja(h, tags) {
  const et = ` ${String(h.tags || "").toLowerCase()} `;
  if (PROHIBIDAS.some((p) => et.includes(` ${p} `) || et.includes(` ${p},`) || et.includes(`,${p} `))) return false;
  const lista = et.split(",").map((x) => x.trim());
  const tiene = (tg) => lista.some((x) => x === tg || x.split(" ").includes(tg));
  return tags.some((tg) => tg === "" || tg.split("+").every(tiene));  // «a+b» = tiene que tener las dos
}

// La IA mira las miniaturas y elige el clip que de verdad muestra lo que se dice (o ninguno)
let avisos429 = 0;
async function elegirConIA(s, candidatos) {
  const clave = process.env.ANTHROPIC_API_KEY;
  if (!clave || candidatos.length === 0) return candidatos.length ? 0 : -1;
  const contenido = [];
  candidatos.forEach((h, k) => {  // h = {tipo, h, mini}
    const url = h.mini;
    contenido.push({ type: "text", text: `Imagen ${k + 1}:` }, { type: "image", source: { type: "url", url } });
  });
  contenido.push({ type: "text", text:
    `Es un reel de Obrayuda (ayudas para obras y reformas en viviendas, en España). En esta escena la voz dice: «${s.voz || s.texto.replace(/\*\*/g, "")}».\n` +
    `Algunas imágenes son fotogramas de vídeo y otras fotos. Elige la que mejor encaje con lo que se dice (por ejemplo: obreros o una obra en una casa, ventanas, monedas de euro, papeles de un trámite, un edificio de viviendas). ` +
    `No hace falta que sea exacta: vale cualquier imagen relacionada con obras, reformas, casas, dinero en euros o trámites. ` +
    `Responde 0 solo si todas son claramente ajenas al tema (deporte, laboratorio, naturaleza, animales, velas, dólares, fábricas…). ` +
    `Responde SOLO con el número.` });
  for (let intento = 0; intento < 4; intento++) try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({ model: process.env.CLAUDE_MODELO_FONDOS || "claude-sonnet-5-5", max_tokens: 10, messages: [{ role: "user", content: contenido }] }),
    });
    const j = await r.json();
    if (r.status === 429 || r.status === 529) {
      if (!avisos429++) console.error(`Límite de la API (${r.status}):`, JSON.stringify(j).slice(0, 300));
      await new Promise((ok) => setTimeout(ok, 15000)); continue;
    }
    if (!r.ok) throw new Error(JSON.stringify(j).slice(0, 200));
    const n = parseInt(String(j.content?.[0]?.text || "").match(/\d+/)?.[0] || "0", 10);
    return n >= 1 && n <= candidatos.length ? n - 1 : -1;
  } catch (e) {
    console.error("La IA no ha podido elegir el fondo:", String(e).slice(0, 160));
    return -1;
  }
  return -1;
}

async function fondoVideo(s, guion, minimo, tmp, i) {
  const clave = process.env.PIXABAY_API_KEY;
  if (!clave) return null;
  const [busquedas, tags] = temaDe(s, guion);
  for (const q of [...busquedas, ...(busquedas === GENERAL[0] ? [] : GENERAL[0])].slice(0, 5)) {
    const exigidas = busquedas.includes(q) ? tags : GENERAL[1];
    try {
      const r = await fetch(`https://pixabay.com/api/videos/?key=${clave}&q=${encodeURIComponent(q)}&per_page=50&safesearch=true&video_type=film&min_width=1280`);
      if (!r.ok) throw new Error(`Pixabay ${r.status}`);
      const validos = ((await r.json()).hits || []).filter((h) => !usados.has(h.id) && !usadosAntes.has(h.id) && h.duration >= Math.min(minimo, 8) && encaja(h, [""]));
      // Primero los que tienen las etiquetas del tema; la IA decide entre los 8 primeros
      const vids = [...validos.filter((h) => encaja(h, exigidas)), ...validos.filter((h) => !encaja(h, exigidas))].slice(0, 4);
      // Fotos verticales (Pixabay tiene muchas más fotos concretas que vídeos); se animan con zoom
      const rf = await fetch(`https://pixabay.com/api/?key=${clave}&q=${encodeURIComponent(q)}&image_type=photo&orientation=vertical&per_page=40&safesearch=true&min_height=1600`);
      const fotos = rf.ok ? ((await rf.json()).hits || []).filter((h) => !usados.has("f" + h.id) && !usadosAntes.has("f" + h.id) && encaja(h, [""]))
        .sort((a, b) => encaja(b, exigidas) - encaja(a, exigidas)).slice(0, 4) : [];
      const candidatos = [...vids.map((h) => ({ tipo: "video", h, mini: h.videos.tiny?.thumbnail || h.videos.small?.thumbnail })),
                          ...fotos.map((h) => ({ tipo: "foto", h, mini: h.webformatURL }))];
      const k = await elegirConIA(s, candidatos);
      if (k < 0) continue;
      const { tipo, h } = candidatos[k];
      let destino;
      if (tipo === "video") {
        usados.add(h.id);
        const v = h.videos.medium?.url ? h.videos.medium : h.videos.large || h.videos.small;
        destino = path.join(tmp, `f${i}.mp4`);
        fs.writeFileSync(destino, Buffer.from(await (await fetch(v.url)).arrayBuffer()));
      } else {
        usados.add("f" + h.id);
        destino = path.join(tmp, `f${i}.jpg`);
        fs.writeFileSync(destino, Buffer.from(await (await fetch(h.largeImageURL)).arrayBuffer()));
      }
      console.error(`Escena ${i + 1}: «${q}» → ${tipo} ${h.id} (${String(h.tags).slice(0, 60)})`);
      return destino;
    } catch (e) {
      console.error(`Búsqueda «${q}» fallida:`, String(e).slice(0, 120));
    }
  }
  return null;
}

function guardarUsados() {
  if (!usados.size || process.env.NO_APUNTAR_CLIPS) return;
  const ids = [...usadosAntes, ...usados].slice(-1500);
  fs.writeFileSync(USADOS_F, JSON.stringify({ ids }, null, 0) + "\n");
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
.banner{position:absolute;left:70px;top:230px;background:#E5322D;color:#fff;font:800 46px N;letter-spacing:2px;padding:12px 26px;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.35)}
.titulo.caja{-webkit-text-stroke:0;text-shadow:none;color:#11302A;background:#fff;border-radius:26px;padding:26px 34px;font-size:78px;line-height:1.08}
.titulo.caja em{color:#0D7A63}
.sello{position:absolute;left:50%;top:470px;transform:translateX(-50%) rotate(-8deg);font:800 170px B;letter-spacing:4px;padding:10px 46px;border:14px solid;border-radius:30px;background:rgba(0,0,0,.35)}
.sello.mito{color:#FF5A4F;border-color:#FF5A4F}.sello.verdad{color:#43D17A;border-color:#43D17A}
.icono{position:absolute;left:50%;top:430px;transform:translateX(-50%);font-size:260px;line-height:1;filter:drop-shadow(0 10px 20px rgba(0,0,0,.5))}
.num{position:absolute;left:50%;top:400px;transform:translateX(-50%);width:300px;height:300px;border-radius:50%;background:#FFC23D;color:#11302A;
  font:800 210px B;display:flex;align-items:center;justify-content:center;box-shadow:0 14px 40px rgba(0,0,0,.4)}
.gigante{position:absolute;left:60px;right:120px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center;padding-bottom:180px;
  font-weight:800;font-size:150px;line-height:.98;letter-spacing:-3px;text-align:left;paint-order:stroke fill;-webkit-text-stroke:18px rgba(0,0,0,.9);
  text-shadow:0 8px 30px rgba(0,0,0,.55)}
.gigante.larga{font-size:128px}.gigante em{font-style:normal;color:#FFC23D}
.gigante.golpe{font-size:160px}.gigante.golpe.larga{font-size:136px}
.gigante .banner{position:static;align-self:flex-start;margin-bottom:34px;-webkit-text-stroke:0;text-shadow:none;letter-spacing:2px}
.cta{position:absolute;left:70px;right:150px;top:330px;background:#FFC23D;color:#11302A;border-radius:44px;padding:56px 54px;box-shadow:0 20px 50px rgba(0,0,0,.35)}
.cta .t{font-weight:800;font-size:84px;line-height:1.05;letter-spacing:-1.5px}.cta em{font-style:normal;color:#0D7A63}
.cta .b{margin-top:34px;display:inline-flex;gap:18px;align-items:center;background:#fff;border-radius:60px;padding:22px 40px;font:800 52px N}
`;

function capa(s, grupo, palabras, activa, estilo) {
  let arriba = "";
  if (s.tipo === "pregunta" || s.tipo === "golpe") {  // gancho en dos golpes: texto enorme y solo, sin subtítulos
    const largo = s.texto.replace(/\*\*/g, "").length > 60 ? " larga" : "";
    const banner = s.banner ? `<div class="banner">${esc(s.banner)}</div>` : "";
    return `<html><head><meta charset="utf-8"><style>${CSS}</style></head><body><div class="e"><div class="marca">${ICONO}<span>@obrayuda</span></div>` +
      `<div class="gigante ${s.tipo === "golpe" ? "golpe" : ""}${largo}">${banner}<div>${marca(s.texto)}</div></div></div></body></html>`;
  }
  if (s.tipo === "gancho" && estilo === "noticia") arriba = `<div class="banner">${esc(s.banner || "🚨 ÚLTIMA HORA")}</div><div class="titulo" style="top:340px">${marca(s.texto)}</div>`;
  else if (s.tipo === "gancho" && estilo === "pov") arriba = `<div class="titulo caja">${marca(s.texto.startsWith("POV") ? s.texto : "POV: " + s.texto)}</div>`;
  else if (s.tipo === "gancho") arriba = `<div class="titulo">${marca(s.texto)}</div>`;
  else if (s.veredicto) arriba = `<div class="sello ${/mito|falso/i.test(s.veredicto) ? "mito" : "verdad"}">${esc(s.veredicto.toUpperCase())}</div>`;
  else if (s.marca === "mal" || s.marca === "bien") arriba = `<div class="icono">${s.marca === "mal" ? "❌" : "✅"}</div>`;
  else if (estilo === "lista" && s.n) arriba = `<div class="num">${esc(s.n)}</div>`;
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
    await pagina.setContent(capa(s, grupo, palabras, activa, guion.estilo || "subtitulos"));
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

  const video = s.tipo === "cta" ? null : await fondoVideo(s, guion, d, tmp, i);
  conVideo += video ? 1 : 0;
  const esFoto = video && video.endsWith(".jpg");
  const fondo = video && !esFoto ? ["-stream_loop", "-1", "-i", video] : ["-loop", "1", "-i", video || fondoMarca];
  const fr = Math.round(d * FPS);
  const base = esFoto
    ? `scale=1296:2304:force_original_aspect_ratio=increase,crop=1296:2304,zoompan=z='1+0.10*on/${fr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=${FPS},setsar=1`
    : `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=${FPS}`;
  const oscuro = s.tipo === "cta" ? "-0.22" : (s.tipo === "pregunta" || s.tipo === "golpe") ? "-0.2" : "-0.12";
  const sonido = audio ? ["-i", audio] : ["-f", "lavfi", "-t", String(d), "-i", "anullsrc=r=44100:cl=stereo"];
  const mp4 = path.join(tmp, `e${i}.mp4`);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...fondo, ...sonido, "-f", "concat", "-safe", "0", "-i", caps,
    "-filter_complex",
    `[0:v]${base},eq=brightness=${oscuro}:saturation=0.9[b];` +
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
guardarUsados();
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`Reel listo: ${path.join(salida, "reel.mp4")} · ${total.toFixed(1)} s · voz en ${conVoz}/${partes.length} · vídeo de fondo en ${conVideo}/${partes.length}`);

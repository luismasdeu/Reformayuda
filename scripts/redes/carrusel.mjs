// Genera las imágenes de un carrusel de Instagram (1080x1350) a partir de un JSON.
// Uso: node scripts/redes/carrusel.mjs docs/redes/carruseles/<nombre>.json
// Deja slide-01.png, slide-02.png… en docs/redes/carruseles/<nombre>/
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const FUENTES = path.join(RAIZ, "web", "fonts");
const fuente = (f) => `data:font/woff2;base64,${fs.readFileSync(path.join(FUENTES, f)).toString("base64")}`;
const ICONO = fs.readFileSync(path.join(RAIZ, "web", "icons", "icon.svg"), "utf8");

const esc = (s = "") => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
// **texto** resalta en amarillo (o verde en fondos claros)
const marca = (s = "") => esc(s).replace(/\*\*(.+?)\*\*/g, "<em>$1</em>").replace(/\n/g, "<br>");

const CSS = `
@font-face{font-family:B;src:url(${fuente("bricolage-grotesque.woff2")})}
@font-face{font-family:N;src:url(${fuente("nunito-sans.woff2")})}
*{box-sizing:border-box}
body{margin:0;width:1080px;height:1350px;font-family:N;overflow:hidden}
.s{position:relative;width:1080px;height:1350px;padding:110px 96px 150px;display:flex;flex-direction:column}
.verde{background:#0D7A63;color:#fff}.verde em{color:#FFC23D;font-style:normal}
.claro{background:#F3F7F5;color:#11302A}.claro em{color:#0D7A63;font-style:normal}
.sol{background:#FFC23D;color:#11302A}.sol em{color:#0D7A63;font-style:normal}
.ceja{font-weight:800;font-size:30px;letter-spacing:3px;text-transform:uppercase;opacity:.85;margin-bottom:34px}
.claro .ceja{color:#0D7A63;opacity:1}
h1{font-family:B;font-weight:800;font-size:96px;line-height:1.0;letter-spacing:-2px;margin:0}
h2{font-family:B;font-weight:800;font-size:68px;line-height:1.05;letter-spacing:-1px;margin:0 0 48px}
.cifra{white-space:nowrap;font-family:B;font-weight:800;font-size:128px;line-height:1;letter-spacing:-4px;margin-top:56px;color:#FFC23D}
.claro .cifra,.sol .cifra{color:#0D7A63}
.sub{font-size:40px;line-height:1.35;font-weight:600;margin-top:28px;opacity:.95}
ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:34px}
li{display:flex;gap:28px;align-items:flex-start;font-size:40px;line-height:1.3;font-weight:600}
li .n{flex:none;width:68px;height:68px;border-radius:50%;background:#0D7A63;color:#fff;font-family:B;font-weight:800;font-size:36px;display:flex;align-items:center;justify-content:center;margin-top:-6px}
.verde li .n{background:#FFC23D;color:#11302A}
li b{font-weight:800}
.nota{margin-top:auto;font-size:28px;line-height:1.4;opacity:.75}
.pie{position:absolute;left:96px;right:96px;bottom:64px;display:flex;align-items:center;justify-content:space-between;font-size:28px;font-weight:700;opacity:.9}
.pie .logo{display:flex;align-items:center;gap:16px}
.pie svg{width:56px;height:56px;border-radius:14px;box-shadow:0 0 0 3px rgba(255,255,255,.85)}
.cta h1{font-size:88px}
.caja{margin-top:56px;background:rgba(17,48,42,.08);border-radius:28px;padding:36px 40px;font-size:38px;line-height:1.4;font-weight:700}
.verde .caja{background:rgba(255,255,255,.12)}
.desliza{font-weight:800;color:#FFC23D}
.claro .desliza,.sol .desliza{color:#0D7A63}
.centro{margin:auto 0}
`;

function slide(s, i, n) {
  const tema = s.tema || (s.tipo === "portada" ? "verde" : s.tipo === "cta" ? "sol" : "claro");
  let cuerpo = "";
  if (s.tipo === "portada") {
    cuerpo = `<div class="centro">${s.ceja ? `<div class="ceja">${esc(s.ceja)}</div>` : ""}
      <h1>${marca(s.titulo)}</h1>${s.cifra ? `<div class="cifra">${esc(s.cifra)}</div>` : ""}
      ${s.sub ? `<div class="sub">${marca(s.sub)}</div>` : ""}</div>`;
  } else if (s.tipo === "lista") {
    cuerpo = `${s.ceja ? `<div class="ceja">${esc(s.ceja)}</div>` : ""}<h2>${marca(s.titulo)}</h2>
      <ul>${s.puntos.map((p, k) => `<li><span class="n">${s.marcas === "check" ? "✓" : k + 1}</span><span>${marca(p)}</span></li>`).join("")}</ul>
      ${s.nota ? `<div class="nota">${marca(s.nota)}</div>` : ""}`;
  } else if (s.tipo === "texto") {
    cuerpo = `<div class="centro">${s.ceja ? `<div class="ceja">${esc(s.ceja)}</div>` : ""}<h2>${marca(s.titulo)}</h2>
      ${s.cifra ? `<div class="cifra" style="margin:0 0 30px">${esc(s.cifra)}</div>` : ""}<div class="sub">${marca(s.texto || "")}</div></div>
      ${s.nota ? `<div class="nota">${marca(s.nota)}</div>` : ""}`;
  } else if (s.tipo === "cta") {
    cuerpo = `<div class="centro cta"><h1>${marca(s.titulo)}</h1>${s.sub ? `<div class="sub">${marca(s.sub)}</div>` : ""}
      <div class="caja">${marca(s.caja || "🔎 Busca las de tu zona en obrayuda.es\n🔔 Avisos al momento en Telegram: t.me/obrayuda")}</div></div>
      ${s.nota ? `<div class="nota">${marca(s.nota)}</div>` : ""}`;
  }
  const derecha = i === 0 && n > 1 ? `<span class="desliza">Desliza →</span>` : `${i + 1}/${n}`;
  return `<div class="s ${tema}">${cuerpo}
    <div class="pie"><span class="logo">${ICONO}<span>@obrayuda</span></span><span>${derecha}</span></div></div>`;
}

const archivo = process.argv[2];
if (!archivo) { console.error("Uso: node scripts/redes/carrusel.mjs <spec.json>"); process.exit(1); }
const spec = JSON.parse(fs.readFileSync(archivo, "utf8"));
const salida = path.join(path.dirname(archivo), path.basename(archivo, ".json"));
fs.mkdirSync(salida, { recursive: true });

const navegador = await chromium.launch();
const pagina = await navegador.newPage({ viewport: { width: 1080, height: 1350 } });
for (const [i, s] of spec.slides.entries()) {
  await pagina.setContent(`<html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${slide(s, i, spec.slides.length)}</body></html>`);
  await pagina.evaluate(() => document.fonts.ready);
  await pagina.screenshot({ path: path.join(salida, `slide-${String(i + 1).padStart(2, "0")}.png`) });
}
await navegador.close();
if (spec.texto) fs.writeFileSync(path.join(salida, "texto.txt"), spec.texto.trim() + "\n");
console.log("Carrusel listo en", salida);

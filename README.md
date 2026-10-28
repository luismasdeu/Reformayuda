# Reformayuda

App gratuita y sin registro para encontrar ayudas y subvenciones para reformar o construir una casa, prepararse para pedirlas y calcular la deducción del IRPF.

- **Web y app instalable:** `web/` (se publica en GitHub Pages y en `reformayuda.es`).
- **Búsqueda diaria:** cada mañana GitHub revisa el BOE y la Base de Datos Nacional de Subvenciones (BDNS) y te propone las ayudas nuevas.
- **Tú decides qué se publica:** nada sale en la app sin que lo apruebes.

```
web/                  La app (lo que ve la gente)
  index.html          Toda la app
  data/ayudas.json    Ayudas publicadas
  manifest.webmanifest, sw.js, icons/   Para instalarla como app
revision/
  candidatas.json     Ayudas encontradas que esperan tu revisión
  descartadas.json    Las que descartaste (no se vuelven a proponer)
  archivo.json        Ayudas cerradas hace más de 6 meses
scripts/
  actualizar.py       Busca en el BOE y la BDNS
  aprobar.py          Pasa a la app las que apruebas
  validar.py          Comprueba que no hay errores antes de publicar
.github/workflows/    Los procesos automáticos de GitHub
diseno/               Icono original (SVG)
docs/                 Guía de Google Play y capturas
```

---

## 1. Ponerla en marcha (una sola vez)

### 1.1 Subir el proyecto a GitHub
1. En GitHub, crea un repositorio **público** llamado `reformayuda`, vacío (sin README).
   GitHub Pages es gratis en repositorios públicos.
2. Sube este proyecto (si te ayuda Claude, lo hace por ti).

### 1.2 Activar la publicación
1. En el repositorio: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. En **Settings → Actions → General → Workflow permissions**, marca **Read and write permissions** y guarda.
3. En la pestaña **Actions**, abre **Publicar la web** y pulsa **Run workflow**.
4. En un par de minutos la web estará en `https://TU_USUARIO.github.io/reformayuda/`.

### 1.3 Conectar tu dominio reformayuda.es
1. En **Settings → Pages → Custom domain**, escribe `reformayuda.es` y guarda.
2. En el panel de tu registrador de dominios, crea estos registros DNS:

   | Tipo | Nombre | Valor |
   |---|---|---|
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |
   | CNAME | www | TU_USUARIO.github.io |

3. Cuando GitHub lo detecte (puede tardar unas horas), marca **Enforce HTTPS**.

### 1.4 Primera búsqueda
En **Actions → Buscar ayudas nuevas → Run workflow**, pon `30` en «Días hacia atrás» para traer las del último mes. A partir de ahí se ejecuta sola cada mañana con los últimos 3 días.

---

## 2. El día a día: revisar ayudas (5-10 minutos)

**Lo fácil: desde el móvil en https://reformayuda.es/revisar/.** Cada ayuda sale como una tarjeta con enlaces a la convocatoria y las bases, los campos principales para corregir y dos botones: **Publicar** y **Descartar**. La primera vez pide una llave de GitHub (las instrucciones salen en la propia página) y ofrece **avisarte con una notificación** cada mañana que haya ayudas nuevas por revisar. La página no aparece en Google.

**Rellenado con IA (opcional, de pago):** si existe el secreto `ANTHROPIC_API_KEY`, cada mañana `scripts/rellenar_ia.py` lee la ficha de la BDNS y las bases de cada candidata nueva con la API de Claude y rellena título, importe, plazo, requisitos, documentos y pasos. En la página de revisión verás «🤖 Rellenada con IA», su recomendación (publicar o descartar) y lo que conviene comprobar. También completa, una vez, las ayudas ya publicadas que tengan datos genéricos («Consulta…»). Se puede lanzar a mano en **Actions → Rellenar con IA**. El modelo se cambia con la variable del repositorio `CLAUDE_MODEL` (Settings → Secrets and variables → Actions → Variables); el coste de cada ejecución queda en `revision/diagnostico-ia.json`.

También se puede hacer a mano en GitHub:

Cuando hay novedades, GitHub abre una incidencia **«Ayudas nuevas por revisar»** y te llega un email de GitHub con la lista y los enlaces oficiales.

1. Abre `revision/candidatas.json` en GitHub y pulsa el lápiz (✏️) para editar.
2. En cada candidata, lee la convocatoria oficial (campo `url` y `_revisar.bases_reguladoras`) y completa lo que falte:

   | Campo | Qué poner | Ejemplo |
   |---|---|---|
   | `title` | Título corto y claro | `"Rehabilitación de vivienda en pueblos de Soria"` |
   | `imp` | Cuánto da, en palabras | `"Hasta 10.000 € por vivienda"` |
   | `importe` | El máximo en número (para ordenar) | `10000` |
   | `cierra` | Último día, `AAAA-MM-DD`, o `null` si no tiene | `"2026-12-01"` |
   | `req` | Requisitos, uno por línea | `["Vivienda habitual", "Obra sin iniciar"]` |
   | `docs` | Documentos | `["DNI", "Presupuesto"]` |
   | `pasos` | Cómo se pide | `["Presenta la solicitud en la sede", "Justifica"]` |
   | `tipo` | `eficiencia`, `solar`, `aerotermia`, `ventanas`, `accesibilidad`, `rehabilitacion`, `construccion` | `["rehabilitacion"]` |
   | `dest` | `vivienda` (particular) y/o `edificio` (comunidad) | `["vivienda"]` |
   | `maxHab` | Solo si es para municipios pequeños | `5000` |
   | `edad` | Solo si tiene límite de edad | `{"max": 35}` o `{"min": 65}` |

3. Cambia `"estado": "pendiente"` por **`"aprobada"`** o **`"descartada"`**.
4. En la lista `boe` (avisos del BOE), pon `"estado": "vista"` cuando la hayas leído. Si es una ayuda nueva, cópiala como candidata.
5. Pulsa **Commit changes**. GitHub pasa las aprobadas a la app, comprueba que todo está bien y publica. Si hay un error (una coma, una fecha mal escrita), la publicación se para y en **Actions** verás qué corregir.

> Consejo: revisa siempre las fechas de plazo con la convocatoria oficial. Un plazo mal puesto es el error que más daño hace al usuario.

Para corregir una ayuda ya publicada, edita directamente `web/data/ayudas.json`.

---

## 3. Páginas para Google y las inteligencias artificiales

La app vive en una sola página que se rellena con JavaScript. Para que Google y las IA (ChatGPT, Claude, Perplexity…) encuentren cada ayuda, en cada publicación `scripts/generar_paginas.py` crea páginas con el texto ya escrito:

| Dirección | Contenido |
|---|---|
| `/ayudas/<nombre>/` | Una página por ayuda: importe, plazo, requisitos, documentos, permiso de obra y enlace oficial |
| `/subvenciones/` | Todas las ayudas, con enlaces por tipo de obra y por comunidad |
| `/subvenciones/<tipo>/` | Por tipo de obra (placas solares, ventanas…) |
| `/subvenciones/<comunidad>/` | Por comunidad autónoma, y por tipo dentro de ella |
| `/preguntas/` | Las preguntas del asistente (salen de `web/data/preguntas.json`) |
| `/llms.txt` | Resumen de la web para inteligencias artificiales |
| `/sitemap.xml` | Todas las direcciones, para Google |

No se guardan en el repositorio: se regeneran siempre a partir de `web/data/`. Las páginas sin contenido propio (por ejemplo, una comunidad sin ayudas autonómicas todavía) llevan «no indexar» para que Google no las vea como repetidas.

Cada página tiene un botón que abre la app directamente en esa ayuda (`/?ayuda=<id>`) o en esa pregunta (`/?pregunta=<n>`).

Para cambiar o añadir preguntas del asistente, edita `web/data/preguntas.json`.

## 4. Notificaciones en el móvil

Avisos de ayudas nuevas en la zona de cada persona y de plazos de sus ayudas guardadas, con Firebase (gratis). Puesta en marcha y funcionamiento: `docs/notificaciones.md`. Hasta que se configure, la app no muestra nada de notificaciones.

## 5. Probarla en tu ordenador

```bash
cd web
python3 ../scripts/generar_paginas.py   # opcional: crea las páginas para Google
python3 -m http.server 8000
# abre http://localhost:8000
```

Buscar ayudas a mano (necesita Python 3, sin instalar nada más):

```bash
python3 scripts/actualizar.py --dias 7
python3 scripts/aprobar.py
python3 scripts/validar.py
```

---

## 6. Pendiente antes del lanzamiento

- [x] Registrar `reformayuda.es` y conectarlo (apartado 1.3).
- [x] Datos del titular y email de contacto en los textos legales.
- [ ] Cargar las ayudas autonómicas y provinciales (primera búsqueda de 30 días + revisión).
- [x] Tipografías alojadas en la propia web (sin Google Fonts).
- [ ] Que un abogado o gestor revise los textos legales y las respuestas del chat sobre leyes (propiedad horizontal, licencias).
- [ ] Publicar en Google Play: ver `docs/google-play.md`.

## 7. Para cuando esté publicada en Google Play: darla a conocer

Plan acordado (todo gratis):

- [ ] **Automático:** feed RSS de ayudas nuevas (`/feed.xml`) generado al publicar, y publicación automática de cada ayuda aprobada en un **canal de Telegram** y en **Bluesky** desde GitHub Actions. Hace falta crear el canal y la cuenta y guardar sus claves como *secrets* del repositorio.
- [ ] **Semiautomático con el RSS:** Facebook e Instagram con Buffer o Make.com (planes gratuitos).
- [ ] **Manual:** compartir ayudas concretas en grupos de Facebook (reformas, comunidades de vecinos, pueblos), escribir a administradores de fincas, nota de prensa a medios locales y vídeos cortos (TikTok, Reels, Shorts).
- [ ] Antes de anunciarla: tener publicadas al menos 20-30 ayudas de varias comunidades.

## 8. Qué no hace todavía

- **Boletines autonómicos y provinciales:** se cubren a través de la BDNS, donde las administraciones registran sus convocatorias. Leer cada boletín directamente es una mejora futura.
- **Lista de municipios del INE:** el municipio se escribe a mano. Cargar el nomenclátor del INE permitiría autocompletar y saber los habitantes automáticamente.
- **Ayuda de IA para rellenar las candidatas:** se puede añadir leyendo el PDF de la convocatoria con una API de IA, siempre con revisión humana.

# Publicar Reformayuda en Google Play

La app de Android es la misma web, empaquetada como **Trusted Web Activity (TWA)**. Cuando actualizas la web, la app se actualiza sola; solo hay que subir una versión nueva a Google Play si cambias el icono, el nombre o los permisos.

## Antes de empezar
- La web tiene que estar funcionando en `https://reformayuda.es` (ver README, apartado 1.3).
- Un móvil Android para probar.

## 1. Cuenta de desarrollador
1. Entra en [Google Play Console](https://play.google.com/console) con tu cuenta de Google.
2. Elige cuenta **personal**, paga la cuota única (25 $) y verifica tu identidad con tu DNI.
3. Las cuentas personales nuevas tienen que hacer una **prueba cerrada con al menos 12 personas durante 14 días seguidos** antes de publicar. Ve buscando 12 amigos o familiares con Android y una cuenta de Gmail.

## 2. Crear el paquete de la app
1. Abre [PWABuilder](https://www.pwabuilder.com), escribe `https://reformayuda.es` y pulsa **Start**.
2. Comprueba que reconoce el manifiesto, el service worker y los iconos.
3. **Package for stores → Android → Generate package** con estos datos:
   - Package ID: `es.reformayuda.app`
   - App name: `Reformayuda`
   - Notification delegation: **activada** (para las notificaciones, ver `docs/notificaciones.md`)
   - Signing key: **Create new**. Guarda en un lugar seguro el archivo de firma y las contraseñas que te da. Sin ellos no podrás actualizar la app nunca más.
4. Descarga el ZIP. Dentro hay un archivo `.aab` (lo que se sube a Google Play) y un `assetlinks.json`.

## 3. Verificar que la web y la app son tuyas
1. Abre el `assetlinks.json` del ZIP y copia la huella (`sha256_cert_fingerprints`).
2. En Play Console, en **Configuración → Integridad de la app**, copia también la huella de la «clave de firma de apps» de Google.
3. Pega las dos en `web/.well-known/assetlinks.json` (sustituyendo `PEGA_AQUI...`), separadas por comas, y guarda. Se publica solo.
4. Comprueba que `https://reformayuda.es/.well-known/assetlinks.json` muestra el archivo. Si no, la app enseñará una barra de navegador arriba.

## 4. Ficha de Google Play

> Textos listos para copiar, gráfico y capturas: `docs/google-play/ficha.md`.

- **Nombre:** Reformayuda: subvenciones casa
- **Descripción corta y completa:** en `docs/google-play/ficha.md`
- **Icono:** `web/icons/icon-512.png`
- **Gráfico de cabecera:** `docs/google-play/grafico-1024x500.png`
- **Capturas:** `docs/google-play/capturas/` (6 imágenes)
- **Categoría:** Finanzas o Casa y hogar.
- **Política de privacidad:** `https://reformayuda.es/#privacidad`
- **Seguridad de los datos:** ver el apartado siguiente.

### Seguridad de los datos
Sin notificaciones no se recoge nada, pero si alguien las activa se guarda en Firebase un identificador del móvil y su zona. Hay que declararlo así:
- ¿Recoge o comparte datos? **Sí, recoge** (no comparte).
- Tipo: **Identificadores del dispositivo u otros** → *Recogido*, **opcional** (el usuario lo elige), finalidad **Funcionalidad de la app** (notificaciones). No se comparte con terceros.
- Tipo: **Ubicación aproximada**: no (la zona la elige el usuario a mano, no se lee del GPS). Si Play lo pregunta, la comunidad y la provincia elegidas se pueden declarar como *Otra información de la app*, opcional, para funcionalidad.
- Datos cifrados en tránsito: **Sí**. El usuario puede pedir que se borren: **Sí** (desactivando las notificaciones o con «Borrar todo»).
- **Anuncios:** No.
- **Clasificación de contenido:** rellena el cuestionario (todo «No»).

## 5. Norma importante: información de la Administración
Google exige que las apps con información de trámites públicos digan que **no son oficiales** y enlacen a las fuentes. Pon esto al principio de la descripción larga:

> Reformayuda no es una app oficial ni está vinculada a ninguna administración pública. La información procede de fuentes oficiales (BOE, Base de Datos Nacional de Subvenciones, boletines autonómicos y provinciales y Agencia Tributaria), con enlace a la convocatoria original en cada ayuda.

La app ya lo dice en el pie de página, en el aviso legal y en cada ficha.

## 6. Pruebas y publicación
1. **Pruebas → Prueba cerrada:** sube el `.aab`, añade los 12 emails de tus probadores y envíales el enlace.
2. Pasados 14 días con al menos 12 personas que la tengan instalada, pide el **acceso a producción** y responde al cuestionario.
3. Google revisa la app (normalmente unos días) y la publica.

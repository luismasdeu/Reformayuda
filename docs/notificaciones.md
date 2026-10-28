# Notificaciones en el móvil (Firebase)

Las notificaciones avisan de **ayudas nuevas en la zona** de cada persona y de que **quedan 7 días o 1 día** para que cierre una ayuda que ha guardado. Como mucho, una al día.

Cómo funciona:

1. La persona pulsa **Activar avisos** en la app.
2. Su móvil genera un identificador de notificaciones, y la app lo guarda en **Firestore** (base de datos de Firebase en la UE) junto a su comunidad, provincia, tipos de obra y ayudas guardadas. No se guarda nombre, email ni teléfono.
3. Cada vez que se publica la web (cada mañana y cada vez que apruebas ayudas), `scripts/notificar.py` mira qué tiene que contar a cada persona y se lo envía con **Firebase Cloud Messaging**.
4. Al desactivar los avisos o pulsar «Borrar todo», la suscripción se borra.

Todo es gratis con el plan Spark de Firebase (sin tarjeta).

---

## Puesta en marcha (una sola vez, unos 15 minutos)

Hazlo con la cuenta **Reformayuda (contacto@reformayuda.es)**, desde el ordenador.

### 1. Crear el proyecto
1. Entra en **https://console.firebase.google.com** → **Crear un proyecto**.
2. Nombre: `reformayuda`. Acepta las condiciones.
3. **Google Analytics: desactívalo** (no lo necesitamos y así no se recogen más datos).
4. **Crear proyecto**.

### 2. Crear la base de datos (Firestore)
1. Menú izquierdo → **Compilación → Firestore Database → Crear base de datos**.
2. Ubicación: **`europe-southwest1` (Madrid)** o, si no aparece, **`eur3 (Europe)`**. No se puede cambiar después.
3. Modo: **producción**.
4. Cuando esté creada, ve a la pestaña **Reglas**, borra lo que haya, pega el contenido del archivo `firestore.rules` de este repositorio y pulsa **Publicar**.

### 3. Registrar la web
1. Arriba a la izquierda, ⚙️ **Configuración del proyecto → General**.
2. Abajo, en «Tus apps», pulsa el icono **`</>`** (Web).
3. Nombre: `Reformayuda`. **No** marques Firebase Hosting. Pulsa **Registrar app**.
4. Te enseñará un bloque `firebaseConfig` con `apiKey`, `authDomain`, `projectId`, `storageBucket`, `messagingSenderId` y `appId`. **Cópialo**: hay que ponerlo en la app.

Estos datos son públicos por diseño: van dentro de la web y no dan acceso a nada que las reglas no permitan.

### 4. Clave para notificaciones web
1. ⚙️ **Configuración del proyecto → Cloud Messaging**.
2. Abajo, en **Configuración web → Certificados push web**, pulsa **Generar par de claves**.
3. **Copia la clave** que aparece (una cadena larga). También es pública.

### 5. Cuenta de servicio (esta sí es secreta)
1. ⚙️ **Configuración del proyecto → Cuentas de servicio → Generar nueva clave privada**. Se descarga un archivo `.json`.
2. En GitHub: **https://github.com/luismasdeu/Reformayuda/settings/secrets/actions → New repository secret**.
   - Name: `FIREBASE_SERVICE_ACCOUNT`
   - Secret: abre el `.json` con un editor de texto, copia **todo** su contenido y pégalo.
3. **Add secret**. Después, borra el `.json` de tu ordenador.

> No envíes nunca este archivo por chat ni por email, ni lo subas al repositorio: permite enviar notificaciones y leer la base de datos.

### 6. Poner los datos públicos en la app
En `web/index.html`, busca estas líneas y rellénalas con los datos de los pasos 3 y 4:

```js
const FB={apiKey:"",authDomain:"",projectId:"",storageBucket:"",messagingSenderId:"",appId:""};
const FB_VAPID="";
```

(O pásaselos a Claude, que los pone por ti.) Al guardar, la web se publica y aparecen el botón **Activar avisos** y el apartado **Notificaciones en el móvil**.

### 7. (Recomendado) Limitar la clave a tu web
En **https://console.cloud.google.com/apis/credentials** (proyecto `reformayuda`), abre la clave «Browser key», en **Restricciones de aplicaciones** elige **Sitios web** y añade `https://reformayuda.es/*`. Así nadie puede usarla desde otra web.

---

## Comprobar que funciona
1. Abre https://reformayuda.es en Chrome del móvil (o la app), haz el test inicial y pulsa **Activar avisos**.
2. En Firebase → Firestore → colección `suscripciones` debe aparecer un documento.
3. Aprueba una ayuda de tu zona: tras la publicación debería llegarte la notificación.
4. En GitHub → Actions → «Publicar la web» → paso «Enviar notificaciones» verás cuántas se han enviado.

## Si algo falla
- **No aparece el botón de activar:** faltan los datos del paso 6, o el navegador no admite notificaciones.
- **iPhone:** solo funcionan con la app instalada en la pantalla de inicio (iOS 16.4 o posterior).
- **App de Google Play:** al generar el paquete en PWABuilder, deja activada la opción **Notification delegation**, para que las notificaciones salgan con el icono de la app.
- **«Firebase sin configurar»** en el registro de GitHub: falta el secreto del paso 5.

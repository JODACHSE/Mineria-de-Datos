# 📦 vendor

Librerías de terceros que el sitio sirve **desde aquí** en lugar de una CDN.

Se cargan como módulo de JavaScript (`import`), y en ese caso el navegador no puede comprobar
que el archivo no fue alterado. Por eso se guarda una copia exacta y verificada.

| Librería | Versión | Licencia | Para qué se usa |
|---|---|---|---|
| [uisfx](https://www.npmjs.com/package/uisfx) | 0.4.0 | MIT | Sonidos de la interfaz (`js/core/sound.js`) |

## Actualizar una librería

1. Descarga el archivo publicado, por ejemplo `https://cdn.jsdelivr.net/npm/uisfx@<versión>/dist/index.js`.
2. Compara su huella SHA-256 con la que publica jsDelivr en `https://data.jsdelivr.com/v1/packages/npm/uisfx@<versión>`:
   ```bash
   openssl dgst -sha256 -binary index.js | openssl base64
   ```
3. Guárdalo en una carpeta nueva `uisfx-<versión>/`, actualiza el `import` de `js/core/sound.js` y esta tabla.

Huella actual de `uisfx-0.4.0/index.js`: `1k7fKPgjsqUqOOjfQQI9Mf5i3gToIuBWn0zS4A3fpXk=`

> Bootstrap y Chart.js siguen en jsDelivr porque se cargan con `<script>`, que sí permite verificar el archivo con `integrity`.

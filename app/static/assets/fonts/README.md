# Tipografías

Este sitio carga las tipografías **Orbitron**, **Exo 2** y **Space Mono**
desde Google Fonts vía CDN (declarado en `app/static/css/styles.css`,
al inicio del archivo con `@import`). No fue posible empaquetar los
binarios `.ttf` directamente en este entorno de generación (sin acceso
de red a `fonts.gstatic.com`).

Si prefieres **autoalojar** las fuentes (recomendado para producción /
RGPD/offline):

1. Descarga los `.ttf`/`.woff2` desde:
   - Orbitron: https://fonts.google.com/specimen/Orbitron
   - Exo 2: https://fonts.google.com/specimen/Exo+2
   - Space Mono: https://fonts.google.com/specimen/Space+Mono
2. Colócalos en esta carpeta (`app/static/assets/fonts/`).
3. Reemplaza la línea `@import url(...)` en `styles.css` por reglas
   `@font-face` apuntando a estos archivos locales, por ejemplo:

```css
@font-face {
  font-family: 'Orbitron';
  src: url('/static/assets/fonts/Orbitron.ttf') format('truetype');
  font-weight: 500 900;
  font-display: swap;
}
```

4. Elimina el `@import` remoto una vez migres.

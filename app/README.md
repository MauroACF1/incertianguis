# Canjea Cerca — prototipo (App CDMX)

Pantalla de la persona beneficiaria de los vales Mercomuna: saldo y fecha límite, mapa de comercios cercanos que aceptan vales, ficha del comercio, retroalimentación opcional y un panel agregado para SEDECO.

## Cómo abrirlo

```
cd app
py -3.12 -m http.server 8000
```

Abre http://localhost:8000 en el navegador, en vista móvil (390 px). El panel oculto está en http://localhost:8000/#panel.

- Sin frameworks ni build. Leaflet 1.9.4 está copiado en `vendor/`, así que solo los tiles del mapa (OpenStreetMap) necesitan internet.
- Datos en `app/data/`, copiados de `data/processed/` con `py -3.12 scripts/09_datos_app.py`: `mercomuna.geojson`, `mercomuna.csv`, `tianguis.geojson`, `mercados_publicos.geojson`. No usa la capa de afiliables.
- Fecha de demo fija: domingo 25 de octubre de 2026 (para "Hoy" en tianguis y los días restantes). Ubicación de demo: 19.345, -99.147 (Utopía Elena Poniatowska Amor, San Lucas, Coyoacán). El CP se estima con el centroide de CP más cercano.
- "Usar mi ubicación" requiere un contexto seguro: funciona en `localhost`, pero desde otro dispositivo de la red local, con `http://IP:8000`, el navegador la bloquea.

## Privacidad

- Las respuestas se guardan solo en `localStorage` como eventos `{fecha, cp, giro, respuesta}`. El `cp` y el `giro` son **los del comercio**, no los de la persona. No se guarda ubicación, nombre ni identificador.
- La fecha se guarda sin hora.
- El texto libre se limita a 60 caracteres y se le quitan números y "@" (para evitar teléfonos o correos).
- Al abrir la app por primera vez se precargan 30 eventos de ejemplo. Se pueden reiniciar desde el panel.

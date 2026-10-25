# Principio de Incertianguis — Chilangatón 2026 (CDMX)

## Contexto
- Hackatón Chilangatón 2026, reto **"Comercio popular y barrial"**. Equipo **Principio de Incertianguis**. Tiempo: ~5 horas.
- Propuesta: un módulo para la **App CDMX** donde las personas beneficiarias de los **vales Mercomuna**:
  1. encuentran comercios de barrio cercanos que aceptan vales,
  2. ven su saldo y fecha límite de uso (**31 de diciembre de 2026**),
  3. de forma **opcional**, confirman si el comercio aceptó el vale.
- Principio rector: **beneficio antes que captura**.

## Reglas de datos
- **No recolectamos datos personales** de personas beneficiarias (nada de nombre, CURP, teléfono, ubicación histórica, etc.). El saldo se consulta, no se almacena.
- **No recolectamos datos sensibles de comerciantes**: ingresos, ventas, extorsión/cobro de piso, situación fiscal o similares.
- La confirmación "¿aceptó el vale?" es opcional, anónima y agregada por comercio (sí/no + fecha), sin identificar a quien la envía.
- Solo usamos datos públicos/abiertos (datos.cdmx.gob.mx, SAPCI, INEGI DENUE). Toda fuente se registra en `data/README.md` (URL, fecha de descarga, descripción).
- Si una fuente trae columnas personales (p. ej. nombre del propietario, teléfono o correo de persona física), se **eliminan** antes de guardar en `data/processed/`.
- `data/raw/` = descargas tal cual; `data/processed/` = salidas de scripts. Nunca editar a mano.

## Estructura
- `data/raw/`, `data/processed/` — datos
- `scripts/` — scripts reproducibles en Python (pandas, rapidfuzz). Ejecutar desde la raíz: `py -3.12 scripts/<script>.py`
- `app/` — prototipo del módulo App CDMX

## Estilo de código
- Python simple, pandas + rapidfuzz, un script por paso, sin notebooks como única fuente.
- Las peticiones web llevan pausas (`time.sleep`) y User-Agent identificable.

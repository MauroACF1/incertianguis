# Informe semanal Canjea Cerca · Vales Mercomuna

**Para:** SEDECO / SAPCI · **Semana:** 19 al 25 de octubre de 2026 · **Fuente:** `data/processed/senales_semana.json`

> ⚠️ **EJEMPLO GENERADO CON DATOS SIMULADOS.** Las 60 respuestas son sintéticas (`scripts/seed-feedback.mjs` del repo mapatianguis) y se repartieron en Iztapalapa, Tlalpan y Coyoacán para ilustrar el formato. Los códigos postales, las colonias, el IDS y los conteos de comercios (DENUE y directorio Mercomuna) son reales. **No usar estas cifras para tomar decisiones.**

## Resumen

- 60 respuestas voluntarias y anónimas en 11 códigos postales.
- El vale fue aceptado en **63%** de las confirmaciones (38 de 60).
- Lo más buscado y no encontrado: **carne** (5 menciones), **pan** (4) y **tortillas** (3).
- Ninguna respuesta contiene datos personales ni ubicación de la persona: solo el CP y el giro del comercio.

## Hallazgos

**1. En colonias de IDS muy bajo el vale se rechaza en tianguis.** Las dos tasas de rechazo más altas de la semana están en tianguis de CP de IDS muy bajo, y ninguno de los dos CP tiene comercios en el directorio Mercomuna:
- 09096, Iztlahuacan (Iztapalapa): 60% (3 de 5);
- 14734, Zacatón / Santa Cruz Atoyac (Tlalpan): 57% (4 de 7).

Las personas intentan usar el vale donde compran habitualmente, pero esos puestos no están afiliados.

**2. Hay demanda en 5 CP de IDS bajo o muy bajo sin un solo comercio Mercomuna**, aunque en cada uno hay de 18 a 37 comercios de alimentos que podrían afiliarse (DENUE):

| CP | Colonia principal | Alcaldía | Respuestas | Afiliables |
|---|---|---|---|---|
| 14734 | Zacatón | Tlalpan | 7 | 18 |
| 04850 | Santa Úrsula Coapa | Coyoacán | 6 | 20 |
| 09096 | Iztlahuacan | Iztapalapa | 5 | 37 |
| 09577 | Ejército de Agua Prieta | Iztapalapa | 4 | 20 |
| 14426 | Mesa de los Hornos | Tlalpan | 4 | 18 |

**3. Lo que más se busca falta justamente donde se busca.**
- **Productos básicos sin ningún comercio afiliable de ese giro en el CP:**
  - carne: 09438 Ampliación El Triunfo, 14734 Zacatón y 04850 Santa Úrsula;
  - pan: 09096, 09577 y 04850;
  - tortillas: 14426 Mesa de los Hornos.
- **Sí hay oferta, pero ningún comercio acepta vales:** en 09577 hay una tortillería y no está en el directorio.
- **Fuera del catálogo de giros afiliables:** "pescado" y "medicinas".

Tasas de rechazo de 40% a 50% también aparecen en zonas de IDS medio:
- 09440, San Andrés Tetepilco: abarrotes;
- 14250, Miguel Hidalgo: pollerías y carnicerías.

## Acciones recomendadas

1. **Brigada de afiliación focalizada en los 5 CP sin Mercomuna**, empezando por 14734 y 04850. Hay que invitar primero a los comercios de los giros más buscados (carnicerías, panaderías y tortillerías): en 09577 la tortillería ya identificada y en 14426 los comercios de alimentos más cercanos.
2. **Aclarar si los tianguis pueden recibir vales y comunicarlo en la app.** Si no pueden, la app debe decirlo antes de que la persona vaya, para evitar viajes en vano. Si sí pueden, conviene un piloto de afiliación de oferentes en los tianguis de 09096 y 14734.
3. **Verificar los comercios afiliados con rechazo alto** (09440 abarrotes; 14250 pollerías y carnicerías). Sugerimos una llamada o visita de SAPCI para confirmar que conocen el procedimiento de canje y el reembolso. Si un comercio rechaza de forma reiterada, hay que revisar su permanencia en el directorio público, para que la persona beneficiaria no llegue a un lugar donde no le aceptarán el vale.

---
*Método.* Las señales salen de `scripts/10_informe_semanal.py` a partir de `GET /api/v1/feedback/summary`:
- **Rechazo alto:** más de 30% de rechazo, con al menos 3 confirmaciones.
- **"Sin oferta":** cero comercios afiliables del giro en el mismo CP.
- **IDS:** estrato más frecuente entre los comercios del CP (Evalúa, 2020).

La "colonia" se aproxima por código postal.

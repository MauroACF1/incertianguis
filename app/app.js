/* Canjea Cerca — prototipo del módulo para App CDMX (Chilangatón 2026).
   Sin frameworks. Datos: app/data/ (copiados con scripts/09_datos_app.py). */
"use strict";

// ---------- Configuración de la demo ----------
const DEMO_HOY = new Date(2026, 9, 25);            // domingo 25 de octubre de 2026
const FECHA_LIMITE = new Date(2026, 11, 31);       // 31 de diciembre de 2026
const UBICACION_DEMO = {                           // Utopía Elena Poniatowska Amor (aprox.)
  lat: 19.345, lon: -99.147,
  texto: "Demo: Utopía Elena Poniatowska Amor, San Lucas, Coyoacán",
};
const VALES = [{ valor: 100, cantidad: 7 }, { valor: 50, cantidad: 6 }];
const RADIO_MAPA_M = 2500;      // puntos que se pintan alrededor de la ubicación
const MAX_LISTA = 20;
const FACTOR_CAMINO = 1.3;      // distancia en línea recta -> caminando (aprox.)
const M_POR_MINUTO = 75;        // ~4.5 km/h
const CLAVE_EVENTOS = "canjeaCerca.eventos.v2";   // respaldo local si la API no responde
const API_FEEDBACK = "http://localhost:3001/api/v1/feedback";   // repo mapatianguis, rama feedback-api

const DIAS = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
const DIA_HOY = DIAS[DEMO_HOY.getDay()];

const FILTROS = [
  { clave: "todos", texto: "Todos", icono: "🛍️" },
  { clave: "abarrotes", texto: "Abarrotes", icono: "🏪", categoria: "Abarrotes y misceláneas" },
  { clave: "carniceria", texto: "Carnicería", icono: "🥩", categoria: "Carnicería" },
  { clave: "polleria", texto: "Pollería", icono: "🍗", categoria: "Pollería" },
  { clave: "frutas", texto: "Frutas y verduras", icono: "🥕", categoria: "Frutas y verduras" },
  { clave: "cremeria", texto: "Cremería", icono: "🧀", categoria: "Cremería, lácteos y embutidos" },
  { clave: "panaderia", texto: "Panadería", icono: "🥖", categoria: "Panadería" },
  { clave: "tortilleria", texto: "Tortillería", icono: "🫓", categoria: "Tortillería" },
  { clave: "mercado", texto: "Mercado", icono: "🏛️" },
  { clave: "tianguis", texto: "Tianguis", icono: "⛺" },
];
const FILTRO_POR_CATEGORIA = Object.fromEntries(FILTROS.filter(f => f.categoria).map(f => [f.categoria, f]));

// ---------- Estado ----------
const estado = {
  lugares: [],          // comercios Mercomuna exactos, mercados y tianguis
  porId: new Map(),
  porCp: [],            // filas Mercomuna con precision="cp"
  centroides: [],       // puntos de referencia para estimar el CP de una coordenada
  ubicacion: { ...UBICACION_DEMO },
  cp: null,
  filtro: "todos",
  soloVales: false,
  mapa: null,
  capaPuntos: null,
  marcadorYo: null,
  ultimo: null,         // {cp, giro} del comercio sobre el que se respondió
  evento: null,         // evento en curso; se envía al salir de "Gracias"
};

// ---------- Utilidades ----------
const $ = sel => document.querySelector(sel);

function el(etiqueta, props = {}, ...hijos) {
  const n = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const h of hijos) if (h != null) n.append(h);
  return n;
}

function distanciaM(a, b) {
  const R = 6371000, rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

function textoCaminando(m) {
  const camino = m * FACTOR_CAMINO;
  const min = Math.max(1, Math.round(camino / M_POR_MINUTO));
  const dist = camino < 1000 ? `${Math.round(camino / 10) * 10} m` : `${(camino / 1000).toFixed(1)} km`;
  return `${dist} · ${min} min caminando (aprox.)`;
}

function pesos(n) {
  return n.toLocaleString("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
}

function giroTexto(categoria, giro) {
  if (categoria) return categoria;
  return giro === "OTRO" ? "Otros giros" : capitaliza(giro);
}

function capitaliza(t) {
  t = (t || "").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

// CSV con comillas dobles (RFC 4180 básico).
function parseCSV(texto) {
  const filas = [];
  let fila = [], campo = "", comillas = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (comillas) {
      if (c === '"' && texto[i + 1] === '"') { campo += '"'; i++; }
      else if (c === '"') comillas = false;
      else campo += c;
    } else if (c === '"') comillas = true;
    else if (c === ",") { fila.push(campo); campo = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && texto[i + 1] === "\n") i++;
      fila.push(campo); filas.push(fila); fila = []; campo = "";
    } else campo += c;
  }
  if (campo || fila.length) { fila.push(campo); filas.push(fila); }
  const [enc, ...datos] = filas;
  return datos.filter(f => f.length === enc.length).map(f => Object.fromEntries(enc.map((k, i) => [k, f[i]])));
}

// ---------- Eventos: API de feedback con respaldo en localStorage ----------
// Un evento por visita: se crea al confirmar Sí/No, se completa con las preguntas
// opcionales y se envía al salir de "Gracias". Si la API no responde, se guarda local.
function leeEventos() {
  try { return JSON.parse(localStorage.getItem(CLAVE_EVENTOS)) || []; }
  catch { return []; }
}
function guardaEventos(lista) {
  try { localStorage.setItem(CLAVE_EVENTOS, JSON.stringify(lista)); } catch { /* sin almacenamiento */ }
}
function nuevoEvento(respuesta) {
  if (!estado.ultimo) return;
  estado.evento = {
    fecha: DEMO_HOY.toISOString().slice(0, 10), cp: estado.ultimo.cp, giro: estado.ultimo.giro,
    respuesta, encontro: null, dificultad: null, busca: null,
  };
}
function completaEvento(campo, valor) {
  if (estado.evento) estado.evento[campo] = valor;
}
async function enviaEvento() {
  const ev = estado.evento;
  if (!ev) return;
  estado.evento = null;
  try {
    const r = await fetch(API_FEEDBACK, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(ev),
      keepalive: true, signal: AbortSignal.timeout(3000),
    });
    if (!r.ok) throw new Error(`API respondió ${r.status}`);
  } catch {
    guardaEventos([...leeEventos(), ev]);
  }
}
function eventosEjemplo() {
  // 30 eventos ficticios, deterministas, para que el panel no se vea vacío sin la API.
  const cps = ["04030", "04000", "04100", "04330", "04360", "04480", "09820", "09310"];
  const giros = ["Abarrotes y misceláneas", "Tortillería", "Frutas y verduras", "Pollería", "Carnicería", "Mercado"];
  const busca = [null, "tortillería", null, "carnicería", null, null, "pan"];
  return Array.from({ length: 30 }, (_, i) => {
    const rechazo = i % 4 === 0;
    return {
      fecha: `2026-10-${String(12 + (i % 13)).padStart(2, "0")}`,
      cp: cps[(i * 3) % cps.length],
      giro: giros[(i * 5) % giros.length],
      respuesta: rechazo ? "no_aceptado" : "aceptado",
      encontro: rechazo ? "no" : ["si", "parcial"][i % 2],
      dificultad: rechazo ? "no_aceptaban" : ["nada", "distancia", "horario", "sin_producto"][i % 4],
      busca: busca[i % busca.length],
    };
  });
}
function siembraEventos(forzar = false) {
  if (forzar || !leeEventos().length) guardaEventos(eventosEjemplo());
}

// ---------- Carga de datos ----------
async function cargaDatos() {
  const [merco, mercoCsv, tianguis, mercados] = await Promise.all([
    fetch("data/mercomuna.geojson").then(r => r.json()),
    fetch("data/mercomuna.csv").then(r => r.text()),
    fetch("data/tianguis.geojson").then(r => r.json()),
    fetch("data/mercados_publicos.geojson").then(r => r.json()),
  ]);

  const filas = parseCSV(mercoCsv);
  for (const f of filas) {
    const lat = parseFloat(f.lat), lon = parseFloat(f.lon);
    if (Number.isFinite(lat)) estado.centroides.push({ lat, lon, cp: f.cp });
    if (f.precision === "cp") estado.porCp.push(f);
  }

  const agrega = l => { estado.lugares.push(l); estado.porId.set(l.id, l); };
  merco.features.forEach((f, i) => {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    const filtro = FILTRO_POR_CATEGORIA[p.categoria];
    agrega({
      id: `c${i}`, tipo: "comercio", nombre: p.nombre, lat, lon, cp: p.cp, alcaldia: p.alcaldia,
      direccion: p.direccion, filtro: filtro ? filtro.clave : "otros",
      giro: giroTexto(p.categoria, p.giro), icono: filtro ? filtro.icono : "🛍️", vales: true,
    });
  });
  mercados.features.forEach((f, i) => {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    agrega({
      id: `m${i}`, tipo: "mercado", nombre: p.nombre, lat, lon, alcaldia: p.alcaldia,
      direccion: [p.direccion, p.colonia].filter(Boolean).join(", "), filtro: "mercado",
      giro: `Mercado público${p.tipo ? " · " + p.tipo.toLowerCase() : ""}`, icono: "🏛️", vales: false,
      extra: p.locales ? `${p.locales} locales` : "",
    });
  });
  tianguis.features.forEach((f, i) => {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    agrega({
      id: `t${i}`, tipo: "tianguis", nombre: p.nombre, lat, lon, alcaldia: p.alcaldia,
      direccion: [p.ubicacion, p.colonia].filter(Boolean).join(", "), filtro: "tianguis",
      giro: "Tianguis", icono: "⛺", vales: false, dias: p.dias || "", horario: p.horario || "",
      hoy: (p.dias || "").split(", ").includes(DIA_HOY),
    });
  });
}

function cpCercano(punto) {
  let mejor = null, dMin = Infinity;
  for (const c of estado.centroides) {
    const d = distanciaM(punto, c);
    if (d < dMin) { dMin = d; mejor = c.cp; }
  }
  return mejor;
}

// ---------- Inicio ----------
function pintaInicio() {
  const total = VALES.reduce((s, v) => s + v.valor * v.cantidad, 0);
  $("#saldo-total").textContent = pesos(total);
  $("#lista-vales").replaceChildren(...VALES.map(v =>
    el("li", {}, el("span", { text: `${v.cantidad} vales de ${pesos(v.valor)}` }),
                 el("strong", { text: pesos(v.valor * v.cantidad) }))));
  const dias = Math.round((Date.UTC(2026, 11, 31) - Date.UTC(2026, DEMO_HOY.getMonth(), DEMO_HOY.getDate())) / 864e5);
  $("#dias-restantes").textContent = `Faltan ${dias} días`;
}

// ---------- Mapa y lista ----------
function iniciaMapa() {
  estado.mapa = L.map("mapa", { zoomControl: true, attributionControl: true })
    .setView([estado.ubicacion.lat, estado.ubicacion.lon], 15);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap",
  }).addTo(estado.mapa);
  estado.capaPuntos = L.layerGroup().addTo(estado.mapa);
  estado.marcadorYo = L.marker([estado.ubicacion.lat, estado.ubicacion.lon], {
    icon: L.divIcon({ className: "", html: '<div class="icono-yo"></div>', iconSize: [20, 20] }),
    keyboard: false, title: "Tu ubicación",
  }).addTo(estado.mapa);
}

function pasaFiltro(l) {
  if (estado.soloVales && !l.vales) return false;
  return estado.filtro === "todos" || l.filtro === estado.filtro;
}

function pintaFiltros() {
  $("#filtros").replaceChildren(...FILTROS.map(f => {
    const b = el("button", { type: "button", "aria-pressed": String(f.clave === estado.filtro), text: `${f.icono} ${f.texto}` });
    b.addEventListener("click", () => { estado.filtro = f.clave; pintaFiltros(); actualizaCercanos(); });
    return b;
  }));
}

function etiquetaLugar(l) {
  if (l.vales) return el("span", { class: "item-vales", text: "✔ Acepta vales Mercomuna" });
  if (l.tipo === "mercado") return el("span", { class: "etiqueta-info", text: "Pregunta en los locales por vales" });
  return null;
}

function actualizaCercanos() {
  const u = estado.ubicacion;
  const visibles = estado.lugares
    .filter(pasaFiltro)
    .map(l => ({ l, d: distanciaM(u, l) }))
    .filter(x => x.d <= RADIO_MAPA_M)
    .sort((a, b) => a.d - b.d);

  estado.capaPuntos.clearLayers();
  for (const { l } of visibles.slice(0, 300)) {
    const clases = `icono-mapa ${l.tipo === "comercio" ? "" : l.tipo} ${l.hoy ? "hoy" : ""}`;
    L.marker([l.lat, l.lon], {
      icon: L.divIcon({ className: "", html: `<div class="${clases}">${l.icono}</div>`, iconSize: [34, 34] }),
      title: l.nombre, alt: l.nombre,
    }).on("click", () => { location.hash = `#comercio/${l.id}`; }).addTo(estado.capaPuntos);
  }

  const lista = visibles.slice(0, MAX_LISTA).map(({ l, d }) => {
    const nombre = el("div", { class: "item-nombre", text: l.nombre });
    if (l.hoy) nombre.append(el("span", { class: "etiqueta-hoy", text: "Hoy" }));
    const giro = l.tipo === "tianguis" ? `Tianguis · ${l.dias}` : l.giro;
    return el("li", {}, el("a", { class: "item", href: `#comercio/${l.id}` },
      el("span", { class: "item-icono", "aria-hidden": "true", text: l.icono }),
      el("div", {}, nombre, el("div", { class: "item-giro", text: giro }),
        el("div", { class: "item-dist", text: textoCaminando(d) }), etiquetaLugar(l))));
  });
  $("#lista-cercanos").replaceChildren(...(lista.length ? lista
    : [el("li", { class: "vacio", text: "No hay lugares con este filtro a menos de 2.5 km." })]));

  pintaListaCp();
}

function pintaListaCp() {
  const f = FILTROS.find(x => x.clave === estado.filtro);
  const filas = estado.porCp.filter(r => r.cp === estado.cp &&
    (estado.filtro === "todos" || (f.categoria && r.categoria === f.categoria)));
  $("#titulo-cp").textContent = `Más comercios en tu código postal (${estado.cp || "—"})`;
  $("#nota-cp").textContent = filas.length
    ? "Aceptan vales, pero aún no tenemos su ubicación exacta en el mapa."
    : "";
  $("#lista-cp").replaceChildren(...(filas.length ? filas.slice(0, 50).map(r =>
    el("li", {}, el("div", { class: "item-nombre", text: r.nombre }),
      el("div", { class: "item-giro", text: giroTexto(r.categoria, r.giro) }),
      el("div", { class: "item-dist", text: r.direccion }),
      el("span", { class: "item-vales", text: "✔ Acepta vales Mercomuna" })))
    : [el("li", { class: "vacio", text: "No hay más comercios registrados en tu código postal con este filtro." })]));
}

function fijaUbicacion(lat, lon, texto) {
  estado.ubicacion = { lat, lon, texto };
  estado.cp = cpCercano(estado.ubicacion);
  $("#ubicacion-texto").textContent = `${texto} · CP aprox. ${estado.cp}`;
  if (estado.mapa) {
    estado.marcadorYo.setLatLng([lat, lon]);
    estado.mapa.setView([lat, lon], 15);
    actualizaCercanos();
  }
}

function usaUbicacionReal() {
  const b = $("#btn-ubicacion");
  if (!("geolocation" in navigator)) { b.textContent = "Tu navegador no permite ubicación"; return; }
  b.textContent = "Buscando tu ubicación…";
  navigator.geolocation.getCurrentPosition(
    p => { fijaUbicacion(p.coords.latitude, p.coords.longitude, "Tu ubicación"); b.textContent = "📍 Usar mi ubicación"; },
    () => { b.textContent = "No se pudo obtener tu ubicación (se usa la de demo)"; },
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 });
}

// ---------- Ficha ----------
function pintaFicha(id) {
  if (!estado.porId.size) return;            // datos aún cargando; navega() se vuelve a llamar
  const l = estado.porId.get(id);
  if (!l) { location.hash = "#mapa"; return; }
  $("#ficha-icono").textContent = l.icono;
  $("#ficha-nombre").textContent = l.nombre;
  $("#ficha-giro").textContent = l.giro;
  $("#ficha-direccion").textContent = l.direccion ? `📍 ${l.direccion}` : "";
  const extra = l.tipo === "tianguis"
    ? `🗓️ ${l.dias}${l.hoy ? " · ¡Se instala hoy!" : ""}${l.horario ? " · " + capitaliza(l.horario) : ""}`
    : (l.extra || "");
  $("#ficha-extra").textContent = extra;
  const vales = $("#ficha-vales");
  vales.hidden = !l.vales && l.tipo !== "mercado";
  vales.textContent = l.vales ? "✔ Acepta vales Mercomuna" : "Pregunta en los locales por vales Mercomuna";
  $("#ficha-llegar").href = `https://www.google.com/maps/dir/?api=1&destination=${l.lat},${l.lon}&travelmode=walking`;
  estado.ultimo = { cp: l.cp || cpCercano(l), giro: l.tipo === "comercio" ? l.giro : capitaliza(l.tipo) };
}

// ---------- Gracias ----------
function reiniciaGracias() {
  document.querySelectorAll("[data-ruta=gracias] .pregunta").forEach(p => p.classList.remove("respondida"));
  document.querySelectorAll("[data-ruta=gracias] .opciones button").forEach(b => b.setAttribute("aria-pressed", "false"));
  $("#deseo").value = "";
}

// ---------- Panel SEDECO ----------
const ETIQUETAS_DIFICULTAD = {
  distancia: "Distancia", horario: "Horario", no_aceptaban: "No aceptaban", sin_producto: "Sin producto", nada: "Nada",
};

// Mismo agregado que GET /api/v1/feedback/summary, para cuando la API no responde.
function normalizaProducto(t) {
  return (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim()
    .replace(/^(un|una|unos|unas|el|la|los|las|mas)\s+/, "").replace(/[^a-z\s]/g, "").replace(/\s+/g, " ").trim();
}
function ranking(conteos) {
  return [...conteos.entries()].map(([producto, n]) => ({ producto, n }))
    .sort((a, b) => b.n - a.n || a.producto.localeCompare(b.producto));
}
function resumenLocal(eventos) {
  const grupos = new Map(), productos = new Map();
  for (const e of eventos) {
    const k = `${e.cp}|${e.giro}`;
    if (!grupos.has(k)) grupos.set(k, { cp: e.cp, giro: e.giro, eventos: 0, aceptados: 0, noAceptados: 0,
      encontro: { si: 0, parcial: 0, no: 0 }, dif: new Map(), prod: new Map() });
    const g = grupos.get(k);
    g.eventos++;
    if (e.respuesta === "aceptado") g.aceptados++;
    if (e.respuesta === "no_aceptado") g.noAceptados++;
    if (e.encontro) g.encontro[e.encontro]++;
    if (e.dificultad && e.dificultad !== "nada") g.dif.set(e.dificultad, (g.dif.get(e.dificultad) || 0) + 1);
    const p = normalizaProducto(e.busca);
    if (p) { g.prod.set(p, (g.prod.get(p) || 0) + 1); productos.set(p, (productos.get(p) || 0) + 1); }
  }
  return {
    totalEventos: eventos.length,
    productosBuscados: ranking(productos),
    grupos: [...grupos.values()].map(({ dif, prod, ...g }) => {
      const conf = g.aceptados + g.noAceptados;
      return { ...g, tasaAceptacion: conf ? g.aceptados / conf : null,
        dificultadComun: ranking(dif)[0]?.producto ?? null, productosBuscados: ranking(prod) };
    }).sort((a, b) => a.cp.localeCompare(b.cp) || a.giro.localeCompare(b.giro)),
  };
}

async function pintaPanel() {
  let resumen, fuente;
  try {
    const r = await fetch(`${API_FEEDBACK}/summary`, { cache: "no-store", signal: AbortSignal.timeout(2500) });
    if (!r.ok) throw new Error(`API respondió ${r.status}`);
    resumen = await r.json();
    fuente = "Fuente: API de retroalimentación (todas las personas usuarias).";
  } catch {
    resumen = resumenLocal(leeEventos());
    fuente = "Fuente: este dispositivo. La API no respondió; se muestran las respuestas guardadas aquí.";
  }
  $("#panel-fuente").textContent = fuente;

  const grupos = resumen.grupos;
  const si = grupos.reduce((s, g) => s + g.aceptados, 0), no = grupos.reduce((s, g) => s + g.noAceptados, 0);
  $("#panel-resumen").replaceChildren(
    el("div", {}, el("strong", { text: String(resumen.totalEventos) }), "respuestas"),
    el("div", {}, el("strong", { text: String(new Set(grupos.map(g => g.cp)).size) }), "códigos postales"),
    el("div", {}, el("strong", { text: String(si + no) }), "confirmaciones de vale"),
    el("div", {}, el("strong", { text: si + no ? `${Math.round(100 * si / (si + no))}%` : "—" }), "vales aceptados"));

  const enc = ["CP", "Giro", "Aceptado", "No aceptado", "% acept.", "Encontró (sí/parc./no)", "Dificultad común", "Buscan"];
  const cuerpo = grupos.map(g => el("tr", {},
    el("td", { text: g.cp }), el("td", { text: g.giro }),
    el("td", { class: "num", text: String(g.aceptados) }), el("td", { class: "num", text: String(g.noAceptados) }),
    el("td", { class: "num", text: g.tasaAceptacion == null ? "—" : `${Math.round(100 * g.tasaAceptacion)}%` }),
    el("td", { class: "num", text: `${g.encontro.si}/${g.encontro.parcial}/${g.encontro.no}` }),
    el("td", { text: g.dificultadComun ? ETIQUETAS_DIFICULTAD[g.dificultadComun] || g.dificultadComun : "—" }),
    el("td", { text: g.productosBuscados.map(p => p.producto).slice(0, 2).join(", ") || "—" })));
  $("#panel-tabla").replaceChildren(
    el("thead", {}, el("tr", {}, ...enc.map(t => el("th", { text: t })))),
    el("tbody", {}, ...cuerpo));
  $("#panel-deseos").replaceChildren(...(resumen.productosBuscados.length
    ? resumen.productosBuscados.map(({ producto, n }) =>
        el("li", { class: "lista-cp" }, el("div", { class: "item", text: `${capitaliza(producto)} · ${n}` })))
    : [el("li", { class: "vacio", text: "Sin sugerencias todavía." })]));
}

// ---------- Navegación ----------
const TITULOS = { inicio: "Canjea Cerca", mapa: "¿Dónde canjeo?", comercio: "Comercio", gracias: "Gracias", panel: "Panel SEDECO" };

function navega() {
  const [ruta, param] = (location.hash.slice(1) || "inicio").split("/");
  const destino = TITULOS[ruta] ? ruta : "inicio";
  if (destino !== "gracias") enviaEvento();
  document.querySelectorAll(".pantalla").forEach(p => p.classList.toggle("activa", p.dataset.ruta === destino));
  $("#titulo").textContent = TITULOS[destino];
  $("#btn-atras").hidden = destino === "inicio";
  if (destino === "mapa" && estado.mapa) setTimeout(() => estado.mapa.invalidateSize(), 0);
  if (destino === "comercio") pintaFicha(param);
  if (destino === "gracias") reiniciaGracias();
  if (destino === "panel") pintaPanel();
  window.scrollTo(0, 0);
}

function conectaEventos() {
  $("#btn-atras").addEventListener("click", () => {
    const ruta = location.hash.slice(1).split("/")[0];
    location.hash = ruta === "mapa" || ruta === "panel" ? "#inicio" : "#mapa";
  });
  $("#btn-ubicacion").addEventListener("click", usaUbicacionReal);
  $("#solo-vales").addEventListener("change", e => { estado.soloVales = e.target.checked; actualizaCercanos(); });
  document.querySelectorAll("[data-retro]").forEach(b => b.addEventListener("click", () => {
    nuevoEvento(b.dataset.retro);
    location.hash = "#gracias";
  }));
  document.querySelectorAll("[data-ruta=gracias] .pregunta[data-pregunta]").forEach(p => {
    p.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
      if (p.classList.contains("respondida")) return;   // una sola pulsación
      b.setAttribute("aria-pressed", "true");
      p.classList.add("respondida");
      completaEvento(p.dataset.pregunta, b.dataset.valor);
    }));
  });
  $("#btn-deseo").addEventListener("click", () => {
    const t = $("#deseo").value.replace(/[\d@]/g, "").trim().slice(0, 60);   // sin números ni correos
    if (!t) return;
    completaEvento("busca", t);
    $("#btn-deseo").closest(".pregunta").classList.add("respondida");
    $("#deseo").value = "";
  });
  $("#btn-reiniciar").addEventListener("click", () => { siembraEventos(true); pintaPanel(); });
  window.addEventListener("hashchange", navega);
  window.addEventListener("pagehide", enviaEvento);
}

async function inicia() {
  pintaInicio();
  siembraEventos();
  conectaEventos();
  navega();
  try {
    await cargaDatos();
  } catch (err) {
    $("#lista-cercanos").replaceChildren(el("li", { class: "vacio",
      text: "No se pudieron cargar los datos. Abre la app con un servidor local (py -3.12 -m http.server)." }));
    return;
  }
  iniciaMapa();
  pintaFiltros();
  fijaUbicacion(UBICACION_DEMO.lat, UBICACION_DEMO.lon, UBICACION_DEMO.texto);
  navega();
}

inicia();

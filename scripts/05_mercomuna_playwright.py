"""Explora con Chromium headless las páginas de Mercomuna para hallar el directorio de comercios.

Registra cada petición/respuesta de red (URL, método, status, content-type, tamaño de XHR/fetch),
espera networkidle, intenta interactuar con selectores de alcaldía o cajas de búsqueda y
sigue enlaces que parezcan de directorio. Escribe un resumen en stdout y, si se pasa
--log, un JSON con todas las peticiones (para depurar; no se guarda en data/).

Hallazgo (2026-10-25): https://comercios-mercomuna.cdmx.gob.mx carga la tabla con
GET /?alcaldia=&colonia=&giro=&establecimiento=&page=N  -> JSON {html, pagination, total}
(10 filas por página, tamaño fijo). Con --descarga se recorre esa paginación con pausas
y se guarda data/raw/mercomuna_directorio.csv (nombre, giro, calle_numero, cp, alcaldia, colonia).

Uso: py -3.12 scripts/05_mercomuna_playwright.py [--log ruta.json]
     py -3.12 scripts/05_mercomuna_playwright.py --descarga [--pausa 0.7] [--cache dir]
"""
import json
import re
import sys
import time

from playwright.sync_api import sync_playwright, Error as PWError

UA = "Incertianguis-Chilangaton2026/0.1 (hackaton; datos publicos)"
PAGINAS = [
    "https://comercios-mercomuna.cdmx.gob.mx",
    "https://sapci.cdmx.gob.mx/mercomuna",
    "https://sapci.cdmx.gob.mx/programas/programa/ingreso-social-mercomuna-cdmx",
]
PALABRAS_DIR = re.compile(r"directorio|comercio|tienda|mapa|establecimiento|padr[oó]n|consulta", re.I)
MAX_EXTRA = 6


def visita(page, url, registro):
    print(f"\n=== {url}")
    try:
        resp = page.goto(url, wait_until="networkidle", timeout=45000)
        print(f"  status documento: {resp.status if resp else 'sin respuesta'}")
    except PWError as e:
        print(f"  ERROR goto: {str(e).splitlines()[0]}")
        return []
    print(f"  titulo: {page.title()!r}  url final: {page.url}")
    texto = page.inner_text("body")[:600].replace("\n", " | ")
    print(f"  texto: {texto}")
    # Interactuar con selects y buscadores.
    for sel in page.query_selector_all("select"):
        opciones = [o.inner_text().strip() for o in sel.query_selector_all("option")]
        print(f"  <select> opciones: {opciones[:20]}")
        if len(opciones) > 1:
            try:
                sel.select_option(index=1)
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWError as e:
                print(f"   select falló: {str(e).splitlines()[0]}")
    for inp in page.query_selector_all("input[type=search], input[type=text]")[:2]:
        try:
            inp.fill("Iztapalapa")
            inp.press("Enter")
            page.wait_for_load_state("networkidle", timeout=15000)
            print("  buscador probado con 'Iztapalapa'")
        except PWError as e:
            print(f"   input falló: {str(e).splitlines()[0]}")
    enlaces = []
    for a in page.query_selector_all("a[href]"):
        href = a.get_attribute("href") or ""
        txt = (a.inner_text() or "").strip()
        if PALABRAS_DIR.search(href + " " + txt) or re.search(r"\.(csv|xlsx?|json|pdf)$", href, re.I):
            enlaces.append((txt[:60], page.urljoin(href) if hasattr(page, "urljoin") else href))
    # Resolver relativos
    from urllib.parse import urljoin
    enlaces = [(t, urljoin(page.url, h)) for t, h in enlaces]
    for t, h in enlaces:
        print(f"  enlace candidato: {t!r} -> {h}")
    return [h for _, h in enlaces]


def main():
    log_path = sys.argv[sys.argv.index("--log") + 1] if "--log" in sys.argv else None
    registro = []
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True)
        ctx = nav.new_context(user_agent=UA, ignore_https_errors=True)
        page = ctx.new_page()

        def on_response(r):
            req = r.request
            ct = r.headers.get("content-type", "")
            tam = None
            if req.resource_type in ("xhr", "fetch") or "json" in ct or "csv" in ct:
                try:
                    tam = len(r.body())
                except PWError:
                    tam = None
            registro.append({"url": r.url, "metodo": req.method, "status": r.status,
                             "tipo": req.resource_type, "content_type": ct, "bytes": tam})

        def on_fail(req):
            registro.append({"url": req.url, "metodo": req.method, "status": None,
                             "tipo": req.resource_type, "error": req.failure})

        page.on("response", on_response)
        page.on("requestfailed", on_fail)

        vistos = set()
        pendientes = list(PAGINAS)
        extra = 0
        while pendientes:
            url = pendientes.pop(0)
            if url in vistos:
                continue
            vistos.add(url)
            nuevos = visita(page, url, registro)
            for n in nuevos:
                if n not in vistos and n.startswith("http") and extra < MAX_EXTRA and "mercomuna" in n.lower():
                    pendientes.append(n)
                    extra += 1
            time.sleep(1.5)
        nav.close()

    print("\n=== Peticiones XHR/fetch/JSON/CSV y fallidas")
    for r in registro:
        if r.get("bytes") is not None or r.get("status") is None or r["tipo"] in ("xhr", "fetch"):
            print(f"  {r['metodo']} {r.get('status')} {r['tipo']} {r.get('content_type','')} "
                  f"{r.get('bytes')} {r.get('error') or ''} {r['url'][:160]}")
    print(f"\nTotal respuestas/fallos registrados: {len(registro)}")
    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=1)


def descarga():
    import csv
    import html as htmlmod
    import urllib.request
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    pausa = float(sys.argv[sys.argv.index("--pausa") + 1]) if "--pausa" in sys.argv else 0.7
    cache = Path(sys.argv[sys.argv.index("--cache") + 1]) if "--cache" in sys.argv else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    base = "https://comercios-mercomuna.cdmx.gob.mx/?alcaldia=&colonia=&giro=&establecimiento=&page={}"

    def pagina(n):
        f = cache / f"p{n:04d}.json" if cache else None
        if f and f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        req = urllib.request.Request(base.format(n), headers={
            "User-Agent": UA, "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
        for intento in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    txt = r.read().decode("utf-8")
                break
            except Exception as e:  # noqa: BLE001
                print(f"  p{n} intento {intento + 1} falló: {e}")
                time.sleep(5)
        else:
            raise RuntimeError(f"página {n} no descargó")
        if f:
            f.write_text(txt, encoding="utf-8")
        time.sleep(pausa)
        return json.loads(txt)

    fila_re = re.compile(r"<tr>(.*?)</tr>", re.S)
    celda_re = re.compile(r"<td>(.*?)</td>", re.S)
    cp_re = re.compile(r"\s*C\.P\.\s*(\d{4,5})\s*$")

    primera = pagina(1)
    total = int(primera["total"])
    paginas = -(-total // 10)
    print(f"total={total} paginas={paginas}")
    filas = []
    for n in range(1, paginas + 1):
        d = primera if n == 1 else pagina(n)
        sin_coment = re.sub(r"<!--.*?-->", "", d["html"], flags=re.S)
        for tr in fila_re.findall(sin_coment):
            c = [re.sub(r"\s+", " ", htmlmod.unescape(x)).strip() for x in celda_re.findall(tr)]
            if len(c) < 5:
                continue
            nombre, direccion, colonia, alcaldia, giro = c[:5]
            m = cp_re.search(direccion)
            cp = m.group(1).zfill(5) if m else ""
            calle = cp_re.sub("", direccion).strip()
            filas.append({"nombre": nombre, "giro": giro, "calle_numero": calle, "cp": cp,
                          "alcaldia": alcaldia, "colonia": colonia})
        if n % 50 == 0:
            print(f"  página {n}/{paginas} filas={len(filas)}", flush=True)
    salida = raiz / "data" / "raw" / "mercomuna_directorio.csv"
    with open(salida, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["nombre", "giro", "calle_numero", "cp", "alcaldia", "colonia"])
        w.writeheader()
        w.writerows(filas)
    print(f"guardado {salida} filas={len(filas)} (total reportado {total})")


if __name__ == "__main__":
    if "--descarga" in sys.argv:
        descarga()
    else:
        main()

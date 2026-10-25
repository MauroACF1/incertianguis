"""Calcula las señales semanales a partir del resumen de retroalimentación de Canjea Cerca.

Lee GET /api/v1/feedback/summary (API de mapatianguis, rama feedback-api) y lo cruza
con nuestras capas para encontrar:
  1. rechazo_alto: CP con tasa de rechazo del vale > 30% (mínimo 3 confirmaciones).
  2. productos_sin_oferta: productos buscados cuyo giro no tiene comercios afiliables
     (DENUE) en el CP, o que no tienen giro afiliable equivalente. También marca
     dónde sí hay comercios afiliables pero ninguno en el directorio Mercomuna.
  3. ids_bajo_sin_mercomuna: CP de IDS bajo o muy bajo con respuestas (demanda)
     y cero comercios Mercomuna.
"Colonia" se aproxima por código postal: el resumen es por CP. Las colonias listadas
son las más frecuentes del CP en el DENUE.

Uso: py -3.12 scripts/10_informe_semanal.py [--url URL | --archivo summary.json]
Salida: data/processed/senales_semana.json
"""
import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
URL = "http://localhost:3001/api/v1/feedback/summary"
UMBRAL_RECHAZO = 0.30
MIN_CONFIRMACIONES = 3
IDS_BAJO = {"bajo", "muy bajo"}

# Producto buscado -> categoría de comercios afiliables (orden: la primera gana).
PRODUCTOS = [
    (r"tortill", "Tortillería"),
    (r"\bpan\b|panader|bolillo", "Panadería"),
    (r"pollo|poller", "Pollería"),
    (r"carne|carnic|\bres\b|cerdo|tocin", "Carnicería"),
    (r"fruta|verdur|legumbre|recaud", "Frutas y verduras"),
    (r"queso|leche|crema|lacteo|embutid|cremer", "Cremería, lácteos y embutidos"),
    (r"abarrot|miscel", "Abarrotes y misceláneas"),
]


def sin_acentos(texto):
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()


def categoria_producto(producto):
    p = sin_acentos(producto)
    return next((cat for patron, cat in PRODUCTOS if re.search(patron, p)), None)


def lee_summary(args):
    if args.archivo:
        return json.loads(Path(args.archivo).read_text(encoding="utf-8")), str(args.archivo)
    try:
        with urllib.request.urlopen(args.url, timeout=10) as r:
            return json.load(r), args.url
    except OSError as e:
        sys.exit(f"No se pudo leer {args.url} ({e}). Levanta la API (npm run dev:api) o usa --archivo.")


def moda(serie):
    serie = serie.dropna()
    return serie.mode().iat[0] if len(serie) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    ap.add_argument("--archivo")
    args = ap.parse_args()
    summary, fuente = lee_summary(args)

    afil = pd.read_csv(PROC / "comercios_afiliables.csv", dtype={"cp": str})
    merco = pd.read_csv(PROC / "mercomuna.csv", dtype={"cp": str})
    denue = pd.read_csv(RAIZ / "data" / "raw" / "denue_09_46.csv", dtype=str, usecols=["cod_postal", "nomb_asent"])
    colonias = (denue.dropna().groupby("cod_postal")["nomb_asent"]
                .agg(lambda s: [c.title() for c, _ in Counter(s).most_common(3)]).to_dict())
    alcaldia_cp = afil.groupby("cp")["alcaldia"].agg(moda).to_dict()
    ids_cp = afil.groupby("cp")["ids_estrato"].agg(moda).to_dict()
    afil_cp_cat = afil.groupby(["cp", "giro"]).size().to_dict()
    merco_cp = merco.groupby("cp").size().to_dict()
    merco_cp_cat = merco.dropna(subset=["categoria"]).groupby(["cp", "categoria"]).size().to_dict()

    def lugar(cp):
        return {"cp": cp, "alcaldia": alcaldia_cp.get(cp), "colonias": colonias.get(cp, []),
                "ids_estrato": ids_cp.get(cp)}

    grupos = pd.DataFrame(summary["grupos"])
    por_cp = grupos.groupby("cp").agg(eventos=("eventos", "sum"), aceptados=("aceptados", "sum"),
                                      no_aceptados=("noAceptados", "sum"))

    # 1. Rechazo alto
    rechazo = []
    for cp, r in por_cp.iterrows():
        conf = r.aceptados + r.no_aceptados
        if conf >= MIN_CONFIRMACIONES and r.no_aceptados / conf > UMBRAL_RECHAZO:
            giros = grupos[grupos.cp == cp]
            rechazo.append({**lugar(cp), "confirmaciones": int(conf), "no_aceptados": int(r.no_aceptados),
                            "tasa_rechazo": round(r.no_aceptados / conf, 3),
                            "giros": [{"giro": g.giro, "aceptados": int(g.aceptados), "no_aceptados": int(g.noAceptados)}
                                      for g in giros.itertuples() if g.noAceptados]})
    rechazo.sort(key=lambda x: (-x["tasa_rechazo"], -x["confirmaciones"]))

    # 2. Productos buscados sin oferta
    buscados = Counter()
    for g in summary["grupos"]:
        for p in g["productosBuscados"]:
            buscados[(g["cp"], p["producto"])] += p["n"]
    productos = []
    for (cp, producto), n in buscados.items():
        cat = categoria_producto(producto)
        afiliables = afil_cp_cat.get((cp, cat), 0) if cat else 0
        en_mercomuna = merco_cp_cat.get((cp, cat), 0) if cat else 0
        if cat is None:
            situacion = "sin_giro_afiliable"
        elif afiliables == 0:
            situacion = "sin_oferta_afiliable_en_cp"
        elif en_mercomuna == 0:
            situacion = "hay_oferta_pero_ninguno_acepta_vales"
        else:
            continue
        productos.append({**lugar(cp), "producto": producto, "veces": n, "categoria": cat,
                          "afiliables_en_cp": afiliables, "mercomuna_en_cp": en_mercomuna, "situacion": situacion})
    productos.sort(key=lambda x: (-x["veces"], x["cp"]))

    # 3. IDS bajo con demanda y cero Mercomuna
    ids_bajo = [{**lugar(cp), "eventos": int(r.eventos), "mercomuna_en_cp": 0,
                 "afiliables_en_cp": int(sum(v for (c, _), v in afil_cp_cat.items() if c == cp))}
                for cp, r in por_cp.iterrows()
                if ids_cp.get(cp) in IDS_BAJO and merco_cp.get(cp, 0) == 0]
    ids_bajo.sort(key=lambda x: -x["eventos"])

    si, no = int(grupos.aceptados.sum()), int(grupos.noAceptados.sum())
    salida = {
        "generado": date.today().isoformat(),
        "fuente_summary": fuente,
        "aviso": "Las respuestas provienen de eventos SINTÉTICOS (scripts/seed-feedback.mjs de mapatianguis); "
                 "los CP y los datos de comercios son reales.",
        "umbrales": {"tasa_rechazo": UMBRAL_RECHAZO, "min_confirmaciones": MIN_CONFIRMACIONES,
                     "ids_bajo": sorted(IDS_BAJO)},
        "totales": {"eventos": summary["totalEventos"], "codigos_postales": int(len(por_cp)),
                    "aceptados": si, "no_aceptados": no,
                    "tasa_aceptacion": round(si / (si + no), 3) if si + no else None,
                    "productos_mas_buscados": summary["productosBuscados"][:5]},
        "senales": {"rechazo_alto": rechazo, "productos_sin_oferta": productos,
                    "ids_bajo_sin_mercomuna": ids_bajo},
    }
    destino = PROC / "senales_semana.json"
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{destino}: rechazo_alto={len(rechazo)}, productos_sin_oferta={len(productos)}, "
          f"ids_bajo_sin_mercomuna={len(ids_bajo)}")


if __name__ == "__main__":
    main()

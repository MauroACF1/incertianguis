"""Intenta obtener el directorio de comercios Mercomuna desde SAPCI.

1) Busca en el HTML referencias a endpoints JSON/CSV/XLSX y los usa.
2) Si no hay, extrae tablas <table> del HTML (con pausa entre peticiones).
Salida: data/raw/mercomuna_directorio.csv
Campos: nombre, giro, calle_numero, cp, alcaldia, colonia

Al 2026-10-25 la página no publica el directorio (solo texto), así que el
script termina con aviso y no escribe nada.

Uso: py -3.12 scripts/02_mercomuna_sapci.py
"""
import re
import sys
import time
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

URLS = [
    "https://sapci.cdmx.gob.mx/mercomuna",
    "https://sapci.cdmx.gob.mx/programas/programa/ingreso-social-mercomuna-cdmx",
]
SALIDA = Path(__file__).resolve().parents[1] / "data" / "raw" / "mercomuna_directorio.csv"
HEADERS = {"User-Agent": "Incertianguis-Chilangaton2026/0.1 (hackaton, datos abiertos)"}
PAUSA = 2  # segundos entre peticiones
# Columnas personales que nunca se guardan.
PROHIBIDAS = ["propietario", "titular", "telefono", "teléfono", "correo", "email", "curp", "rfc"]

COLUMNAS = {
    "nombre": ["nombre", "comercio", "establecimiento", "razon"],
    "giro": ["giro", "actividad", "tipo"],
    "calle_numero": ["calle", "direccion", "dirección", "domicilio"],
    "cp": ["cp", "c.p", "codigo", "código"],
    "alcaldia": ["alcaldia", "alcaldía"],
    "colonia": ["colonia"],
}


def normaliza_columnas(df):
    df = df[[c for c in df.columns if not any(p in str(c).lower() for p in PROHIBIDAS)]]
    renombre = {}
    for destino, pistas in COLUMNAS.items():
        for c in df.columns:
            if c not in renombre and any(p in str(c).lower() for p in pistas):
                renombre[c] = destino
                break
    df = df.rename(columns=renombre)
    return df[[c for c in COLUMNAS if c in df.columns]]


def main():
    tablas = []
    for url in URLS:
        html = requests.get(url, headers=HEADERS, timeout=60).text
        time.sleep(PAUSA)
        # 1) endpoints de datos referenciados en la página
        for ref in set(re.findall(r'["\']([^"\']+\.(?:json|csv|xlsx))(?:\?[^"\']*)?["\']', html)):
            if "favicon" in ref or "manifest" in ref:
                continue
            u = urljoin(url, ref)
            print("Endpoint candidato:", u)
            if u.endswith(".json"):
                tablas.append(pd.json_normalize(requests.get(u, headers=HEADERS, timeout=60).json()))
            elif u.endswith(".csv"):
                tablas.append(pd.read_csv(u, storage_options=HEADERS))
            else:
                tablas.append(pd.read_excel(u))
            time.sleep(PAUSA)
        # 2) tablas HTML
        if "<table" in html.lower():
            tablas += pd.read_html(StringIO(html))

    if not tablas:
        print("SAPCI no publica el directorio Mercomuna en estas páginas (sin tabla ni endpoint).")
        sys.exit(1)

    df = pd.concat([normaliza_columnas(t) for t in tablas], ignore_index=True).drop_duplicates()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"{len(df)} comercios -> {SALIDA}")


if __name__ == "__main__":
    main()

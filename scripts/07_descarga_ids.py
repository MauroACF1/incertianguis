"""Descarga el Índice de Desarrollo Social (IDS) 2020 de Evalúa CDMX a nivel manzana y
los polígonos de manzana del Marco Geoestadístico 2020 (INEGI), ambos desde datos.cdmx.gob.mx.

El IDS no trae geometría; se une a los polígonos por CVEGEO (folio_mza, 16 dígitos).

Uso: py -3.12 scripts/07_descarga_ids.py
Salida: data/raw/ids_2020_manzana.csv, data/raw/manzanas_mg2020.zip (zip ignorado por git)
"""
import time
from pathlib import Path

import requests

PORTAL = "https://datos.cdmx.gob.mx/dataset"
ARCHIVOS = {
    "ids_2020_manzana.csv": f"{PORTAL}/46ead7d7-8c8c-4660-b1d6-63f8875e0a93/resource/"
                            "1d4dc7a6-f2ce-43cd-90f3-bd927f4e1615/download/1d4dc7a6-f2ce-43cd-90f3-bd927f4e1615.csv",
    "ids_2020_diccionario_manzana.xlsx": f"{PORTAL}/46ead7d7-8c8c-4660-b1d6-63f8875e0a93/resource/"
                                         "6bc41139-d81a-49b7-95cf-90ec0faac570/download/"
                                         "6bc41139-d81a-49b7-95cf-90ec0faac570.xlsx",
    "manzanas_mg2020.zip": f"{PORTAL}/93a59c20-5bfd-43ec-b631-057e9f9f6891/resource/"
                           "6987f6cd-2844-4baf-817b-ee0589a438d0/download/6987f6cd-2844-4baf-817b-ee0589a438d0.zip",
}
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {"User-Agent": "Incertianguis-Chilangaton2026/0.1 (hackaton, datos abiertos)"}


def main():
    for nombre, url in ARCHIVOS.items():
        r = requests.get(url, headers=HEADERS, timeout=300)
        r.raise_for_status()
        (RAW / nombre).write_bytes(r.content)
        print(f"{nombre}: {len(r.content):,} bytes")
        time.sleep(1)


if __name__ == "__main__":
    main()

"""Descarga el DENUE (INEGI) de comercio al por menor (SCIAN 46) y lo filtra a la
Ciudad de México (cve_ent = 09).

INEGI publica el sector 46 solo a nivel nacional, en 4 archivos. Las rutas se
obtuvieron del API de https://www.inegi.org.mx/app/descarga/?ti=6
(Otros > DENUE > Actividad económica > Comercio al por menor, corte 05/2026).
El servidor rechaza peticiones sin User-Agent/Referer de navegador.

Se eliminan columnas de contacto y de posible dato personal (razón social,
teléfono, correo, web) y el tamaño por personal ocupado.

Uso: py -3.12 scripts/03_descarga_denue.py
Salida: data/raw/denue_09_46.csv  (zips en data/raw/denue_zip/, ignorados por git)
"""
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE = "https://www.inegi.org.mx/contenidos/masiva/denue/"
ARCHIVOS = ["denue_00_46111", "denue_00_46112-46311", "denue_00_46321-46531", "denue_00_46591-46911"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0 Safari/537.36",
    "Referer": "https://www.inegi.org.mx/app/descarga/?ti=6",
}
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
ZIPS = RAW / "denue_zip"
SALIDA = RAW / "denue_09_46.csv"
COLUMNAS = ["id", "nom_estab", "codigo_act", "nombre_act", "tipo_vial", "nom_vial", "numero_ext",
            "letra_ext", "tipo_asent", "nomb_asent", "cod_postal", "cve_ent", "cve_mun", "municipio",
            "latitud", "longitud", "fecha_alta"]


def descarga(nombre):
    destino = ZIPS / f"{nombre}_csv.zip"
    if destino.exists() and zipfile.is_zipfile(destino):
        return destino
    print(f"Descargando {nombre}_csv.zip ...")
    with requests.get(f"{BASE}{nombre}_csv.zip", headers=HEADERS, stream=True, timeout=600) as r:
        r.raise_for_status()
        if "zip" not in r.headers.get("Content-Type", ""):
            raise RuntimeError(f"INEGI no devolvió un zip para {nombre} (posible bloqueo WAF)")
        with open(destino, "wb") as f:
            for bloque in r.iter_content(1 << 20):
                f.write(bloque)
    time.sleep(2)
    return destino


def lee_cdmx(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv") and "diccionario" not in n.lower()
                and "/conjunto_de_datos/" in n.lower().replace("\\", "/")] or \
               [n for n in z.namelist() if n.lower().endswith(".csv") and "diccionario" not in n.lower()]
        partes = []
        for n in csvs:
            with z.open(n) as f:
                for chunk in pd.read_csv(f, encoding="latin-1", dtype=str, chunksize=200_000):
                    chunk.columns = [c.strip().lower() for c in chunk.columns]
                    partes.append(chunk[chunk["cve_ent"].str.strip().str.zfill(2) == "09"])
    df = pd.concat(partes, ignore_index=True)
    return df[[c for c in COLUMNAS if c in df.columns]]


def main():
    ZIPS.mkdir(parents=True, exist_ok=True)
    df = pd.concat([lee_cdmx(descarga(a)) for a in ARCHIVOS], ignore_index=True)
    df = df[df["codigo_act"].str.startswith("46")].drop_duplicates("id")
    df.to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"{len(df):,} establecimientos de comercio al por menor en CDMX -> {SALIDA}")


if __name__ == "__main__":
    main()

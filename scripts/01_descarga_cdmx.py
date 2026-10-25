"""Descarga los CSV de "Mercados públicos" y "Tianguis de la Ciudad de México" (SEDECO)
desde el portal CKAN datos.cdmx.gob.mx a data/raw/.

Uso (desde la raíz del repo): py -3.12 scripts/01_descarga_cdmx.py
"""
import re
import time
from datetime import date
from pathlib import Path

import requests

PORTAL = "https://datos.cdmx.gob.mx"
DATASETS = ["mercados-publicos", "tianguis-de-la-ciudad-de-mexico"]
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {"User-Agent": "Incertianguis-Chilangaton2026/0.1 (hackaton, datos abiertos)"}


def slug(texto):
    texto = texto.lower()
    for a, b in zip("áéíóúñü", "aeiounu"):
        texto = texto.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", texto).strip("_")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for ds in DATASETS:
        r = requests.get(f"{PORTAL}/api/3/action/package_show", params={"id": ds},
                         headers=HEADERS, timeout=60)
        r.raise_for_status()
        pkg = r.json()["result"]
        for res in pkg["resources"]:
            if res["format"].upper() != "CSV":
                continue
            # El API devuelve URLs con una IP interna; se usa el dominio público.
            url = re.sub(r"^https?://[^/]+", PORTAL, res["url"])
            destino = RAW / f"{ds}__{slug(res['name'] or res['id'])}.csv"
            print(f"Descargando {res['name']} -> {destino.name}")
            d = requests.get(url, headers=HEADERS, timeout=120)
            d.raise_for_status()
            destino.write_bytes(d.content)
            print(f"  {len(d.content):,} bytes | {url} | {date.today()}")
            time.sleep(1)


if __name__ == "__main__":
    main()

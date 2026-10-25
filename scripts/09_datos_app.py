"""Copia a app/data/ las capas que usa el prototipo "Canjea Cerca".

Solo comercios Mercomuna, mercados y tianguis (no la capa de afiliables).
Uso: py -3.12 scripts/09_datos_app.py
"""
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVOS = ["mercomuna.geojson", "mercomuna.csv", "tianguis.geojson", "mercados_publicos.geojson"]


def main():
    destino = RAIZ / "app" / "data"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ARCHIVOS:
        shutil.copy2(RAIZ / "data" / "processed" / nombre, destino / nombre)
        print(f"{nombre} -> app/data/")


if __name__ == "__main__":
    main()

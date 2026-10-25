"""Genera las capas del mapa en data/processed/ (GeoJSON WGS84 + CSV).

Capas:
  mercados    -> mercados_publicos.geojson / .csv
  tianguis    -> tianguis.geojson / .csv (un punto por tianguis, con todos sus días)
  comercios   -> comercios_afiliables.geojson / .csv (DENUE, giros de alimentos)
  resumen     -> resumen_alcaldias.csv

Uso: py -3.12 scripts/06_capas_mapa.py [mercados|tianguis|comercios|resumen ...]
     (sin argumentos genera todas)
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
OUT = RAIZ / "data" / "processed"

# Caja aproximada de la CDMX para descartar coordenadas erróneas (p. ej. 0,0).
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 19.04, 19.60, -99.37, -98.94

# Giros de alimentos donde se canjean vales (catálogo SCIAN 2023, verificado contra el DENUE).
GIROS_AFILIABLES = {
    "461110": "Abarrotes y misceláneas",
    "461121": "Carnicería",
    "461122": "Pollería",
    "461130": "Frutas y verduras",
    "461150": "Cremería, lácteos y embutidos",
    "311812": "Panadería",  # panificación tradicional; INEGI la clasifica en manufacturas
    "311830": "Tortillería",  # tortillas de maíz y molienda de nixtamal; también manufacturas
}

ALCALDIAS = ["Álvaro Obregón", "Azcapotzalco", "Benito Juárez", "Coyoacán", "Cuajimalpa de Morelos",
             "Cuauhtémoc", "Gustavo A. Madero", "Iztacalco", "Iztapalapa", "La Magdalena Contreras",
             "Miguel Hidalgo", "Milpa Alta", "Tláhuac", "Tlalpan", "Venustiano Carranza", "Xochimilco"]


def clave(texto):
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", texto)


CANON = {clave(a): a for a in ALCALDIAS}


def alcaldia(texto):
    return CANON.get(clave(texto)) if pd.notna(texto) else None


def en_cdmx(df):
    return df["lat"].between(LAT_MIN, LAT_MAX) & df["lon"].between(LON_MIN, LON_MAX)


def guarda(df, nombre):
    """Escribe <nombre>.csv y <nombre>.geojson; las columnas lat/lon se vuelven la geometría."""
    OUT.mkdir(parents=True, exist_ok=True)
    df = df.reset_index(drop=True)
    df.to_csv(OUT / f"{nombre}.csv", index=False, encoding="utf-8")
    props = df.drop(columns=["lat", "lon"]).astype(object).where(df.drop(columns=["lat", "lon"]).notna(), None)
    features = [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
         "properties": p}
        for lat, lon, p in zip(df["lat"], df["lon"], props.to_dict("records"))
    ]
    with open(OUT / f"{nombre}.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
    print(f"{nombre}: {len(df):,} puntos")
    return df


def mercados():
    m = pd.read_csv(RAW / "mercados-publicos__mercados_publicos.csv", dtype=str)
    df = pd.DataFrame({
        "nombre": "Mercado " + m["mercado"].str.title(),
        "numero": m["numero"],
        "alcaldia": m["alcaldia_mercado"].map(alcaldia),
        "colonia": m["colonia_mercado"].str.title(),
        "direccion": m["direccion"],
        "tipo": m["tipo"].str.capitalize(),
        "locales": pd.to_numeric(m["locales"], errors="coerce").astype("Int64"),
        "lat": m["latitud"].astype(float),
        "lon": m["longitud"].astype(float),
    })
    return guarda(df[en_cdmx(df)], "mercados_publicos")


def tianguis():
    t = pd.read_csv(RAW / "tianguis-de-la-ciudad-de-mexico__ubicacion_de_los_tianguis_en_la_ciudad_de_mexico.csv",
                    dtype=str)
    t["lat"], t["lon"] = t["latitud"].astype(float), t["longitud"].astype(float)
    fuera = ~en_cdmx(t)
    if fuera.any():
        print(f"tianguis: {fuera.sum()} filas descartadas por coordenadas fuera de CDMX")
    t = t[~fuera]
    orden = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]

    def dias(valores):
        encontrados = {d for v in valores for d in clave_dia(v).replace(",", " ").split()}
        return ", ".join(d.capitalize().replace("Miercoles", "Miércoles").replace("Sabado", "Sábado")
                         for d in orden if d in encontrados)

    # El CSV trae una fila por día de operación: se agrupa por ubicación.
    g = t.groupby(["alcaldia", "colonia", "ubicacion"], dropna=False).agg(
        dias=("dia", dias), horario=("horario", "first"), giro=("giro", "first"),
        lat=("lat", "first"), lon=("lon", "first")).reset_index()
    df = pd.DataFrame({
        "nombre": "Tianguis " + g["colonia"].str.title(),
        "alcaldia": g["alcaldia"].map(alcaldia),
        "colonia": g["colonia"].str.title(),
        "ubicacion": g["ubicacion"],
        "dias": g["dias"],
        "horario": g["horario"],
        "tipo": g["giro"].where(~g["giro"].isin(["0", "NA"])).str.capitalize(),
        "lat": g["lat"], "lon": g["lon"],
    })
    return guarda(df, "tianguis")


def clave_dia(texto):
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z, ]", " ", texto)


def comercios():
    cols = ["nom_estab", "codigo_act", "municipio", "cod_postal", "latitud", "longitud"]
    d = pd.concat([pd.read_csv(RAW / "denue_09_46.csv", dtype=str, usecols=cols),
                   pd.read_csv(RAW / "denue_09_3118.csv", dtype=str, usecols=cols)])
    d = d[d["codigo_act"].isin(GIROS_AFILIABLES)]
    df = pd.DataFrame({
        "nombre": d["nom_estab"].fillna("Sin nombre").str.title(),
        "giro": d["codigo_act"].map(GIROS_AFILIABLES),
        "scian": d["codigo_act"],
        "alcaldia": d["municipio"].map(alcaldia),
        "cp": d["cod_postal"].str.zfill(5),
        "lat": d["latitud"].astype(float),
        "lon": d["longitud"].astype(float),
    })
    df = df[en_cdmx(df)].sort_values(["alcaldia", "scian"])
    print(df["giro"].value_counts().to_string())
    return guarda(df, "comercios_afiliables")


def resumen():
    capas = {"mercados": "mercados_publicos", "tianguis": "tianguis", "comercios_afiliables": "comercios_afiliables"}
    conteos = {k: pd.read_csv(OUT / f"{v}.csv", usecols=["alcaldia"])["alcaldia"].value_counts()
               for k, v in capas.items()}
    r = pd.DataFrame(conteos).reindex(ALCALDIAS).fillna(0).astype(int).rename_axis("alcaldia").reset_index()
    r.loc[len(r)] = ["Total CDMX", *r[list(capas)].sum()]
    r.to_csv(OUT / "resumen_alcaldias.csv", index=False, encoding="utf-8")
    print(r.to_string(index=False))


if __name__ == "__main__":
    capas = {"mercados": mercados, "tianguis": tianguis, "comercios": comercios, "resumen": resumen}
    for nombre in sys.argv[1:] or list(capas):
        capas[nombre]()

"""Capas Mercomuna y cobertura respecto a los comercios afiliables (DENUE).

Entradas: data/processed/mercomuna_comercios_geo.csv (04), comercios_afiliables.csv y
          resumen_alcaldias.csv (06; correr 06 antes que este script).
Salidas en data/processed/:
  mercomuna.geojson / .csv   puntos con ubicación exacta (cruce DENUE), con ids_estrato.
                             El CSV trae todos los comercios con su precision.
  mercomuna_por_cp.geojson   un punto por CP (centroide DENUE) con el conteo de comercios
                             ubicados solo por CP, para pintarlos como círculos agregados.
  resumen_alcaldias.csv      + columnas Mercomuna y cobertura.
  cobertura_ids.csv          cobertura por estrato IDS para toda la ciudad.

Giros de alimentos: el directorio usa su propio catálogo. Se equiparan a las categorías
SCIAN de comercios_afiliables así: ABARROTES, VERDURAS y PANADERIA directo; OTRO se
reclasifica por palabras clave del nombre (carnicería, pollería, cremería, tortillería...);
en COMIDA solo se rescatan nombres inequívocos (p. ej. "Carnicería Beto").
Se excluyen por no tener equivalente en los giros afiliables: el resto de COMIDA (alimentos preparados,
SCIAN 722), DULCERIA (461160), AGUA (purificadoras) y pescaderías/mariscos (461123), además
de los giros no alimentarios.

IDS de los comercios ubicados por CP: no se sabe en qué manzana están, así que para los
conteos se reparten entre estratos en proporción a los comercios afiliables de su CP
(valor esperado). En el punto, ids_estrato solo se llena con ubicación exacta.

Uso: py -3.12 scripts/08_capa_mercomuna.py
"""
import importlib.util
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
OUT = RAIZ / "data" / "processed"

# Reutiliza utilidades del script de capas (alcaldías, guardado e IDS).
_spec = importlib.util.spec_from_file_location("capas", RAIZ / "scripts" / "06_capas_mapa.py")
capas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capas)

GIRO_DIRECTO = {"ABARROTES": "Abarrotes y misceláneas", "VERDURAS": "Frutas y verduras",
                "PANADERIA": "Panadería"}
# Orden importa: la primera coincidencia gana.
PALABRAS = [
    (r"marisc|pescad", None),  # sin equivalente afiliable
    (r"tortill", "Tortillería"),
    (r"poller|pollo", "Pollería"),
    (r"carnic|tocin|carnes|obrador", "Carnicería"),
    (r"cremer|lacteo|queso|salchich|embutid", "Cremería, lácteos y embutidos"),
    (r"panader|pasteler|\bpan\b", "Panadería"),
    (r"recaud|verdur|fruta|legumbre", "Frutas y verduras"),
    (r"abarrot|miscel|\bsuper\b|\btienda\b(?! de)|ultramarin", "Abarrotes y misceláneas"),
]
# En COMIDA (alimentos preparados) solo palabras inequívocas de comercio de alimentos.
PALABRAS_COMIDA = r"carnic|poller|tortill|cremer|recaud|abarrot|miscel"
ESTRATOS = capas.ESTRATOS


def sin_acentos(texto):
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()


def categoria(giro, nombre):
    if giro in GIRO_DIRECTO:
        return GIRO_DIRECTO[giro]
    n = sin_acentos(nombre)
    if giro == "COMIDA" and not re.search(PALABRAS_COMIDA, n):
        return None
    if giro in ("OTRO", "COMIDA"):
        for patron, cat in PALABRAS:
            if re.search(patron, n):
                return cat
    return None


def guarda_geojson(df, nombre, props):
    features = [{"type": "Feature",
                 "geometry": {"type": "Point", "coordinates": [round(r.lon, 6), round(r.lat, 6)]},
                 "properties": {k: (None if pd.isna(getattr(r, k)) else getattr(r, k)) for k in props}}
                for r in df.itertuples()]
    with open(OUT / f"{nombre}.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False, default=int)
    print(f"{nombre}.geojson: {len(features):,} puntos")


def main():
    m = pd.read_csv(OUT / "mercomuna_comercios_geo.csv", dtype={"cp": str})
    m["alcaldia"] = m["alcaldia"].map(capas.alcaldia)
    m["categoria"] = [categoria(g, n) for g, n in zip(m["giro"], m["nombre"])]
    m["alimentos"] = m["categoria"].notna()
    for g in ("OTRO", "COMIDA"):
        sub = m[m["giro"] == g]
        print(f"{g} reclasificados como alimentos: {sub['alimentos'].sum()} de {len(sub)}")
    print("Giros excluidos (sin equivalencia de alimentos):",
          m.loc[~m["alimentos"], "giro"].value_counts().to_dict())

    # ids_estrato solo con ubicación exacta.
    exactas = m["precision"] == "exacta"
    m["ids_estrato"] = capas.agrega_ids(m[exactas])["ids_estrato"].reindex(m.index)
    cols = ["nombre", "giro", "categoria", "alimentos", "direccion", "cp", "alcaldia", "precision",
            "ids_estrato", "lat", "lon"]
    m[cols].to_csv(OUT / "mercomuna.csv", index=False, encoding="utf-8")
    guarda_geojson(m[exactas], "mercomuna", [c for c in cols if c not in ("lat", "lon")])

    # Círculos agregados por CP para los ubicados por centroide.
    por_cp = (m[m["precision"] == "cp"]
              .groupby("cp")
              .agg(comercios=("nombre", "size"), comercios_alimentos=("alimentos", "sum"),
                   alcaldia=("alcaldia", lambda s: s.mode().iat[0] if s.notna().any() else None),
                   lat=("lat", "first"), lon=("lon", "first"))
              .reset_index())
    guarda_geojson(por_cp, "mercomuna_por_cp", ["cp", "alcaldia", "comercios", "comercios_alimentos"])

    # Distribución esperada de IDS por comercio Mercomuna de alimentos.
    afil = pd.read_csv(OUT / "comercios_afiliables.csv", dtype={"cp": str})
    reparto_cp = pd.crosstab(afil["cp"], afil["ids_estrato"], normalize="index").reindex(columns=ESTRATOS,
                                                                                       fill_value=0)
    ali = m[m["alimentos"]].copy()
    pesos = pd.DataFrame(0.0, index=ali.index, columns=ESTRATOS)
    for e in ESTRATOS:
        pesos.loc[ali["ids_estrato"] == e, e] = 1.0
    por_cp_idx = ali.index[(ali["precision"] == "cp")]
    pesos.loc[por_cp_idx] = reparto_cp.reindex(ali.loc[por_cp_idx, "cp"]).fillna(0).values
    ali = ali.join(pesos)

    # Resumen por alcaldía.
    r = pd.read_csv(OUT / "resumen_alcaldias.csv")
    r = r[r["alcaldia"] != "Total CDMX"].set_index("alcaldia")
    r["mercomuna"] = m["alcaldia"].value_counts().reindex(r.index).fillna(0).astype(int)
    r["mercomuna_alimentos"] = ali["alcaldia"].value_counts().reindex(r.index).fillna(0).astype(int)
    r["mercomuna_alimentos_ids_bajo_y_muy_bajo_est"] = (
        ali.groupby("alcaldia")[["bajo", "muy bajo"]].sum().sum(axis=1).reindex(r.index).fillna(0).round(0))
    total = r.sum()
    r.loc["Total CDMX"] = total
    r["cobertura_pct"] = (100 * r["mercomuna_alimentos"] / r["comercios_afiliables"]).round(1)
    r["cobertura_ids_bajo_y_muy_bajo_pct"] = (100 * r["mercomuna_alimentos_ids_bajo_y_muy_bajo_est"]
                                              / r["comercios_ids_bajo_y_muy_bajo"]).round(1)
    r["pct_comercios_ids_bajo_y_muy_bajo"] = (100 * r["comercios_ids_bajo_y_muy_bajo"]
                                              / r["comercios_afiliables"]).round(1)
    enteras = [c for c in r.columns if not c.endswith("_pct") and not c.startswith("pct_")]
    r[enteras] = r[enteras].round(0).astype(int)
    r.reset_index().to_csv(OUT / "resumen_alcaldias.csv", index=False, encoding="utf-8")

    # Cobertura por estrato, toda la ciudad.
    c = pd.DataFrame({
        "ids_estrato": ESTRATOS,
        "comercios_afiliables": [int((afil["ids_estrato"] == e).sum()) for e in ESTRATOS],
        "mercomuna_alimentos_est": [round(ali[e].sum()) for e in ESTRATOS],
        "mercomuna_alimentos_exacta": [int((ali["ids_estrato"] == e).sum()) for e in ESTRATOS],
    })
    c.loc[len(c)] = ["sin dato", int(afil["ids_estrato"].isna().sum()),
                     round(len(ali) - ali[ESTRATOS].sum().sum()), int(((ali["precision"] == "exacta")
                                                                       & ali["ids_estrato"].isna()).sum())]
    c["cobertura_pct"] = (100 * c["mercomuna_alimentos_est"] / c["comercios_afiliables"]).round(1)
    c.to_csv(OUT / "cobertura_ids.csv", index=False, encoding="utf-8")
    print(c.to_string(index=False))

    cols_ver = ["comercios_afiliables", "mercomuna", "mercomuna_alimentos", "cobertura_pct",
                "comercios_ids_bajo_y_muy_bajo", "mercomuna_alimentos_ids_bajo_y_muy_bajo_est",
                "cobertura_ids_bajo_y_muy_bajo_pct"]
    print(r[cols_ver].to_string())
    print("\n5 alcaldías con menor cobertura en IDS bajo + muy bajo:")
    print(r.drop("Total CDMX").nsmallest(5, "cobertura_ids_bajo_y_muy_bajo_pct")[cols_ver[4:]].to_string())


if __name__ == "__main__":
    main()

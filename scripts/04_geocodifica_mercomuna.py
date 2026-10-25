"""Geocodifica el directorio Mercomuna cruzándolo con el DENUE (comercio al por menor CDMX).

1) Coincidencia "exacta": mismo código postal + nombre normalizado (sin acentos,
   minúsculas, sin puntuación) con similitud difusa >= UMBRAL (rapidfuzz).
   Si varios establecimientos del CP empatan (nombres genéricos como
   "Abarrotes sin nombre"), se desempata por calle y número; si sigue ambiguo
   no se considera exacta.
2) Si no cruza: centroide de los establecimientos DENUE del mismo CP (precision="cp").
3) Si el CP no existe en DENUE: lat/lon vacías (precision="sin_ubicacion").

Uso: py -3.12 scripts/04_geocodifica_mercomuna.py [directorio.csv] [denue.csv] [salida.csv]
Por defecto: data/raw/mercomuna_directorio.csv, data/raw/denue_09_46.csv,
             data/processed/mercomuna_comercios_geo.csv
"""
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

RAIZ = Path(__file__).resolve().parents[1]
UMBRAL = 88
UMBRAL_DIRECCION = 80
# Palabras genéricas que no ayudan a distinguir comercios.
VACIAS = {"la", "el", "los", "las", "de", "del", "y", "sa", "cv", "rl", "s", "a", "c", "v",
          "tienda", "abarrotes", "miscelanea", "local"}


def normaliza(texto):
    if pd.isna(texto):
        return ""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    palabras = re.sub(r"[^a-z0-9 ]", " ", texto).split()
    return " ".join(p for p in palabras if p not in VACIAS)


def normaliza_cp(cp):
    digitos = re.sub(r"\D", "", str(cp)) if pd.notna(cp) else ""
    return digitos.zfill(5) if digitos else ""


def elige(nombre_n, dir_n, grupo):
    """Devuelve (índice, score) del establecimiento DENUE que cruza, o None si no hay o es ambiguo."""
    hallados = process.extract(nombre_n, grupo["nombre_n"], scorer=fuzz.token_sort_ratio,
                               score_cutoff=UMBRAL, limit=None)
    if not hallados:
        return None
    mejor_score = max(h[1] for h in hallados)
    empatados = [h[2] for h in hallados if h[1] == mejor_score]
    if len(empatados) == 1:
        return empatados[0], mejor_score
    if not dir_n:
        return None
    por_dir = sorted(((fuzz.token_set_ratio(dir_n, grupo.at[i, "dir_n"]), i) for i in empatados), reverse=True)
    if por_dir[0][0] >= UMBRAL_DIRECCION and (len(por_dir) == 1 or por_dir[0][0] > por_dir[1][0]):
        return por_dir[0][1], mejor_score
    return None


def main(dir_csv, denue_csv, salida_csv):
    merco = pd.read_csv(dir_csv, dtype=str)
    denue = pd.read_csv(denue_csv, dtype=str, usecols=["id", "nom_estab", "nom_vial", "numero_ext",
                                                           "cod_postal", "latitud", "longitud"])

    denue["cp"] = denue["cod_postal"].map(normaliza_cp)
    denue["nombre_n"] = denue["nom_estab"].map(normaliza)
    denue["dir_n"] = (denue["nom_vial"].fillna("") + " " + denue["numero_ext"].fillna("")).map(normaliza)
    denue[["latitud", "longitud"]] = denue[["latitud", "longitud"]].astype(float)
    centroides = denue.groupby("cp")[["latitud", "longitud"]].mean()
    candidatos = {cp: g[g["nombre_n"] != ""] for cp, g in denue.groupby("cp")}

    filas = []
    for _, m in merco.iterrows():
        cp = normaliza_cp(m.get("cp"))
        nombre_n = normaliza(m.get("nombre"))
        fila = {
            "nombre": m.get("nombre"),
            "giro": m.get("giro"),
            "direccion": ", ".join(str(x) for x in [m.get("calle_numero"), m.get("colonia")] if pd.notna(x)),
            "cp": cp,
            "alcaldia": m.get("alcaldia"),
            "lat": None, "lon": None, "precision": "sin_ubicacion", "fuente_match": "",
        }
        grupo = candidatos.get(cp)
        mejor = None
        if nombre_n and grupo is not None and len(grupo):
            mejor = elige(nombre_n, normaliza(m.get("calle_numero")), grupo)
        if mejor:
            idx, score = mejor
            d = grupo.loc[idx]
            fila.update(lat=d["latitud"], lon=d["longitud"], precision="exacta",
                        fuente_match=f"denue:{d['id']} (score {score:.0f})")
        elif cp in centroides.index:
            c = centroides.loc[cp]
            fila.update(lat=round(c["latitud"], 6), lon=round(c["longitud"], 6), precision="cp",
                        fuente_match="centroide_cp_denue")
        filas.append(fila)

    salida = pd.DataFrame(filas)
    Path(salida_csv).parent.mkdir(parents=True, exist_ok=True)
    salida.to_csv(salida_csv, index=False, encoding="utf-8")

    conteo = salida["precision"].value_counts()
    total = len(salida)
    print(f"{total} comercios -> {salida_csv}")
    for p in ["exacta", "cp", "sin_ubicacion"]:
        n = int(conteo.get(p, 0))
        print(f"  {p:14s} {n:6d}  ({100 * n / total:.1f}%)" if total else f"  {p}: 0")


if __name__ == "__main__":
    args = sys.argv[1:] + [None] * 3
    main(args[0] or RAIZ / "data/raw/mercomuna_directorio.csv",
         args[1] or RAIZ / "data/raw/denue_09_46.csv",
         args[2] or RAIZ / "data/processed/mercomuna_comercios_geo.csv")

"""
================================================================================
PROYECTO INTEGRADOR - INTELIGENCIA ARTIFICIAL (SIST5036) - FASE 2 (CORTE 2)
VALIDACIÓN DE NAVEGABILIDAD: ninguna arista debe cruzar tierra.

Usa data/landmask.npz (raster 0.02° construido de Natural Earth 10m
admin-0: Dinamarca, Suecia, Noruega, Alemania y Polonia). Solo numpy/pandas.
Regla: el 90% central del segmento puede pisar tierra como máximo 2.0 nm
(tolerancia por resolución + pasos por estrechos). Retorna exit 1 si hay
cruces mayores (para usar en CI o antes de una demo).

Uso:  .venv/bin/python validar_tierra.py
================================================================================
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

TOL_NM = 2.0   # máximo permitido de segmento sobre tierra
TRIM = 0.05    # se ignoran los extremos (puertos sobre la costa)

# Canales de acceso dragados (<1 nm de ancho, no resueltos por la máscara 10m):
# se reportan aparte y NO cuentan como fallo. Mantener en sync con
# ACCESOS_FIORDO de dataset.py.
EXENTOS_FIORDO = {
    ("DK_AAL", "WP_HALS"), ("DK_HOR", "WP_HORSENS_M"), ("DK_VEJ", "WP_VEJLE_M"),
    ("DK_ODN", "WP_ODENSE_M"), ("SE_UDD", "WP_UDDEVALLA_M"),
}


def cargar_mascara():
    z = np.load(DATA_DIR / "landmask.npz")
    return z["grid"], float(z["lon0"]), float(z["lat0"]), float(z["step"])

def es_tierra(grid, lon0, lat0, step, lat, lon) -> bool:
    c = int((lon - lon0) / step)
    r = int((lat - lat0) / step)
    if 0 <= r < grid.shape[0] and 0 <= c < grid.shape[1]:
        return bool(grid[r, c])
    return False  # fuera del mapa: se asume agua


def haversine_nm(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3440.065 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def nm_sobre_tierra(grid, lon0, lat0, step, lat1, lon1, lat2, lon2, ns=200) -> float:
    """Millas náuticas del 90% central del segmento que pisan tierra."""
    dentro = 0.0
    for i in range(ns):
        f = (i + 0.5) / ns
        if f < TRIM or f > 1 - TRIM:
            continue
        a = (lat1 + (lat2 - lat1) * i / ns, lon1 + (lon2 - lon1) * i / ns)
        b = (lat1 + (lat2 - lat1) * (i + 1) / ns, lon1 + (lon2 - lon1) * (i + 1) / ns)
        if es_tierra(grid, lon0, lat0, step, *a) and es_tierra(grid, lon0, lat0, step, *b):
            dentro += haversine_nm(*a, *b)
    return dentro


def auditar(tol_nm: float = TOL_NM, verbose: bool = True):
    grid, lon0, lat0, step = cargar_mascara()
    nodos = pd.read_csv(DATA_DIR / "nodes.csv").set_index("id")
    aristas = pd.read_csv(DATA_DIR / "edges.csv")
    malas = []
    for _, r in aristas.iterrows():
        a, b = nodos.loc[r.origen], nodos.loc[r.destino]
        nm = nm_sobre_tierra(grid, lon0, lat0, step, a.lat, a.lon, b.lat, b.lon)
        if nm > tol_nm:
            malas.append((nm, r.origen, r.destino, r.distancia))
    malas.sort(reverse=True)
    exentas = [(nm, o, d, dist) for nm, o, d, dist in malas
               if (o, d) in EXENTOS_FIORDO or (d, o) in EXENTOS_FIORDO]
    fallos = [m for m in malas if m not in exentas]
    if verbose:
        print(f"Aristas auditadas: {len(aristas)} | tolerancia: {tol_nm} nm sobre tierra")
        for nm, o, d, dist in fallos:
            print(f"  CRUCE {nm:6.1f} nm | {o} -> {d} (arista {dist} nm)")
        for nm, o, d, dist in exentas:
            print(f"  canal dragado (exento) {nm:5.1f} nm | {o} -> {d}")
        print(f"Cruces: {len(fallos)} (exentos: {len(exentas)})")
    return fallos


if __name__ == "__main__":
    malas = auditar()
    sys.exit(1 if malas else 0)

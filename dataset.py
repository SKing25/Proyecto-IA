"""
================================================================================
PROYECTO INTEGRADOR - INTELIGENCIA ARTIFICIAL (SIST5036) - FASE 1
DOMINIO: LOGÍSTICA PORTUARIA AUTÓNOMA (SMART PORT)
BACKEND DE DATOS AIS Y MODELADO DEL ENTORNO G = (V, E)
================================================================================
"""
import hashlib
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

# Rutas del proyecto
BASE_DIR: Path = Path(__file__).resolve().parent
RAW_CSV: Path = BASE_DIR / "aisdk-2025-02-27.csv"
DATA_DIR: Path = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
NODES_OUTPUT: Path = DATA_DIR / "nodes.csv"
EDGES_OUTPUT: Path = DATA_DIR / "edges.csv"
GRAPH_IMG_OUTPUT: Path = DATA_DIR / "grafo_red.png"


# ------------------------------------------------------------------------------
# 1. Distancia Ortodrómica Esférica (Fórmula de Haversine)
# ------------------------------------------------------------------------------
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """
    Calcula la distancia geodésica real entre dos puntos sobre el elipsoide terrestre.
    
    Args:
        lat1, lon1: Coordenadas del nodo origen en grados decimales.
        lat2, lon2: Coordenadas del nodo destino en grados decimales.
        
    Returns:
        Tuple[float, float]: (distancia_km, distancia_millas_nauticas).
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    dist_km = 6371.0 * c
    dist_nm = dist_km / 1.852
    return round(dist_km, 2), round(dist_nm, 2)


# ------------------------------------------------------------------------------
# 2. Carga y Preprocesamiento Optimizado de Datos AIS
# ------------------------------------------------------------------------------
def cargar_y_limpiar_ais(
    ruta_csv: Path,
    max_chunks: int = 3,
    chunksize: int = 100_000
) -> pd.DataFrame:
    """
    Lee y filtra registros de telemetría AIS por bloques con tipado estricto,
    evitando consumo excesivo de memoria RAM.
    """
    print(f"[1/4] Ingestando telemetría marítima ({max_chunks * chunksize:,} registros planificados)...")
    
    # Pre-declaración estricta de tipos de datos para evitar warnings y optimizar memoria
    dtypes_input = {
        "MMSI": str,
        "# Timestamp": str,
        "BaseDateTime": str,
        "Latitude": float,
        "LAT": float,
        "Longitude": float,
        "LON": float,
        "SOG": float
    }

    rename_cols = {
        "# Timestamp": "timestamp", "BaseDateTime": "timestamp",
        "Latitude": "lat", "LAT": "lat",
        "Longitude": "lon", "LON": "lon",
        "SOG": "sog", "MMSI": "mmsi"
    }

    chunks_limpios: List[pd.DataFrame] = []

    for i, chunk in enumerate(pd.read_csv(ruta_csv, chunksize=chunksize, dtype=dtypes_input, low_memory=False)):
        chunk = chunk.rename(columns=rename_cols)

        # Convertir y limpiar coordenadas y velocidad
        for col in ["lat", "lon", "sog"]:
            if col in chunk.columns:
                chunk[col] = pd.to_numeric(chunk[col], errors="coerce")

        # Filtrar valores atípicos y acotar a la región geográfica navegable
        valido = chunk.dropna(subset=["lat", "lon", "mmsi"]).copy()
        filtro_espacial = (
            valido["lat"].between(53.0, 59.5) &
            valido["lon"].between(6.0, 16.0) &
            valido["sog"].between(0.5, 35.0)
        )
        chunks_limpios.append(valido[filtro_espacial])

        if i + 1 >= max_chunks:
            break

    df_total = pd.concat(chunks_limpios, ignore_index=True)
    print(f"      -> Pings limpios: {len(df_total):,} | Buques mercantes únicos (MMSI): {df_total['mmsi'].nunique():,}")
    return df_total


# ------------------------------------------------------------------------------
# 3. Topología de Nodos: Puertos Inteligentes y Waypoints Estratégicos
# ------------------------------------------------------------------------------
NODOS_RED: Dict[str, Dict[str, Any]] = {
    # Puertos Comerciales e Industriales
    "DK_CPH": {"nombre": "Copenhagen Smart Port", "tipo": "Puerto", "lat": 55.70, "lon": 12.60, "pais": "Dinamarca"},
    "DK_AAR": {"nombre": "Aarhus Logistics Port", "tipo": "Puerto", "lat": 56.15, "lon": 10.22, "pais": "Dinamarca"},
    "DK_ESB": {"nombre": "Esbjerg Energy Port", "tipo": "Puerto", "lat": 55.47, "lon": 8.44, "pais": "Dinamarca"},
    "DK_FRC": {"nombre": "Fredericia Terminal", "tipo": "Puerto", "lat": 55.56, "lon": 9.75, "pais": "Dinamarca"},
    "DK_AAL": {"nombre": "Aalborg Cargo Port", "tipo": "Puerto", "lat": 57.05, "lon": 9.92, "pais": "Dinamarca"},
    "DK_SKA": {"nombre": "Skagen Anchor Hub", "tipo": "Puerto", "lat": 57.72, "lon": 10.60, "pais": "Dinamarca"},
    "SE_GOT": {"nombre": "Gothenburg Port Hub", "tipo": "Puerto", "lat": 57.70, "lon": 11.97, "pais": "Suecia"},
    "SE_MAL": {"nombre": "Malmö Logistic Terminal", "tipo": "Puerto", "lat": 55.61, "lon": 12.99, "pais": "Suecia"},
    "SE_HEL": {"nombre": "Helsingborg Gateway", "tipo": "Puerto", "lat": 56.05, "lon": 12.69, "pais": "Suecia"},
    "DE_ROS": {"nombre": "Rostock Baltic Terminal", "tipo": "Puerto", "lat": 54.15, "lon": 12.10, "pais": "Alemania"},
    "DE_KLM": {"nombre": "Kiel Canal Approach", "tipo": "Puerto", "lat": 54.37, "lon": 10.15, "pais": "Alemania"},
    "NO_KRS": {"nombre": "Kristiansand Port", "tipo": "Puerto", "lat": 58.14, "lon": 8.00, "pais": "Noruega"},
    "NO_OSL": {"nombre": "Oslofjord Terminal", "tipo": "Puerto", "lat": 59.10, "lon": 10.60, "pais": "Noruega"},
    # --- Puertos FASE 2: top destinos reales del AIS (curaduría híbrida) ---
    # Jutlandia oeste (Mar del Norte)
    "DK_HVS": {"nombre": "Hvide Sande Port", "tipo": "Puerto", "lat": 56.00, "lon": 8.13, "pais": "Dinamarca"},
    "DK_THY": {"nombre": "Thyboron Port", "tipo": "Puerto", "lat": 56.70, "lon": 8.21, "pais": "Dinamarca"},
    "DK_HAN": {"nombre": "Hanstholm Port", "tipo": "Puerto", "lat": 57.11, "lon": 8.60, "pais": "Dinamarca"},
    "DK_HIR": {"nombre": "Hirtshals Port", "tipo": "Puerto", "lat": 57.59, "lon": 9.96, "pais": "Dinamarca"},
    "DK_FRH": {"nombre": "Frederikshavn Port", "tipo": "Puerto", "lat": 57.44, "lon": 10.54, "pais": "Dinamarca"},
    # Jutlandia este / Fionia (Kattegat / Belt)
    "DK_GRN": {"nombre": "Grenaa Port", "tipo": "Puerto", "lat": 56.41, "lon": 10.93, "pais": "Dinamarca"},
    "DK_EBE": {"nombre": "Ebeltoft Port", "tipo": "Puerto", "lat": 56.19, "lon": 10.68, "pais": "Dinamarca"},
    "DK_HOR": {"nombre": "Horsens Port", "tipo": "Puerto", "lat": 55.86, "lon": 9.85, "pais": "Dinamarca"},
    "DK_VEJ": {"nombre": "Vejle Port", "tipo": "Puerto", "lat": 55.71, "lon": 9.54, "pais": "Dinamarca"},
    "DK_KOL": {"nombre": "Kolding Port", "tipo": "Puerto", "lat": 55.49, "lon": 9.48, "pais": "Dinamarca"},
    "DK_ODN": {"nombre": "Odense-Lindo Terminal", "tipo": "Puerto", "lat": 55.48, "lon": 10.42, "pais": "Dinamarca"},
    "DK_KER": {"nombre": "Kerteminde Port", "tipo": "Puerto", "lat": 55.45, "lon": 10.66, "pais": "Dinamarca"},
    "DK_FAA": {"nombre": "Faaborg Port", "tipo": "Puerto", "lat": 55.10, "lon": 10.25, "pais": "Dinamarca"},
    "DK_SVE": {"nombre": "Svendborg Port", "tipo": "Puerto", "lat": 55.06, "lon": 10.61, "pais": "Dinamarca"},
    # Selandia / Lolland-Falster / islas menores
    "DK_HUN": {"nombre": "Hundested Port", "tipo": "Puerto", "lat": 55.96, "lon": 11.85, "pais": "Dinamarca"},
    "DK_GIL": {"nombre": "Gilleleje Port", "tipo": "Puerto", "lat": 56.12, "lon": 12.31, "pais": "Dinamarca"},
    "DK_KAL": {"nombre": "Kalundborg Port", "tipo": "Puerto", "lat": 55.68, "lon": 11.08, "pais": "Dinamarca"},
    "DK_KOR": {"nombre": "Korsoer Port", "tipo": "Puerto", "lat": 55.34, "lon": 11.14, "pais": "Dinamarca"},
    "DK_NYB": {"nombre": "Nyborg Port", "tipo": "Puerto", "lat": 55.31, "lon": 10.80, "pais": "Dinamarca"},
    "DK_VOR": {"nombre": "Vordingborg Port", "tipo": "Puerto", "lat": 55.01, "lon": 11.91, "pais": "Dinamarca"},
    "DK_NAK": {"nombre": "Nakskov Port", "tipo": "Puerto", "lat": 54.68, "lon": 11.14, "pais": "Dinamarca"},
    "DK_BAN": {"nombre": "Bandholm Port", "tipo": "Puerto", "lat": 54.84, "lon": 11.48, "pais": "Dinamarca"},
    "DK_GED": {"nombre": "Gedser Ferry Port", "tipo": "Puerto", "lat": 54.58, "lon": 11.93, "pais": "Dinamarca"},
    "DK_ROD": {"nombre": "Rodby Ferry Port", "tipo": "Puerto", "lat": 54.66, "lon": 11.35, "pais": "Dinamarca"},
    "DK_KOG": {"nombre": "Koge Port", "tipo": "Puerto", "lat": 55.46, "lon": 12.19, "pais": "Dinamarca"},
    "DK_RUD": {"nombre": "Rudkobing Port", "tipo": "Puerto", "lat": 54.94, "lon": 10.71, "pais": "Dinamarca"},
    "DK_SOB": {"nombre": "Soby Port (Aero)", "tipo": "Puerto", "lat": 54.89, "lon": 10.26, "pais": "Dinamarca"},
    "DK_FYN": {"nombre": "Fynshav Port (Als)", "tipo": "Puerto", "lat": 55.00, "lon": 9.99, "pais": "Dinamarca"},
    "DK_RON": {"nombre": "Ronne Port (Bornholm)", "tipo": "Puerto", "lat": 55.10, "lon": 14.70, "pais": "Dinamarca"},
    # Suecia (costa Kattegat / Oresund / Báltico)
    "SE_HAL": {"nombre": "Halmstad Port", "tipo": "Puerto", "lat": 56.66, "lon": 12.86, "pais": "Suecia"},
    "SE_LAN": {"nombre": "Landskrona Port", "tipo": "Puerto", "lat": 55.87, "lon": 12.83, "pais": "Suecia"},
    "SE_TRE": {"nombre": "Trelleborg Port", "tipo": "Puerto", "lat": 55.38, "lon": 13.15, "pais": "Suecia"},
    "SE_YST": {"nombre": "Ystad Port", "tipo": "Puerto", "lat": 55.43, "lon": 13.82, "pais": "Suecia"},
    "SE_LYS": {"nombre": "Lysekil Port", "tipo": "Puerto", "lat": 58.27, "lon": 11.43, "pais": "Suecia"},
    "SE_UDD": {"nombre": "Uddevalla Port", "tipo": "Puerto", "lat": 58.35, "lon": 11.94, "pais": "Suecia"},
    # Alemania (Mar del Norte / Báltico)
    "DE_TRV": {"nombre": "Travemunde Port", "tipo": "Puerto", "lat": 53.96, "lon": 10.87, "pais": "Alemania"},
    "DE_PUT": {"nombre": "Puttgarden Ferry Port", "tipo": "Puerto", "lat": 54.50, "lon": 11.23, "pais": "Alemania"},
    "DE_CUX": {"nombre": "Cuxhaven Port", "tipo": "Puerto", "lat": 53.87, "lon": 8.71, "pais": "Alemania"},
    "DE_BRV": {"nombre": "Bremerhaven Port", "tipo": "Puerto", "lat": 53.57, "lon": 8.13, "pais": "Alemania"},
    # Noruega (costa sur)
    "NO_MAN": {"nombre": "Mandal Port", "tipo": "Puerto", "lat": 57.98, "lon": 7.45, "pais": "Noruega"},
    "NO_LAR": {"nombre": "Larvik Port", "tipo": "Puerto", "lat": 59.05, "lon": 10.03, "pais": "Noruega"},
    # Polonia (puerta este del Báltico)
    "PL_SWI": {"nombre": "Swinoujscie Port", "tipo": "Puerto", "lat": 53.91, "lon": 14.25, "pais": "Polonia"},

    # Waypoints de Navegación y Corredores TSS
    "WP_SKAGERRAK":   {"nombre": "Skagerrak TSS Corridor", "tipo": "Waypoint", "lat": 57.80, "lon": 9.50, "pais": "Internacional"},
    "WP_KATTEGAT_N":  {"nombre": "Kattegat North Lane", "tipo": "Waypoint", "lat": 57.30, "lon": 11.30, "pais": "Internacional"},
    "WP_KATTEGAT_S":  {"nombre": "Kattegat South Lane", "tipo": "Waypoint", "lat": 56.35, "lon": 11.80, "pais": "Internacional"},
    "WP_STOREBAELT_N":{"nombre": "Great Belt North Chokepoint", "tipo": "Waypoint", "lat": 55.75, "lon": 10.90, "pais": "Dinamarca"},
    "WP_STOREBAELT_S":{"nombre": "Great Belt South Chokepoint", "tipo": "Waypoint", "lat": 55.20, "lon": 11.10, "pais": "Dinamarca"},
    "WP_ORESUND_N":   {"nombre": "The Sound North TSS", "tipo": "Waypoint", "lat": 56.12, "lon": 12.58, "pais": "Dinamarca-Suecia"},
    "WP_ORESUND_S":   {"nombre": "The Sound South TSS", "tipo": "Waypoint", "lat": 55.50, "lon": 12.75, "pais": "Dinamarca-Suecia"},
    "WP_FEHMARNBELT": {"nombre": "Fehmarn Belt Passage", "tipo": "Waypoint", "lat": 54.55, "lon": 11.30, "pais": "Alemania-Dinamarca"},
    "WP_NORTHSEA_N":  {"nombre": "North Sea North Approach", "tipo": "Waypoint", "lat": 56.80, "lon": 7.50, "pais": "Internacional"},
    "WP_NORTHSEA_S":  {"nombre": "North Sea South Route", "tipo": "Waypoint", "lat": 55.00, "lon": 7.50, "pais": "Internacional"},
    "WP_BALTIC_W":    {"nombre": "Baltic Sea West Gateway", "tipo": "Waypoint", "lat": 54.80, "lon": 13.50, "pais": "Internacional"},
    # --- Waypoints FASE 2: corredores intermedios para la red ampliada ---
    "WP_LAESO":      {"nombre": "Laeso Channel", "tipo": "Waypoint", "lat": 57.30, "lon": 10.75, "pais": "Internacional"},
    "WP_ANHOLT":     {"nombre": "Anholt Passage", "tipo": "Waypoint", "lat": 56.72, "lon": 11.58, "pais": "Internacional"},
    "WP_SAMSO":      {"nombre": "Samso Belt", "tipo": "Waypoint", "lat": 55.87, "lon": 10.78, "pais": "Dinamarca"},
    "WP_LILLEBAELT": {"nombre": "Little Belt South", "tipo": "Waypoint", "lat": 55.35, "lon": 9.72, "pais": "Dinamarca"},
    "WP_KIEL_W":     {"nombre": "Kiel Canal West Approach", "tipo": "Waypoint", "lat": 53.95, "lon": 8.80, "pais": "Alemania"},
    "WP_BORNHOLM_W": {"nombre": "Bornholm West", "tipo": "Waypoint", "lat": 55.10, "lon": 13.90, "pais": "Internacional"},
    "WP_BALTIC_E":   {"nombre": "Baltic Sea East Gateway", "tipo": "Waypoint", "lat": 54.30, "lon": 14.00, "pais": "Internacional"},
    "WP_SKAW_E":     {"nombre": "Skaw East", "tipo": "Waypoint", "lat": 57.75, "lon": 11.00, "pais": "Internacional"},
    # --- Waypoints FASE 2b: pasos obligados para no cruzar tierra ---
    "WP_FALSTERBO":  {"nombre": "Falsterbo Round", "tipo": "Waypoint", "lat": 55.28, "lon": 13.00, "pais": "Internacional"},
    "WP_DROGDEN":    {"nombre": "Drogden Channel", "tipo": "Waypoint", "lat": 55.60, "lon": 12.78, "pais": "Dinamarca"},
    "WP_OSLOFJORD":  {"nombre": "Oslofjord Mouth", "tipo": "Waypoint", "lat": 59.03, "lon": 10.58, "pais": "Noruega"},
    # --- Waypoints FASE 2c: bocas de fiordo y pasos entre islas ---
    "WP_HALS":       {"nombre": "Hals Approach (Limfjord)", "tipo": "Waypoint", "lat": 57.00, "lon": 10.45, "pais": "Dinamarca"},
    "WP_LANGELAND_S":{"nombre": "Langeland South", "tipo": "Waypoint", "lat": 54.70, "lon": 10.85, "pais": "Dinamarca"},
    "WP_HORSENS_M":  {"nombre": "Horsens Fjord Mouth", "tipo": "Waypoint", "lat": 55.82, "lon": 10.10, "pais": "Dinamarca"},
    "WP_VEJLE_M":    {"nombre": "Vejle Fjord Mouth", "tipo": "Waypoint", "lat": 55.63, "lon": 9.80, "pais": "Dinamarca"},
    "WP_ODENSE_M":   {"nombre": "Odense Fjord Mouth", "tipo": "Waypoint", "lat": 55.60, "lon": 10.47, "pais": "Dinamarca"},
    "WP_ENDELAVE_N": {"nombre": "Endelave North Passage", "tipo": "Waypoint", "lat": 55.81, "lon": 10.42, "pais": "Dinamarca"},
    "WP_UDDEVALLA_M":{"nombre": "Uddevalla Fjord Mouth", "tipo": "Waypoint", "lat": 58.28, "lon": 11.55, "pais": "Suecia"},
    "WP_EBELTOFT_S": {"nombre": "Ebeltoft South Approach", "tipo": "Waypoint", "lat": 56.03, "lon": 10.62, "pais": "Dinamarca"}
}

ARISTAS_BASE: List[Tuple[str, str, int, bool]] = [
    # (origen, destino, incidentes_historicos, disponibilidad_base)
    # Troncal manual de la Fase 1: se conserva intacto para no romper rutas probadas.
    ("WP_NORTHSEA_S", "DK_ESB", 1, True),
    ("WP_NORTHSEA_S", "WP_NORTHSEA_N", 0, True),
    ("WP_NORTHSEA_N", "WP_SKAGERRAK", 3, True),
    ("WP_SKAGERRAK", "NO_KRS", 0, True),
    ("WP_SKAGERRAK", "NO_OSL", 1, True),
    ("WP_SKAGERRAK", "DK_SKA", 2, True),
    ("DK_SKA", "DK_AAL", 0, True),
    ("DK_SKA", "WP_KATTEGAT_N", 2, True),
    ("WP_KATTEGAT_N", "SE_GOT", 1, True),
    ("WP_KATTEGAT_N", "WP_KATTEGAT_S", 1, True),
    ("WP_KATTEGAT_S", "DK_AAR", 0, True),
    ("WP_KATTEGAT_S", "WP_STOREBAELT_N", 2, True),
    ("WP_KATTEGAT_S", "WP_ORESUND_N", 3, True),
    ("WP_STOREBAELT_N", "DK_FRC", 0, True),
    ("WP_STOREBAELT_N", "WP_STOREBAELT_S", 4, True),  # Estrecho estrecho con alto tránsito
    ("WP_STOREBAELT_S", "DE_KLM", 1, True),
    ("WP_STOREBAELT_S", "WP_FEHMARNBELT", 1, True),
    ("WP_ORESUND_N", "SE_HEL", 1, True),
    ("WP_ORESUND_N", "DK_CPH", 2, True),
    ("DK_CPH", "SE_MAL", 0, True),
    ("DK_CPH", "WP_ORESUND_S", 1, True),
    ("SE_MAL", "WP_ORESUND_S", 0, True),
    ("WP_FEHMARNBELT", "DE_ROS", 1, True),
    ("WP_FEHMARNBELT", "WP_BALTIC_W", 0, True),
    ("WP_ORESUND_S", "WP_BALTIC_W", 1, True),
    ("DE_ROS", "WP_BALTIC_W", 0, True)
]


def _dist_nm(a_id: str, b_id: str) -> float:
    """Distancia Haversine en millas náuticas entre dos nodos del diccionario."""
    na, nb = NODOS_RED[a_id], NODOS_RED[b_id]
    _, dist_nm = haversine(na["lat"], na["lon"], nb["lat"], nb["lon"])
    return dist_nm


def _incidentes_default(u: str, v: str) -> int:
    """Nº de incidentes determinista (0-2) derivado del hash del par, para aristas nuevas."""
    clave = "".join(sorted([u, v]))
    return int(hashlib.md5(clave.encode()).hexdigest(), 16) % 3


# ------------------------------------------------------------------------------
# Navegabilidad: ninguna arista debe cruzar tierra (salvo canales dragados).
# Reutiliza la auditoría de validar_tierra.py como fuente única de verdad.
# ------------------------------------------------------------------------------
from validar_tierra import TOL_NM, cargar_mascara, nm_sobre_tierra


def _agua_ok(u: str, v: str) -> bool:
    """True si el segmento u->v es navegable (no cruza tierra)."""
    na, nb = NODOS_RED[u], NODOS_RED[v]
    grid, lon0, lat0, step = cargar_mascara()
    return nm_sobre_tierra(grid, lon0, lat0, step,
                           na["lat"], na["lon"], nb["lat"], nb["lon"]) <= TOL_NM


# Canales de acceso dragados (puertos de fiordo): la máscara 10m no resuelve
# canales mantenidos de <1 nm de ancho; son rutas reales, se eximen del test.
# (puerto, waypoint de boca, incidentes)
ACCESOS_FIORDO: List[Tuple[str, str, int]] = [
    ("DK_AAL", "WP_HALS", 1),        # Limfjord: Aalborg -> Hals
    ("DK_HOR", "WP_HORSENS_M", 0),    # Horsens Fjord
    ("DK_VEJ", "WP_VEJLE_M", 1),      # Vejle Fjord
    ("DK_ODN", "WP_ODENSE_M", 0),     # Odense Fjord
    ("SE_UDD", "WP_UDDEVALLA_M", 0),  # Uddevalla Fjord (Havstensfjord)
]


def generar_conexiones(k: int = 3, max_dist_nm: float = 90.0,
                       max_candidata_nm: float = 110.0) -> List[Tuple[str, str, int, bool]]:
    """
    Red navegable: troncal manual (reparando cruces por tierra con rutas
    solo-agua) + k-vecinos solo-agua + puentes de conectividad solo-agua.

    - Cada nodo se conecta a sus k vecinos más cercanos navegables.
    - Se garantiza que el grafo resultante sea conexo.
    - Retorna lista de (origen, destino, incidentes, disponibilidad).
    """
    vistos: set = set()
    aristas: List[Tuple[str, str, int, bool]] = []

    def agregar(u: str, v: str, inc: int, disp: bool) -> None:
        clave = tuple(sorted([u, v]))
        if u != v and clave not in vistos:
            vistos.add(clave)
            aristas.append((u, v, inc, disp))

    ids = list(NODOS_RED.keys())

    # 1. Grafo candidato: todos los pares cercanos cuyo segmento no cruza tierra
    print("[2a/4] Verificando navegabilidad de pares cercanos (máscara de tierra)...")
    cand = nx.Graph()
    cand.add_nodes_from(ids)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            u, v = ids[i], ids[j]
            d = _dist_nm(u, v)
            if d <= max_candidata_nm and _agua_ok(u, v):
                cand.add_edge(u, v, peso=d)

    # 2. Troncal: conservar la navegable; reenrutar la que cruce tierra
    for u, v, inc, disp in ARISTAS_BASE:
        if _agua_ok(u, v):
            agregar(u, v, inc, disp)
            continue
        try:
            ruta = nx.shortest_path(cand, u, v, weight="peso")
            for a, b in zip(ruta, ruta[1:]):
                agregar(a, b, _incidentes_default(a, b), True)
            print(f"      -> troncal reenrutada {u}->{v}: {' -> '.join(ruta)}")
        except nx.NetworkXNoPath:
            # Sin alternativa navegable: se elimina (la conectividad global
            # la garantiza el paso 4 con puentes solo-agua).
            print(f"      !! {u}->{v} cruza tierra y no tiene ruta alterna: se elimina")

    # 2b. Accesos a puertos de fiordo (canales dragados, exentos del test)
    for u, v, inc in ACCESOS_FIORDO:
        agregar(u, v, inc, True)

    # 3. k-vecinos solo-agua
    for u in ids:
        cercanas = sorted(((d["peso"], vv) for vv, d in cand[u].items()), key=lambda t: t[0])
        for dist, vv in cercanas[:k]:
            if dist <= max_dist_nm:
                agregar(u, vv, _incidentes_default(u, vv), True)

    # Garantizar conectividad: unir componentes con el par navegable más cercano
    G = nx.Graph()
    G.add_nodes_from(ids)
    for u, v, _, _ in aristas:
        G.add_edge(u, v)
    while not nx.is_connected(G):
        comps = list(nx.connected_components(G))
        mejor = None
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                for u in comps[i]:
                    for v in comps[j]:
                        if not _agua_ok(u, v):
                            continue
                        d = _dist_nm(u, v)
                        if mejor is None or d < mejor[0]:
                            mejor = (d, u, v)
        if mejor is None:
            print("      !! componentes aisladas:")
            for c in comps:
                print(f"         ({len(c)}): {sorted(c)[:12]}")
            raise RuntimeError("Sin puente navegable entre componentes; revisar waypoints.")
        _, u, v = mejor
        agregar(u, v, _incidentes_default(u, v), True)
        G.add_edge(u, v)

    return aristas


CONEXIONES_NAV: List[Tuple[str, str, int, bool]] = generar_conexiones()


# ------------------------------------------------------------------------------
# 4. Procesamiento Optimizado del Grafo con los 7 Atributos Obligatorios
# ------------------------------------------------------------------------------
def procesar_red_maritima(df_ais: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Construye la red de movilidad aplicando agregación espacial vectorizada O(N) + O(E).
    Calcula obligatoriamente los 7 atributos requeridos por la rúbrica para cada arista.
    """
    print("[2/4] Ejecución de agregación espacial optimizada para cálculo de métricas...")

    # OPTIMIZACIÓN PANDAS: Pre-discretización en celdas espaciales de 0.5 grados
    # Esto elimina el cuello de botella de recorrer todo el DataFrame en cada iteración del bucle.
    df_grid = df_ais.copy()
    df_grid["grid_lat"] = (df_grid["lat"] / 0.5).round() * 0.5
    df_grid["grid_lon"] = (df_grid["lon"] / 0.5).round() * 0.5

    # Pre-agregación en tabla hash: conteo de buques únicos y velocidad media por celda
    grid_stats = df_grid.groupby(["grid_lat", "grid_lon"]).agg(
        buques_unicos=("mmsi", "nunique"),
        vel_media=("sog", "mean")
    ).reset_index().set_index(["grid_lat", "grid_lon"])

    # 1. Generar DataFrame de Nodos
    df_nodos = pd.DataFrame([{"id": k, **v} for k, v in NODOS_RED.items()])

    # 2. Generar DataFrame de Aristas con los 7 atributos obligatorios
    aristas = []
    consumo_base_galon_nm = 3.5  # Galones de combustible base por milla náutica
    precio_galon_usd = 2.85      # Costo en USD por galón

    for u, v, incidentes, disponible in CONEXIONES_NAV:
        n1, n2 = NODOS_RED[u], NODOS_RED[v]
        dist_km, dist_nm = haversine(n1["lat"], n1["lon"], n2["lat"], n2["lon"])

        # Identificar celdas correspondientes al corredor
        mid_lat = round(((n1["lat"] + n2["lat"]) / 2.0) / 0.5) * 0.5
        mid_lon = round(((n1["lon"] + n2["lon"]) / 2.0) / 0.5) * 0.5

        if (mid_lat, mid_lon) in grid_stats.index:
            stats = grid_stats.loc[(mid_lat, mid_lon)]
            buques = int(stats["buques_unicos"])
            vel_prom = round(float(stats["vel_media"]), 2)
        else:
            buques = 15
            vel_prom = 12.0

        # Atributo 2: tiempo_estimado (horas)
        tiempo_est = round(dist_nm / max(vel_prom, 1.0), 2)

        # Atributo 4: nivel_congestion (Baja, Media, Alta)
        if buques < 40:
            congestion = "Baja"
            factor_congestion = 1.0
        elif buques < 85:
            congestion = "Media"
            factor_congestion = 1.25
        else:
            congestion = "Alta"
            factor_congestion = 1.60

        # Atributo 5: costo (costo operativo en USD considerando distancia y congestión)
        costo_operativo = round(dist_nm * consumo_base_galon_nm * precio_galon_usd * factor_congestion, 2)

        aristas.append({
            "origen": u,
            "destino": v,
            "distancia": dist_nm,               # 1. distancia (millas náuticas)
            "tiempo_estimado": tiempo_est,       # 2. tiempo_estimado (horas)
            "velocidad_promedio": vel_prom,     # 3. velocidad_promedio (nudos)
            "nivel_congestion": congestion,      # 4. nivel_congestion (Baja/Media/Alta)
            "costo": costo_operativo,           # 5. costo (USD de combustible y operación)
            "disponibilidad": disponible,       # 6. disponibilidad (Booleano True/False)
            "num_incidentes": incidentes,       # 7. num_incidentes (Entero)
            # Metadatos auxiliares para visualización
            "distancia_km": dist_km,
            "buques_detectados": buques
        })

    df_aristas = pd.DataFrame(aristas)
    return df_nodos, df_aristas


# ------------------------------------------------------------------------------
# 5. Visualización del Grafo con Distinción de Puertos y Waypoints
# ------------------------------------------------------------------------------
def dibujar_grafo(
    df_nodos: pd.DataFrame,
    df_aristas: pd.DataFrame,
    ruta_img: Path = GRAPH_IMG_OUTPUT
) -> None:
    """
    Genera el diagrama georreferenciado de la red diferenciando visualmente:
    - Puertos Comerciales (Azul #1F77B4)
    - Waypoints / Canales TSS (Naranja/Púrpura #E67E22)
    - Aristas coloreadas por nivel de congestión (Verde, Naranja, Rojo).
    """
    print("[3/4] Generando visualización georreferenciada con distinción de tipos de nodo...")
    G = nx.Graph()

    for _, row in df_nodos.iterrows():
        G.add_node(
            row["id"],
            nombre=row["nombre"],
            tipo=row["tipo"],
            pos=(row["lon"], row["lat"])
        )

    for _, row in df_aristas.iterrows():
        G.add_edge(
            row["origen"],
            row["destino"],
            distancia=row["distancia"],
            congestion=row["nivel_congestion"]
        )

    plt.figure(figsize=(13, 9), dpi=250)
    pos = nx.get_node_attributes(G, "pos")

    # Separación y coloreado por tipo de nodo
    puerto_nodes = [n for n, d in G.nodes(data=True) if d.get("tipo") == "Puerto"]
    waypoint_nodes = [n for n, d in G.nodes(data=True) if d.get("tipo") == "Waypoint"]

    # Colores según nivel de congestión en las aristas
    mapa_colores = {"Baja": "#27AE60", "Media": "#F39C12", "Alta": "#D9381E"}
    edge_colors = [mapa_colores.get(G.edges[e]["congestion"], "#95A5A6") for e in G.edges()]

    # Dibujar aristas
    nx.draw_networkx_edges(G, pos, edge_color=edge_colors, width=2.6, alpha=0.8)

    # Dibujar nodos de tipo Puerto (Azul Oscuro con borde blanco)
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=puerto_nodes,
        node_color="#1B4F72",
        node_size=420,
        node_shape="s",
        edgecolors="white",
        linewidths=1.5,
        label="Puerto Comercial (Azul Oscuro)"
    )

    # Dibujar nodos de tipo Waypoint (Morado con borde blanco)
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=waypoint_nodes,
        node_color="#8E44AD",
        node_size=320,
        node_shape="o",
        edgecolors="white",
        linewidths=1.5,
        label="Waypoint / Canal TSS (Morado)"
    )

    # Etiquetas de nombres
    labels = {n: G.nodes[n]["nombre"] for n in G.nodes()}
    nx.draw_networkx_labels(
        G, pos,
        labels=labels,
        font_size=6.8,
        font_weight="bold",
        verticalalignment="bottom"
    )

    plt.title(
        "Dominio: Logística Portuaria Autónoma (Smart Port) - Red de Movilidad G = (V, E)\n"
        "Nodos: Puertos (Azul Oscuro) vs Waypoints (Morado) | Aristas: Congestión AIS",
        fontsize=11, fontweight="bold", pad=12
    )
    plt.xlabel("Longitud (°E)", fontsize=9)
    plt.ylabel("Latitud (°N)", fontsize=9)
    plt.legend(loc="lower right", framealpha=0.9, fontsize=8)
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()

    plt.savefig(ruta_img, bbox_inches="tight")
    plt.close()
    print(f"      -> Gráfico guardado en: {ruta_img.name}")


# ------------------------------------------------------------------------------
# 6. Punto de Entrada Principal
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    if not RAW_CSV.exists():
        print(f"Error: Dataset crudo no encontrado en: {RAW_CSV}")
        exit(1)

    df_ais = cargar_y_limpiar_ais(RAW_CSV, max_chunks=3, chunksize=100_000)
    df_nodos, df_aristas = procesar_red_maritima(df_ais)

    # Exportación estricta a CSV
    df_nodos.to_csv(NODES_OUTPUT, index=False)
    df_aristas.to_csv(EDGES_OUTPUT, index=False)
    print(f"[4/4] Archivos exportados exitosamente:\n      -> {NODES_OUTPUT.name} ({len(df_nodos)} nodos)\n      -> {EDGES_OUTPUT.name} ({len(df_aristas)} aristas con los 7 atributos)")

    dibujar_grafo(df_nodos, df_aristas)

    print("\n" + "=" * 70)
    print(" VERIFICACIÓN DE LOS 7 ATRIBUTOS OBLIGATORIOS EN EDGES.CSV:")
    for i, col in enumerate(["distancia", "tiempo_estimado", "velocidad_promedio", "nivel_congestion", "costo", "disponibilidad", "num_incidentes"], 1):
        print(f"  {i}. {col:20} -> Presente ({df_aristas[col].dtype})")
    print("=" * 70 + "\n")


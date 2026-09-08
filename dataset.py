"""
================================================================================
PROYECTO INTEGRADOR - INTELIGENCIA ARTIFICIAL (SIST5036) - FASE 1
DOMINIO: LOGÍSTICA PORTUARIA AUTÓNOMA (SMART PORT)
BACKEND DE DATOS AIS Y MODELADO DEL ENTORNO G = (V, E)
================================================================================
"""
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
    "WP_BALTIC_W":    {"nombre": "Baltic Sea West Gateway", "tipo": "Waypoint", "lat": 54.80, "lon": 13.50, "pais": "Internacional"}
}

CONEXIONES_NAV: List[Tuple[str, str, int, bool]] = [
    # (origen, destino, incidentes_historicos, disponibilidad_base)
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


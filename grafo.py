"""
grafo.py

"""

from pathlib import Path
import pandas as pd
import networkx as nx

BASE_DIR = Path(__file__).resolve().parent
NODES_PATH = BASE_DIR / "data" / "nodes.csv"
EDGES_PATH = BASE_DIR / "data" / "edges.csv"


def construir_grafo(nodes_path: Path = NODES_PATH, edges_path: Path = EDGES_PATH) -> nx.Graph:
    """Construye el grafo G=(V,E) de la red marítima a partir de los CSV."""
    nodes_df = pd.read_csv(nodes_path)
    edges_df = pd.read_csv(edges_path)

    G = nx.Graph()

    # --- Nodos (V): puertos y waypoints ---
    for _, fila in nodes_df.iterrows():
        G.add_node(
            fila["id"],
            nombre=fila["nombre"],
            tipo=fila["tipo"],          # "Puerto" o "Waypoint"
            lat=fila["lat"],
            lon=fila["lon"],
            pais=fila["pais"],
        )

    # --- Aristas (E): conexiones con los 7 atributos obligatorios ---
    for _, fila in edges_df.iterrows():
        G.add_edge(
            fila["origen"],
            fila["destino"],
            distancia=fila["distancia"],
            tiempo_estimado=fila["tiempo_estimado"],
            velocidad_promedio=fila["velocidad_promedio"],
            nivel_congestion=fila["nivel_congestion"],
            costo=fila["costo"],
            disponibilidad=bool(fila["disponibilidad"]),
            num_incidentes=fila["num_incidentes"],
        )

    return G


if __name__ == "__main__":
    G = construir_grafo()
    print(f"Grafo cargado: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
    print("Ejemplo de nodo:", list(G.nodes(data=True))[0])
    print("Ejemplo de arista:", list(G.edges(data=True))[0])

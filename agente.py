"""
agente.py

"""

from dataclasses import dataclass, field
from typing import Optional
import networkx as nx

from grafo import construir_grafo


class AccionInvalidaError(Exception):
    """Se lanza cuando el agente intenta moverse a un nodo no adyacente
    o a una conexión no disponible (disponibilidad=False)."""
    pass


@dataclass
class AgenteMaritimo:
    """
    Agente reactivo simple que navega sobre la red marítima G=(V,E).

    Atributos de estado (lo que el agente "sabe" en todo momento):
        grafo         : networkx.Graph con nodos y aristas de la red.
        nodo_actual   : id del nodo donde se encuentra el agente ahora.
        historial     : secuencia de nodos visitados (para trazabilidad).
        tiempo_total  : suma de 'tiempo_estimado' de las aristas recorridas.
        costo_total   : suma de 'costo' de las aristas recorridas.
        distancia_total: suma de 'distancia' de las aristas recorridas.
    """

    grafo: nx.Graph
    nodo_actual: str
    historial: list = field(default_factory=list)
    tiempo_total: float = 0.0
    costo_total: float = 0.0
    distancia_total: float = 0.0

    def __post_init__(self):
        if self.nodo_actual not in self.grafo.nodes:
            raise ValueError(f"Nodo inicial '{self.nodo_actual}' no existe en el grafo.")
        self.historial.append(self.nodo_actual)

    # ------------------------------------------------------------------
    # SENSORES: percibir el entorno
    # ------------------------------------------------------------------
    def percibir(self) -> dict:
        """
        Simula la lectura de sensores (AIS/GPS): devuelve el estado actual
        del agente y la información disponible del nodo donde se encuentra.
        """
        datos_nodo = self.grafo.nodes[self.nodo_actual]
        return {
            "nodo_actual": self.nodo_actual,
            "nombre": datos_nodo.get("nombre"),
            "tipo": datos_nodo.get("tipo"),
            "lat": datos_nodo.get("lat"),
            "lon": datos_nodo.get("lon"),
            "pais": datos_nodo.get("pais"),
            "vecinos_disponibles": self.consultar_acciones(),
        }

    # ------------------------------------------------------------------
    # CONSULTA AL GRAFO: qué acciones son legales desde el nodo actual
    # ------------------------------------------------------------------
    def consultar_acciones(self) -> list[dict]:
        """
        Devuelve la lista de acciones legales (moverse a un nodo adyacente)
        desde el nodo actual, con el costo asociado a cada una. Solo se
        incluyen conexiones con disponibilidad=True.
        """
        acciones = []
        for vecino in self.grafo.neighbors(self.nodo_actual):
            datos_arista = self.grafo.edges[self.nodo_actual, vecino]
            if not datos_arista.get("disponibilidad", True):
                continue
            acciones.append({
                "destino": vecino,
                "distancia": datos_arista["distancia"],
                "tiempo_estimado": datos_arista["tiempo_estimado"],
                "costo": datos_arista["costo"],
                "nivel_congestion": datos_arista["nivel_congestion"],
            })
        return acciones

    # ------------------------------------------------------------------
    # ACTUADORES: ejecutar una acción (moverse)
    # ------------------------------------------------------------------
    def ejecutar_accion(self, nodo_destino: str) -> dict:
        """
        Mueve al agente desde nodo_actual hasta nodo_destino, siempre que
        exista una arista disponible entre ambos. Actualiza el estado
        interno (historial y medida de desempeño acumulada).

        Lanza AccionInvalidaError si el movimiento no es legal.
        """
        if not self.grafo.has_edge(self.nodo_actual, nodo_destino):
            raise AccionInvalidaError(
                f"No existe conexión directa entre '{self.nodo_actual}' y '{nodo_destino}'."
            )

        datos_arista = self.grafo.edges[self.nodo_actual, nodo_destino]
        if not datos_arista.get("disponibilidad", True):
            raise AccionInvalidaError(
                f"La conexión '{self.nodo_actual}' -> '{nodo_destino}' no está disponible."
            )

        # Actualizar medida de desempeño (performance measure)
        self.tiempo_total += datos_arista["tiempo_estimado"]
        self.costo_total += datos_arista["costo"]
        self.distancia_total += datos_arista["distancia"]

        # Ejecutar el movimiento
        origen = self.nodo_actual
        self.nodo_actual = nodo_destino
        self.historial.append(nodo_destino)

        return {
            "origen": origen,
            "destino": nodo_destino,
            "tiempo_arista": datos_arista["tiempo_estimado"],
            "costo_arista": datos_arista["costo"],
            "distancia_arista": datos_arista["distancia"],
            "tiempo_total_acumulado": self.tiempo_total,
            "costo_total_acumulado": self.costo_total,
            "distancia_total_acumulada": self.distancia_total,
        }

    def resumen(self) -> str:
        return (
            f"Nodo actual: {self.nodo_actual} | "
            f"Nodos visitados: {len(self.historial)} | "
            f"Distancia total: {self.distancia_total:.2f} nm | "
            f"Tiempo total: {self.tiempo_total:.2f} h | "
            f"Costo total: ${self.costo_total:.2f}"
        )


if __name__ == "__main__":
    # Demostración mínima: crear el agente en un puerto y percibir su entorno
    G = construir_grafo()
    agente = AgenteMaritimo(grafo=G, nodo_actual="DK_CPH")

    print("=== Percepción inicial ===")
    percepcion = agente.percibir()
    print(f"Ubicación: {percepcion['nombre']} ({percepcion['nodo_actual']})")
    print(f"Vecinos disponibles: {[v['destino'] for v in percepcion['vecinos_disponibles']]}")

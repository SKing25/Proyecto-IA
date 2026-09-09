"""
test_agente.py

"""

from grafo import construir_grafo
from agente import AgenteMaritimo, AccionInvalidaError


def prueba_1_percepcion_inicial(G):
    """El agente debe poder percibir correctamente su nodo inicial."""
    print("\n--- Prueba 1: Percepción inicial ---")
    agente = AgenteMaritimo(grafo=G, nodo_actual="DK_CPH")
    percepcion = agente.percibir()
    assert percepcion["nodo_actual"] == "DK_CPH"
    assert len(percepcion["vecinos_disponibles"]) > 0
    print(f"OK: {agente.resumen()}")
    print(f"Vecinos detectados: {[v['destino'] for v in percepcion['vecinos_disponibles']]}")


def prueba_2_movimiento_simple(G):
    """El agente debe poder ejecutar un único movimiento válido."""
    print("\n--- Prueba 2: Movimiento simple (un salto) ---")
    agente = AgenteMaritimo(grafo=G, nodo_actual="DK_CPH")
    resultado = agente.ejecutar_accion("WP_ORESUND_N")
    assert agente.nodo_actual == "WP_ORESUND_N"
    assert agente.historial == ["DK_CPH", "WP_ORESUND_N"]
    print(f"OK: se movió de {resultado['origen']} a {resultado['destino']}")
    print(f"    distancia={resultado['distancia_arista']} nm, "
          f"tiempo={resultado['tiempo_arista']} h, "
          f"costo=${resultado['costo_arista']}")
    print(agente.resumen())


def prueba_3_ruta_multiple_saltos(G):
    """
    El agente debe poder recorrer una ruta de varios nodos consecutivos
    entre dos puntos reales de la red: DK_CPH (puerto) -> DE_ROS (puerto),
    pasando por los waypoints intermedios.
    """
    print("\n--- Prueba 3: Ruta de múltiples saltos entre dos puertos ---")
    agente = AgenteMaritimo(grafo=G, nodo_actual="DK_CPH")
    ruta = ["DK_CPH", "WP_ORESUND_S", "WP_BALTIC_W", "DE_ROS"]

    for siguiente_nodo in ruta[1:]:
        agente.ejecutar_accion(siguiente_nodo)

    assert agente.nodo_actual == "DE_ROS"
    assert agente.historial == ruta
    print(f"OK: ruta completada {' -> '.join(agente.historial)}")
    print(agente.resumen())


def prueba_4_accion_invalida_es_rechazada(G):
    """
    El agente NO debe poder moverse a un nodo que no sea adyacente:
    debe lanzar AccionInvalidaError y no debe cambiar de estado.
    """
    print("\n--- Prueba 4: Rechazo de una acción inválida ---")
    agente = AgenteMaritimo(grafo=G, nodo_actual="DK_CPH")
    nodo_no_adyacente = "NO_OSL"  # no está conectado directamente a DK_CPH

    try:
        agente.ejecutar_accion(nodo_no_adyacente)
        raise AssertionError("Se esperaba AccionInvalidaError y no se lanzó.")
    except AccionInvalidaError as e:
        assert agente.nodo_actual == "DK_CPH"  # el estado no debe cambiar
        print(f"OK: la acción inválida fue rechazada correctamente -> {e}")


def prueba_5_todos_los_nodos_son_alcanzables(G):
    """
    Sanity check estructural del grafo: confirma que la red es conexa,
    es decir, que en teoría existe un camino entre cualquier par de
    nodos (requisito para que un algoritmo de búsqueda del Corte 2
    pueda encontrar rutas entre cualquier origen y destino).
    """
    print("\n--- Prueba 5: Conectividad general de la red ---")
    import networkx as nx
    conexo = nx.is_connected(G)
    print(f"¿La red es conexa? {conexo}")
    assert conexo, "La red tiene nodos aislados; revisar edges.csv"
    print("OK: todos los nodos son alcanzables entre sí.")


if __name__ == "__main__":
    G = construir_grafo()
    print(f"Grafo cargado para pruebas: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")

    prueba_1_percepcion_inicial(G)
    prueba_2_movimiento_simple(G)
    prueba_3_ruta_multiple_saltos(G)
    prueba_4_accion_invalida_es_rechazada(G)
    prueba_5_todos_los_nodos_son_alcanzables(G)

    print("\n=== TODAS LAS PRUEBAS PASARON CORRECTAMENTE ===")

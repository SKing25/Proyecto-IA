"""
test_busqueda.py — Batería de pruebas del motor de búsqueda (Corte 2).

Verifica: validez de rutas, optimalidad UCS/A*, rechazo de errores,
respeto a disponibilidad=False, admisibilidad de la heurística y comparar().
Uso:  .venv/bin/python test_busqueda.py
"""
from grafo import construir_grafo
from busqueda import (ALGORITMOS, buscar, comparar, heuristica,
                      verificar_admisibilidad, ucs)


def prueba_1_todos_encuentran_ruta(G):
    print("\n--- Prueba 1: los 5 algoritmos encuentran DK_CPH -> DE_ROS ---")
    for a in ALGORITMOS:
        r = buscar(a, "DK_CPH", "DE_ROS", G, "distancia")
        assert r.exito, f"{a} no encontró ruta: {r.error}"
        assert r.camino[0] == "DK_CPH" and r.camino[-1] == "DE_ROS"
        # cada paso debe ser una arista real disponible
        for x, y in zip(r.camino, r.camino[1:]):
            assert G.has_edge(x, y), f"{a}: paso inválido {x}->{y}"
            assert G.edges[x, y].get("disponibilidad", True)
        print(f"  OK {a:6s}: {' -> '.join(r.camino)} | {r.distancia_total:.1f} nm | "
              f"expandidos={r.nodos_expandidos}")


def prueba_2_ucs_y_astar_son_optimos(G):
    print("\n--- Prueba 2: UCS y A* son óptimos en los 3 criterios ---")
    for crit, campo in [("distancia", "distancia_total"), ("tiempo", "tiempo_total"),
                        ("costo", "costo_total")]:
        costos = {}
        for a in ALGORITMOS:
            r = buscar(a, "NO_OSL", "PL_SWI", G, crit)
            assert r.exito, f"{a}/{crit}: {r.error}"
            costos[a] = getattr(r, campo)
        optimo = costos["ucs"]
        assert abs(costos["astar"] - optimo) < 1e-6, f"A* no óptimo en {crit}: {costos}"
        assert costos["bfs"] >= optimo - 1e-6 and costos["dfs"] >= optimo - 1e-6 \
            and costos["voraz"] >= optimo - 1e-6
        print(f"  OK {crit:9s}: ucs={optimo:.2f} astar={costos['astar']:.2f} "
              f"bfs={costos['bfs']:.2f} dfs={costos['dfs']:.2f} voraz={costos['voraz']:.2f}")


def prueba_3_astar_expande_menos_que_ucs(G):
    print("\n--- Prueba 3: A* expande <= nodos que UCS (heurística consistente) ---")
    total_ucs = total_astar = 0
    pares = [("DK_ESB", "DK_RON"), ("NO_OSL", "DE_TRV"), ("SE_LYS", "PL_SWI"),
             ("DK_HAN", "SE_TRE"), ("DE_BRV", "DK_FRH")]
    for o, d in pares:
        ru = buscar("ucs", o, d, G, "distancia")
        ra = buscar("astar", o, d, G, "distancia")
        assert ru.exito and ra.exito
        assert abs(ru.distancia_total - ra.distancia_total) < 1e-6, "costos difieren"
        total_ucs += ru.nodos_expandidos
        total_astar += ra.nodos_expandidos
        print(f"  {o}->{d}: ucs={ru.nodos_expandidos} astar={ra.nodos_expandidos}")
    assert total_astar <= total_ucs, "A* expandió más que UCS en agregado"
    print(f"  OK total: ucs={total_ucs} astar={total_astar}")


def prueba_4_casos_borde(G):
    print("\n--- Prueba 4: casos borde y errores controlados ---")
    r = buscar("astar", "DK_CPH", "DK_CPH", G)
    assert r.exito and r.camino == ["DK_CPH"] and r.profundidad == 0
    print("  OK origen == destino")
    r = buscar("bfs", "DK_CPH", "NO_EXISTE", G)
    assert not r.exito and r.error
    print(f"  OK destino inválido -> {r.error}")
    r = buscar("dfs", "NO_EXISTE", "DK_CPH", G)
    assert not r.exito and r.error
    print(f"  OK origen inválido -> {r.error}")
    r = buscar(" Dijkstra ", "DK_CPH", "DE_ROS", G)
    assert not r.exito and "no válido" in r.error
    print(f"  OK algoritmo inválido -> {r.error}")
    r = buscar("ucs", "DK_CPH", "DE_ROS", G, "dinero")
    assert not r.exito and "no válido" in r.error
    print(f"  OK criterio inválido -> {r.error}")


def prueba_5_disponibilidad_bloqueada(G):
    print("\n--- Prueba 5: respeta disponibilidad=False (canal bloqueado) ---")
    G2 = G.copy()
    # Bloquear la salida sur DK_CPH -> WP_FALSTERBO -> WP_BALTIC_W
    G2.edges["WP_FALSTERBO", "WP_BALTIC_W"]["disponibilidad"] = False
    r = buscar("astar", "DK_CPH", "DE_ROS", G2, "distancia")
    assert r.exito, "debía existir ruta alterna"
    assert ("WP_FALSTERBO", "WP_BALTIC_W") not in list(zip(r.camino, r.camino[1:])) \
        and ("WP_BALTIC_W", "WP_FALSTERBO") not in list(zip(r.camino, r.camino[1:]))
    print(f"  OK ruta alterna: {' -> '.join(r.camino)}")
    # Aislar un nodo por completo -> sin ruta pero sin excepción
    G3 = G.copy()
    for v in list(G3.neighbors("DK_RON")):
        G3.edges["DK_RON", v]["disponibilidad"] = False
    r = buscar("bfs", "DK_RON", "SE_YST", G3)
    assert not r.exito and "Sin ruta" in r.error
    print("  OK nodo aislado retorna exito=False sin lanzar excepción")


def prueba_6_heuristica_admisible(G):
    print("\n--- Prueba 6: admisibilidad h(n) <= h*(n) en los 3 criterios ---")
    for crit in ("distancia", "tiempo", "costo"):
        rep = verificar_admisibilidad(G, crit)
        assert rep["es_admisible"], f"violaciones en {crit}: {rep['violaciones'][:3]}"
        assert rep["pares_revisados"] > 0
        print(f"  OK {crit:9s}: {rep['pares_revisados']} pares, 0 violaciones")
    # consistencia puntual: h(n) <= c(n,n') + h(n')
    import random
    random.seed(42)
    nodos = list(G.nodes)
    for _ in range(50):
        n = random.choice(nodos)
        goal = random.choice(nodos)
        for v in list(G.neighbors(n)):
            dd = G.edges[n, v]
            if not dd.get("disponibilidad", True):
                continue
            hn = heuristica(n, goal, G, "distancia")
            hn2 = heuristica(v, goal, G, "distancia")
            # épsilon 0.01: edges.csv redondea distancias a 2 decimales
            assert hn <= float(dd["distancia"]) + hn2 + 0.01, f"inconsistencia en {n}->{v}"
    print("  OK consistencia verificada en 50 muestras (desigualdad triangular)")


def prueba_7_comparar(G):
    print("\n--- Prueba 7: comparar() retorna los 5 algoritmos ---")
    res = comparar("DK_ESB", "SE_GOT", G, "tiempo")
    assert len(res) == 5 and all(r.exito for r in res)
    assert [r.algoritmo for r in res] == ALGORITMOS
    print("  OK tabla: " + " | ".join(f"{r.algoritmo}={r.tiempo_total:.1f}h" for r in res))


if __name__ == "__main__":
    G = construir_grafo()
    print(f"Grafo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
    prueba_1_todos_encuentran_ruta(G)
    prueba_2_ucs_y_astar_son_optimos(G)
    prueba_3_astar_expande_menos_que_ucs(G)
    prueba_4_casos_borde(G)
    prueba_5_disponibilidad_bloqueada(G)
    prueba_6_heuristica_admisible(G)
    prueba_7_comparar(G)
    print("\n=== TODAS LAS PRUEBAS DE BÚSQUEDA PASARON CORRECTAMENTE ===")

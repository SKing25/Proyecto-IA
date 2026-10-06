"""
================================================================================
PROYECTO INTEGRADOR - INTELIGENCIA ARTIFICIAL (SIST5036) - FASE 2 (CORTE 2)
MOTOR DE BÚSQUEDA: BFS, DFS, UCS, Voraz (Greedy) y A*

Lógica pura del agente: NO depende de FastAPI, matplotlib ni del frontend.
Criterios de optimización soportados: distancia (nm), tiempo (h), costo (USD).
================================================================================
"""
import heapq
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import networkx as nx

# Criterio público -> atributo de arista en el grafo
PESOS: Dict[str, str] = {
    "distancia": "distancia",          # millas náuticas
    "tiempo": "tiempo_estimado",       # horas
    "costo": "costo",                 # USD
}

ALGORITMOS = ["bfs", "dfs", "ucs", "voraz", "astar"]

DESCRIPCION_ALGORITMOS: Dict[str, str] = {
    "bfs": "BFS: no informado, óptimo en nº de saltos. Expande por niveles.",
    "dfs": "DFS: no informado, rápido pero no óptimo. Explora en profundidad.",
    "ucs": "UCS: no informado, óptimo en costo. Expande por menor g(n).",
    "voraz": "Voraz: informado, rápido pero no óptimo. Expande por menor h(n).",
    "astar": "A*: informado, óptimo con heurística admisible. Expande por g(n)+h(n).",
}


@dataclass
class ResultadoBusqueda:
    """Resultado estándar de cualquier algoritmo de búsqueda."""
    algoritmo: str
    criterio: str
    exito: bool
    camino: List[str] = field(default_factory=list)
    distancia_total: float = 0.0       # nm
    tiempo_total: float = 0.0          # h
    costo_total: float = 0.0           # USD
    nodos_expandidos: int = 0          # nodos sacados de la frontera
    nodos_visitados: List[str] = field(default_factory=list)  # orden de expansión
    profundidad: int = 0               # nº de aristas del camino
    tiempo_ms: float = 0.0
    frontera_max: int = 0
    error: Optional[str] = None
    # Árbol de decisiones: un registro por nodo expandido, en orden cronológico.
    # Cada registro: {"nodo": id, "padre": id|None, "g": costo acumulado
    # en unidades del criterio, "prof": profundidad en el árbol}.
    arbol: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "algoritmo": self.algoritmo,
            "criterio": self.criterio,
            "exito": self.exito,
            "camino": self.camino,
            "distancia_total": round(self.distancia_total, 2),
            "tiempo_total": round(self.tiempo_total, 2),
            "costo_total": round(self.costo_total, 2),
            "nodos_expandidos": self.nodos_expandidos,
            "nodos_visitados": self.nodos_visitados,
            "profundidad": self.profundidad,
            "tiempo_ms": round(self.tiempo_ms, 3),
            "frontera_max": self.frontera_max,
            "error": self.error,
            "arbol": self.arbol,
        }


# ------------------------------------------------------------------------------
# Utilidades sobre el grafo
# ------------------------------------------------------------------------------
def _arista_disponible(datos: dict) -> bool:
    disp = datos.get("disponibilidad", True)
    if isinstance(disp, str):
        return disp.strip().lower() not in ("false", "0", "no", "cerrada")
    return bool(disp)


def vecinos_disponibles(G: nx.Graph, nodo: str):
    """Genera (vecino, datos_arista) solo para conexiones disponibles."""
    for vecino in G.neighbors(nodo):
        datos = G.edges[nodo, vecino]
        if _arista_disponible(datos):
            yield vecino, datos


def _validar(G: nx.Graph, origen: str, destino: str) -> Optional[str]:
    if origen not in G.nodes:
        return f"Nodo origen '{origen}' no existe en el grafo."
    if destino not in G.nodes:
        return f"Nodo destino '{destino}' no existe en el grafo."
    return None


def _reconstruir_camino(padres: dict, origen: str, destino: str) -> List[str]:
    camino = [destino]
    while camino[-1] != origen:
        camino.append(padres[camino[-1]])
    camino.reverse()
    return camino


def _totales(G: nx.Graph, camino: List[str]):
    dist = t = c = 0.0
    for a, b in zip(camino, camino[1:]):
        d = G.edges[a, b]
        dist += float(d["distancia"])
        t += float(d["tiempo_estimado"])
        c += float(d["costo"])
    return dist, t, c


def _g_criterio(G: nx.Graph, padres: dict, origen: str, nodo: str, peso: str) -> float:
    """Costo acumulado en unidades del criterio siguiendo la cadena de padres."""
    g, x = 0.0, nodo
    while x != origen:
        p = padres.get(x)
        if p is None:
            break
        g += float(G.edges[p, x][peso])
        x = p
    return g


def _profundidad(padres: dict, origen: str, nodo: str) -> int:
    """Nº de aristas desde el origen siguiendo la cadena de padres."""
    d, x = 0, nodo
    while x != origen:
        if x not in padres:
            break
        x = padres[x]
        d += 1
    return d


def _registrar(G: nx.Graph, arbol: List[dict], padres: dict, origen: str,
               nodo: str, peso: str, g: Optional[float] = None) -> None:
    """Añade el registro de una expansión al árbol de decisiones."""
    if g is None:
        g = _g_criterio(G, padres, origen, nodo, peso)
    arbol.append({"nodo": nodo, "padre": padres.get(nodo),
                  "g": round(g, 2), "prof": _profundidad(padres, origen, nodo)})


# ------------------------------------------------------------------------------
# Heurística admisible y consistente (Haversine como cota inferior)
# ------------------------------------------------------------------------------
# Caché de constantes del grafo (se calculan una vez; G se carga una vez en la app).
_CACHE: Dict[tuple, float] = {}


def _vel_max(G: nx.Graph) -> float:
    clave = (id(G), "vmax")
    if clave not in _CACHE:
        vals = [float(d.get("velocidad_promedio", 0) or 0)
                for _, _, d in G.edges(data=True) if _arista_disponible(d)]
        _CACHE[clave] = max(vals) if vals and max(vals) > 0 else 25.0
    return _CACHE[clave]


def _costo_min_por_nm(G: nx.Graph) -> float:
    clave = (id(G), "cmin")
    if clave not in _CACHE:
        ratios = []
        for _, _, d in G.edges(data=True):
            if not _arista_disponible(d):
                continue
            dist = float(d.get("distancia", 0) or 0)
            if dist > 0:
                ratios.append(float(d.get("costo", 0) or 0) / dist)
        _CACHE[clave] = min(ratios) if ratios else 0.0
    return _CACHE[clave]


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 3440.065 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def heuristica(nodo: str, goal: str, G: nx.Graph, criterio: str = "distancia") -> float:
    """
    h(n) admisible: distancia geodésica recta (Haversine) expresada en
    unidades del criterio. Ninguna ruta real por canales puede ser más
    corta que la recta sobre la esfera, luego h(n) <= h*(n).

    - distancia: recta en nm.
    - tiempo:    recta / velocidad máxima observada (cota inferior del tiempo).
    - costo:     recta * costo mínimo por nm (cota inferior del costo).
    Es además consistente por la desigualdad triangular sobre la esfera:
    h(n) <= c(n,a,n') + h(n').
    """
    a, b = G.nodes[nodo], G.nodes[goal]
    recta = _haversine_nm(a["lat"], a["lon"], b["lat"], b["lon"])
    if criterio == "tiempo":
        return recta / _vel_max(G)
    if criterio == "costo":
        return recta * _costo_min_por_nm(G)
    return recta


# ------------------------------------------------------------------------------
# Búsquedas no informadas
# ------------------------------------------------------------------------------
def bfs(origen: str, destino: str, G: nx.Graph, criterio: str = "distancia") -> ResultadoBusqueda:
    t0 = time.perf_counter()
    err = _validar(G, origen, destino)
    if err:
        return ResultadoBusqueda("bfs", criterio, False, error=err)
    if origen == destino:
        return ResultadoBusqueda("bfs", criterio, True, [origen], tiempo_ms=0.0)
    peso = PESOS.get(criterio, "distancia")

    padres, visitado, orden, arbol = {}, {origen}, [], []
    cola, fmax = deque([origen]), 1
    while cola:
        fmax = max(fmax, len(cola))
        n = cola.popleft()
        orden.append(n)
        _registrar(G, arbol, padres, origen, n, peso)
        if n == destino:
            cam = _reconstruir_camino(padres, origen, destino)
            d, t, c = _totales(G, cam)
            return ResultadoBusqueda("bfs", criterio, True, cam, d, t, c,
                                     len(orden), orden, len(cam) - 1,
                                     (time.perf_counter() - t0) * 1000, fmax, arbol=arbol)
        for v, _d in vecinos_disponibles(G, n):
            if v not in visitado:
                visitado.add(v)
                padres[v] = n
                cola.append(v)
    return ResultadoBusqueda("bfs", criterio, False, error=f"Sin ruta entre '{origen}' y '{destino}'.",
                             nodos_expandidos=len(orden), nodos_visitados=orden,
                             tiempo_ms=(time.perf_counter() - t0) * 1000, frontera_max=fmax, arbol=arbol)


def dfs(origen: str, destino: str, G: nx.Graph, criterio: str = "distancia") -> ResultadoBusqueda:
    t0 = time.perf_counter()
    err = _validar(G, origen, destino)
    if err:
        return ResultadoBusqueda("dfs", criterio, False, error=err)
    if origen == destino:
        return ResultadoBusqueda("dfs", criterio, True, [origen], tiempo_ms=0.0)
    peso = PESOS.get(criterio, "distancia")

    padres, visitado, orden, arbol = {}, set(), [], []
    pila, fmax = [origen], 1
    while pila:
        fmax = max(fmax, len(pila))
        n = pila.pop()
        if n in visitado:
            continue
        visitado.add(n)
        orden.append(n)
        _registrar(G, arbol, padres, origen, n, peso)
        if n == destino:
            cam = _reconstruir_camino(padres, origen, destino)
            d, t, c = _totales(G, cam)
            return ResultadoBusqueda("dfs", criterio, True, cam, d, t, c,
                                     len(orden), orden, len(cam) - 1,
                                     (time.perf_counter() - t0) * 1000, fmax, arbol=arbol)
        for v, _d in vecinos_disponibles(G, n):
            if v not in visitado and v not in padres:
                padres[v] = n
                pila.append(v)
    return ResultadoBusqueda("dfs", criterio, False, error=f"Sin ruta entre '{origen}' y '{destino}'.",
                             nodos_expandidos=len(orden), nodos_visitados=orden,
                             tiempo_ms=(time.perf_counter() - t0) * 1000, frontera_max=fmax, arbol=arbol)


def ucs(origen: str, destino: str, G: nx.Graph, criterio: str = "distancia") -> ResultadoBusqueda:
    """Costo Uniforme: óptimo en el criterio elegido."""
    t0 = time.perf_counter()
    err = _validar(G, origen, destino)
    if err:
        return ResultadoBusqueda("ucs", criterio, False, error=err)
    if origen == destino:
        return ResultadoBusqueda("ucs", criterio, True, [origen], tiempo_ms=0.0)
    peso = PESOS.get(criterio, "distancia")

    padres, mejor_g, orden, arbol = {}, {origen: 0.0}, [], []
    heap, fmax = [(0.0, origen)], 1
    while heap:
        fmax = max(fmax, len(heap))
        g, n = heapq.heappop(heap)
        if g > mejor_g.get(n, math.inf):
            continue
        orden.append(n)
        _registrar(G, arbol, padres, origen, n, peso, g)
        if n == destino:
            cam = _reconstruir_camino(padres, origen, destino)
            d, t, c = _totales(G, cam)
            return ResultadoBusqueda("ucs", criterio, True, cam, d, t, c,
                                     len(orden), orden, len(cam) - 1,
                                     (time.perf_counter() - t0) * 1000, fmax, arbol=arbol)
        for v, dd in vecinos_disponibles(G, n):
            g2 = g + float(dd[peso])
            if g2 < mejor_g.get(v, math.inf):
                mejor_g[v] = g2
                padres[v] = n
                heapq.heappush(heap, (g2, v))
    return ResultadoBusqueda("ucs", criterio, False, error=f"Sin ruta entre '{origen}' y '{destino}'.",
                             nodos_expandidos=len(orden), nodos_visitados=orden,
                             tiempo_ms=(time.perf_counter() - t0) * 1000, frontera_max=fmax, arbol=arbol)


# ------------------------------------------------------------------------------
# Búsquedas informadas
# ------------------------------------------------------------------------------
def greedy(origen: str, destino: str, G: nx.Graph, criterio: str = "distancia") -> ResultadoBusqueda:
    """Voraz (best-first): expande por menor h(n). Rápido, no garantiza optimalidad."""
    t0 = time.perf_counter()
    err = _validar(G, origen, destino)
    if err:
        return ResultadoBusqueda("voraz", criterio, False, error=err)
    if origen == destino:
        return ResultadoBusqueda("voraz", criterio, True, [origen], tiempo_ms=0.0)
    peso = PESOS.get(criterio, "distancia")

    padres, visitado, orden, arbol = {}, set(), [], []
    gac = {origen: 0.0}
    heap, fmax = [(heuristica(origen, destino, G, criterio), origen)], 1
    while heap:
        fmax = max(fmax, len(heap))
        _, n = heapq.heappop(heap)
        if n in visitado:
            continue
        visitado.add(n)
        orden.append(n)
        _registrar(G, arbol, padres, origen, n, peso, gac.get(n, 0.0))
        if n == destino:
            cam = _reconstruir_camino(padres, origen, destino)
            d, t, c = _totales(G, cam)
            return ResultadoBusqueda("voraz", criterio, True, cam, d, t, c,
                                     len(orden), orden, len(cam) - 1,
                                     (time.perf_counter() - t0) * 1000, fmax, arbol=arbol)
        for v, dd in vecinos_disponibles(G, n):
            if v not in visitado and v not in padres:
                padres[v] = n
                gac[v] = gac[n] + float(dd[peso])
                heapq.heappush(heap, (heuristica(v, destino, G, criterio), v))
    return ResultadoBusqueda("voraz", criterio, False, error=f"Sin ruta entre '{origen}' y '{destino}'.",
                             nodos_expandidos=len(orden), nodos_visitados=orden,
                             tiempo_ms=(time.perf_counter() - t0) * 1000, frontera_max=fmax, arbol=arbol)


def astar(origen: str, destino: str, G: nx.Graph, criterio: str = "distancia") -> ResultadoBusqueda:
    """A*: óptimo con heurística admisible. Expande por f(n) = g(n) + h(n)."""
    t0 = time.perf_counter()
    err = _validar(G, origen, destino)
    if err:
        return ResultadoBusqueda("astar", criterio, False, error=err)
    if origen == destino:
        return ResultadoBusqueda("astar", criterio, True, [origen], tiempo_ms=0.0)
    peso = PESOS.get(criterio, "distancia")

    padres, mejor_g, orden, arbol = {}, {origen: 0.0}, [], []
    heap = [(heuristica(origen, destino, G, criterio), 0.0, origen)]
    fmax = 1
    while heap:
        fmax = max(fmax, len(heap))
        _, g, n = heapq.heappop(heap)
        if g > mejor_g.get(n, math.inf):
            continue
        orden.append(n)
        _registrar(G, arbol, padres, origen, n, peso, g)
        if n == destino:
            cam = _reconstruir_camino(padres, origen, destino)
            d, t, c = _totales(G, cam)
            return ResultadoBusqueda("astar", criterio, True, cam, d, t, c,
                                     len(orden), orden, len(cam) - 1,
                                     (time.perf_counter() - t0) * 1000, fmax, arbol=arbol)
        for v, dd in vecinos_disponibles(G, n):
            g2 = g + float(dd[peso])
            if g2 < mejor_g.get(v, math.inf):
                mejor_g[v] = g2
                padres[v] = n
                heapq.heappush(heap, (g2 + heuristica(v, destino, G, criterio), g2, v))
    return ResultadoBusqueda("astar", criterio, False, error=f"Sin ruta entre '{origen}' y '{destino}'.",
                             nodos_expandidos=len(orden), nodos_visitados=orden,
                             tiempo_ms=(time.perf_counter() - t0) * 1000, frontera_max=fmax, arbol=arbol)


FUNCIONES: Dict[str, Callable] = {
    "bfs": bfs, "dfs": dfs, "ucs": ucs, "voraz": greedy, "astar": astar,
}


def buscar(algoritmo: str, origen: str, destino: str, G: nx.Graph,
            criterio: str = "distancia") -> ResultadoBusqueda:
    """Despachador único usado por el agente y por la API web."""
    algo = (algoritmo or "").strip().lower()
    if algo not in FUNCIONES:
        return ResultadoBusqueda(algo, criterio, False,
                                 error=f"Algoritmo '{algoritmo}' no válido. Use: {ALGORITMOS}.")
    if criterio not in PESOS:
        return ResultadoBusqueda(algo, criterio, False,
                                 error=f"Criterio '{criterio}' no válido. Use: {list(PESOS)}.")
    return FUNCIONES[algo](origen, destino, G, criterio)


def comparar(origen: str, destino: str, G: nx.Graph,
             criterio: str = "distancia") -> List[ResultadoBusqueda]:
    """Ejecuta los 5 algoritmos sobre el mismo escenario para la tabla comparativa."""
    return [buscar(a, origen, destino, G, criterio) for a in ALGORITMOS]


def verificar_admisibilidad(G: nx.Graph, criterio: str = "distancia",
                            pares: Optional[List[tuple]] = None) -> dict:
    """
    Comprueba h(n) <= h*(n) en una muestra de pares (origen, destino),
    usando UCS como costo real óptimo h*. Retorna nº de violaciones.
    """
    nodos = list(G.nodes)
    if pares is None:
        pares = [(nodos[i], nodos[-1 - i]) for i in range(0, min(20, len(nodos) // 2))]
    violaciones, revisados = [], 0
    # TOL: edges.csv redondea a 2 decimales; se admite épsilon de 0.05
    # por error acumulado de redondeo (no es sobreestimación real).
    for o, d in pares:
        if o == d:
            continue
        real = ucs(o, d, G, criterio)
        if not real.exito:
            continue
        peso = PESOS[criterio]
        h0 = heuristica(o, d, G, criterio)
        h_real = {"distancia": real.distancia_total,
                  "tiempo": real.tiempo_total,
                  "costo": real.costo_total}[criterio]
        revisados += 1
        if h0 > h_real + 0.05:
            violaciones.append({"origen": o, "destino": d, "h": h0, "h_real": h_real})
    return {"criterio": criterio, "pares_revisados": revisados,
            "violaciones": violaciones, "es_admisible": len(violaciones) == 0}

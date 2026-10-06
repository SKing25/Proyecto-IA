"""
App web del Corte 2 (FastAPI).

Separación de responsabilidades:
  - grafo.py / agente.py / busqueda.py : lógica del agente y del dominio.
  - app/main.py                        : capa web (carga el grafo una vez y expone la API).
  - app/templates + app/static         : presentación (Leaflet, sin lógica de búsqueda).
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel, Field

from grafo import construir_grafo
from busqueda import ALGORITMOS, DESCRIPCION_ALGORITMOS, PESOS, buscar, comparar

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Planificador Marítimo Inteligente (Corte 2)",
              description="Agente + BFS/DFS/UCS/Voraz/A* sobre la red G=(V,E).")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# El grafo se carga una sola vez al arrancar (no por petición).
G = construir_grafo()


class PeticionRuta(BaseModel):
    origen: str = Field(..., min_length=1)
    destino: str = Field(..., min_length=1)
    algoritmo: str = "astar"
    criterio: str = "distancia"


class PeticionComparar(BaseModel):
    origen: str = Field(..., min_length=1)
    destino: str = Field(..., min_length=1)
    criterio: str = "distancia"


def _coords(nodo_id: str) -> dict:
    n = G.nodes[nodo_id]
    return {"id": nodo_id, "nombre": n.get("nombre"), "tipo": n.get("tipo"),
            "lat": float(n.get("lat")), "lon": float(n.get("lon")),
            "pais": n.get("pais")}


def _enriquecer(resultado) -> dict:
    """Añade coordenadas del camino y del orden de expansión (grafo de decisiones)."""
    d = resultado.to_dict()
    d["camino_coords"] = [_coords(x) for x in resultado.camino] if resultado.exito else []
    d["expansion"] = [{"orden": i + 1, **_coords(x)}
                      for i, x in enumerate(resultado.nodos_visitados)]
    return d


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/api/algoritmos")
def lista_algoritmos():
    return {"algoritmos": [{"id": a, "descripcion": DESCRIPCION_ALGORITMOS[a]}
                           for a in ALGORITMOS],
            "criterios": list(PESOS.keys())}


@app.get("/api/nodos")
def lista_nodos():
    return {"nodos": [_coords(n) for n in G.nodes],
            "total": G.number_of_nodes()}


@app.get("/api/red")
def red_completa():
    """Toda la red para dibujar el mapa base una sola vez."""
    nodos = [_coords(n) for n in G.nodes]
    aristas = [{"origen": u, "destino": v,
                "nivel_congestion": d.get("nivel_congestion"),
                "distancia": float(d.get("distancia", 0)),
                "disponibilidad": bool(d.get("disponibilidad", True))}
               for u, v, d in G.edges(data=True)]
    return {"nodos": nodos, "aristas": aristas,
            "total_nodos": G.number_of_nodes(), "total_aristas": G.number_of_edges()}


@app.post("/api/ruta")
def calcular_ruta(p: PeticionRuta):
    r = buscar(p.algoritmo, p.origen.strip(), p.destino.strip(), G, p.criterio)
    if not r.exito and r.error and "no válido" in r.error:
        raise HTTPException(status_code=422, detail=r.error)
    return _enriquecer(r)


@app.post("/api/comparar")
def comparar_algoritmos(p: PeticionComparar):
    if p.criterio not in PESOS:
        raise HTTPException(status_code=422, detail=f"Criterio no válido. Use: {list(PESOS)}.")
    return {"origen": p.origen, "destino": p.destino, "criterio": p.criterio,
            "resultados": [_enriquecer(r) for r in comparar(p.origen, p.destino, G, p.criterio)]}


if __name__ == "__main__":
    # Permite:  .venv/bin/python -m app.main   (desde la raíz del proyecto)
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

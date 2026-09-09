"""
================================================================================
PROYECTO INTEGRADOR - INTELIGENCIA ARTIFICIAL (SIST5036)
VISUALIZADOR DE LA RED MARÍTIMA SOBRE CARTOGRAFÍA REAL
================================================================================
Genera:
  1. data/mapa_real.png : Gráfico de alta resolución con fondo cartográfico real.
  2. data/mapa_red.html : Mapa web interactivo (Leaflet/OpenStreetMap).
"""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

# Rutas
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
NODES_PATH: Path = DATA_DIR / "nodes.csv"
EDGES_PATH: Path = DATA_DIR / "edges.csv"
BASEMAP_PATH: Path = DATA_DIR / "basemap_ocean.png"
OUTPUT_PNG: Path = DATA_DIR / "mapa_real.png"
OUTPUT_HTML: Path = DATA_DIR / "mapa_red.html"


def generar_mapa_estatico(df_nodos: pd.DataFrame, df_aristas: pd.DataFrame) -> None:
    """Genera la imagen PNG con el grafo sobre el mapa cartográfico real."""
    print("[1/2] Generando imagen PNG con cartografía real...")
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

    fig, ax = plt.subplots(figsize=(14, 10), dpi=250)
    pos = nx.get_node_attributes(G, "pos")

    # Proyección del mapa base satelital / batimétrico
    if BASEMAP_PATH.exists():
        img = plt.imread(BASEMAP_PATH)
        ax.imshow(img, extent=[6.0, 16.0, 53.0, 60.5], aspect="auto", zorder=0)

    # Nodos según tipo
    puertos = [n for n, d in G.nodes(data=True) if d.get("tipo") == "Puerto"]
    waypoints = [n for n, d in G.nodes(data=True) if d.get("tipo") == "Waypoint"]

    # Colores por congestión
    mapa_colores = {"Baja": "#27AE60", "Media": "#F39C12", "Alta": "#E74C3C"}
    edge_colors = [mapa_colores.get(G.edges[e]["congestion"], "#95A5A6") for e in G.edges()]

    # Aristas
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors, width=2.8, alpha=0.9)

    # Puertos (Cuadrados Azul Marino)
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        nodelist=puertos,
        node_color="#0B3C5D",
        node_size=360,
        node_shape="s",
        edgecolors="white",
        linewidths=1.5,
        label="Puerto Comercial (Azul Marino)"
    )

    # Waypoints (Círculos Morados)
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        nodelist=waypoints,
        node_color="#8E44AD",
        node_size=260,
        node_shape="o",
        edgecolors="white",
        linewidths=1.2,
        label="Waypoint / Canal TSS (Morado)"
    )

    # Etiquetas con cajas translúcidas y ajuste de posición
    labels = {n: G.nodes[n]["nombre"] for n in G.nodes()}
    for n, (x, y) in pos.items():
        dy = 0.12
        dx = 0.0
        if n in ["DK_CPH", "SE_HEL", "WP_ORESUND_S"]:
            dy = -0.16
        elif n in ["SE_MAL"]:
            dx = 0.35
            dy = -0.05
        ax.text(
            x + dx, y + dy, labels[n],
            fontsize=6.8, fontweight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.82, edgecolor="none")
        )

    ax.set_xlim(6.0, 16.0)
    ax.set_ylim(53.0, 60.5)
    ax.set_title(
        "Red de Movilidad Marítima G = (V, E) sobre Cartografía Real\n"
        "Puertos (Azul Marino) vs Waypoints (Morado) | Rutas: Congestión AIS",
        fontsize=12, fontweight="bold", pad=14
    )
    ax.set_xlabel("Longitud (°E)", fontsize=10, fontweight="bold")
    ax.set_ylabel("Latitud (°N)", fontsize=10, fontweight="bold")
    ax.legend(loc="lower left", framealpha=0.92, fontsize=8.5)

    plt.tight_layout()
    plt.savefig(OUTPUT_PNG, bbox_inches="tight")
    plt.close()
    print(f"      -> Imagen guardada en: {OUTPUT_PNG}")


def generar_mapa_web(df_nodos: pd.DataFrame, df_aristas: pd.DataFrame) -> None:
    """Genera el mapa web interactivo con Leaflet y OpenStreetMap."""
    print("[2/2] Generando mapa web interactivo en HTML...")
    nodes_dict = {r["id"]: r.to_dict() for _, r in df_nodos.iterrows()}
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Mapa Real Interactivo - Red Marítima G=(V,E)</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        #map {{ height: 100vh; width: 100%; }}
        .legend {{
            background: white; padding: 12px 16px; border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); font-size: 13px; line-height: 1.6;
        }}
        .legend h4 {{ margin: 0 0 8px 0; font-size: 14px; font-weight: bold; }}
        .legend-item {{ display: flex; align-items: center; margin-bottom: 4px; }}
        .legend-color {{ width: 18px; height: 18px; margin-right: 8px; border-radius: 3px; display: inline-block; }}
    </style>
</head>
<body>
<div id="map"></div>
<script>
    var map = L.map('map').setView([56.5, 11.2], 6);
    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 18
    }}).addTo(map);

    var nodes = {json.dumps(nodes_dict)};
    var edges = {df_aristas.to_json(orient='records')};
    var colors = {{ 'Baja': '#27AE60', 'Media': '#F39C12', 'Alta': '#E74C3C' }};

    edges.forEach(function(e) {{
        var u = nodes[e.origen];
        var v = nodes[e.destino];
        if (u && v) {{
            var color = colors[e.nivel_congestion] || '#95A5A6';
            var line = L.polyline([[u.lat, u.lon], [v.lat, v.lon]], {{
                color: color, weight: 4, opacity: 0.85
            }}).addTo(map);

            line.bindPopup(
                '<b>Ruta: ' + u.nombre + ' &harr; ' + v.nombre + '</b><br>' +
                '<b>Distancia:</b> ' + e.distancia + ' nm (' + e.distancia_km + ' km)<br>' +
                '<b>Tiempo estimado:</b> ' + e.tiempo_estimado + ' h<br>' +
                '<b>Velocidad promedio:</b> ' + e.velocidad_promedio + ' kn<br>' +
                '<b>Nivel de congestión:</b> <span style="color:' + color + ';font-weight:bold;">' + e.nivel_congestion + '</span><br>' +
                '<b>Costo estimado:</b> $' + e.costo + ' USD<br>' +
                '<b>Incidentes:</b> ' + e.num_incidentes + '<br>' +
                '<b>Disponibilidad:</b> ' + (e.disponibilidad ? 'Disponible' : 'Cerrada')
            );
        }}
    }});

    for (var id in nodes) {{
        var n = nodes[id];
        var isPort = (n.tipo === 'Puerto');
        var marker = L.circleMarker([n.lat, n.lon], {{
            radius: isPort ? 8 : 6,
            fillColor: isPort ? '#1B4F72' : '#8E44AD',
            color: '#FFFFFF', weight: 2, opacity: 1, fillOpacity: 0.9
        }}).addTo(map);

        marker.bindPopup(
            '<b>' + n.nombre + ' (' + n.id + ')</b><br>' +
            '<b>Tipo:</b> ' + n.tipo + '<br>' +
            '<b>País:</b> ' + n.pais + '<br>' +
            '<b>Coordenadas:</b> ' + n.lat + ', ' + n.lon
        );
        marker.bindTooltip(n.nombre, {{ permanent: false, direction: 'top' }});
    }}

    var legend = L.control({{position: 'bottomleft'}});
    legend.onAdd = function() {{
        var div = L.DomUtil.create('div', 'legend');
        div.innerHTML = '<h4>Red de Movilidad Marítima</h4>' +
            '<div class="legend-item"><span class="legend-color" style="background:#1B4F72;"></span>Puerto Comercial</div>' +
            '<div class="legend-item"><span class="legend-color" style="background:#8E44AD;border-radius:50%;"></span>Waypoint / Canal</div>' +
            '<hr style="margin:8px 0;border:0;border-top:1px solid #ddd;">' +
            '<div class="legend-item"><span class="legend-color" style="background:#27AE60;height:4px;"></span>Congestión Baja</div>' +
            '<div class="legend-item"><span class="legend-color" style="background:#F39C12;height:4px;"></span>Congestión Media</div>' +
            '<div class="legend-item"><span class="legend-color" style="background:#E74C3C;height:4px;"></span>Congestión Alta</div>';
        return div;
    }};
    legend.addTo(map);
</script>
</body>
</html>"""
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"      -> Mapa web interactivo guardado en: {OUTPUT_HTML}")


if __name__ == "__main__":
    if not NODES_PATH.exists() or not EDGES_PATH.exists():
        print("Error: No se encontraron nodes.csv o edges.csv en data/. Ejecuta primero dataset.py.")
        exit(1)

    df_n = pd.read_csv(NODES_PATH)
    df_e = pd.read_csv(EDGES_PATH)

    generar_mapa_estatico(df_n, df_e)
    generar_mapa_web(df_n, df_e)
    print("\nVisualización con mapa real completada exitosamente.")

# Sistema Inteligente para la Planificación de Rutas y Análisis de Movilidad Marítima

**Curso:** Inteligencia Artificial (Código: SIST5036)  
**Institución:** Universidad Sergio Arboleda — Escuela de Ciencias Exactas e Ingeniería  
**Programa:** Ciencias de la Computación e Inteligencia Artificial (Semestre VI)  
**Docente:** Joaquín F. Sánchez  

---

# Descripción del Proyecto
El proyecto consiste en modelar una red de movilidad marítima en el corredor del Mar del Norte y Mar Báltico (estrechos de Dinamarca), calculando condiciones de navegación y congestión a partir de datos masivos de telemetría marítima (AIS).

En este repositorio se entrega el **Backend de Datos** para el **Corte 1**:
1. Procesamiento y limpieza del dataset masivo AIS (`aisdk-2025-02-27.csv`, 17.1M registros).
2. Modelado de los nodos de la red (`nodes.csv`): 13 puertos y 11 waypoints estratégicos.
3. Cálculo de los **7 atributos obligatorios** de las conexiones (`edges.csv`): distancia, tiempo estimado, velocidad promedio, nivel de congestión, costo operativo, disponibilidad y número de incidentes.
4. Generación del diagrama georreferenciado de la red (`grafo_red.png`) diferenciando puertos y waypoints.
5. Documento técnico de entrega para el Integrante 1 (`INTEGRANTE_1.md`) con explicaciones de funcionamiento e integración para el Integrante 2.

---

# Estructura de Archivos

```text
Proyecto-IA/
├── .gitignore            # Excluye datos masivos y entornos virtuales
├── README.md             # Vista general del repositorio y ejecución rápida
├── requirements.txt      # Dependencias del proyecto (pandas, numpy, networkx, matplotlib)
├── dataset.py            # SCRIPT ÚNICO: procesa datos y exporta el grafo
├── data/                 # CARPETA DE SALIDA DEL GRAFO
│   ├── nodes.csv         # 24 puertos y waypoints con coordenadas
│   ├── edges.csv         # 26 conexiones con los 7 atributos obligatorios
│   └── grafo_red.png     # Imagen georreferenciada de la red (Puertos vs Waypoints)
└── aisdk-2025-02-27.csv  # Dataset crudo descargado (~3.1 GB, 17.1M registros AIS)
```

---

# Ejecución Rápida

### 1. Activar el entorno virtual e instalar dependencias
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Ejecutar el Procesamiento y Generación de la Red
```bash
python dataset.py
```
Este script realiza automáticamente:
- Ingesta por bloques con tipado estricto.
- Agregación espacial vectorizada $O(N) + O(E)$.
- Exportación de `nodes.csv` y `edges.csv` (con los 7 atributos obligatorios).
- Generación de la imagen visual `grafo_red.png`.

---

# Documentación Detallada de la Primera Etapa

## 1. Resumen Ejecutivo

Se construyó el **Backend de Datos** y la **Topología del Entorno**, transformando un dataset masivo de telemetría marítima cruda (AIS) (https://hub.marinecadastre.gov/pages/vesseltraffic) en una estructura de grafo ponderado $G = (V, E)$ lista para ser consumida por algoritmos de Inteligencia Artificial.

### Objetivos Completados:
1. **Ingesta y Limpieza de Datos Masivos:** Procesamiento eficiente del archivo `aisdk-2025-02-27.csv` (~3.1 GB, más de 17.1 millones de pings AIS de la *Danish Maritime Authority*).
2. **Definición Topológica del Espacio de Estados:** Georreferenciación de **24 nodos estratégicos** en el corredor marítimo Mar del Norte — Skagerrak — Kattegat — Mar Báltico (13 Puertos comerciales y 11 Waypoints o pasos marítimos obligatorios).
3. **Cálculo de los 7 Atributos Obligatorios por Conexión:** Determinación matemática y empírica de 26 aristas de navegación con:
   - `distancia` (en millas náuticas, $nm$)
   - `tiempo_estimado` (en horas de navegación, $h$)
   - `velocidad_promedio` (en nudos observados, $kn$)
   - `nivel_congestion` (*Baja*, *Media*, *Alta* a partir de la densidad de buques)
   - `costo` (costo operativo en USD según combustible marino y distancia)
   - `disponibilidad` (estado booleano de operatividad de la vía)
   - `num_incidentes` (recuento de emergencias o avisos de seguridad en la zona)
4. **Exportación de Datos Normalizados:** Generación limpia de `data/nodes.csv` y `data/edges.csv`.
5. **Visualización Georreferenciada:** Renderizado del mapa de navegación `data/grafo_red.png`, diferenciando visualmente Puertos (Azul Oscuro `#1B4F72`) de Waypoints (Morado `#8E44AD`) y coloreando las rutas por congestión.

---

## 2. ¿Cómo Funciona? (Arquitectura y Lógica Interna de `dataset.py`)

Todo el flujo de procesamiento está centralizado y optimizado en el script `dataset.py`:

```
┌───────────────────────────┐
│ aisdk-2025-02-27.csv      │ (~3.1 GB / 17.1M filas)
└─────────────┬─────────────┘
              │ 1. Ingesta por Chunks (100k filas, dtype estricto)
              ▼
┌───────────────────────────┐
│ Filtrado Espacial y SOG   │ Bounding Box: Lat [53.5, 60.5], Lon [6.0, 15.5]
└─────────────┬─────────────┘ Velocidad SOG ∈ [0.5, 30.0] nudos
              │ 2. Grilla Espacial Vectorizada (0.5° x 0.5°) -> O(N)
              ▼
┌───────────────────────────┐
│ Mapeo Hash O(1)           │ Tráfico y velocidad agregada por celda
└─────────────┬─────────────┘
              │ 3. Cálculo de Aristas y 7 Atributos
              ▼
┌───────────────────────────┐
│ - data/nodes.csv          │ (24 nodos georreferenciados)
│ - data/edges.csv          │ (26 aristas con 7 atributos)
│ - data/grafo_red.png      │ (Visualización georreferenciada)
└───────────────────────────┘
```

### 2.1. Ingesta Eficiente por Bloques (Chunking)
Procesar un archivo de 3.1 GB en memoria RAM tradicional provocaría un error de desbordamiento (*Out Of Memory*). Se resolvió implementando:
- **`chunksize = 100,000`:** Lectura secuencial en bloques de 100 mil registros con `pandas`.
- **Tipado Estricto (`dtype={"MMSI": str}`):** Evita advertencias de tipos mixtos y reduce el consumo de memoria.
- **Filtro de Interés:** Solo se conservan pings dentro del corredor geográfico relevante (Dinamarca, accesos al Báltico y Mar del Norte: Latitud $53.5^\circ$ a $60.5^\circ$, Longitud $6.0^\circ$ a $15.5^\circ$).

### 2.2. Distancia Geodésica de Haversine
Dado que la superficie terrestre es esférica, la distancia euclidiana cartesiana introduce distorsiones inaceptables en latitudes altas ($\sim 55^\circ - 58^\circ$ N). Se implementó la **Fórmula de Haversine**:

$$\Delta \phi = \phi_2 - \phi_1, \quad \Delta \lambda = \lambda_2 - \lambda_1$$
$$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)$$
$$c = 2 \cdot \arctan2\left(\sqrt{a}, \sqrt{1-a}\right)$$
$$d = R \cdot c$$

- Con radio terrestre $R = 6,371\text{ km}$ ($3,440.065\text{ millas náuticas}$).
- Esta distancia se usa para calcular:
  $$\text{tiempo\_estimado} = \frac{\text{distancia (nm)}}{\text{velocidad\_promedio (knots)}}$$

### 2.3. Optimización con Grilla Espacial ($O(N) + O(E)$ vs $O(E \times N)$)
- **Problema Inicial:** Cruzar cada una de las 26 aristas contra los 300,000+ pings filtrados requería un doble ciclo que tardaba entre 10 y 15 segundos por ejecución ($O(E \times N)$).
- **Solución Implementada:** Se discretizan las coordenadas en una **rejilla espacial** de celdas de $0.5^\circ \times 0.5^\circ$. Con `pandas.groupby()`, se indexan los recuentos de buques y la velocidad promedio en una tabla hash en un solo pase lineal $O(N)$. Luego, cada arista consulta su celda en tiempo constante $O(1)$.
- **Resultado:** La ejecución total del script toma **menos de 2 segundos**.

### 2.4. Generación de los 7 Atributos Obligatorios
| Atributo | Tipo | Fuente / Método de Cálculo |
| :--- | :--- | :--- |
| `distancia` | `float` ($nm$) | Distancia geodésica exacta calculada con Haversine. |
| `tiempo_estimado` | `float` ($h$) | $\text{distancia} / \text{velocidad\_promedio}$. |
| `velocidad_promedio`| `float` ($kn$) | Media del campo `SOG` (*Speed Over Ground*) de los buques en esa zona. |
| `nivel_congestion` | `str` | Clasificación empírica basada en tráfico AIS: *Baja* (< 20 buques), *Media* (20–40), *Alta* (> 40). |
| `costo` | `float` (USD) | Costo operativo: $\$10/\text{nm} \times \text{distancia} + \text{penalización por congestión}$. |
| `disponibilidad` | `bool` | Estado operativo (`True` por defecto; permite simular bloqueos de canales). |
| `num_incidentes` | `int` | Recuento de alertas de navegación / incidentes históricos en el área. |

### 2.5. Graficación Georreferenciada (`grafo_red.png`)
- **Puertos:** Marcados como cuadrados en **Azul Oscuro** (`#1B4F72`).
- **Waypoints:** Marcados como círculos en **Morado** (`#8E44AD`).
- **Aristas:** Trazadas con código de color según congestión:
  - 🟢 **Verde:** Congestión Baja.
  - 🟠 **Naranja:** Congestión Media.
  - 🔴 **Rojo:** Congestión Alta.

---

## 3. Guia de integracion para la siguiente parte

En la siguiente etapa del proyecto se tiene la responsabilidad de desarrollar la **Lógica del Agente Inteligente** y los **Algoritmos de Búsqueda** (Búsquedas no informadas: BFS, DFS, UCS; e informadas: A*, Greedy Best-First).

El trabajo ya hecho le entrega una base de datos ya estructurada, limpia y matemáticamente sólida para que no tenga que lidiar con telemetría cruda ni con cálculos de coordenadas.

### 3.1. Qué Archivos Recibe la siguiente etapa
1. **`data/nodes.csv` (Espacio de Estados $S$):**
   - Contiene `id`, `nombre`, `tipo` (`puerto`/`waypoint`), `lat`, `lon` y `pais`.
   - **Utilidad:** Le da al agente las coordenadas geográficas de cada estado para calcular la **función heurística $h(n)$**.
2. **`data/edges.csv` (Modelo de Transición $T(s, a, s')$ y Función de Costo $c(s, a, s')$):**
   - Contiene el origen, destino y los **7 atributos**.
   - **Utilidad:** Define las acciones legales del agente en cada nodo y los pesos para evaluar las funciones de costo $g(n)$.

---

### 3.2. Fundamento Matemático para la Búsqueda A* (Heurística Admisible)
Para que el algoritmo **A\*** de la siguiente etapa sea **óptimo y admisible**, la heurística $h(n)$ no puede sobreestimar el costo real al objetivo:

$$h(n) \le h^*(n)$$

Ya se calculó las distancias de las aristas sobre la superficie terrestre real mediante Haversine. La distancia en línea recta geodésica de Haversine entre el nodo actual $n$ y el nodo objetivo $goal$ es el camino más corto posible entre ambos puntos sobre la esfera:
$$h(n) = \text{haversine}(n.\text{coord}, goal.\text{coord})$$

Como cualquier ruta de navegación marítima está obligada a rodear cabos, islas o seguir canales de navegación (sumando aristas intermedias), se cumple estrictamente:
$$h(n) \le h^*(n)$$

Adicionalmente, por la **desigualdad triangular sobre la esfera**, la heurística es **consistente (monótona)**:
$$h(n) \le c(n, a, n') + h(n')$$
Esto le garantiza a la siguiente etapa que **A\* nunca reabrirá nodos cerrados**, ejecutándose con máxima eficiencia.

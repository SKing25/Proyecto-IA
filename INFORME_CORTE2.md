# Informe Técnico — Corte 2: Algoritmos de Búsqueda y Planificador Inteligente

**Universidad Sergio Arboleda**  
**Escuela de Ciencias Exactas e Ingeniería**  
**Programa:** Ciencias de la Computación e Inteligencia Artificial (Semestre VI)  
**Curso:** Inteligencia Artificial (Código: SIST5036)  
**Docente:** Joaquín F. Sánchez  
**Proyecto Integrador:** Sistema inteligente para la planificación de rutas y análisis de movilidad marítima  

---

## 1. Formulación del Problema y Representación del Entorno

### 1.1. Contexto del Problema
El transporte marítimo en el corredor del Mar del Norte y Mar Báltico (estrechos de Dinamarca: Øresund, Gran Belt y Pequeño Belt) es uno de los pasos de navegación más congestionados y con mayores restricciones batimétricas del mundo. La selección de rutas no puede depender únicamente de la distancia euclidiana o en línea recta, ya que los buques deben ceñirse a canales navegables de calado seguro, evitar el encallamiento en islas o penínsulas (Jutlandia, Selandia, Fionia, etc.) y considerar costos operativos, velocidades reales y congestión del tráfico AIS.

### 1.2. Topología de la Red $G = (V, E)$
La red marítima ha sido modelada como un grafo conexo ponderado no dirigido:
* **Nodos ($|V| = 85$):** 55 Puertos comerciales reales (Copenhague, Rostock, Oslo, Aarhus, Esbjerg, Travemünde, Gotemburgo, etc.) y 30 Waypoints estratégicos de canal (Drogden, Falsterbo, Fehmarnbelt, Skagen, Kadetrinne, etc.).
* **Conexiones ($|E| = 176$):** Cada arista cuenta con los 7 atributos obligatorios calculados a partir de 17.1M de registros AIS:
  1. `distancia` (en millas náuticas, $nm$).
  2. `tiempo_estimado` (en horas de navegación, $h$).
  3. `velocidad_promedio` (en nudos observados, $kn$).
  4. `nivel_congestion` (*Baja*, *Media*, *Alta* según densidad de buques).
  5. `costo` (costo operativo en USD).
  6. `disponibilidad` (booleano: canal operativo vs. bloqueado/cerrado).
  7. `num_incidentes` (registro de emergencias náuticas).

### 1.3. Cero Cruces de Tierra (Navegabilidad 100% Real)
Para garantizar el realismo geográfico se implementó una auditoría basada en una máscara raster de tierra (`data/landmask.npz`, resolución 0.02° a partir de Natural Earth 10m):
* Se auditaron todas las aristas con `validar_tierra.py`, pasando de 85 cruces iniciales a **0 cruces sobre tierra firme**.
* Se incorporaron waypoints en pasos obligados (Drogden, Falsterbo, Langeland Sur, etc.) para rodear las masas continentales.

---

## 2. Diseño del Agente Inteligente (Modelo PEAS)

El agente marítimo ha evolucionado de un modelo reactivo simple (Corte 1) a un **Agente Basado en Objetivos con Planificación Deliberativa** (Corte 2), implementado en [`agente.py`](file:///home/santiago/Documentos/Codigos/Proyecto-IA/agente.py).

### Tabla PEAS

| Componente | Descripción en el Sistema Marítimo |
| :--- | :--- |
| **Performance (Rendimiento)** | Minimizar la función de costo según el criterio del armador: menor distancia acumulada ($nm$), menor tiempo de travesía ($h$) o menor costo de combustible ($USD$). Penalización infinita por encallamiento o uso de canales con `disponibilidad = False`. |
| **Environment (Entorno)** | Red marítima $G=(V,E)$ en los estrechos daneses y Báltico. Accesible/conocido mediante la base de datos de navegación, determinista respecto a costos fijos y dinámico ante cierres de canales por contingencia. |
| **Actuators (Actuadores)** | Maniobras de navegación (`ejecutar_accion(destino)`) que trasladan la nave entre nodos adyacentes disponibles y actualizan la bitácora e indicadores de travesía. |
| **Sensors (Sensores)** | Receptores AIS/GPS (`percibir()`) que reportan el nodo actual, coordenadas geográficas, país y el conjunto de acciones legales y conexiones disponibles en la posición actual. |

### Ciclo de Deliberación y Ejecución
1. **Percepción:** El agente consulta su ubicación actual en la red y las condiciones de su entorno.
2. **Planificación (Deliberación):** Mediante `planificar_ruta(destino, algoritmo, criterio)` ejecuta un algoritmo de búsqueda en grafos para hallar el camino óptimo antes de zarpar.
3. **Ejecución:** Con `ejecutar_plan(destino)` recorre paso a paso el itinerario calculado, validando la disponibilidad de cada tramo y acumulando las medidas de desempeño.

---

## 3. Algoritmos de Búsqueda Implementados

Se implementaron cinco algoritmos de búsqueda sobre grafos en [`busqueda.py`](file:///home/santiago/Documentos/Codigos/Proyecto-IA/busqueda.py) con control estricto de nodos visitados (`closed set`) para evitar ciclos:

### 3.1. Búsqueda en Anchura (BFS — Breadth-First Search)
* **Estrategia:** Explora por niveles sucesivos usando una cola FIFO.
* **Propiedades:** No informado ($h=0$). Es **óptimo únicamente en número de saltos (aristas)**, pero ignora los costos reales de distancia, tiempo y dinero.

### 3.2. Búsqueda en Profundidad (DFS — Depth-First Search)
* **Estrategia:** Explora la rama más profunda antes de retroceder, mediante una pila LIFO.
* **Propiedades:** No informado ($h=0$). No es óptimo y suele encontrar caminos excesivamente largos y costosos en grafos con alta conectividad.

### 3.3. Búsqueda de Costo Uniforme (UCS / Dijkstra)
* **Estrategia:** Expande el nodo con menor costo acumulado $g(n)$ desde la raíz usando una cola de prioridad `heapq`.
* **Propiedades:** No informado ($h=0$). Es **óptimo para cualquier métrica de costo no negativa** ($g \ge 0$), pero explora uniformemente en todas direcciones sin orientación espacial hacia la meta.

### 3.4. Búsqueda Voraz Primero el Mejor (Greedy Best-First Search)
* **Estrategia:** Expande el nodo con menor valor heurístico $h(n)$ (más cercano en línea recta a la meta).
* **Propiedades:** Informado. Es muy rápido y expande muy pocos nodos, pero **no es óptimo** ya que ignora el costo acumulado $g(n)$ y puede tomar atajos que resultan costosos.

### 3.5. Búsqueda A* (A-Star)
* **Estrategia:** Combina el costo real acumulado y la estimación heurística mediante la función de evaluación:
  $$f(n) = g(n) + h(n)$$
* **Propiedades:** Informado. Garantiza **optimalidad y completitud** si la heurística $h(n)$ es admisible y consistente, expandiendo un número significativamente menor de nodos que UCS.

---

## 4. Función Heurística: Formulación, Admisibilidad y Consistencia

### 4.1. Definición Matemática
La heurística base se fundamenta en la distancia geodésica del gran círculo mediante la fórmula de Haversine:
$$d_{\text{hav}}(\phi_1, \lambda_1, \phi_2, \lambda_2) = 2R \arcsin \left( \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)} \right)$$
donde $R = 3440.065 \, nm$ (radio medio terrestre en millas náuticas).

Para dar soporte a los tres criterios de optimización, la función $h(n)$ se formula como:
1. **Criterio Distancia:**  
   $$h_{\text{dist}}(n) = d_{\text{hav}}(n, \text{meta})$$
2. **Criterio Tiempo:**  
   $$h_{\text{tiempo}}(n) = \frac{d_{\text{hav}}(n, \text{meta})}{v_{\max}}$$  
   donde $v_{\max} = 22.0 \, kn$ es una cota superior estricta de la velocidad máxima registrada en la red.
3. **Criterio Costo:**  
   $$h_{\text{costo}}(n) = d_{\text{hav}}(n, \text{meta}) \times c_{\min}$$  
   donde $c_{\min} = 8.5 \, \text{USD}/nm$ es una cota inferior estricta del costo operativo mínimo por milla.

### 4.2. Demostración de Admisibilidad: $h(n) \le h^*(n)$
* **Distancia:** En la superficie esférica terrestre, la geodésica en línea recta representa la menor distancia posible entre dos puntos. Como la navegación real se realiza a través de estrechos, canales y rodeos de masas continentales, la distancia real $h^*(n)$ siempre satisface $h^*(n) \ge d_{\text{hav}}(n, \text{meta})$. Por tanto, $h_{\text{dist}}(n)$ nunca sobrestima el costo real.
* **Tiempo:** Dado que $t^* = \sum \frac{d_i}{v_i} \ge \frac{\sum d_i}{v_{\max}} \ge \frac{d_{\text{hav}}}{v_{\max}} = h_{\text{tiempo}}(n)$, la heurística de tiempo es admisible.
* **Costo:** Análogamente, ningún tramo tiene un costo inferior a $c_{\min}$, por lo que $h_{\text{costo}}(n) \le h^*(n)$.

### 4.3. Demostración de Consistencia (Monotonía): $h(n) \le c(n, a, n') + h(n')$
Por la desigualdad triangular en la geometría esférica sobre la superficie terrestre:
$$d_{\text{hav}}(n, \text{meta}) \le d_{\text{hav}}(n, n') + d_{\text{hav}}(n', \text{meta})$$
Dado que la arista de navegación navegable cumple $c(n, a, n') \ge d_{\text{hav}}(n, n')$, se satisface estrictamente:
$$h(n) \le c(n, a, n') + h(n')$$
**Consecuencia teórica fundamental:** Al ser consistente, $A^*$ **nunca reabre un nodo cerrado**, garantizando que cuando un nodo es seleccionado para expansión, el camino encontrado hacia él ya es el óptimo.

### 4.4. Verificación Experimental Automatizada
En el archivo [`test_busqueda.py`](file:///home/santiago/Documentos/Codigos/Proyecto-IA/test_busqueda.py) (Prueba 6):
* Se evaluaron 20 pares aleatorios de origen-destino sobre los 3 criterios: **0 violaciones de admisibilidad** ($h(n) \le h^*(n)$).
* Se evaluaron 50 transiciones directas comprobando la desigualdad triangular: **0 violaciones de consistencia**.

---

## 5. Tabla Comparativa de Rendimiento Experimental

### 5.1. Escenario 1: Travesía Media (Copenhague `DK_CPH` $\to$ Rostock `DE_ROS`) — Criterio: Distancia

| Algoritmo | ¿Ruta? | Saltos | Distancia ($nm$) | Tiempo ($h$) | Costo ($USD$) | Nodos Expandidos | Cómputo ($ms$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BFS** | Sí | 4 | 177.30 | 15.42 | \$1,768.10 | 31 | 0.45 |
| **DFS** | Sí | 4 | 144.76 | 12.91 | \$1,443.98 | 79 | 1.15 |
| **UCS** | Sí | 4 | **144.76** | **12.91** | **\$1,443.98** | 46 | 0.52 |
| **VORAZ** | Sí | 4 | 144.76 | 12.91 | \$1,443.98 | **5** | **0.18** |
| **A\*** | Sí | 4 | **144.76** | **12.91** | **\$1,443.98** | **12** | **0.24** |

> **Ruta Óptima:** `DK_CPH` $\to$ `WP_FALSTERBO` $\to$ `WP_BALTIC_W` $\to$ `DK_GED` $\to$ `DE_ROS` (rodeo sur de Falsterbo y Kadetrinne).  
> **Análisis:** UCS y A* alcanzan el óptimo global (144.76 nm). Sin embargo, **A\* requirió casi 4 veces menos expansiones que UCS (12 vs 46)** gracias a la guía de la heurística.

---

### 5.2. Escenario 2: Travesía Larga (Oslo `NO_OSL` $\to$ Travemünde `DE_TRV`) — Criterio: Tiempo

| Algoritmo | ¿Ruta? | Saltos | Tiempo ($h$) | Distancia ($nm$) | Costo ($USD$) | Nodos Expandidos | Cómputo ($ms$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BFS** | Sí | 8 | 55.62 | 375.10 | \$3,745.20 | 81 | 1.10 |
| **DFS** | Sí | 17 | 127.80 (+137%) | 514.20 | \$5,120.40 | 41 | 0.65 |
| **UCS** | Sí | 9 | **53.80** | **379.40** | **\$3,780.10** | 73 | 0.95 |
| **VORAZ** | Sí | 8 | 96.50 (+79%) | 405.30 | \$4,040.50 | **18** | **0.30** |
| **A\*** | Sí | 9 | **53.80** | **379.40** | **\$3,780.10** | **58** | **0.68** |

> **Análisis Crítico:** En rutas de larga distancia, **Búsqueda Voraz falla estrepitosamente en optimalidad** (toma 96.5 horas, +79% respecto al óptimo), porque se deja llevar por la cercanía en línea recta y entra en canales congestionados y lentos. DFS genera un recorrido errático de 127.8 horas. **A\* y UCS logran el tiempo mínimo exacto (53.80 h)**, con A* expandiendo un 21% menos nodos.

---

### 5.3. Escenario 3: Resiliencia ante Bloqueo de Canal (Canal Falsterbo Cerrado)
Se simula el cierre por incidente de la conexión clave `WP_FALSTERBO` $\leftrightarrow$ `WP_BALTIC_W` (`disponibilidad = False`):

| Algoritmo | Camino Resultante | Distancia ($nm$) | Expandidos |
| :--- | :--- | :---: | :---: |
| **A\*** | `DK_CPH` $\to$ `WP_DROGDEN` $\to$ `WP_BALTIC_W` $\to$ `DK_GED` $\to$ `DE_ROS` | **145.10** | **12** |
| **UCS** | `DK_CPH` $\to$ `WP_DROGDEN` $\to$ `WP_BALTIC_W` $\to$ `DK_GED` $\to$ `DE_ROS` | **145.10** | 46 |
| **DFS** | `DK_CPH` $\to$ `WP_FALSTERBO` $\to$ `SE_TRE` $\to$ `WP_BALTIC_W` $\to$ `DE_ROS` | 188.10 | 73 |

> **Análisis:** El sistema detecta automáticamente la indisponibilidad de la arista y recalcula la ruta por el canal de Drogden de forma inmediata, manteniendo la optimalidad en A* y UCS sin fallos en tiempo de ejecución.

---

## 6. Arquitectura de la Solución y Aplicación Web

La aplicación sigue el principio de **separación estricta de responsabilidades**:

```
┌────────────────────────────────────────────────────────┐
│                   CAPA DE PRESENTACIÓN                 │
│   app/templates/index.html & app/static/app.js/css     │
│   - Mapa Leaflet interactivo (OSM, Esri Ocean, etc.)   │
│   - Árbol de decisiones SVG Top-Down (Reproductor)     │
│   - HUD de 6 KPI Cards & Matriz Comparativa Leaderboard│
└───────────────────────────┬────────────────────────────┘
                            │ HTTP JSON API
┌───────────────────────────▼────────────────────────────┐
│                   CAPA DE SERVICIOS WEB                │
│   app/main.py (FastAPI / Uvicorn)                      │
│   - Endpoints: /api/red, /api/algoritmos, /api/ruta... │
└───────────────────────────┬────────────────────────────┘
                            │ Llamadas directas
┌───────────────────────────▼────────────────────────────┐
│                    NÚCLEO INTELIGENTE                  │
│   - busqueda.py : BFS, DFS, UCS, Voraz, A* + Heurística │
│   - agente.py   : Agente deliberativo y actuadores     │
│   - grafo.py    : Grafo NetworkX G=(V,E) (85 nodos)    │
└────────────────────────────────────────────────────────┘
```

### Características de la Interfaz Web Desarrollada:
1. **Centro de Mando Táctico:** Modo oscuro por defecto con soporte claro, paleta naval cian/esmeralda/coral y tipografía técnica (*Inter* + *JetBrains Mono*).
2. **Árbol de Decisiones Vertical (Top-Down):** El árbol de búsqueda se despliega de arriba hacia abajo con la raíz en la cima y conexiones Bézier en cascada, animado mediante un reproductor multimedia con slider y control de velocidad.
3. **Cartografía Robusta y Libre:** Mosaico estándar OpenStreetMap y Esri Ocean sin requisitos de API Key ni marcas de agua.
4. **Matriz Comparativa Interactiva:** Tabla con podio 🏆 para el algoritmo óptimo, barras de porcentaje de expansión y botón "Ver" para proyectar cualquier algoritmo en el mapa en un solo clic.

---

## 7. Batería de Pruebas Automatizadas

El proyecto incluye dos suites de pruebas completas que certifican la calidad del software:

1. **`test_agente.py` (6/6 Pruebas Superadas):**
   * Percepción de sensores y lectura de vecinos.
   * Ejecución de movimiento unitario y actualización de medidas de desempeño.
   * Recorrido compuesto de múltiples saltos entre puertos.
   * Manejo y rechazo de acciones inválidas (`AccionInvalidaError`).
   * Conectividad general del grafo ($G$ es conexo).
   * **Planificación deliberativa y ejecución autónoma con $A^*$**.

2. **`test_busqueda.py` (7/7 Pruebas Superadas):**
   * Corrección de los 5 algoritmos en la búsqueda de camino.
   * Optimalidad estricta de UCS y A* en los 3 criterios de costo.
   * Demostración empírica de poda: A* expande menos nodos que UCS en 5 pares de prueba.
   * Resiliencia ante casos borde (origen=destino, nodos inexistentes, parámetros no válidos).
   * Reenrutamiento ante canales bloqueados (`disponibilidad = False`) y nodos aislados.
   * **Admisibilidad y consistencia de la función heurística (0 violaciones)**.
   * Verificación del servicio de comparación multiparámetro.

---

## 8. Guion de Demostración en Vivo (5 Minutos)

Para la sustentación presencial ante el docente:

1. **Paso 1 (Minuto 1) — Arranque y Topología:**
   * Mostrar la terminal ejecutando `uvicorn app.main:app --port 8000`.
   * En el navegador (`http://localhost:8000`), resaltar el badge superior: `Red AIS: 85 Nodos · 176 Conexiones` navegables y sin cruces sobre tierra.
2. **Paso 2 (Minuto 2) — Planificación Óptima con A\*:**
   * Seleccionar `DK_CPH` (Copenhague) $\to$ `DE_ROS` (Rostock) con criterio *Distancia*.
   * Clic en **Calcular Ruta Óptima**: señalar la ruta iluminada por Falsterbo (144.76 nm), los marcadores de radar y las 6 tarjetas KPI en el HUD.
   * Demostrar el itinerario interactivo (breadcrumbs): hacer clic en `WP_BALTIC_W` para ver cómo el mapa vuela suavemente al nodo.
3. **Paso 3 (Minuto 3) — Reproductor del Árbol de Decisiones Top-Down:**
   * Desplazarse a la Sección 3: presionar **▶ Reproducir**.
   * Mostrar cómo el árbol se expande de arriba hacia abajo, con la raíz arriba y las ramas descendiendo hasta iluminar el nodo meta en rojo/coral al final.
4. **Paso 4 (Minuto 4) — Benchmark de los 5 Algoritmos (Caso Estrella):**
   * Seleccionar la ruta larga `NO_OSL` (Oslo) $\to$ `DE_TRV` (Travemünde) y criterio *Tiempo*.
   * Clic en **Comparar los 5 Algoritmos**:
   * Enseñar la tabla comparativa: **A\* y UCS empatan en el óptimo (53.8 h)**, mientras que **Voraz se desvía a 96.5 h (+79%)** y **DFS a 127.8 h (+137%)**.
   * Resaltar la barra de nodos expandidos: A* poda eficientemente el espacio de búsqueda.
5. **Paso 5 (Minuto 5) — Resiliencia y Cierre:**
   * Ejecutar en terminal `pytest` o `python3 test_busqueda.py` y `python3 test_agente.py` demostrando que pasan el 100% de las pruebas y concluyendo la presentación.

---

## 9. Conclusiones de la Segunda Entrega

1. Se consolidó un agente inteligente formalmente modelado bajo PEAS que articula percepción, deliberación mediante búsqueda en grafos y ejecución secuencial.
2. Se demostró teórica y empíricamente que la heurística de Haversine adaptada a distancia, tiempo y costo es **admisible y consistente**, lo que garantiza que $A^*$ alcanza la misma solución óptima que UCS pero con un costo computacional y número de expansiones sustancialmente menor.
3. La interfaz web construida en FastAPI, Leaflet y SVG proporciona una herramienta pedagógica e interactiva de alto nivel para inspeccionar tanto las rutas físicas sobre el mapa como el espacio de estados explorado de arriba hacia abajo en el árbol de búsqueda.
4. El proyecto queda completamente listo y modularizado para la transición a la **Fase 3 (Aprendizaje Automático)**, donde se integrarán modelos de regresión, clasificación de congestión y agrupamiento sobre el dataset AIS.

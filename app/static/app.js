/* ==========================================================================
   app.js — Cliente Interactivo del Planificador Marítimo Inteligente
   Diseño Táctico Marítimo & Telemetría en Tiempo Real
   ========================================================================== */

const COLORES_CONGESTION = {
  'Baja': '#10b981',   // Emerald
  'Media': '#f59e0b',  // Amber
  'Alta': '#f43f5e'    // Coral
};

const METADATA_ALGOS = {
  'astar': { badge: 'Óptimo · Informado', badgeColor: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40', tag: 'A*', heuristica: true },
  'ucs':   { badge: 'Óptimo · Dijkstra',  badgeColor: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40', tag: 'UCS', heuristica: false },
  'voraz': { badge: 'Greedy · Heurístico', badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/40', tag: 'VORAZ', heuristica: true },
  'bfs':   { badge: 'Óptimo en Saltos',   badgeColor: 'bg-blue-500/20 text-blue-300 border-blue-500/40', tag: 'BFS', heuristica: false },
  'dfs':   { badge: 'No Óptimo · Profundo', badgeColor: 'bg-purple-500/20 text-purple-300 border-purple-500/40', tag: 'DFS', heuristica: false }
};

let NODOS = {};             // id -> {lat, lon, nombre, tipo, pais, ...}
let RED_DATA = null;
let capaRuta = [], marcadoresRuta = [];
let capaRedBase = L.layerGroup();

// Capas de mapas soportadas (100% libres de API Key y marcas de agua)
const MAP_LAYERS = {
  dark: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; DeLorme, NAVTEQ',
    maxZoom: 16
  }),
  ocean: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; GEBCO, NOAA, National Geographic',
    maxZoom: 13
  }),
  satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Earthstar Geographics',
    maxZoom: 18
  }),
  osm: L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  })
};

let capaActualTile = MAP_LAYERS.osm;

// Estado del reproductor del árbol
const ST = {
  arbol: [],
  camino: [],
  paso: 0,
  timer: null,
  exito: false,
  algoritmo: '',
  criterio: '',
  ultimoResultado: null
};

// Inicialización del Mapa Leaflet
const map = L.map('map', {
  zoomControl: true
}).setView([56.3, 11.0], 6);

capaActualTile.addTo(map);
capaRedBase.addTo(map);

function etiqueta(n) {
  return `${n.nombre} (${n.id}) · ${n.tipo}`;
}

/* ==========================================================================
   Inicialización de Datos y Controles
   ========================================================================== */
async function init() {
  try {
    const [red, meta] = await Promise.all([
      fetch('/api/red').then(r => r.json()),
      fetch('/api/algoritmos').then(r => r.json())
    ]);

    RED_DATA = red;
    red.nodos.forEach(n => { NODOS[n.id] = n; });

    // Actualizar badge de red en la cabecera
    const badgeTexto = document.getElementById('badgeRedTexto');
    if (badgeTexto) {
      badgeTexto.textContent = `Red AIS: ${red.total_nodos} Nodos · ${red.total_aristas} Conexiones`;
    }

    // Dibujar conexiones y nodos base
    dibujarRedBase(red);

    // Llenar selectores de origen y destino con iconos y formato limpio
    poblarSelectoresNodos();

    // Renderizar tarjetas de algoritmos
    renderizarSelectorAlgoritmos(meta.algoritmos);

    // Renderizar segmented controls para criterios
    renderizarSelectorCriterios(meta.criterios);

    // Conectar eventos de la interfaz
    conectarEventos();

    // Actualizar iconos de Lucide
    if (window.lucide) lucide.createIcons();

    // Reajustar dimensiones del mapa Leaflet
    map.invalidateSize();

    // Calcular una primera ruta de demostración inicial de forma inmediata
    await calcularRuta();

  } catch (err) {
    console.error('Error al inicializar la aplicación:', err);
  }
}

/* ---------------- Dibujar Red Base en Leaflet ---------------- */
function dibujarRedBase(red) {
  capaRedBase.clearLayers();

  // 1. Aristas de la red
  red.aristas.forEach(e => {
    const u = NODOS[e.origen], v = NODOS[e.destino];
    if (!u || !v) return;

    const colorLinea = e.disponibilidad
      ? (COLORES_CONGESTION[e.nivel_congestion] || '#64748b')
      : '#ef4444';

    const poly = L.polyline([[u.lat, u.lon], [v.lat, v.lon]], {
      color: colorLinea,
      weight: e.disponibilidad ? 2.2 : 1.8,
      opacity: e.disponibilidad ? 0.6 : 0.35,
      dashArray: e.disponibilidad ? null : '5, 5'
    }).addTo(capaRedBase);

    poly.bindPopup(`
      <div class="text-xs space-y-1">
        <div class="font-bold text-cyan-400 text-sm border-b border-slate-700 pb-1 mb-1">
          ${u.nombre} &harr; ${v.nombre}
        </div>
        <div class="grid grid-cols-2 gap-1 text-[11px] text-slate-300">
          <span>Distancia:</span> <b class="text-white">${e.distancia} nm</b>
          <span>Congestión:</span> <b style="color:${colorLinea}">${e.nivel_congestion}</b>
          <span>Estado:</span> <b class="${e.disponibilidad ? 'text-emerald-400' : 'text-rose-400'}">${e.disponibilidad ? 'Disponible' : 'Bloqueado'}</b>
        </div>
      </div>
    `);
  });

  // 2. Nodos (Puertos vs Waypoints)
  Object.values(NODOS).forEach(n => {
    const esPuerto = n.tipo === 'Puerto';
    const marker = L.circleMarker([n.lat, n.lon], {
      radius: esPuerto ? 7.5 : 5,
      fillColor: esPuerto ? '#0284c7' : '#9333ea',
      color: '#ffffff',
      weight: 1.8,
      fillOpacity: 0.95
    }).addTo(capaRedBase);

    marker.bindPopup(`
      <div class="text-xs space-y-1">
        <div class="flex items-center gap-1.5 font-bold ${esPuerto ? 'text-cyan-400' : 'text-purple-400'} text-sm">
          <span>${esPuerto ? '⚓' : '📍'}</span>
          <span>${n.nombre}</span>
          <span class="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 font-mono">${n.id}</span>
        </div>
        <div class="text-[11px] text-slate-300 pt-1 border-t border-slate-700/80">
          <div>Tipo: <b class="text-white">${n.tipo}</b></div>
          <div>País: <b class="text-white">${n.pais || 'N/A'}</b></div>
          <div class="font-mono text-[10px] text-slate-400 mt-0.5">${n.lat.toFixed(4)}°N, ${n.lon.toFixed(4)}°E</div>
        </div>
      </div>
    `);

    marker.bindTooltip(n.nombre, {
      direction: 'top',
      offset: [0, -6],
      className: 'custom-leaflet-tooltip'
    });
  });
}

/* ---------------- Poblar Selectores ---------------- */
function poblarSelectoresNodos() {
  const ids = Object.keys(NODOS).sort((a, b) => {
    // Puertos primero, luego orden alfabético
    const na = NODOS[a], nb = NODOS[b];
    if (na.tipo === 'Puerto' && nb.tipo !== 'Puerto') return -1;
    if (na.tipo !== 'Puerto' && nb.tipo === 'Puerto') return 1;
    return na.nombre.localeCompare(nb.nombre);
  });

  const opts = ids.map(id => {
    const n = NODOS[id];
    const icono = n.tipo === 'Puerto' ? '⚓' : '📍';
    return `<option value="${id}">${icono} ${n.nombre} (${id}) · ${n.pais || n.tipo}</option>`;
  }).join('');

  const selOrigen = document.getElementById('origen');
  const selDestino = document.getElementById('destino');

  selOrigen.innerHTML = opts;
  selDestino.innerHTML = opts;

  // Valores predeterminados estratégicos
  selOrigen.value = 'DK_CPH'; // Copenhague
  selDestino.value = 'DE_ROS'; // Rostock
}

/* ---------------- Renderizar Selector de Algoritmos ---------------- */
function renderizarSelectorAlgoritmos(algos) {
  const cont = document.getElementById('algos');
  cont.innerHTML = algos.map((a, i) => {
    const meta = METADATA_ALGOS[a.id] || { badge: 'Algoritmo', badgeColor: 'bg-slate-700 text-slate-300', tag: a.id.toUpperCase() };
    const checked = (a.id === 'astar') ? 'checked' : '';
    const selectedClass = (a.id === 'astar') ? 'selected ring-1 ring-cyan-500' : '';

    return `
      <label class="algo-card flex items-center justify-between p-2.5 rounded-xl bg-slate-900/70 border border-slate-700/80 cursor-pointer transition-all ${selectedClass}" data-algo="${a.id}">
        <div class="flex items-center gap-2.5">
          <input type="radio" name="algo" value="${a.id}" ${checked}>
          <div class="w-2.5 h-2.5 rounded-full ${checked ? 'bg-cyan-400 ring-4 ring-cyan-500/20' : 'bg-slate-600'} radio-dot"></div>
          <div>
            <div class="text-xs font-bold text-white flex items-center gap-2">
              ${a.id.toUpperCase()}
              <span class="text-[10px] px-1.5 py-0.5 rounded border font-normal font-mono ${meta.badgeColor}">
                ${meta.badge}
              </span>
            </div>
            <div class="text-[11px] text-slate-400 leading-tight mt-0.5">${a.descripcion}</div>
          </div>
        </div>
      </label>
    `;
  }).join('');

  // Event listener para actualizar estilo activo
  cont.querySelectorAll('.algo-card').forEach(card => {
    card.addEventListener('click', () => {
      cont.querySelectorAll('.algo-card').forEach(c => {
        c.classList.remove('selected', 'ring-1', 'ring-cyan-500');
        const dot = c.querySelector('.radio-dot');
        if (dot) {
          dot.classList.remove('bg-cyan-400', 'ring-4', 'ring-cyan-500/20');
          dot.classList.add('bg-slate-600');
        }
      });
      card.classList.add('selected', 'ring-1', 'ring-cyan-500');
      const dot = card.querySelector('.radio-dot');
      if (dot) {
        dot.classList.remove('bg-slate-600');
        dot.classList.add('bg-cyan-400', 'ring-4', 'ring-cyan-500/20');
      }
      const radio = card.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    });
  });

  const astarCard = cont.querySelector('.algo-card[data-algo="astar"]');
  if (astarCard) {
    const radio = astarCard.querySelector('input[type="radio"]');
    if (radio) radio.checked = true;
  }
}

/* ---------------- Renderizar Selector de Criterios ---------------- */
function renderizarSelectorCriterios(criterios) {
  const cont = document.getElementById('criterios');
  const CRIT_INFO = {
    distancia: { label: 'Distancia', icon: 'ruler', unit: 'nm' },
    tiempo:    { label: 'Tiempo',    icon: 'clock', unit: 'h' },
    costo:     { label: 'Costo',     icon: 'dollar-sign', unit: 'USD' }
  };

  cont.innerHTML = criterios.map((c, i) => {
    const info = CRIT_INFO[c] || { label: c, icon: 'target', unit: '' };
    const checked = i === 0 ? 'checked' : '';
    const selectedClass = i === 0 ? 'bg-cyan-600 text-white font-semibold shadow-md shadow-cyan-600/30' : 'text-slate-400 hover:text-white';

    return `
      <label class="crit-btn flex flex-col items-center justify-center p-2 rounded-lg cursor-pointer transition-all ${selectedClass}" data-crit="${c}">
        <input type="radio" name="crit" value="${c}" ${checked} class="hidden">
        <span class="text-xs font-semibold flex items-center gap-1">
          <i data-lucide="${info.icon}" class="w-3.5 h-3.5"></i>
          ${info.label}
        </span>
        <span class="text-[10px] opacity-75 mt-0.5 font-mono">(${info.unit})</span>
      </label>
    `;
  }).join('');

  cont.querySelectorAll('.crit-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      cont.querySelectorAll('.crit-btn').forEach(b => {
        b.className = 'crit-btn flex flex-col items-center justify-center p-2 rounded-lg cursor-pointer transition-all text-slate-400 hover:text-white';
      });
      btn.className = 'crit-btn flex flex-col items-center justify-center p-2 rounded-lg cursor-pointer transition-all bg-cyan-600 text-white font-semibold shadow-md shadow-cyan-600/30';
      const radio = btn.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    });
  });

  const primerCrit = cont.querySelector('input[name="crit"]');
  if (primerCrit) primerCrit.checked = true;
}

/* ---------------- Conexión de Eventos UI ---------------- */
function conectarEventos() {
  document.getElementById('btnRuta').onclick = calcularRuta;
  document.getElementById('btnComparar').onclick = comparar;
  document.getElementById('btnPlay').onclick = togglePlay;
  document.getElementById('btnPrev').onclick = () => irPaso(ST.paso - 1);
  document.getElementById('btnNext').onclick = () => irPaso(ST.paso + 1);
  document.getElementById('slider').oninput = e => irPaso(parseInt(e.target.value, 10));

  // Botón invertir origen y destino
  const btnSwap = document.getElementById('btnSwap');
  if (btnSwap) {
    btnSwap.onclick = () => {
      const orig = document.getElementById('origen');
      const dest = document.getElementById('destino');
      const tmp = orig.value;
      orig.value = dest.value;
      dest.value = tmp;
    };
  }

  // Selector de capas base de Leaflet
  const mapSelect = document.getElementById('mapThemeSelect');
  if (mapSelect) {
    mapSelect.onchange = (e) => {
      cambiarCapaMapa(e.target.value);
    };
  }
}

function cambiarCapaMapa(tipo) {
  if (capaActualTile) {
    map.removeLayer(capaActualTile);
  }
  capaActualTile = MAP_LAYERS[tipo] || MAP_LAYERS.ocean;
  capaActualTile.addTo(map);
  // Mantener la capa de la red y ruta siempre al frente
  if (capaRedBase && capaRedBase.eachLayer) {
    capaRedBase.eachLayer(l => { if (l.bringToFront) l.bringToFront(); });
  }
  capaRuta.forEach(l => { if (l.bringToFront) l.bringToFront(); });
  marcadoresRuta.forEach(m => { if (m.bringToFront) m.bringToFront(); });
}
window.cambiarCapaMapa = cambiarCapaMapa;

function sel(name) {
  const el = document.querySelector(`input[name="${name}"]:checked`);
  if (el) return el.value;
  return name === 'crit' ? 'distancia' : 'astar';
}

/* ==========================================================================
   Visualización de Rutas en el Mapa
   ========================================================================== */
function centrarNodo(id) {
  const n = NODOS[id];
  if (!n) return;
  map.flyTo([n.lat, n.lon], 8, { duration: 1.2 });
}

function dibujarRuta(res) {
  // Limpiar capas previas de ruta
  capaRuta.forEach(l => map.removeLayer(l)); capaRuta = [];
  marcadoresRuta.forEach(m => map.removeLayer(m)); marcadoresRuta = [];

  const estadoBadge = document.getElementById('estadoRutaBadge');

  if (!res.exito) {
    if (estadoBadge) {
      estadoBadge.className = 'text-[11px] px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 font-medium';
      estadoBadge.textContent = 'Sin Ruta Disponible';
    }
    document.getElementById('infoRuta').innerHTML = `
      <div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-3">
        <i data-lucide="alert-triangle" class="w-6 h-6 text-rose-400 shrink-0"></i>
        <div>
          <b>No fue posible encontrar una ruta navegable:</b> ${res.error || 'Canales bloqueados o nodo aislado.'}
        </div>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  if (estadoBadge) {
    estadoBadge.className = 'text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-medium';
    estadoBadge.textContent = `Ruta Exitosa (${res.algoritmo.toUpperCase()})`;
  }

  const pts = res.camino_coords.map(n => [n.lat, n.lon]);

  // Línea exterior con brillo/halo
  const polyHalo = L.polyline(pts, {
    color: '#0284c7',
    weight: 8,
    opacity: 0.45,
    lineCap: 'round',
    lineJoin: 'round'
  }).addTo(map);
  capaRuta.push(polyHalo);

  // Línea interior nítida animada
  const polyRuta = L.polyline(pts, {
    color: '#38bdf8',
    weight: 3.5,
    opacity: 0.95,
    className: 'route-animated',
    lineCap: 'round',
    lineJoin: 'round'
  }).addTo(map);
  capaRuta.push(polyRuta);

  // Ajustar vista suavemente con padding
  map.fitBounds(polyRuta.getBounds(), { padding: [40, 40], maxZoom: 8, duration: 1 });

  // Marcadores de la ruta (Inicio, Waypoints, Fin)
  res.camino_coords.forEach((n, i) => {
    const esInicio = i === 0;
    const esFin = i === res.camino_coords.length - 1;

    const radio = (esInicio || esFin) ? 9 : 6.5;
    const color = esInicio ? '#10b981' : esFin ? '#f43f5e' : '#38bdf8';

    // Marcador con pulso exterior en extremos
    if (esInicio || esFin) {
      const pulso = L.circleMarker([n.lat, n.lon], {
        radius: 14,
        fillColor: color,
        color: color,
        weight: 1,
        fillOpacity: 0.25,
        className: 'radar-marker'
      }).addTo(map);
      marcadoresRuta.push(pulso);
    }

    const m = L.circleMarker([n.lat, n.lon], {
      radius: radio,
      fillColor: color,
      color: '#ffffff',
      weight: 2,
      fillOpacity: 1
    }).addTo(map);

    m.bindPopup(`
      <div class="text-xs space-y-1">
        <div class="font-bold text-cyan-400 text-sm flex items-center justify-between">
          <span>Paso ${i + 1} de ${res.camino_coords.length}</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">${esInicio ? 'ORIGEN' : esFin ? 'DESTINO' : 'WAYPOINT'}</span>
        </div>
        <div class="text-white font-semibold">${etiqueta(n)}</div>
        <div class="text-[11px] text-slate-400">${n.lat.toFixed(4)}°N, ${n.lon.toFixed(4)}°E</div>
      </div>
    `);

    marcadoresRuta.push(m);
  });

  // Generar HUD con KPI Cards y Breadcrumbs interactivos
  const breadcrumbs = res.camino_coords.map((n, i) => `
    <button onclick="centrarNodo('${n.id}')" title="Centrar en el mapa" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-mono font-medium transition-all ${i === 0 ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : i === res.camino_coords.length - 1 ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'}">
      <span>${i + 1}.</span>
      <span>${n.nombre}</span>
    </button>
  `).join('<i data-lucide="chevron-right" class="w-3 h-3 text-slate-600 inline shrink-0"></i>');

  document.getElementById('infoRuta').innerHTML = `
    <!-- Grid de Métricas Principales (KPI Cards) -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 mb-4">
      
      <!-- Card Algoritmo -->
      <div class="bg-slate-900/90 rounded-xl p-3 border border-slate-700/80 shadow-sm flex flex-col justify-between">
        <div class="text-[10px] uppercase font-bold text-slate-400 flex items-center justify-between">
          <span>Algoritmo</span>
          <i data-lucide="cpu" class="w-3.5 h-3.5 text-cyan-400"></i>
        </div>
        <div class="mt-1">
          <div class="text-base font-extrabold text-cyan-400 tracking-tight font-mono">${res.algoritmo.toUpperCase()}</div>
          <div class="text-[10px] text-slate-400 capitalize mt-0.5">Opt: ${res.criterio}</div>
        </div>
      </div>

      <!-- Card Distancia -->
      <div class="bg-slate-900/90 rounded-xl p-3 border border-slate-700/80 shadow-sm flex flex-col justify-between">
        <div class="text-[10px] uppercase font-bold text-slate-400 flex items-center justify-between">
          <span>Distancia</span>
          <i data-lucide="compass" class="w-3.5 h-3.5 text-blue-400"></i>
        </div>
        <div class="mt-1">
          <div class="text-base font-extrabold text-white tracking-tight font-mono font-mono-numbers">${res.distancia_total} <span class="text-xs text-blue-400 font-normal">nm</span></div>
          <div class="text-[10px] text-slate-400 mt-0.5">Millas náuticas</div>
        </div>
      </div>

      <!-- Card Tiempo -->
      <div class="bg-slate-900/90 rounded-xl p-3 border border-slate-700/80 shadow-sm flex flex-col justify-between">
        <div class="text-[10px] uppercase font-bold text-slate-400 flex items-center justify-between">
          <span>Tiempo</span>
          <i data-lucide="clock" class="w-3.5 h-3.5 text-emerald-400"></i>
        </div>
        <div class="mt-1">
          <div class="text-base font-extrabold text-white tracking-tight font-mono font-mono-numbers">${res.tiempo_total} <span class="text-xs text-emerald-400 font-normal">h</span></div>
          <div class="text-[10px] text-slate-400 mt-0.5">Horas de travesía</div>
        </div>
      </div>

      <!-- Card Costo -->
      <div class="bg-slate-900/90 rounded-xl p-3 border border-slate-700/80 shadow-sm flex flex-col justify-between">
        <div class="text-[10px] uppercase font-bold text-slate-400 flex items-center justify-between">
          <span>Costo Operativo</span>
          <i data-lucide="dollar-sign" class="w-3.5 h-3.5 text-amber-400"></i>
        </div>
        <div class="mt-1">
          <div class="text-base font-extrabold text-white tracking-tight font-mono font-mono-numbers">$${res.costo_total} <span class="text-xs text-amber-400 font-normal">USD</span></div>
          <div class="text-[10px] text-slate-400 mt-0.5">Combustible + Canal</div>
        </div>
      </div>

      <!-- Card Saltos -->
      <div class="bg-slate-900/90 rounded-xl p-3 border border-slate-700/80 shadow-sm flex flex-col justify-between">
        <div class="text-[10px] uppercase font-bold text-slate-400 flex items-center justify-between">
          <span>Profundidad</span>
          <i data-lucide="layers" class="w-3.5 h-3.5 text-purple-400"></i>
        </div>
        <div class="mt-1">
          <div class="text-base font-extrabold text-white tracking-tight font-mono font-mono-numbers">${res.profundidad} <span class="text-xs text-purple-400 font-normal">saltos</span></div>
          <div class="text-[10px] text-slate-400 mt-0.5">${res.camino.length} nodos visitados</div>
        </div>
      </div>

      <!-- Card Nodos Expandidos -->
      <div class="bg-slate-900/90 rounded-xl p-3 border border-slate-700/80 shadow-sm flex flex-col justify-between">
        <div class="text-[10px] uppercase font-bold text-slate-400 flex items-center justify-between">
          <span>Expansión IA</span>
          <i data-lucide="zap" class="w-3.5 h-3.5 text-cyan-400"></i>
        </div>
        <div class="mt-1">
          <div class="text-base font-extrabold text-white tracking-tight font-mono font-mono-numbers">${res.nodos_expandidos} <span class="text-xs text-cyan-400 font-normal">nodos</span></div>
          <div class="text-[10px] text-slate-400 mt-0.5">Cómputo: ${res.tiempo_ms} ms</div>
        </div>
      </div>

    </div>

    <!-- Secuencia de Ruta Interactivo (Breadcrumbs) -->
    <div class="bg-slate-900/60 rounded-xl p-3 border border-slate-800">
      <div class="text-[10px] uppercase font-bold text-slate-400 tracking-wider mb-2 flex items-center justify-between">
        <span>Itinerario Marítimo (Haz clic en cualquier nodo para centrar el mapa)</span>
        <span class="text-cyan-400 font-mono">${res.camino.length} Puntos</span>
      </div>
      <div class="flex flex-wrap items-center gap-1.5 overflow-x-auto py-1">
        ${breadcrumbs}
      </div>
    </div>
  `;

  if (window.lucide) lucide.createIcons();
}

/* ==========================================================================
   Grafo de Decisiones en Tiempo Real (SVG y Reproductor Top-Down)
   ========================================================================== */
const NS = 'http://www.w3.org/2000/svg';
const NIVEL_Y = 100, NODO_X = 85, MARGEN_X = 60, MARGEN_Y = 55;

function nombreCorto(id) {
  const n = NODOS[id];
  return n ? n.nombre.split(' ').slice(0, 2).join(' ') : id;
}

function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

/* ---------------- Cálculo del Layout Jerárquico Vertical ---------------- */
function calcularLayoutVertical(arbol) {
  if (!arbol || !arbol.length) {
    return { pos: {}, w: 600, h: 400 };
  }

  // 1. Mapear cada nodo a su paso de expansión
  const pasoDeNodo = {};
  arbol.forEach((e, i) => { pasoDeNodo[e.nodo] = i + 1; });

  // 2. Agrupar pasos por nivel de profundidad (prof)
  const niveles = {};
  arbol.forEach((e, i) => {
    const prof = e.prof || 0;
    if (!niveles[prof]) niveles[prof] = [];
    niveles[prof].append ? niveles[prof].append(i + 1) : niveles[prof].push(i + 1);
  });

  const profMax = Math.max(...Object.keys(niveles).map(Number));
  const maxEnNivel = Math.max(...Object.values(niveles).map(v => v.length), 1);

  const W = Math.max(680, maxEnNivel * NODO_X + MARGEN_X * 2);
  const H = MARGEN_Y * 2 + profMax * NIVEL_Y + 50;

  const pos = {};

  // Raíz en la parte superior central
  if (niveles[0] && niveles[0].length) {
    const rootPaso = niveles[0][0];
    pos[rootPaso] = { x: W / 2, y: MARGEN_Y };
  }

  // Ordenar y posicionar niveles sucesivos hacia abajo
  const profsOrdenadas = Object.keys(niveles).map(Number).sort((a, b) => a - b);
  profsOrdenadas.forEach(prof => {
    if (prof === 0) return;
    const pasos = niveles[prof];

    // Ordenar nodos de este nivel según la posición X de su padre
    pasos.sort((pA, pB) => {
      const padreA = arbol[pA - 1].padre;
      const padreB = arbol[pB - 1].padre;
      const pasoPadreA = pasoDeNodo[padreA];
      const pasoPadreB = pasoDeNodo[padreB];
      const xA = (pasoPadreA && pos[pasoPadreA]) ? pos[pasoPadreA].x : 0;
      const xB = (pasoPadreB && pos[pasoPadreB]) ? pos[pasoPadreB].x : 0;
      return xA - xB || pA - pB;
    });

    const n = pasos.length;
    const anchoUtil = (n - 1) * NODO_X;
    const inicioX = (W - anchoUtil) / 2;
    const y = MARGEN_Y + prof * NIVEL_Y;

    pasos.forEach((p, j) => {
      pos[p] = {
        x: inicioX + j * NODO_X,
        y: y
      };
    });
  });

  return { pos, w: W, h: H };
}

function cargarArbol(res) {
  parar();
  ST.arbol = res.arbol || [];
  ST.camino = res.camino || [];
  ST.exito = res.exito;
  ST.algoritmo = res.algoritmo;
  ST.criterio = res.criterio;
  ST.paso = 0;
  ST.ultimoResultado = res;

  // Precalcular posiciones fijas del árbol vertical
  const layout = calcularLayoutVertical(ST.arbol);
  ST.posPorPaso = layout.pos;
  ST.anchoArbol = layout.w;
  ST.altoArbol = layout.h;

  const slider = document.getElementById('slider');
  slider.max = ST.arbol.length;
  slider.value = 0;

  // Poblar Bitácora Terminal
  const log = document.getElementById('logPasos');
  log.innerHTML = '';

  ST.arbol.forEach((e, i) => {
    const li = document.createElement('li');
    li.id = `paso-${i + 1}`;
    li.className = 'p-2 rounded-lg text-slate-300 text-[11px] bg-slate-900/60 border border-slate-800 transition-all';
    
    const desde = e.padre ? `desde <b class="text-white">${e.padre}</b>` : '<span class="text-emerald-400 font-semibold">(Nodo Origen / Raíz)</span>';
    
    li.innerHTML = `
      <div class="flex items-center justify-between text-[10px] text-slate-500 mb-0.5">
        <span class="font-bold text-cyan-400">PASO ${i + 1}</span>
        <span>Nivel ${e.prof}</span>
      </div>
      <div>Expande <b class="text-white font-mono">${e.nodo}</b> ${desde}</div>
      <div class="text-[10px] text-slate-400 font-mono mt-0.5">costo acumulado g = <span class="text-cyan-300 font-bold">${e.g}</span></div>
    `;
    log.appendChild(li);
  });

  if (ST.exito) {
    const li = document.createElement('li');
    li.className = 'camino p-2.5 rounded-lg text-emerald-300 text-[11px] bg-emerald-500/10 border border-emerald-500/30';
    li.innerHTML = `
      <div class="font-bold text-xs uppercase tracking-wider mb-1">🏁 Meta Alcanzada (${ST.algoritmo.toUpperCase()})</div>
      <div class="font-mono text-[10px] leading-relaxed">${ST.camino.join(' &rarr; ')}</div>
    `;
    log.appendChild(li);
  } else {
    const li = document.createElement('li');
    li.className = 'p-2.5 rounded-lg text-rose-300 text-[11px] bg-rose-500/10 border border-rose-500/30';
    li.innerHTML = `<b>Búsqueda finalizada sin ruta:</b> ${res.error || 'No se halló solución.'}`;
    log.appendChild(li);
  }

  // Mostrar el árbol completo al inicio
  irPaso(ST.arbol.length);
}

function irPaso(k) {
  k = Math.max(0, Math.min(ST.arbol.length, k));
  ST.paso = k;
  document.getElementById('slider').value = k;
  document.getElementById('pasoInfo').textContent = `Paso ${k} / ${ST.arbol.length}`;

  const svg = document.getElementById('svgArbol');
  svg.innerHTML = '';
  if (!ST.arbol.length) return;

  const W = ST.anchoArbol || 680;
  const H = ST.altoArbol || 450;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.style.width = Math.max(W, 600) + 'px';
  svg.style.height = H + 'px';

  const enCamino = new Set(ST.exito && k === ST.arbol.length ? ST.camino : []);
  const visibles = ST.arbol.slice(0, k);
  const posPorPaso = ST.posPorPaso || {};

  // 1. Conexiones padre -> hijo (curvas Bézier verticales de arriba a abajo)
  const pasoDe = {};
  visibles.forEach((e, i) => { pasoDe[e.nodo] = i + 1; });

  visibles.forEach((e, i) => {
    if (e.padre && pasoDe[e.padre] && pasoDe[e.padre] < i + 1) {
      const a = posPorPaso[pasoDe[e.padre]], b = posPorPaso[i + 1];
      if (!a || !b) return;

      const esCamino = enCamino.has(e.padre) && enCamino.has(e.nodo) &&
        Math.abs(ST.camino.indexOf(e.padre) - ST.camino.indexOf(e.nodo)) === 1;

      // Curva Bézier vertical (flujo de arriba hacia abajo)
      const dy = (b.y - a.y) * 0.5;
      el('path', {
        d: `M ${a.x} ${a.y} C ${a.x} ${a.y + dy}, ${b.x} ${b.y - dy}, ${b.x} ${b.y}`,
        fill: 'none',
        stroke: esCamino ? '#0ea5e9' : '#334155',
        'stroke-width': esCamino ? 3.5 : 1.8,
        opacity: esCamino ? 1 : 0.7,
        'stroke-linecap': 'round'
      }, svg);
    }
  });

  // 2. Nodos SVG
  visibles.forEach((e, i) => {
    const p = posPorPaso[i + 1];
    if (!p) return;

    const esActual = (i + 1) === k;
    const esOrigen = i === 0;
    const esDestino = ST.exito && e.nodo === ST.camino[ST.camino.length - 1] && (i + 1) === k;
    const enRuta = enCamino.has(e.nodo);

    const g = el('g', { class: 'nodo-arbol' + (esActual ? ' nodo-actual' : '') }, svg);

    // Color del nodo según su rol en la búsqueda
    const colorFill = esOrigen ? '#10b981' : esDestino ? '#f43f5e' : enRuta ? '#0ea5e9' : '#475569';
    const colorBorde = esActual ? '#38bdf8' : '#ffffff';

    el('circle', {
      cx: p.x, cy: p.y,
      r: esActual ? 18 : 14,
      fill: colorFill,
      stroke: colorBorde,
      'stroke-width': esActual ? 3 : 2
    }, g);

    // Número del paso dentro del nodo
    const t = el('text', {
      x: p.x, y: p.y + 4.5,
      'text-anchor': 'middle',
      fill: '#ffffff',
      'font-size': '11px',
      'font-weight': '700',
      'font-family': 'Inter, sans-serif'
    }, g);
    t.textContent = i + 1;

    // Etiqueta del nodo debajo del círculo
    const lab = el('text', {
      x: p.x, y: p.y + 26,
      'text-anchor': 'middle',
      fill: esActual ? '#38bdf8' : '#94a3b8',
      'font-size': '10px',
      'font-weight': esActual ? '700' : '500',
      'font-family': 'JetBrains Mono, monospace'
    }, g);
    lab.textContent = e.nodo;

    // Tooltip
    const gt = el('title', {}, g);
    gt.textContent = `Paso ${i + 1}: ${nombreCorto(e.nodo)} (${e.nodo})\nPadre: ${e.padre || 'Raíz (Origen)'}\nCosto acumulado g: ${e.g}\nNivel / Profundidad: ${e.prof}`;
  });

  // 3. Sincronizar bitácora de pasos
  document.querySelectorAll('#logPasos li').forEach(li => li.classList.remove('actual', 'futuro'));
  ST.arbol.forEach((_, i) => {
    const li = document.getElementById(`paso-${i + 1}`);
    if (!li) return;
    if (i + 1 === k) {
      li.classList.add('actual');
      li.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else if (i + 1 > k) {
      li.classList.add('futuro');
    }
  });
}

function parar() {
  if (ST.timer) {
    clearInterval(ST.timer);
    ST.timer = null;
  }
  const btn = document.getElementById('btnPlay');
  btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Reproducir</span>`;
  if (window.lucide) lucide.createIcons();
}

function togglePlay() {
  if (ST.timer) {
    parar();
    return;
  }
  if (ST.paso >= ST.arbol.length) irPaso(0);
  const btn = document.getElementById('btnPlay');
  btn.innerHTML = `<i data-lucide="pause" class="w-3.5 h-3.5"></i><span>Pausar</span>`;
  if (window.lucide) lucide.createIcons();

  const ms = parseInt(document.getElementById('velocidad').value, 10);
  ST.timer = setInterval(() => {
    if (ST.paso >= ST.arbol.length) {
      parar();
      return;
    }
    irPaso(ST.paso + 1);
  }, ms);
}

/* ==========================================================================
   Acciones Principales: Búsqueda y Comparación
   ========================================================================== */
async function calcularRuta() {
  const btn = document.getElementById('btnRuta');
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Calculando...</span>`;
  if (window.lucide) lucide.createIcons();

  try {
    const body = {
      origen: document.getElementById('origen').value,
      destino: document.getElementById('destino').value,
      algoritmo: sel('algo'),
      criterio: sel('crit')
    };

    const res = await fetch('/api/ruta', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(r => r.json());

    dibujarRuta(res);
    cargarArbol(res);

  } catch (err) {
    console.error('Error calculando ruta:', err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    if (window.lucide) lucide.createIcons();
  }
}

async function comparar() {
  const btn = document.getElementById('btnComparar');
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Comparando...</span>`;
  if (window.lucide) lucide.createIcons();

  try {
    const body = {
      origen: document.getElementById('origen').value,
      destino: document.getElementById('destino').value,
      criterio: sel('crit')
    };

    const data = await fetch('/api/comparar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(r => r.json());

    renderizarTablaComparativa(data, body);

  } catch (err) {
    console.error('Error comparando algoritmos:', err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    if (window.lucide) lucide.createIcons();
  }
}

/* ---------------- Renderizar Tabla Comparativa Avanzada ---------------- */
function renderizarTablaComparativa(data, body) {
  const rows = data.resultados;
  const metrica = body.criterio === 'distancia' ? 'distancia_total' : body.criterio === 'tiempo' ? 'tiempo_total' : 'costo_total';
  const mejor = Math.min(...rows.filter(r => r.exito).map(r => r[metrica]));

  // Valores máximos para las barras relativas
  const maxExpandidos = Math.max(...rows.map(r => r.nodos_expandidos), 1);
  const maxMetrica = Math.max(...rows.filter(r => r.exito).map(r => r[metrica]), 1);

  // Guardar resultados en ventana para inspección rápida
  window._ultimosResultadosComparacion = rows;

  const html = `
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs">
      <div class="flex items-center gap-2">
        <span class="px-2.5 py-1 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 font-semibold font-mono">
          ${body.origen} &rarr; ${body.destino}
        </span>
        <span class="text-slate-400">
          Criterio evaluado: <b class="text-white capitalize">${body.criterio}</b>
        </span>
      </div>
      <div class="text-[11px] text-emerald-400 flex items-center gap-1 font-medium">
        <i data-lucide="check-circle" class="w-3.5 h-3.5"></i>
        <span>Algoritmo con menor ${body.criterio} resaltado como ganador</span>
      </div>
    </div>

    <div class="border border-slate-700/80 rounded-xl overflow-hidden shadow-lg">
      <table class="w-full text-left border-collapse tabla-comparativa text-xs">
        <thead>
          <tr class="bg-slate-900 border-b border-slate-700 text-slate-300 font-semibold uppercase text-[10px] tracking-wider">
            <th class="py-3 px-4">Algoritmo</th>
            <th class="py-3 px-3 text-center">¿Ruta?</th>
            <th class="py-3 px-3 text-center">Saltos</th>
            <th class="py-3 px-3 text-right">Distancia (nm)</th>
            <th class="py-3 px-3 text-right">Tiempo (h)</th>
            <th class="py-3 px-3 text-right">Costo (USD)</th>
            <th class="py-3 px-4">Nodos Expandidos</th>
            <th class="py-3 px-3 text-right">Cómputo (ms)</th>
            <th class="py-3 px-3 text-center">Acción</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800">
          ${rows.map((r, idx) => {
            const esGanador = r.exito && r[metrica] === mejor;
            const meta = METADATA_ALGOS[r.algoritmo] || { badge: r.algoritmo, badgeColor: 'bg-slate-700' };
            const pctExpandidos = Math.round((r.nodos_expandidos / maxExpandidos) * 100);

            return `
              <tr class="${esGanador ? 'mejor' : ''} hover:bg-slate-800/50 transition-colors">
                
                <!-- Algoritmo & Badge -->
                <td class="py-3 px-4">
                  <div class="flex items-center gap-2">
                    ${esGanador ? '<span title="Óptimo en este criterio" class="text-amber-400 text-sm">🏆</span>' : ''}
                    <div>
                      <b class="text-white text-xs">${r.algoritmo.toUpperCase()}</b>
                      <span class="block text-[10px] text-slate-400 font-mono">${meta.badge}</span>
                    </div>
                  </div>
                </td>

                <!-- Éxito -->
                <td class="py-3 px-3 text-center">
                  ${r.exito
                    ? '<span class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-bold">Sí</span>'
                    : '<span class="px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 text-[10px] font-bold">No</span>'}
                </td>

                <!-- Saltos -->
                <td class="py-3 px-3 text-center font-mono font-mono-numbers text-slate-300">
                  ${r.profundidad}
                </td>

                <!-- Distancia -->
                <td class="py-3 px-3 text-right font-mono font-mono-numbers ${body.criterio === 'distancia' && esGanador ? 'text-emerald-400 font-bold' : 'text-slate-200'}">
                  ${r.distancia_total}
                </td>

                <!-- Tiempo -->
                <td class="py-3 px-3 text-right font-mono font-mono-numbers ${body.criterio === 'tiempo' && esGanador ? 'text-emerald-400 font-bold' : 'text-slate-200'}">
                  ${r.tiempo_total}
                </td>

                <!-- Costo -->
                <td class="py-3 px-3 text-right font-mono font-mono-numbers ${body.criterio === 'costo' && esGanador ? 'text-emerald-400 font-bold' : 'text-slate-200'}">
                  $${r.costo_total}
                </td>

                <!-- Barra de Nodos Expandidos -->
                <td class="py-3 px-4">
                  <div class="w-full">
                    <div class="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1">
                      <span>${r.nodos_expandidos} nodos</span>
                      <span>${pctExpandidos}%</span>
                    </div>
                    <div class="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full rounded-full ${r.algoritmo === 'astar' ? 'bg-cyan-400' : 'bg-slate-500'}" style="width: ${pctExpandidos}%"></div>
                    </div>
                  </div>
                </td>

                <!-- Tiempo Cómputo -->
                <td class="py-3 px-3 text-right font-mono font-mono-numbers text-slate-400">
                  ${r.tiempo_ms} ms
                </td>

                <!-- Acción Ver en Mapa -->
                <td class="py-3 px-3 text-center">
                  <button onclick="cargarResultadoEspecifico(${idx})" title="Visualizar esta ruta en el mapa y árbol" class="px-2 py-1 rounded bg-slate-800 hover:bg-cyan-600/30 text-slate-300 hover:text-cyan-300 border border-slate-700 text-[11px] transition-all flex items-center justify-center gap-1 mx-auto">
                    <i data-lucide="eye" class="w-3 h-3"></i>
                    <span>Ver</span>
                  </button>
                </td>

              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;

  document.getElementById('tabla').innerHTML = html;

  // Cargar visualmente la ruta ganadora
  const ganadora = rows.find(r => r.exito && r[metrica] === mejor);
  if (ganadora) {
    dibujarRuta(ganadora);
    cargarArbol(ganadora);
  }

  if (window.lucide) lucide.createIcons();
}

function cargarResultadoEspecifico(idx) {
  if (window._ultimosResultadosComparacion && window._ultimosResultadosComparacion[idx]) {
    const res = window._ultimosResultadosComparacion[idx];
    dibujarRuta(res);
    cargarArbol(res);
  }
}

// Iniciar aplicación
init();

/* ======================= CONFIG ======================= */
const METRIC_CFG = {
  mortality_rate: {
    label : 'Mortality (per 100 k)',
    value : p => p.mortality_rate ?? 0,
    colour: v => `rgb(0, 0, ${Math.min(v * 5, 255)})`,
    range : [2013, 2024],
    description: [
      '• WEEKLY all-cause deaths per 100 000 inhabitants.',
      '• Source: Eurostat - "demo_r_mwk3_ts".',
      '• Spatial resolution: NUTS-3 (district).',
      '• Coverage: 2013 - 2024 (weekly).'
    ]
  },

  population_density: {
    label : 'Population Density (km²)',
    value : p => p.population_density ?? 0,
    colour: v => `rgb(0, ${Math.min(v, 255)}, 0)`,
    range : [2000, 2023],
    description: [
      '• Annual population per km² (mid-year stock).',
      '• Source: Eurostat - "demo_r_d3dens".',
      '• Spatial resolution: NUTS-3.',
      '• Coverage: 2000 - 2023 (yearly).'
    ]
  },

  temperature_rcp45: {
    label : 'Temperature (°C)',
    value : p => p.temperature_rcp45 ?? -20,
    colour: v => `rgb(${Math.min((v + 20) * 5, 255)}, 0, 0)`,
    range : [2006, 2100],
    description: [
      '• Mean 2-m air temperature under medium-emission scenario RCP 4.5.',
      '• Source: EURO-CORDEX / ESGF, variable "tas".',
      '• Spatial resolution: 0.11° (~12 km); sampled at region centroid.',
      '• Coverage: 2006 - 2100 (monthly, interpolated to daily in this dash).'
    ]
  },

  temperature_rcp85: {
    label : 'Temperature (°C)',
    value : p => p.temperature_rcp85 ?? -20,
    colour: v => `rgb(${Math.min((v + 20) * 5, 255)}, 0, 0)`,
    range : [2006, 2100],
    description: [
      '• Mean 2-m air temperature under high-emission scenario RCP 8.5.',
      '• Source: EURO-CORDEX / ESGF, variable "tas".',
      '• Spatial resolution: 0.11° (~12 km); sampled at region centroid.',
      '• Coverage: 2006 - 2100 (monthly, interpolated to weekly for the dashboard).'
    ]
  }
};

/* ======================= MAP INIT ======================= */
// take the first metric as default
let currentMetric = Object.keys(METRIC_CFG)[0];
const map = L.map('map', { zoomControl: false })
            .setView([FLASK_CTX.centerLat, FLASK_CTX.centerLon], FLASK_CTX.zoom);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
let geoJsonLayer = null;

/* ======================= DATA LOAD ======================= */
function loadGeoJSON(region, year, week) {
  return fetch(`/api/data?region=${region}&year=${year}&week=${week}&metric=${currentMetric}`)
    .then(r => r.json())
    .then(data => {
      if (geoJsonLayer) map.removeLayer(geoJsonLayer);
      geoJsonLayer = L.geoJSON(data, {
        style: featureStyle,
        onEachFeature
      }).addTo(map);
      return geoJsonLayer.getBounds();      // return bounds for drill-down
    })
    .catch(err => console.error('Error fetching data:', err));
}

/* ======================= STYLING ======================= */
function featureStyle(feature) {
  const cfg = METRIC_CFG[currentMetric];
  const val = cfg.value(feature.properties);
  return {
    fillColor: cfg.colour(val),
    fillOpacity: 0.7,
    weight: 1,
    color: '#666'
  };
}

/* ---------- helper: placeholder graph ---------- */
function resetGraph() {
  const holder = document.getElementById('graph');
  holder.innerHTML =
    '<div style="color:#555;font:14px/1.4em system-ui, sans-serif;'+
    'text-align:center;padding-top:40%;opacity:0.8;">'+
    'Click on a region to display its information</div>';
}

/* ========  NAVIGATION (breadcrumb + drill-down)  ======== */
const viewStack = [];  // [{nutsID, name}]

function renderBreadcrumb() {
  const div = document.getElementById('breadcrumb');
  div.innerHTML = viewStack.map((v,i) =>
      `<span data-d="${i}">${v.name}</span>${i<viewStack.length-1?'<span class="sep">></span>':''}`
  ).join('');
  div.querySelectorAll('span[data-d]')
     .forEach(el => el.onclick = () => popTo(+el.dataset.d));
}

function pushView(nutsID, name) {
  if (viewStack.at(-1)?.nutsID === nutsID) return;   // avoid duplicate push
  viewStack.push({ nutsID, name });
  renderBreadcrumb();
}

function popTo(depth) {
  viewStack.splice(depth + 1);
  renderBreadcrumb();

  const top = viewStack.at(-1);
  const name = top.name || 'Europe';
  const nutsID = top.nutsID || 'EU';
  changeRegion(nutsID, name);  // drill down to the top view
}

/* Change the region in the map and update the breadcrumb. */
function changeRegion(nutsID, name) {
  // We get the bounding box for the selected region
  fetch(`/api/bbox?nuts_id=${nutsID || 'EU'}`)
    .then(r => r.json())
    .then(({ bbox, center, zoom }) => {
      map.fitBounds(bbox);
      map.setView(center, zoom);
    })
    .catch(err => console.error('Error fetching bbox:', err));
  // Change the current region nutsID
  FLASK_CTX.nutsID = nutsID;
  // Update the breadcrumb
  pushView(nutsID, name);
  // Load the new region shapes
  loadGeoJSON(FLASK_CTX.nutsID, yearSlider.value, weekSlider.value);
}

/* ======================= INFO ======================= */  
function updateInfoPanel(metric) {
  const holder = document.getElementById('infoPanel');
  const cfg = METRIC_CFG[metric];
  holder.innerHTML = `
    <h3>${cfg.label}</h3>
    <ul>
      ${cfg.description.map(line => `<li>${line.replace(/^•\s*/, '')}</li>`).join('')}
    </ul>
  `;
}

/* =================== POPUP + CHART ===================== */
function onEachFeature(feature, layer) {
  const p = feature.properties;

  // Build the list only with fields that exist
  const popupLines = [`<b>${p.name}</b>`];

  if (p.mortality_rate   != null) popupLines.push(`Mortality: ${p.mortality_rate} per 100 k`);
  if (p.population_density != null) popupLines.push(`Population Density: ${p.population_density} per km²`);
  if (p.temperature_rcp45 != null) popupLines.push(`Temp (RCP 4.5): ${p.temperature_rcp45} °C`);
  if (p.temperature_rcp85 != null) popupLines.push(`Temp (RCP 8.5): ${p.temperature_rcp85} °C`);

  const nutsID = (p.NUTS_ID ?? '').toUpperCase();
  const name = (p.name ?? 'Unnamed');
  if (nutsID.length === 2) {
    popupLines.push(`<button onclick="changeRegion('${nutsID}', '${name}')">District view</button>`);
  }

  layer.bindPopup(popupLines.join('<br>'));

  // Click -> show time-series
  layer.on('click', () => {
    drawTimeSeries(p.NUTS_ID, p.name);
  });
}

/* ---------- Time-series ---------- */
let currentChart = null;

function drawTimeSeries(nutsId, regionName) {
  const cfg = METRIC_CFG[currentMetric];

  fetch(`/api/data/ts?region=${FLASK_CTX.nutsID}&metric=${currentMetric}&nuts_id=${nutsId}`)
    .then(r => r.json())
    .then(res => {
      if (!res.data || !res.data.length) return;

      /* labels & values */
      const labels = res.data.map(d => `${d.year}-W${String(d.week).padStart(2, '0')}`);
      const values = res.data.map(d => d.value);

      /* prepare a fresh canvas each click */
      const holder = document.getElementById('graph');
      holder.innerHTML = '';                          // remove any previous canvas
      const canvas = document.createElement('canvas');
      holder.appendChild(canvas);

      new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label : `${cfg.label} - ${regionName}`,
            data  : values,
            borderColor   : '#6dc201',
            backgroundColor: '#6dc2014d',
            fill  : true,
            tension: 0.25,
            pointRadius: 0,
            pointHitRadius: 20
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { ticks: { autoSkip: true, maxTicksLimit: 12 } },
            y: { beginAtZero: true }
          }
        }
      });
    })
    .catch(err => console.error('Error loading TS:', err));
}

/* ==================== EVENT HANDLERS =================== */
const yearSlider = document.getElementById('yearSlider');
const weekSlider = document.getElementById('weekSlider');
const metricSelect = document.getElementById('metricSelect');
const yearValue = document.getElementById('yearValue');
const weekValue = document.getElementById('weekValue');
let debounce;

/* --- helper to (re)range the year slider --- */
function applyYearRange([minYear, maxYear]) {
  yearSlider.min = minYear;
  yearSlider.max = maxYear;

  if (+yearSlider.value < minYear) yearSlider.value = minYear;
  if (+yearSlider.value > maxYear) yearSlider.value = maxYear;

  yearValue.textContent = yearSlider.value;
}

yearSlider.oninput = () => {
  yearValue.textContent = yearSlider.value;
  clearTimeout(debounce);
  debounce = setTimeout(() => loadGeoJSON(FLASK_CTX.nutsID, yearSlider.value, weekSlider.value), 250);
};

weekSlider.oninput = () => {
  weekValue.textContent = weekSlider.value;
  clearTimeout(debounce);
  debounce = setTimeout(() => loadGeoJSON(FLASK_CTX.nutsID, yearSlider.value, weekSlider.value), 250);
};

metricSelect.onchange = () => {
  currentMetric = metricSelect.value;
  applyYearRange(METRIC_CFG[currentMetric].range);
  loadGeoJSON(FLASK_CTX.nutsID, yearSlider.value, weekSlider.value);
  if (currentChart) { currentChart.destroy(); currentChart = null; }
  resetGraph();
  updateInfoPanel(currentMetric);
};

/* ====================== START-UP ====================== */
applyYearRange(METRIC_CFG[currentMetric].range);
pushView('EU', 'Europe');
loadGeoJSON(FLASK_CTX.nutsID, yearSlider.value, weekSlider.value);
resetGraph();
updateInfoPanel(currentMetric);

/* ======================= CONFIG ======================= */

const mortalityColour = v => {
  if (v < 0)   return '#000000';   // black
  if (v < 5)   return '#66c2a5';   // light blue
  if (v < 10)  return '#abdda4';   // teal
  if (v < 15)  return '#e6f598';   // light green
  if (v < 20)  return '#fee08b';   // yellow
  if (v < 25)  return '#fdae61';   // orange
  return '#d7191c';                // red
};

const populationDensityColour = v => {
  if (v < 0)   return '#000000';   // black
  if (v < 50) return '#000066';   // IE dark blue
  if (v < 100) return '#47bfff';   // IE light blue
  if (v < 200) return '#e6f598';   // mixed blue to green
  return '#6dc201';                // IE green
};

/* --- shared, step-wise palette for all temperature metrics ------------- */
const tempColour = v => {
  if (v < -90) return '#000000';   // black
  if (v < 0)   return '#2b83ba';   // deep blue
  if (v < 5)   return '#66c2a5';   // light blue
  if (v < 10)  return '#abdda4';   // teal
  if (v < 15)  return '#e6f598';   // light green
  if (v < 20)  return '#fee08b';   // yellow
  if (v < 25)  return '#fdae61';   // orange
  return '#d7191c';                // red (≥ 25 °C)
};

const METRIC_CFG = {
  mortality_rate: {
    label : 'Mortality (per 100 k)',
    value : p => p.mortality_rate ?? -99,
    colour: mortalityColour,
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
    value : p => p.population_density ?? -99,
    colour: populationDensityColour,
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
    value : p => p.temperature_rcp45 ?? -99,
    colour: tempColour, 
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
    value : p => p.temperature_rcp85 ?? -99,
    colour: tempColour,
    range : [2006, 2100],
    description: [
      '• Mean 2-m air temperature under high-emission scenario RCP 8.5.',
      '• Source: EURO-CORDEX / ESGF, variable "tas".',
      '• Spatial resolution: 0.11° (~12 km); sampled at region centroid.',
      '• Coverage: 2006 - 2100 (monthly, interpolated to weekly for the dashboard).'
    ]
  }
};

/* ======================= INIT PARAMS ====================== */
Chart.register(window.ChartZoom);   // make Chart.js aware of the plugin

/* ======================= MAP ======================= */

// take the first metric as default
let currentMetric = Object.keys(METRIC_CFG)[0];
const map = L.map('map', {
  zoomControl: false,
  doubleClickZoom: false
  }).setView([FLASK_CTX.centerLat, FLASK_CTX.centerLon], FLASK_CTX.zoom);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
let geoJsonLayer = null;

/* --- helper: to style GeoJSON features --- */
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

/* ---------- helper: what to do on each feature (variable)? ---------- */
function onEachFeature(feature, layer) {
  const p = feature.properties;

  // Click -> show time-series
  layer.on('click', () => {
    drawTimeSeries(p.NUTS_ID, p.name);
    // Hold the region info to avoid flickering
    if (holdRegionInfo !== p.NUTS_ID) {
      holdRegionInfo = p.NUTS_ID;
      drawregionInfo(feature);  // display region info
    } else {
      holdRegionInfo = null;  // reset if clicked again
    }
  });

  // Double click -> zoom in on the region
  layer.on('dblclick', () => {
    changeRegion(p.NUTS_ID, p.name);
  });

  /* hover glue  */
  layer.on({
    mouseover: e => {
      if (holdRegionInfo === null) {drawregionInfo(feature)};
      e.target.setStyle(highlightStyle());
      // keep it on top so the thick edge isn't hidden
      if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
        e.target.bringToFront();
      }
    },
    mouseout: e => {
      geoJsonLayer.resetStyle(e.target);   // revert to normal style()
    }
  });
}

/* --- Load the initial GeoJSON data for the default region --- */
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

/* ---------- helper: placeholder regionInfo ---------- */
function resetPopup() {
  const holder = document.getElementById('regionInfo');
  holder.innerHTML =
    '<div style="color:#555;font:14px/1.4em system-ui, sans-serif;'+
    'text-align:center;padding-top:40%;opacity:0.8;">'+
    'Click on a region to display its information</div>';
}

/* ---------- a helper that returns the highlight style ---------- */
function highlightStyle() {
  return { weight: 3, color: '#fff', fillOpacity: 0.7 };   // thicker, darker edge
}

/* ---------- regionInfo ---------- */
let holdRegionInfo = null;  // hold the last region info to avoid flickering

function drawregionInfo(feature) {
  const p = feature.properties;

  // Build the list only with fields that exist
  const popupLines = [`<b>${p.name}</b>`];

  if (p.mortality_rate   != null) popupLines.push(`Mortality: ${p.mortality_rate} per 100 k`);
  if (p.population_density != null) popupLines.push(`Population Density: ${p.population_density} per km²`);
  if (p.temperature_rcp45 != null) popupLines.push(`Temperature (RCP 4.5): ${p.temperature_rcp45} °C`);
  if (p.temperature_rcp85 != null) popupLines.push(`Temperature (RCP 8.5): ${p.temperature_rcp85} °C`);

  const nutsID = (p.NUTS_ID ?? '').toUpperCase();
  // If this code does not appear in /api/bbox, we do not display the button
  if (FLASK_CTX.availableIDs.includes(nutsID)) {
    popupLines.push(`<i>(Double click to zoom in)</i>`);
  }

  // If no info is available for this region, we show a message
  if (popupLines.length === 1) {
    popupLines.push('<i>No information available for this region</i>');
  }

  // Update the regionInfo
  const holder = document.getElementById('regionInfo');
  holder.innerHTML = popupLines.join('<br>');
}

/* ========  BREADCRUMB  ======== */
/* This breadcrumb controls the region levels in the map. */

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
  // First we make sure the region is valid
  if (!FLASK_CTX.availableIDs.includes(nutsID)) {
    return;
  }

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

/* ==================== SPLITTER DRAGGING =================== */

const splitter = document.getElementById('splitter');
const sidebar  = document.getElementById('sidebar');
let isDragging = false;

splitter.addEventListener('mousedown', () => {
  isDragging = true;
  document.body.style.cursor = 'col-resize';
  splitter.style.backgroundColor = '#6dc201';  // change splitter color on drag
});

document.addEventListener('mousemove', e => {
  if (!isDragging) return;
  // Calculate new width, but clamp between min/max
  const newWidth = Math.min(
    Math.max(e.clientX, 150),        // no less than 150px
    window.innerWidth * 0.6          // no more than 60% of viewport
  );
  sidebar.style.width = newWidth + 'px';
  map.invalidateSize();             // if using Leaflet, tell it to reflow
});

document.addEventListener('mouseup', () => {
  if (isDragging) {
    isDragging = false;
    document.body.style.cursor = '';
  }
  splitter.style.backgroundColor = '';  // reset splitter color
});

/* =================== LEFT SIDEBAR ===================== */

/* -------------- Year & Week Sliders ---------- */
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

/* ----------Information panel ---------- */
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

      /* auto-centre:  ±10 years around the current slider year */
      const curYear = +yearSlider.value;
      const minYear = Math.max(curYear - 10, +labels[0].slice(0,4));
      const maxYear = Math.min(curYear + 10, +labels.at(-1).slice(0,4));
      const minLabel = labels.findIndex(s => +s.slice(0,4) >= minYear);
      const maxLabel = labels.findLastIndex(s => +s.slice(0,4) <= maxYear);

      /* prepare a fresh canvas each click */
      const holder = document.getElementById('regionGraph');
      holder.innerHTML = '<canvas></canvas>';
      const ctx = holder.firstChild.getContext('2d');

      if (currentChart) currentChart.destroy();

      currentChart = new Chart(ctx, {
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
            x: {
              ticks : { autoSkip: true, maxTicksLimit:12 },
              min   : labels[minLabel],
              max   : labels[maxLabel]
            },
            y: { beginAtZero:true }
          },
          /* ------------ Zoom / Pan only on X ------------- */
          plugins: {
            zoom: {
              limits: { x: {min: labels[0], max: labels.at(-1)} },
              zoom: {
                wheel   : { enabled:true },
                mode    : 'x'
              },
              pan: {
                enabled: true,   // allow panning
                mode   : 'x'     // x-axis only
              }              
            }
          }
        }
      });
    })
    .catch(err => console.error('Error loading TS:', err));
}

/* ---------- helper: reset the time series ---------- */
function resetGraph() {
  const holder = document.getElementById('regionGraph');
  holder.innerHTML =
    '<div style="color:#555;font:14px/1.4em system-ui, sans-serif;'+
    'text-align:center;padding-top:40%;opacity:0.8;">'+
    'Click on a region to display its information</div>';
}

/* ====================== START-UP ====================== */
applyYearRange(METRIC_CFG[currentMetric].range);
pushView('EU', 'Europe');
loadGeoJSON(FLASK_CTX.nutsID, yearSlider.value, weekSlider.value);
resetPopup();
resetGraph();
updateInfoPanel(currentMetric);

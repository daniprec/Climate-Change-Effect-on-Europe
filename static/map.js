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
    ],
    url: 'https://doi.org/10.2908/DEMO_R_MWK3_TS',
    colorbarStops: [[0, "#ffffcc"], [0.5, "#fd8d3c"], [1, "#800026"]],
    colorbarMin: "0",
    colorbarMax: "1500"
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
    ],
    url: 'https://doi.org/10.2908/DEMO_R_D3DENS',
    colorbarStops: [[0, "#000066"], [0.33, "#47bfff"], [0.66, "#e6f598"], [1, "#6dc201"]],
    colorbarMin: "0",
    colorbarMax: "500"
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
    ],
    url: 'https://cordex.org/data-access/cordex-cmip5-data/cordex-cmip5-esgf/',
    colorbarStops: [[0, "#4575b4"], [0.5, "#fee090"], [1, "#d73027"]],
    colorbarMin: "-5",
    colorbarMax: "40"
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
    ],
    url: 'https://cordex.org/data-access/cordex-cmip5-data/cordex-cmip5-esgf/',
    colorbarStops: [[0, "#4575b4"], [0.5, "#fee090"], [1, "#d73027"]],
    colorbarMin: "-5",
    colorbarMax: "40"
  }
};

/* ======================= INIT PARAMS ====================== */
Chart.register(window.ChartZoom);   // make Chart.js aware of the plugin

/* ======================= MAP ======================= */

const map = L.map('map', {
  zoomControl: false,
  doubleClickZoom: false
  }).setView([FLASK_CTX.centerLat, FLASK_CTX.centerLon], FLASK_CTX.zoom);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
let geoJsonLayer = null;

/* --- helper: to style GeoJSON features (metrics) --- */
function featureStyle(feature) {
  const cfg = METRIC_CFG[mainMetric];
  const val = cfg.value(feature.properties);
  return {
    fillColor: cfg.colour(val),
    fillOpacity: 0.7,
    weight: 1,
    color: '#666'
  };
}

/* ---------- helper: what to do on each feature (metric)? ---------- */
function onEachFeature(feature, layer) {
  const p = feature.properties;

  let clickTimeout = null;  // to prevent double-clicks from triggering single-click logic

  // Click -> show time-series
  layer.on('click', () => {
    if (clickTimeout !== null) return;  // prevent double click from triggering single-click logic

      clickTimeout = setTimeout(() => {
        clickTimeout = null;
      drawTimeSeries(p.NUTS_ID, p.name);
      // Hold the region info to avoid flickering
      if (holdRegionInfo.NUTS_ID !== p.NUTS_ID) {
        holdRegionInfo.NUTS_ID = p.NUTS_ID;
        holdRegionInfo.name = p.name;
        drawRegionInfo(feature);  // display region info
        // if we are in mobile mode, open the sidebar
        if (window.innerWidth < 768) {
          sidebarOpenClose();  // open sidebar on mobile
          // and automatically scroll down to the graph section
          document.getElementById('regionGraph').scrollIntoView({ behavior: 'smooth' });
      }
      } else {
        holdRegionInfo.NUTS_ID = null;  // reset if clicked again
      }
    }, 250);  // wait for double-click timeout
  });

  // Double click -> zoom in on the region
  layer.on('dblclick', () => {
    changeRegion(p.NUTS_ID, p.name);
  });

  /* hover glue  */
  layer.on({
    mouseover: e => {
      if (holdRegionInfo.NUTS_ID == null) {drawRegionInfo(feature)};
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
function loadGeoJSON(map_id, year, week) {
  return fetch(`/api/data?map_id=${map_id}&year=${year}&week=${week}&metric=${mainMetric}`)
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

/* ---------- a helper that returns the highlight style ---------- */
function highlightStyle() {
  return { weight: 3, color: '#fff', fillOpacity: 0.7 };   // thicker, darker edge
}

/* ---------- regionInfo ---------- */
let holdRegionInfo = {
  NUTS_ID: null,
  name: null
};  // hold the last region info to avoid flickering

function drawRegionInfo(feature) {
  const p = feature.properties;

  // Build the list only with fields that exist
  const popupLines = [`<b>${p.name}</b>`];

  if (p.mortality_rate   != null) popupLines.push(`Mortality: ${p.mortality_rate} per 100 k`);
  if (p.population_density != null) popupLines.push(`Population Density: ${p.population_density} per km²`);
  if (p.temperature_rcp45 != null) popupLines.push(`Temperature (RCP 4.5): ${p.temperature_rcp45} °C`);
  if (p.temperature_rcp85 != null) popupLines.push(`Temperature (RCP 8.5): ${p.temperature_rcp85} °C`);

  const nutsID = (p.NUTS_ID ?? '').toUpperCase();
  // If this code does not appear in /api/bbox, we do not display the button
  if (FLASK_CTX.availableMapIDs.includes(nutsID)) {
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

/* --- Colorbar for the current metric --- */

function updateColorbar(metric) {
  const cfg = METRIC_CFG[metric];
  if (!cfg || !cfg.colorbarStops) {
    console.warn(`Missing colorbar configuration for ${metric}`);
    return;
  }

  const canvas = document.getElementById("colorbar-canvas");
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  const gradient = ctx.createLinearGradient(0, 0, width, 0);
  cfg.colorbarStops.forEach(([offset, color]) => {
    gradient.addColorStop(offset, color);
  });

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  // Update labels
  document.getElementById("colorbar-label").textContent = cfg.label;
  document.getElementById("colorbar-min").textContent = cfg.colorbarMin ?? '';
  document.getElementById("colorbar-max").textContent = cfg.colorbarMax ?? '';
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

function pushView(mapID, name) {
  if (viewStack.at(-1)?.mapID === mapID) return;   // avoid duplicate push
  viewStack.push({ mapID, name });
  renderBreadcrumb();
}

function popTo(depth) {
  viewStack.splice(depth + 1);
  renderBreadcrumb();

  const top = viewStack.at(-1);
  const name = top.name || 'Europe';
  const mapID = top.mapID || 'EU';
  changeRegion(mapID, name);  // drill down to the top view
}

/* Change the region in the map and update the breadcrumb. */
function changeRegion(mapID, name) {
  // First we make sure the region is valid
  if (!FLASK_CTX.availableMapIDs.includes(mapID)) {
    return;
  }

  // We get the bounding box for the selected region
  fetch(`/api/bbox?nuts_id=${mapID || 'EU'}`)
    .then(r => r.json())
    .then(({ bbox, center, zoom }) => {
      map.fitBounds(bbox);
      map.setView(center, zoom);
    })
    .catch(err => console.error('Error fetching bbox:', err));
  // Change the current region mapID
  FLASK_CTX.mapID = mapID;
  // Update the breadcrumb
  pushView(mapID, name);
  // Load the new region shapes
  loadGeoJSON(FLASK_CTX.mapID, yearSlider.value, weekSlider.value);
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
const compareSelect = document.getElementById('compareSelect');
const yearValue = document.getElementById('yearValue');
const weekValue = document.getElementById('weekValue');
const rangeButtons  = document.getElementById('rangeButtons').querySelectorAll('button');

let debounce;

let mainMetric = metricSelect.value;
let compareMetric = compareSelect.value || null;

/* --- helper to (re)range the year slider --- */
function applyYearRange([minYear, maxYear]) {
  yearSlider.min = minYear;
  yearSlider.max = maxYear;

  if (+yearSlider.value < minYear) yearSlider.value = minYear;
  if (+yearSlider.value > maxYear) yearSlider.value = maxYear;

  yearValue.textContent = yearSlider.value;
  weekValue.textContent = weekSlider.value;
}

yearSlider.oninput = () => {
  yearValue.textContent = yearSlider.value;
  updateWeekLabel();
  clearTimeout(debounce);
  debounce = setTimeout(() => loadGeoJSON(FLASK_CTX.mapID, yearSlider.value, weekSlider.value), 250);
  drawTimeSeries(holdRegionInfo.NUTS_ID, holdRegionInfo.name);  // redraw TS for the new year
};

function getOrdinal(n) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function getISOWeekStartDate(year, week) {
  const simple = new Date(year, 0, 1 + (week - 1) * 7);
  const dow = simple.getDay();
  const ISOweekStart = new Date(simple);
  if (dow <= 4)
    ISOweekStart.setDate(simple.getDate() - simple.getDay() + 1);
  else
    ISOweekStart.setDate(simple.getDate() + 8 - simple.getDay());
  return ISOweekStart;
}

function updateWeekLabel() {
  const week = parseInt(weekSlider.value);
  const year = parseInt(yearSlider.value);
  const startDate = getISOWeekStartDate(year, week);
  const endDate = new Date(startDate);
  endDate.setDate(startDate.getDate() + 6); // one full week

  const startMonth = startDate.toLocaleString('default', { month: 'short' });
  const endMonth = endDate.toLocaleString('default', { month: 'short' });

  const startStr = `${startMonth} ${getOrdinal(startDate.getDate())}`;
  const endStr = `${endMonth} ${getOrdinal(endDate.getDate())}`;

  weekValue.textContent = `${week} (${startStr} - ${endStr})`;
}

weekSlider.oninput = () => {
  updateWeekLabel();
  clearTimeout(debounce);
  debounce = setTimeout(() => loadGeoJSON(FLASK_CTX.mapID, yearSlider.value, weekSlider.value), 250);
};

metricSelect.onchange = () => {
  mainMetric = metricSelect.value;
  applyYearRange(METRIC_CFG[mainMetric].range);
  updateWeekLabel();
  loadGeoJSON(FLASK_CTX.mapID, yearSlider.value, weekSlider.value);
  updateMetricInfo(mainMetric);
  updateColorbar(mainMetric);
  drawTimeSeries(holdRegionInfo.NUTS_ID, holdRegionInfo.name);  // redraw TS for the new metric
};

compareSelect.onchange = () => {
  compareMetric = compareSelect.value || null;
  drawTimeSeries(holdRegionInfo.NUTS_ID, holdRegionInfo.name);
};

/* ----------Information panel ---------- */
function updateMetricInfo(metric) {
  const cfg = METRIC_CFG[metric];
  document.getElementById('metricTitle').textContent = cfg.label;

  const ul = document.getElementById('metricDesc');
  ul.innerHTML = cfg.description.map(line => `<li>${line.replace(/^•\s*/, '')}</li>`).join('');

  const btn = document.getElementById('metricSource');
  if (cfg.url) {
    btn.style.display = 'inline-block';
    btn.onclick = () => window.open(cfg.url, '_blank');
  } else {
    btn.style.display = 'none';
  }
}

/* ---------- Time-series ---------- */
let currentChart = null;

// parse a range string like "10Y" or "5M" into an object
function parseRange(r) {
  const num = +r.slice(0, -1);
  switch (r.slice(-1)) {
    case 'M': return num / 24 ;
    case 'Y': return num / 2;
  }
  return 5;
}
let activeRange = 5;  // default +/-10 years
rangeButtons.forEach(btn => {
  btn.onclick = () => {
    rangeButtons.forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    activeRange = parseRange(btn.dataset.range);
    drawTimeSeries(holdRegionInfo.NUTS_ID, holdRegionInfo.name);  // redraw TS for the new range
  };
});

// inject or replace the <canvas> inside #regionGraph
function prepareCanvas() {
  const holder = document.getElementById('regionGraph');
  holder.innerHTML = '<canvas></canvas>';
  return holder.querySelector('canvas').getContext('2d');
}

// actually render Chart.js with two Y-axes
function renderDualAxisChart(labels, data1, data2, m1, m2, regionName) {
  const ctx = prepareCanvas();
  if (currentChart) currentChart.destroy();

  const datasets = [{
    label   : `${METRIC_CFG[m1].label} — ${regionName}`,
    data    : data1,
    yAxisID : 'yLeft',
    borderColor: '#6dc201',
    backgroundColor: '#6dc2014d',
    fill  : true,
    tension: 0.25,
    pointRadius: 0,
    pointHitRadius: 20
  }];

  if (m2) {
    datasets.push({
      label   : `${METRIC_CFG[m2].label} — ${regionName}`,
      data    : data2,
      yAxisID : 'yRight',
      borderColor: '#000066',
      fill: false,
      // prevent grid lines from cluttering
      grid: { drawOnChartArea: false }
    });
  }

  // assume `activeRange` is in years
  const curYear  = +yearSlider.value;
  const curWeek  = +weekSlider.value;
  const weekCount = 53;               // enough to cover any ISO week overlap

  // flatten current position to a single number
  const curIndex = curYear * weekCount + curWeek;
  const delta    = activeRange * weekCount;

  // precompute label-indices once
  const labelIndices = labels.map(l => {
    // l === "2023-W05"
    const [yearStr, weekStr] = l.split('-W');
    const y = +yearStr, w = +weekStr;
    return y * weekCount + w;
  });

  // now find min/max positions
  let minTarget = curIndex - delta;
  let maxTarget = curIndex + delta;

  // if the minTarget goes below the first label, we need to adjust the
  // maxTarget to account for that difference
  if (minTarget < labelIndices[0]) {
    const diff = labelIndices[0] - minTarget;
    // adjust maxTarget to keep the range size
    maxTarget += diff;
  }
  // if the maxTarget goes above the last label, we need to adjust the
  // minTarget to account for that difference
  if (maxTarget > labelIndices.at(-1)) {
    const diff = maxTarget - labelIndices.at(-1);
    // adjust minTarget to keep the range size
    minTarget -= diff;
  }

  const minLabel = labelIndices.findIndex(idx => idx >= minTarget);
  const maxLabel = labelIndices.map((idx, i) => idx <= maxTarget ? i : -1)
                              .filter(i => i >= 0).pop();

  currentChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ticks : { autoSkip: true, maxTicksLimit:12 },
          min   : labels[minLabel],
          max   : labels[maxLabel]
        },
        yLeft: {
          beginAtZero:true,
          type:'linear',
          position:'left',
          title:{ display:true, text: METRIC_CFG[m1].label }
        },
        // only show right axis if comparing
        ...(m2 && {
          yRight: {
            beginAtZero:true,
            type:'linear',
            position:'right',
            title:{ display:true, text: METRIC_CFG[m2].label }
          }
        })
      },
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
}

// fetch both series in parallel, then render
function drawTimeSeries(nutsId, regionName) {
  // if the region is not selected, do nothing
  if (!nutsId || nutsId === 'EU') {
    document.getElementById('regionGraph').innerHTML = '<p>Select a region to see the time-series.</p>';
    return;
  }

  // build two fetches
  const p1 = fetch(
    `/api/data/ts?map_id=${FLASK_CTX.mapID}&metric=${mainMetric}&nuts_id=${nutsId}`
  ).then(r=>r.json());

  const p2 = compareMetric
    ? fetch(
        `/api/data/ts?map_id=${FLASK_CTX.mapID}&metric=${compareMetric}&nuts_id=${nutsId}`
      ).then(r=>r.json())
    : Promise.resolve({ data: [] });

  Promise.all([p1, p2]).then(([res1, res2]) => {
    const labels = res1.data.map(d => `${d.year}-W${String(d.week).padStart(2,'0')}`);
    const data1  = res1.data.map(d => d.value);
    const data2  = res2.data.map(d => d.value);
    renderDualAxisChart(labels, data1, data2, mainMetric, compareMetric, regionName);
  }).catch(console.error);
}

/* --- Download data button --- */
document.getElementById('downloadData').addEventListener('click', () => {
  const metric1 = mainMetric;
  const metric2 = compareMetric || 'none';  // if no comparison, use 'none'
  const nutsID = holdRegionInfo.NUTS_ID || 'none';  // use selected region or 'EU' if none
  const url = `/api/data/download?map_id=${FLASK_CTX.mapID}&nuts_id=${nutsID}&metric=${metric1}&metric2=${metric2}`;
  window.open(url, '_blank');
});

/* === MOBILE MENU === */
const menuIcon = document.getElementById('menuToggle');
const sidebarContainer = document.getElementById('sidebarContainer');

function sidebarOpenClose() {
  /* If the sidebar is already active, remove it */
  if (sidebarContainer.classList.contains('active')) {
    sidebarContainer.classList.remove('active');
    /* Change the menu icon back to bars */
    menuIcon.innerHTML = '<i class="fa-solid fa-bars"></i>';
  } else {
    /* If the sidebar is not active, show it */
    sidebarContainer.classList.add('active');
    /* Change the menu icon to a cross */
    menuIcon.innerHTML = '<i class="fa-solid fa-xmark"></i>';
  }
}

document.getElementById('menuToggle').addEventListener('click', () => {
  sidebarOpenClose();
});

/* ====================== START-UP ====================== */
applyYearRange(METRIC_CFG[mainMetric].range);
pushView('EU', 'Europe');
loadGeoJSON(FLASK_CTX.mapID, yearSlider.value, weekSlider.value);
updateWeekLabel();
updateMetricInfo(mainMetric);
updateColorbar(mainMetric);

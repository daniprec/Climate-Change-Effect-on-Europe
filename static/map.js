/* ======================= IMPORTS ====================== */
import { METRIC_CFG } from './config.js';
import { drawTimeSeries, drawRRCurve } from './plot.js';

/* ======================= INIT PARAMS ====================== */
Chart.register(window.ChartZoom);   // make Chart.js aware of the plugin

/* ======================= MOBILE MODE ====================== */
// Set a global variable (attached to window)
window.isMobile = window.innerWidth <= 768;

// Function to check and update the global variable
function checkWindowSize() {
  const currentMobile = window.innerWidth <= 768;
  if (window.isMobile !== currentMobile) {
    window.isMobile = currentMobile;
  }
}

// Initial check
checkWindowSize();

// Attach listener to window resize
window.addEventListener("resize", checkWindowSize);

// If the window is resized, reload the GeoJSON data
window.addEventListener("resize", () => {
  loadGeoJSON(FLASK_CTX.mapID, yearSlider.value, weekSlider.value, sexSelect.value, ageSelect.value);
});

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

  // Display the name as tooltip
  layer.bindTooltip(p.name, {
    direction: 'top',
    sticky: true
  });

  if (holdRegionProperties.NUTS_ID === p.NUTS_ID) {
    writeRegionProperties(feature);  // if we are holding this region, display its info
  }

  let clickTimeout = null;  // to prevent double-clicks from triggering single-click logic

  // timeout depends whether we are on mobile or desktop
  let timeout = window.isMobile ? 500 : 0;  // 500ms on mobile, none on desktop

  // Click -> show time-series
  layer.on('click', () => {
    if (clickTimeout !== null) return;  // prevent double click from triggering single-click logic

      clickTimeout = setTimeout(() => {
        clickTimeout = null;
        drawTimeSeries(
          p.NUTS_ID,
          p.name,
          mainMetric,
          compareMetric,
          sexSelect.value,
          ageSelect.value,
          FLASK_CTX,
          activeRange
        );
        hideRRCurve();
      // Hold the region info to avoid flickering
      if (holdRegionProperties.NUTS_ID !== p.NUTS_ID) {
        holdRegionProperties.NUTS_ID = p.NUTS_ID;
        holdRegionProperties.name = p.name;
        writeRegionProperties(feature);  // display region info
        // if we are in mobile mode, open the sidebar
        if (window.isMobile) {
          sidebarOpenClose();  // open sidebar on mobile
          // and automatically scroll down to the graph section
          document.getElementById('regionGraph').scrollIntoView({ behavior: 'smooth' });
      }
      } else {
        holdRegionProperties.NUTS_ID = null;  // reset if clicked again
        holdRegionProperties.name = null;
      }
    }, timeout);  // wait for double-click timeout
  });

  // Double click -> zoom in on the region
  layer.on('dblclick', () => {
    changeRegion(p.NUTS_ID, p.name);
    hideRRCurve();
  });

  /* hover glue  */
  layer.on({
    mouseover: e => {
      
      if (holdRegionProperties.NUTS_ID == null) {writeRegionProperties(feature)};
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
function loadGeoJSON(map_id, year, week, sex, age) {
  return fetch(
    `/api/data?map_id=${map_id}&year=${year}&week=${week}&metric=${mainMetric}`
    +`&sex=${sex}&age=${age}`)
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
let holdRegionProperties = {
  NUTS_ID: null,
  name: null
};  // hold the last region info to avoid flickering

function writeRegionProperties(feature) {
  const p = feature.properties;

  // Build the list only with fields that exist
  const popupLines = [`<b>${p.name}</b>`];
  
  popupLines.push(`<span style="font-size: smaller;">${p.year} ${weekStartEnd}<br></span>`);
  if (p.mortality_rate   != null) popupLines.push(`Mortality: ${p.mortality_rate} per 100 k`);
  if (p.population_density != null) popupLines.push(`Population Density: ${p.population_density} per km²`);
  if (p.temp_era5_q50 != null) popupLines.push(`Temperature (ERA5): ${p.temp_era5_q50} °C`);
  if (p.temp_rcp45 != null) popupLines.push(`Temperature (RCP 4.5): ${p.temp_rcp45} °C`);
  if (p.temp_rcp85 != null) popupLines.push(`Temperature (RCP 8.5): ${p.temp_rcp85} °C`);
  if (p.NOx != null) popupLines.push(`Nitrogen Oxides (NOx): ${p.NOx} µg/m³`);
  if (p.O3 != null) popupLines.push(`Ozone (O3): ${p.O3} µg/m³`);
  if (p.pm10 != null) popupLines.push(`Particle Matters (pm10): ${p.pm10} µg/m³`);

  const nutsID = (p.NUTS_ID ?? '').toUpperCase();
  // If this code does not appear in /api/bbox, we do not display the button
  if (FLASK_CTX.availableMapIDs.includes(nutsID)) {
    popupLines.push(`<br><i>(Double click to zoom in)</i>`);
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
  loadGeoJSON(FLASK_CTX.mapID, yearSlider.value, weekSlider.value, sexSelect.value, ageSelect.value);
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
const sexSelect = document.getElementById('sexSelect');
const ageSelect = document.getElementById('ageSelect');

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
  debounce = setTimeout(() => loadGeoJSON(
    FLASK_CTX.mapID, yearSlider.value, weekSlider.value, sexSelect.value, ageSelect.value),
    250);
  drawTimeSeries(
    holdRegionProperties.NUTS_ID,
    holdRegionProperties.name,
    mainMetric,
    compareMetric,
    sexSelect.value,
    ageSelect.value,
    FLASK_CTX,
    activeRange
  );  // redraw TS for the new year
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

let weekStartEnd = ``;  // to hold the start-end date string for the week

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
  // Update the global weekStartEnd variable
  weekStartEnd = `(${startStr} - ${endStr})`;
}

weekSlider.oninput = () => {
  updateWeekLabel();
  clearTimeout(debounce);
  debounce = setTimeout(() => loadGeoJSON(
    FLASK_CTX.mapID, yearSlider.value, weekSlider.value, sexSelect.value, ageSelect.value),
    250);
};

function metricSelectOnChange() {
  mainMetric = metricSelect.value;
  compareMetric = compareSelect.value || null;
  applyYearRange(METRIC_CFG[mainMetric].range);
  updateWeekLabel();
  loadGeoJSON(FLASK_CTX.mapID, yearSlider.value, weekSlider.value, sexSelect.value, ageSelect.value);
  updateMetricInfo(mainMetric);
  updateColorbar(mainMetric);
  drawTimeSeries(
    holdRegionProperties.NUTS_ID,
    holdRegionProperties.name,
    mainMetric,
    compareMetric,
    sex,
    age,
    FLASK_CTX,
    activeRange
  ); // redraw TS for the new metric
  hideRRCurve();
}

metricSelect.onchange = metricSelectOnChange;
sexSelect.onchange = metricSelectOnChange;
ageSelect.onchange = metricSelectOnChange;
compareSelect.onchange = metricSelectOnChange;

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
    drawTimeSeries(
      holdRegionProperties.NUTS_ID,
      holdRegionProperties.name,
      mainMetric,
      compareMetric,
      sexSelect.value,
      ageSelect.value,
      FLASK_CTX,
      activeRange
    );  // redraw TS for the new range
  };
});

/* --- Button: Download data --- */
document.getElementById('downloadData').addEventListener('click', () => {
  const metric1 = mainMetric;
  const metric2 = compareMetric || 'none';  // if no comparison, use 'none'
  const nutsID = holdRegionProperties.NUTS_ID || 'none';  // use selected region or 'EU' if none
  const sex = sexSelect.value;
  const age = ageSelect.value;
  const url = `/api/data/download?map_id=${FLASK_CTX.mapID}&nuts_id=${nutsID}`
    +`&metric=${metric1}&metric2=${metric2}&sex=${sex}&age=${age}`;
  window.open(url, '_blank');
});

/* --- Button: Generate RR curve --- */
document.getElementById('generateRR').addEventListener('click', () => {
  const nutsID = holdRegionProperties.NUTS_ID || 'none';  // use selected region or 'EU' if none
  if (nutsID === 'none') {
    alert('Please select a region to generate the RR curve.');
    return;
  }
  const metric1 = mainMetric;
  const metric2 = compareMetric || metric1;  // if no comparison, use 'none'
  // If metrics are the same, we do not generate RR curve
  if (metric1 === metric2) {
    alert('Cannot generate RR curve. Please select a secondary metric different than the main metric.');
    return;
  }  
  drawRRCurve(nutsID, metric1, metric2, sexSelect.value, ageSelect.value, FLASK_CTX);
  /* Show the graph */
  document.getElementById('RRCurve').style.display = 'block';
});

/* Function to hide the RR curve */
function hideRRCurve() {
  // Hide only if it is currently displayed
  if (document.getElementById('RRCurve').style.display === 'block')
    {document.getElementById('RRCurve').style.display = 'none';}
}

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

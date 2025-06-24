/* ======================= CONFIG ======================= */
const METRIC_CFG = {
    mortality_rate: {
      label: 'Mortality (per 100 k)',
      value: p => p.mortality_rate ?? 0,
      colour: v => `rgb(0, 0, ${Math.min(v * 5, 255)})`
    },
    population_density: {
      label: 'Population Density (km²)',
      value: p => p.population_density ?? 0,
      colour: v => `rgb(0, ${Math.min(v, 255)}, 0)`
    },
    temperature_rcp45: {
      label: 'Temperature (RCP 4.5) (°C)',
      value: p => p.temperature_rcp45 ?? 0,
      colour: v => `rgb(${Math.min((v + 20) * 5, 255)}, 0, 0)`
    },
    temperature_rcp85: {
      label: 'Temperature (RCP 8.5) (°C)',
      value: p => p.temperature_rcp85 ?? 0,
      colour: v => `rgb(${Math.min((v + 20) * 5, 255)}, 0, 0)`
    }
  };
  
  /* ======================= MAP INIT ======================= */
  let currentMetric = 'temperature_rcp85';
  const map = L.map('map', { zoomControl: false })
    .setView([FLASK_CTX.centerLat, FLASK_CTX.centerLon], FLASK_CTX.zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
  let geoJsonLayer = null;
  
  /* ======================= DATA LOAD ======================= */
  function loadGeoJSON(year, week) {
    fetch(`/api/data?region=${FLASK_CTX.regionSlug}&year=${year}&week=${week}&metric=${currentMetric}`)
      .then(r => r.json())
      .then(data => {
        if (geoJsonLayer) map.removeLayer(geoJsonLayer);
        geoJsonLayer = L.geoJSON(data, {
          style: featureStyle,
          onEachFeature
        }).addTo(map);
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

  /* ---------- helper: show placeholder text ---------- */
  function resetGraph() {
    const holder = document.getElementById('graph');
    holder.innerHTML =
      '<div style="color:#555;font:14px/1.4em system-ui, sans-serif;'+
      'text-align:center;padding-top:40%;opacity:0.8;">'+
      'Click on a region to display its information</div>';
  }
  
  /* call it once at startup */
  resetGraph();
  
  /* =================== POPUP + CHART ===================== */
  function onEachFeature(feature, layer) {
    const p = feature.properties;
  
    // Build the list only with fields that exist
    const popupLines = [`<b>${p.name}</b>`];
  
    if (p.mortality_rate   != null) popupLines.push(`Mortality: ${p.mortality_rate} per 100 k`);
    if (p.population_density != null) popupLines.push(`Population Density: ${p.population_density} per km²`);
    if (p.temperature_rcp45 != null) popupLines.push(`Temp (RCP 4.5): ${p.temperature_rcp45} °C`);
    if (p.temperature_rcp85 != null) popupLines.push(`Temp (RCP 8.5): ${p.temperature_rcp85} °C`);
  
    // Optional navigation button for Austria
    if (p.name === 'Austria') {
      popupLines.push(
        '<button onclick="window.location.href=\'/austria\'">Go to Austria</button>'
      );
    }
  
    layer.bindPopup(popupLines.join('<br>'));
  
    // Click ⇒ show time-series
    layer.on('click', () => {
      drawTimeSeries(p.NUTS_ID, p.name);
    });
  }  

  /* global to hold the active chart */
  let currentChart = null;
  
  function drawTimeSeries(nutsId, regionName) {
    const cfg = METRIC_CFG[currentMetric];
  
    fetch(`/api/data/ts?region=${FLASK_CTX.regionSlug}&metric=${currentMetric}&nuts_id=${nutsId}`)
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
              label : `${cfg.label} – ${regionName}`,
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
  let debounce;
  
  yearSlider.addEventListener('input', () => {
    document.getElementById('yearLabel').innerText = yearSlider.value;
    clearTimeout(debounce);
    debounce = setTimeout(() => loadGeoJSON(yearSlider.value, weekSlider.value), 250);
  });
  
  weekSlider.addEventListener('input', () => {
    document.getElementById('weekLabel').innerText = weekSlider.value;
    clearTimeout(debounce);
    debounce = setTimeout(() => loadGeoJSON(yearSlider.value, weekSlider.value), 250);
  });
  
  metricSelect.addEventListener('change', () => {
    currentMetric = metricSelect.value;
    loadGeoJSON(yearSlider.value, weekSlider.value);
    if (currentChart) { currentChart.destroy(); currentChart = null; }
    resetGraph();                         // show hint again
    document.getElementById('graph').innerHTML = '';
    document.getElementById('info-popup').style.display = 'none';
  });
  
  /* ====================== START ========================== */
  loadGeoJSON(FLASK_CTX.maxYear, 1);
  
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
      label: 'Temperature RCP 4.5 (°C)',
      value: p => p.temperature_rcp45 ?? 0,
      colour: v => `rgb(${Math.min((v + 20) * 5, 255)}, 0, 0)`
    },
    temperature_rcp85: {
      label: 'Temperature RCP 8.5 (°C)',
      value: p => p.temperature_rcp85 ?? 0,
      colour: v => `rgb(${Math.min((v + 20) * 5, 255)}, 0, 0)`
    }
  };
  
  /* ======================= MAP INIT ======================= */
  let currentMetric = 'temperature_rcp85';
  const map = L.map('map').setView([FLASK_CTX.centerLat, FLASK_CTX.centerLon], FLASK_CTX.zoom);
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
  
  /* =================== POPUP + CHART ===================== */
  function onEachFeature(feature, layer) {
    const p = feature.properties;
    const popup = [
      `<b>${p.name}</b>`,
      `Mortality: ${p.mortality_rate ?? 'n/a'} per 100 k`,
      `Population Density: ${p.population_density ?? 'n/a'} per km²`,
      `Temp RCP 4.5: ${p.temperature_rcp45 ?? 'n/a'} °C`,
      `Temp RCP 8.5: ${p.temperature_rcp85 ?? 'n/a'} °C`
    ];
    if (p.name === 'Austria') popup.push('<button onclick="window.location.href=\'/austria\'">Go to Austria</button>');
    layer.bindPopup(popup.join('<br>'));
  
    layer.on('click', () => {
      const cfg = METRIC_CFG[currentMetric];
      const val = cfg.value(p);
      updateInfo(p.name, cfg.label, val);
      drawTimeSeries(p.NUTS_ID, p.name);
    });
  }

  function updateInfo(name, label, value) {
    document.getElementById('regionName').innerText = name;
    document.getElementById('metricLabel').innerText = label;
    document.getElementById('metricValue').innerText = value;
    document.getElementById('info-popup').style.display = 'block';
  }
  
  function drawTimeSeries(nutsId, regionName) {
    const cfg = METRIC_CFG[currentMetric];
    fetch(`/api/data/ts?region=${FLASK_CTX.regionSlug}&metric=${currentMetric}&nuts_id=${nutsId}`)
      .then(r => r.json())
      .then(res => {
        if (!res.data) return;
  
        const labels = res.data.map(d => `${d.year}-W${String(d.week).padStart(2, '0')}`);
        const values = res.data.map(d => d.value);
  
        const gDiv = document.getElementById('graph');
        gDiv.innerHTML = '';
        const canvas = document.createElement('canvas');
        gDiv.appendChild(canvas);
  
        new Chart(canvas.getContext('2d'), {
          type: 'line',
          data: {
            labels,
            datasets: [{
              label: `${cfg.label} for ${regionName}`,
              data: values,
              borderColor: '#6dc201',
              backgroundColor: '#6dc2014D',
              fill: true,
              tension: 0.2
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
    document.getElementById('graph').innerHTML = '';
    document.getElementById('info-popup').style.display = 'none';
  });
  
  /* ====================== START ========================== */
  loadGeoJSON(FLASK_CTX.maxYear, 1);
  
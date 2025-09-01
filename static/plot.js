/* ======================= IMPORTS ====================== */
import { METRIC_CFG } from './config.js';


/* ======================= TIME SERIES CHARTS ====================== */

let currentTimeSeries = null;

// inject or replace the <canvas> inside #regionGraph
function prepareCanvas(canvasID) {
  const holder = document.getElementById(canvasID);
  holder.innerHTML = '<canvas></canvas>';
  return holder.querySelector('canvas').getContext('2d');
}
  
// actually render Chart.js with two Y-axes
function renderTimeSeriesChart(labels, data1, data2, m1, m2, regionName, activeRange) {
  const ctx = prepareCanvas('regionGraph');
  if (currentTimeSeries) currentTimeSeries.destroy();

  const datasets = [{
    label   : `${METRIC_CFG[m1].label} — ${regionName}`,
    data    : data1,
    yAxisID : 'yLeft',
    borderColor: '#6dc201',
    tension: 0.25,
    fill: false,
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
      pointRadius: 0,
      pointHitRadius: 20,
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

  currentTimeSeries = new Chart(ctx, {
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
export function drawTimeSeries(
  nutsId,
  regionName,
  mainMetric,
  compareMetric,
  sex,
  age,
  FLASK_CTX,
  activeRange) {
  // if the region is not selected, do nothing
  if (!nutsId || nutsId === 'EU') {
    document.getElementById('regionGraph').innerHTML = '<p>Click on a region to see the time-series.</p>';
    return;
  }

  // build fetch
  const url = `/api/data/ts?map_id=${FLASK_CTX.mapID}&nuts_id=${nutsId}`
    +`&metric=${mainMetric}&metric2=${compareMetric}&sex=${sex}&age=${age}`;
  fetch(url)
  .then(r=>r.json())
  .then((res) => {
    const labels = res.data.map(d => `${d.year}-W${String(d.week).padStart(2,'0')}`);
    const data1  = res.data.map(d => d.value);
    let data2;
    if (compareMetric !== null) {
      data2  = res.data.map(d => d.value2);
    } else {
      data2 = [];
    }
    renderTimeSeriesChart(labels, data1, data2, mainMetric, compareMetric, regionName, activeRange);
  }).catch(console.error);
}

/* ======================= RR CURVE ====================== */

/* -------------------- CONFIG -------------------- */
const COLORS = {
  line : '#b30000',
  shade: 'rgba(179,0,0,.20)',
  axis : '#444'
};

/* -------------------- MAIN PLOTTER -------------- */
let  currentRRCurve = null;

function renderRRCurve(json) {
  const ctx = prepareCanvas('RRCurve');
  if ( currentRRCurve)  currentRRCurve.destroy();

  // Extract the values from the JSON response
  const x_grid = json.x_grid;
  const rr = json.rr;
  const label   = json.label;
  const units   = json.units;

  const points = x_grid.map((t, i) => ({ x: t, y: rr[i] }));
  const datasets = [
    {
      label: 'Relative Risk',
      data : points,
      borderColor: COLORS.line,
      tension: 0.25,
      pointRadius: 0,
      fill: false
    }
  ];

  const xMin = json.x_grid[0];
  const xMax = json.x_grid.at(-1);

  currentRRCurve = new Chart(ctx, {
    type: 'line',
    data: { labels: x_grid, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'linear',
          min : xMin,
          max : xMax,
          title: { display: true, text: `${label} (${units})`, color: COLORS.axis },
          ticks: {
            // keep integer labels only
            callback(v) { return Number.isInteger(v) ? v : '' }
          }
        },      
        y: {
          title: { display: true, text: 'Relative Risk', color: COLORS.axis },
          beginAtZero: false,
          grid: { color: 'rgba(0,0,0,.1)' }
        }        
      },
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false }
      }
    }
  });
}

/* -------------------- PUBLIC API --------------- */

export function drawRRCurve(nutsId, metric, metric2, sex, age, FLASK_CTX) {
  const url = `/api/data/rr_curve?map_id=${FLASK_CTX.mapID}&nuts_id=${nutsId}` +
              `&metric=${metric}&metric2=${metric2}&sex=${sex}&age=${age}`;

  fetch(url)
    .then(resp => resp.json())
    .then(renderRRCurve)
    .catch(err => {
      console.error(err);
      document.getElementById('RRCurve').innerHTML =
        '<p style="color:red">Unable to load RR curve.</p>';
    });
}

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
  FLASK_CTX,
  activeRange) {
  // if the region is not selected, do nothing
  if (!nutsId || nutsId === 'EU') {
    document.getElementById('regionGraph').innerHTML = '<p>Click on a region to see the time-series.</p>';
    return;
  }

  // build fetch
  const url = `/api/data/ts?map_id=${FLASK_CTX.mapID}&nuts_id=${nutsId}`
    +`&metric=${mainMetric}&metric2=${compareMetric}`;
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
  const rr_low = json.rr_low;
  const rr_high = json.rr_high;
  const label   = json.label;
  const units   = json.units;

  // Calculate the y-axis max: min(3, max(rr_high))
  const maxY = Math.min(3, Math.max(...rr_high));

  /* We create three datasets:
     0 = lower bound  (invisible)
     1 = upper bound  (invisible, fills to previous to make ribbon)
     2 = RR line
  */
  const datasets = [
    {
      label: 'CI 95% lower',
      data : rr_low,
      borderColor: 'rgba(0,0,0,0)',
      backgroundColor: COLORS.shade,
      fill : '+1',      // fill to the *next* dataset (index 1)
      pointRadius: 0
    },
    {
      label: 'CI 95 % upper',
      data : rr_high,
      borderColor: 'rgba(0,0,0,0)',
      backgroundColor: COLORS.shade,
      fill : '-1',      // fill back to previous dataset (index 0)
      pointRadius: 0
    },
    {
      label: 'Relative Risk',
      data : rr,
      borderColor: COLORS.line,
      backgroundColor: COLORS.line,
      tension: 0.25,
      pointRadius: 0,
      fill: false
    }
  ];

   currentRRCurve = new Chart(ctx, {
    type: 'line',
    data: { labels: x_grid, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: true, text: `${label} (${units})`, color: COLORS.axis },
          ticks: { autoSkip: true, maxTicksLimit: 10 }
        },
        y: {
          title: { display: true, text: 'Relative Risk', color: COLORS.axis },
          max: maxY,
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

export function drawRRCurve(nutsId, metric, metric2, FLASK_CTX) {
  const url = `/api/data/rr_curve?map_id=${FLASK_CTX.mapID}&nuts_id=${nutsId}` +
              `&metric=${metric}&metric2=${metric2}`;

  fetch(url)
    .then(resp => resp.json())
    .then(renderRRCurve)
    .catch(err => {
      console.error(err);
      document.getElementById('RRCurve').innerHTML =
        '<p style="color:red">Unable to load RR curve.</p>';
    });
}

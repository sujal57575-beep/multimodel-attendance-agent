/**
 * engagement.js — Engagement analytics charts and table
 */

let _compositeChart = null;
let _radarChart = null;

async function loadEngagementData(sessionId) {
  try {
    const res  = await fetch(`/api/sessions/${sessionId}/engagement`);
    const data = await res.json();
    const windows  = data.windows  || [];
    const summary  = data.summary  || {};

    // Update info bar
    setEl('si-windows', windows.length);
    setEl('si-avg',     (summary.mean || 0).toFixed(2));
    setEl('si-trend',   summary.trend || '—');

    const lowBadge = document.getElementById('low-windows-badge');
    if (lowBadge && summary.low_engagement_windows > 0) {
      lowBadge.textContent = `⚠️ ${summary.low_engagement_windows} low-engagement windows`;
      lowBadge.style.display = 'inline';
    }

    renderEngagementTable(windows);
    renderCompositeChart(windows);
    renderRadarChart(summary, windows);

  } catch(e) {
    showToast('Failed to load engagement data', 'error');
    console.error(e);
  }
}

function renderEngagementTable(windows) {
  const tbody = document.getElementById('engagement-tbody');
  if (!tbody) return;

  if (windows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--text-muted)">No engagement data yet. Process a session video first.</td></tr>';
    return;
  }

  tbody.innerHTML = windows.map(w => {
    const score = w.composite_score || 0;
    const scoreColor = score >= 0.65 ? 'var(--green)' : score >= 0.4 ? 'var(--amber)' : 'var(--red)';
    return `
      <tr>
        <td>${w.window_index + 1}</td>
        <td>${fmtTimeShort(w.window_start)}</td>
        <td>${fmtTimeShort(w.window_end)}</td>
        <td>${scoreBar(w.presence_score, 'var(--blue)')}</td>
        <td>${scoreBar(w.motion_score,   'var(--violet)')}</td>
        <td>${scoreBar(w.audio_score,    'var(--amber)')}</td>
        <td>
          <div style="display:flex;align-items:center;gap:6px">
            ${scoreBar(score, scoreColor)}
            <span style="font-size:0.78rem;font-weight:600;color:${scoreColor}">${(score*100).toFixed(0)}%</span>
          </div>
        </td>
        <td>${w.participant_count || 0}</td>
        <td>${Math.round((w.confidence||1)*100)}%</td>
      </tr>
    `;
  }).join('');
}

function scoreBar(val, color) {
  const pct = Math.round((val || 0) * 100);
  return `<div style="width:70px;background:rgba(255,255,255,0.07);border-radius:3px;height:6px;overflow:hidden;display:inline-block;vertical-align:middle">
    <div style="width:${pct}%;height:100%;background:${color};border-radius:3px;transition:width 0.4s"></div>
  </div>`;
}

function fmtTimeShort(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch(e) { return isoStr; }
}

function renderCompositeChart(windows) {
  if (typeof Chart === 'undefined') return;
  const ctx = document.getElementById('chart-composite');
  if (!ctx) return;
  if (_compositeChart) _compositeChart.destroy();

  const labels = windows.map((_, i) => `W${i+1}`);
  _compositeChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Composite',
          data: windows.map(w => w.composite_score),
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99,102,241,0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
        },
        {
          label: 'Presence',
          data: windows.map(w => w.presence_score),
          borderColor: '#22c55e',
          borderDash: [4,3],
          fill: false,
          tension: 0.4,
          pointRadius: 2,
        },
        {
          label: 'Audio',
          data: windows.map(w => w.audio_score),
          borderColor: '#f59e0b',
          borderDash: [2,3],
          fill: false,
          tension: 0.4,
          pointRadius: 2,
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 12, padding: 16 } }
      },
      scales: {
        y: {
          min: 0, max: 1,
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { callback: v => (v*100)+'%' },
        },
        x: { grid: { display: false } }
      }
    }
  });
}

function renderRadarChart(summary, windows) {
  if (typeof Chart === 'undefined') return;
  const ctx = document.getElementById('chart-radar');
  if (!ctx) return;
  if (_radarChart) _radarChart.destroy();

  const avg = arr => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0;
  const presence = avg(windows.map(w => w.presence_score || 0));
  const motion   = avg(windows.map(w => w.motion_score   || 0));
  const audio    = avg(windows.map(w => w.audio_score    || 0));
  const headpose = avg(windows.map(w => w.head_pose_score || 0));
  const composite = summary.mean || 0;

  _radarChart = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: ['Presence', 'Motion', 'Audio', 'Head Pose', 'Composite'],
      datasets: [{
        label: 'Session Average',
        data: [presence, motion, audio, headpose, composite],
        borderColor: 'rgba(99,102,241,0.85)',
        backgroundColor: 'rgba(99,102,241,0.15)',
        pointBackgroundColor: '#6366f1',
        pointRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0, max: 1,
          grid: { color: 'rgba(255,255,255,0.08)' },
          angleLines: { color: 'rgba(255,255,255,0.08)' },
          pointLabels: { color: '#94a3b8', font: { size: 11 } },
          ticks: { display: false },
        }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

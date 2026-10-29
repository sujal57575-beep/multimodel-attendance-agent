/**
 * dashboard.js — Global utilities + dashboard KPIs
 * Multimodal Attendance & Engagement Agent
 */

// ── Toast notifications ───────────────────────────────────────
function showToast(msg, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const t = document.createElement('div');
  t.className = `toast toast--${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ── Modal helpers ─────────────────────────────────────────────
function closeModal() {
  const m = document.getElementById('global-modal');
  if (m) m.style.display = 'none';
}

// ── Time formatting ───────────────────────────────────────────
function fmtDuration(seconds) {
  if (!seconds) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function fmtTime(isoStr) {
  if (!isoStr) return '—';
  return new Date(isoStr).toLocaleString();
}

function fmtDate(isoStr) {
  if (!isoStr) return '—';
  return new Date(isoStr).toLocaleDateString();
}

// ── Session info loader (shared across pages) ─────────────────
async function loadSessionInfo(sessionId) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}`);
    if (!res.ok) return;
    const ses = await res.json();
    ['si-name', 'si-subject', 'si-duration', 'si-status'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      if (id === 'si-name')     el.textContent = ses.name     || '—';
      if (id === 'si-subject')  el.textContent = ses.subject  || '—';
      if (id === 'si-duration') el.textContent = fmtDuration(ses.duration_seconds);
      if (id === 'si-status') {
        el.textContent = ses.status || '—';
        el.className = 'info-value badge ' + statusBadgeClass(ses.status);
      }
    });
  } catch (e) { /* silently ignore */ }
}

function statusBadgeClass(status) {
  const map = {
    completed: 'badge--green',
    processing: 'badge--amber',
    active: 'badge--blue',
    error: 'badge--red',
  };
  return map[status] || '';
}

// ── Dashboard KPIs ────────────────────────────────────────────
async function loadDashboardKPIs() {
  try {
    const res = await fetch('/api/sessions');
    const data = await res.json();
    const sessions = data.sessions || [];

    document.getElementById('total-sessions').textContent = sessions.length;

    const completedSessions = sessions.filter(s => s.status === 'completed');
    let totalParticipants = 0;
    let totalAttendancePct = 0;
    let totalEngagement = 0;
    let engCount = 0;

    // Aggregate across completed sessions
    const promises = completedSessions.slice(0, 10).map(async s => {
      try {
        const [attRes, engRes] = await Promise.all([
          fetch(`/api/sessions/${s.id}/attendance`),
          fetch(`/api/sessions/${s.id}/engagement`),
        ]);
        const att = await attRes.json();
        const eng = await engRes.json();
        totalParticipants += att.total || 0;
        if (att.attendance_pct) totalAttendancePct += att.attendance_pct;
        if (eng.summary && eng.summary.mean != null) {
          totalEngagement += eng.summary.mean;
          engCount++;
        }
      } catch(e) {}
    });

    await Promise.all(promises);

    document.getElementById('total-participants').textContent = totalParticipants;
    const numCompleted = completedSessions.length;
    document.getElementById('avg-attendance').textContent =
      numCompleted ? `${(totalAttendancePct / numCompleted).toFixed(1)}%` : '—';
    document.getElementById('avg-engagement').textContent =
      engCount ? (totalEngagement / engCount).toFixed(2) : '—';

  } catch(e) {
    console.error('Dashboard KPI load error:', e);
    showToast('Failed to load dashboard statistics', 'error');
  }
}

// ── Chart.js global defaults ──────────────────────────────────
function applyChartDefaults() {
  if (typeof Chart === 'undefined') return;
  Chart.defaults.color = '#64748b';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 11;
}

// ── Engagement trend chart (dashboard) ────────────────────────
async function initEngagementChart() {
  if (typeof Chart === 'undefined') return;
  applyChartDefaults();

  const ctx = document.getElementById('chart-engagement');
  if (!ctx) return;

  // Fetch last 10 sessions and their avg engagement
  let labels = [], values = [];
  try {
    const res = await fetch('/api/sessions');
    const data = await res.json();
    const completed = (data.sessions || []).filter(s => s.status === 'completed').slice(0, 10).reverse();
    for (const s of completed) {
      try {
        const r = await fetch(`/api/sessions/${s.id}/engagement`);
        const d = await r.json();
        labels.push(s.name.length > 14 ? s.name.slice(0,14)+'…' : s.name);
        values.push(d.summary?.mean || 0);
      } catch(e) {}
    }
  } catch(e) {}

  if (values.length === 0) {
    labels = ['No sessions yet'];
    values = [0];
  }

  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Avg Engagement',
        data: values,
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,0.12)',
        tension: 0.4,
        fill: true,
        pointBackgroundColor: '#6366f1',
        pointRadius: 4,
        pointHoverRadius: 7,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          min: 0, max: 1,
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { callback: v => (v * 100).toFixed(0) + '%' },
        },
        x: { grid: { display: false } }
      }
    }
  });
}

// ── Attendance distribution donut ─────────────────────────────
async function initAttendanceChart() {
  if (typeof Chart === 'undefined') return;
  const ctx = document.getElementById('chart-attendance-dist');
  if (!ctx) return;

  let marked = 0, unmarked = 0;
  try {
    const res = await fetch('/api/sessions');
    const data = await res.json();
    const completed = (data.sessions || []).filter(s => s.status === 'completed').slice(0, 10);
    for (const s of completed) {
      try {
        const r  = await fetch(`/api/sessions/${s.id}/attendance`);
        const at = await r.json();
        marked   += at.marked || 0;
        unmarked += (at.total || 0) - (at.marked || 0);
      } catch(e) {}
    }
  } catch(e) {}

  if (marked + unmarked === 0) { marked = 1; }

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Present', 'Absent / Unconfirmed'],
      datasets: [{
        data: [marked, Math.max(unmarked, 0)],
        backgroundColor: ['rgba(34,197,94,0.75)', 'rgba(239,68,68,0.45)'],
        borderColor:     ['#22c55e', '#ef4444'],
        borderWidth: 1.5,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true,
      cutout: '68%',
      plugins: {
        legend: { position: 'bottom', labels: { padding: 16, boxWidth: 12 } }
      }
    }
  });
}

// ── Recent sessions table (dashboard) ────────────────────────
async function loadRecentSessions() {
  const tbody = document.getElementById('sessions-tbody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/sessions');
    const data = await res.json();
    const sessions = (data.sessions || []).slice(0, 8);

    if (sessions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:24px">No sessions yet.</td></tr>';
      return;
    }

    tbody.innerHTML = sessions.map(s => `
      <tr>
        <td><strong>${escHtml(s.name)}</strong><br/><small style="color:var(--text-muted)">${fmtDate(s.created_at)}</small></td>
        <td>${escHtml(s.subject || '—')}</td>
        <td>${escHtml(s.instructor || '—')}</td>
        <td><span class="badge ${statusBadgeClass(s.status)}">${s.status}</span></td>
        <td>—</td>
        <td>—</td>
        <td>
          <a href="/sessions/${s.id}/attendance" class="btn btn-ghost" style="padding:4px 10px;font-size:0.75rem">View</a>
        </td>
      </tr>
    `).join('');
  } catch(e) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:var(--red);text-align:center;padding:24px">Failed to load sessions.</td></tr>';
  }
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

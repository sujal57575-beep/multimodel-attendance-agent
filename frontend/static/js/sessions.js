/**
 * sessions.js — Session management: create, list, upload, process
 */

let _currentSessionId = null;
let _pollInterval = null;

// ── Modal open/close ───────────────────────────────────────────
function openNewSessionModal() {
  document.getElementById('new-session-modal').style.display = 'flex';
  document.getElementById('s-name').focus();
}
function closeNewSessionModal() {
  document.getElementById('new-session-modal').style.display = 'none';
  document.getElementById('new-session-form').reset();
  document.getElementById('file-preview').style.display = 'none';
  document.getElementById('session-form-error').style.display = 'none';
}

// ── File select handler ───────────────────────────────────────
function handleFileSelect(input) {
  const f = input.files[0];
  if (!f) return;
  const preview = document.getElementById('file-preview');
  preview.textContent = `📎 ${f.name} (${(f.size / 1024 / 1024).toFixed(1)} MB)`;
  preview.style.display = 'block';
}

// ── Drag & drop ───────────────────────────────────────────────
(function setupDragDrop() {
  const zone = document.getElementById('file-drop-zone');
  if (!zone) return;
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (!f) return;
    const input = document.getElementById('s-video');
    const dt = new DataTransfer();
    dt.items.add(f);
    input.files = dt.files;
    handleFileSelect(input);
  });
})();

// ── Create session + upload + process ────────────────────────
async function submitNewSession(event) {
  event.preventDefault();
  const form = document.getElementById('new-session-form');
  const data = Object.fromEntries(new FormData(form));
  const errBox = document.getElementById('session-form-error');
  errBox.style.display = 'none';

  if (!data.name || !data.name.trim()) {
    errBox.textContent = 'Session name is required.';
    errBox.style.display = 'block';
    return;
  }

  setBtnLoading('btn-create-session', true);

  try {
    // 1. Create session
    const createRes = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: data.name.trim(),
        subject: data.subject || '',
        instructor: data.instructor || '',
        location: data.location || '',
      }),
    });
    if (!createRes.ok) {
      const err = await createRes.json();
      throw new Error(err.error || 'Failed to create session');
    }
    const { session_id } = await createRes.json();
    _currentSessionId = session_id;

    // 2. Upload video if selected
    const videoFile = document.getElementById('s-video').files[0];
    if (videoFile) {
      const fd = new FormData();
      fd.append('file', videoFile);
      const uploadRes = await fetch(`/api/sessions/${session_id}/video`, {
        method: 'POST',
        body: fd,
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json();
        throw new Error(err.error || 'Video upload failed');
      }

      // 3. Start processing
      const procRes = await fetch(`/api/sessions/${session_id}/process`, {
        method: 'POST',
      });
      if (!procRes.ok) {
        showToast('Session created but processing could not start.', 'error');
      } else {
        closeNewSessionModal();
        showProcessingOverlay(session_id);
        return;
      }
    }

    closeNewSessionModal();
    showToast('Session created successfully!', 'success');
    await loadSessionsList();

  } catch(e) {
    errBox.textContent = e.message;
    errBox.style.display = 'block';
  } finally {
    setBtnLoading('btn-create-session', false);
  }
}

// ── Processing overlay ────────────────────────────────────────
function showProcessingOverlay(sessionId) {
  const overlay = document.getElementById('processing-overlay');
  if (!overlay) return;
  overlay.style.display = 'flex';
  _pollInterval = setInterval(() => pollProgress(sessionId), 1500);
}

async function pollProgress(sessionId) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}/progress`);
    const data = await res.json();
    const bar  = document.getElementById('processing-progress-bar');
    const pctEl = document.getElementById('processing-pct');
    const msgEl = document.getElementById('processing-status-msg');
    if (bar)    bar.style.width  = (data.pct || 0) + '%';
    if (pctEl)  pctEl.textContent = (data.pct || 0) + '%';
    if (msgEl)  msgEl.textContent = data.status || 'Working…';

    if (data.status === 'completed') {
      clearInterval(_pollInterval);
      document.getElementById('processing-overlay').style.display = 'none';
      showToast('Processing complete! Session ready.', 'success');
      await loadSessionsList();
    } else if (data.status === 'error') {
      clearInterval(_pollInterval);
      document.getElementById('processing-overlay').style.display = 'none';
      showToast(`Processing failed: ${data.error}`, 'error');
      await loadSessionsList();
    }
  } catch(e) { /* retry */ }
}

// ── Load sessions grid ────────────────────────────────────────
async function loadSessionsList() {
  const grid = document.getElementById('sessions-grid');
  if (!grid) return;

  const loading = document.getElementById('sessions-loading');
  const empty   = document.getElementById('sessions-empty');
  if (loading) loading.style.display = 'flex';
  if (empty)   empty.style.display = 'none';

  try {
    const res = await fetch('/api/sessions');
    const data = await res.json();
    let sessions = data.sessions || [];

    // Apply search filter
    const q = (document.getElementById('session-search')?.value || '').toLowerCase();
    const st = document.getElementById('session-status-filter')?.value || '';
    if (q)  sessions = sessions.filter(s => (s.name + s.subject + s.instructor).toLowerCase().includes(q));
    if (st) sessions = sessions.filter(s => s.status === st);

    if (loading) loading.style.display = 'none';

    if (sessions.length === 0) {
      if (empty) empty.style.display = 'flex';
      return;
    }

    const cards = sessions.map(s => buildSessionCard(s)).join('');
    // Keep the hidden elements, insert cards before them
    grid.querySelectorAll('.session-card').forEach(c => c.remove());
    grid.insertAdjacentHTML('afterbegin', cards);

  } catch(e) {
    if (loading) loading.style.display = 'none';
    showToast('Failed to load sessions', 'error');
  }
}

function buildSessionCard(s) {
  const statusClass = statusBadgeClass(s.status);
  return `
    <div class="session-card glass" role="listitem" id="card-${s.id}">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
        <div>
          <div class="session-card-title">${escHtml(s.name)}</div>
          <div class="session-card-meta">${escHtml(s.subject||'')} ${s.instructor ? '· ' + escHtml(s.instructor) : ''} · ${fmtDate(s.created_at)}</div>
        </div>
        <span class="badge ${statusClass}">${s.status}</span>
      </div>
      ${s.location ? `<div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">📍 ${escHtml(s.location)}</div>` : ''}
      <div class="session-card-actions">
        <a href="/sessions/${s.id}/attendance" class="btn btn-ghost" style="flex:1;justify-content:center;font-size:0.78rem">👥 Attendance</a>
        <a href="/sessions/${s.id}/engagement" class="btn btn-ghost" style="flex:1;justify-content:center;font-size:0.78rem">📊 Engagement</a>
        <a href="/sessions/${s.id}/recommendations" class="btn btn-ghost" style="flex:1;justify-content:center;font-size:0.78rem">💡 Suggestions</a>
      </div>
      <div style="display:flex;gap:6px;margin-top:6px">
        <a href="/sessions/${s.id}/report" class="btn btn-primary" style="flex:1;justify-content:center;font-size:0.78rem">📄 Report</a>
        <button class="btn btn-ghost" onclick="deleteSession('${s.id}')" style="padding:7px 10px" title="Delete session">🗑️</button>
      </div>
    </div>
  `;
}

// ── Delete session ────────────────────────────────────────────
async function deleteSession(sessionId) {
  if (!confirm('Delete this session and all associated data? This cannot be undone.')) return;
  try {
    const res = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
    if (res.ok) {
      document.getElementById(`card-${sessionId}`)?.remove();
      showToast('Session deleted', 'success');
    } else {
      showToast('Failed to delete session', 'error');
    }
  } catch(e) { showToast('Error deleting session', 'error'); }
}

// ── Helpers ──────────────────────────────────────────────────
function setBtnLoading(id, loading) {
  const btn = document.getElementById(id);
  if (!btn) return;
  btn.disabled = loading;
  const text    = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.btn-spinner');
  if (text)    text.style.display    = loading ? 'none' : 'inline';
  if (spinner) spinner.style.display = loading ? 'inline-block' : 'none';
}

// ── Filters ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadSessionsList();
  document.getElementById('session-search')?.addEventListener('input', loadSessionsList);
  document.getElementById('session-status-filter')?.addEventListener('change', loadSessionsList);
});

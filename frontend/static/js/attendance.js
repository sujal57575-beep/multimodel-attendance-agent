/**
 * attendance.js — Attendance page controller
 */

async function loadAttendanceData(sessionId) {
  try {
    const res  = await fetch(`/api/sessions/${sessionId}/attendance`);
    const data = await res.json();

    document.getElementById('att-total').textContent  = data.total  || 0;
    document.getElementById('att-marked').textContent = data.marked || 0;

    const needsReview = (data.participants || []).filter(p => p.needs_review).length;
    document.getElementById('att-review').textContent = needsReview;

    if (needsReview > 0) {
      const badge = document.getElementById('att-needs-review-badge');
      if (badge) badge.style.display = 'inline';
    }

    renderAttendanceTable(data.participants || [], sessionId);
  } catch(e) {
    showToast('Failed to load attendance data', 'error');
  }
}

function renderAttendanceTable(participants, sessionId) {
  const tbody = document.getElementById('attendance-tbody');
  if (!tbody) return;

  if (participants.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:32px;color:var(--text-muted)">No participants recorded for this session.</td></tr>';
    return;
  }

  tbody.innerHTML = participants.map(p => `
    <tr id="row-${p.id}">
      <td><code style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:var(--accent)">${escHtml(p.track_id)}</code></td>
      <td>
        <span id="name-display-${p.id}">${escHtml(p.display_name || 'Anonymous')}</span>
        <button onclick="editName('${p.id}')" title="Edit name" style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:0.75rem;margin-left:4px">✏️</button>
      </td>
      <td>${fmtTime(p.first_seen_at)}</td>
      <td>${fmtTime(p.last_seen_at)}</td>
      <td>${fmtDuration(p.total_duration_seconds)}</td>
      <td>
        <div style="display:flex;align-items:center;gap:6px">
          <div style="width:50px;background:rgba(255,255,255,0.07);border-radius:3px;height:5px;overflow:hidden">
            <div style="width:${Math.round((p.confidence||0)*100)}%;height:100%;background:${confidenceColor(p.confidence)}"></div>
          </div>
          <span style="font-size:0.75rem;color:var(--text-muted)">${Math.round((p.confidence||0)*100)}%</span>
        </div>
      </td>
      <td>
        ${p.attendance_marked
          ? '<span class="badge badge--green">✓ Present</span>'
          : '<span class="badge badge--red">✗ Absent</span>'}
        ${p.needs_review ? ' <span class="badge badge--amber">Review</span>' : ''}
      </td>
      <td>
        <button class="btn btn-ghost" style="padding:4px 10px;font-size:0.75rem"
          onclick="toggleAttendance('${sessionId}', '${p.id}', ${p.attendance_marked ? 0 : 1})">
          ${p.attendance_marked ? 'Mark Absent' : 'Mark Present'}
        </button>
      </td>
    </tr>
  `).join('');
}

function confidenceColor(conf) {
  if (conf >= 0.7) return 'var(--green)';
  if (conf >= 0.45) return 'var(--amber)';
  return 'var(--red)';
}

async function toggleAttendance(sessionId, participantId, newValue) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}/attendance/${participantId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attendance_marked: newValue }),
    });
    if (res.ok) {
      showToast('Attendance updated', 'success');
      loadAttendanceData(sessionId);
    } else {
      showToast('Update failed', 'error');
    }
  } catch(e) { showToast('Error updating attendance', 'error'); }
}

function editName(participantId) {
  const span = document.getElementById(`name-display-${participantId}`);
  const current = span.textContent === 'Anonymous' ? '' : span.textContent;
  const newName = prompt('Enter display name (leave blank for Anonymous):', current);
  if (newName === null) return;
  updateParticipantName(participantId, newName.trim() || 'Anonymous');
}

async function updateParticipantName(participantId, name) {
  try {
    const sessionId = typeof SESSION_ID !== 'undefined' ? SESSION_ID : '';
    await fetch(`/api/sessions/${sessionId}/attendance/${participantId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name }),
    });
    const span = document.getElementById(`name-display-${participantId}`);
    if (span) span.textContent = name;
    showToast('Name updated', 'success');
  } catch(e) { showToast('Failed to update name', 'error'); }
}

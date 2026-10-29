/**
 * attendance.js — Attendance page controller
 */

async function loadAttendanceData(sessionId) {
  try {
    const res  = await fetch(`/api/sessions/${sessionId}/attendance`);
    const data = await res.json();

    document.getElementById('att-total').textContent  = data.total  || 0;
    document.getElementById('att-marked').textContent = data.marked || 0;

    const faceEl = document.getElementById('att-face-verified');
    if (faceEl) faceEl.textContent = data.face_verified_count || 0;

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
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--text-muted)">No participants recorded for this session.</td></tr>';
    return;
  }

  tbody.innerHTML = participants.map(p => `
    <tr id="row-${p.id}">
      <td><code style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:var(--accent)">${escHtml(p.track_id)}</code></td>
      <td>
        <span id="name-display-${p.id}">${escHtml(p.display_name || 'Anonymous')}</span>
        <button onclick="editName('${p.id}')" title="Edit name" style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:0.75rem;margin-left:4px">✏️</button>
      </td>
      <td>
        ${p.face_verified
          ? `<span class="badge badge--violet" title="Verified in ${p.face_count || 0} frames (conf: ${Math.round((p.face_confidence||0.9)*100)}%)">👤 Verified (${p.face_count || 0})</span>`
          : (p.face_count > 0
              ? `<span class="badge badge--blue" title="Detected in ${p.face_count} frames">🔍 ${p.face_count} frames</span>`
              : `<span class="badge badge--confidence" title="No facial frames recorded">Silhouette</span>`)}
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

// ── Live Face Attendance Scanner ─────────────────────────────
let _webcamStream = null;
let _scanTimer = null;
let _isScanning = false;

function openLiveFaceScanner() {
  const modal = document.getElementById('live-face-modal');
  if (modal) modal.style.display = 'flex';
}

function closeLiveFaceScanner() {
  stopWebcam();
  const modal = document.getElementById('live-face-modal');
  if (modal) modal.style.display = 'none';
}

async function toggleWebcam() {
  if (_webcamStream) {
    stopWebcam();
  } else {
    await startWebcam();
  }
}

async function startWebcam() {
  const video = document.getElementById('live-webcam');
  const btn = document.getElementById('btn-toggle-cam');
  const placeholder = document.getElementById('camera-placeholder');
  const statusText = document.getElementById('live-status-text');

  try {
    _webcamStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
      audio: false,
    });
    video.srcObject = _webcamStream;
    if (placeholder) placeholder.style.display = 'none';
    if (btn) btn.textContent = 'Stop Camera';
    if (statusText) statusText.textContent = 'Camera active — detecting faces…';

    _scanTimer = setInterval(scanWebcamFrame, 450);
  } catch (err) {
    showToast('Camera access denied or unavailable: ' + err.message, 'error');
    if (statusText) statusText.textContent = 'Camera error';
  }
}

function stopWebcam() {
  if (_scanTimer) {
    clearInterval(_scanTimer);
    _scanTimer = null;
  }
  if (_webcamStream) {
    _webcamStream.getTracks().forEach(track => track.stop());
    _webcamStream = null;
  }
  const video = document.getElementById('live-webcam');
  if (video) video.srcObject = null;
  const canvas = document.getElementById('live-canvas');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  const placeholder = document.getElementById('camera-placeholder');
  if (placeholder) placeholder.style.display = 'block';
  const btn = document.getElementById('btn-toggle-cam');
  if (btn) btn.textContent = 'Start Camera';
  const statusText = document.getElementById('live-status-text');
  if (statusText) statusText.textContent = 'Camera Idle';
  const countBadge = document.getElementById('live-face-count');
  if (countBadge) countBadge.textContent = '0 faces';
}

async function scanWebcamFrame() {
  if (_isScanning || !_webcamStream) return;
  const video = document.getElementById('live-webcam');
  if (!video || video.readyState < 2) return;

  _isScanning = true;
  try {
    // Capture current frame
    const offscreen = document.createElement('canvas');
    offscreen.width = video.videoWidth || 640;
    offscreen.height = video.videoHeight || 480;
    const offCtx = offscreen.getContext('2d');
    offCtx.drawImage(video, 0, 0, offscreen.width, offscreen.height);

    const b64 = offscreen.toDataURL('image/jpeg', 0.7);
    const sid = typeof SESSION_ID !== 'undefined' ? SESSION_ID : '';
    const res = await fetch(`/api/sessions/${sid}/detect-face`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: b64 }),
    });

    if (res.ok) {
      const data = await res.json();
      drawFaceOverlays(video, data.faces || []);
      const countBadge = document.getElementById('live-face-count');
      if (countBadge) countBadge.textContent = `${data.faces_detected || 0} faces detected`;
    }
  } catch (err) {
    console.error('Face scan error:', err);
  } finally {
    _isScanning = false;
  }
}

function drawFaceOverlays(video, faces) {
  const canvas = document.getElementById('live-canvas');
  if (!canvas || !video) return;

  canvas.width = video.clientWidth;
  canvas.height = video.clientHeight;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const scaleX = canvas.width / (video.videoWidth || 640);
  const scaleY = canvas.height / (video.videoHeight || 480);

  faces.forEach((f, idx) => {
    const [x, y, w, h] = f.bbox;
    const rx = x * scaleX;
    const ry = y * scaleY;
    const rw = w * scaleX;
    const rh = h * scaleY;

    // Glowing bounding box
    ctx.strokeStyle = f.is_frontal ? '#22c55e' : '#f59e0b';
    ctx.lineWidth = 2.5;
    ctx.strokeRect(rx, ry, rw, rh);

    // Label banner
    ctx.fillStyle = f.is_frontal ? 'rgba(34, 197, 94, 0.85)' : 'rgba(245, 158, 11, 0.85)';
    ctx.fillRect(rx, Math.max(0, ry - 22), rw, 22);

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px Inter, sans-serif';
    const tag = f.is_frontal ? `Face Verified ${Math.round(f.confidence * 100)}%` : `Turned Away`;
    ctx.fillText(tag, rx + 6, Math.max(15, ry - 6));

    // Landmarks (eyes, nose, mouth)
    if (f.landmarks) {
      ctx.fillStyle = '#6366f1';
      Object.values(f.landmarks).forEach(([lx, ly]) => {
        ctx.beginPath();
        ctx.arc(lx * scaleX, ly * scaleY, 3, 0, 2 * Math.PI);
        ctx.fill();
      });
    }
  });
}

# Multimodal Attendance & Engagement Agent

> **Privacy-preserving · Offline-first · AI-powered classroom analytics**

---

## Overview

The Multimodal Attendance & Engagement Agent is a full-stack web application for educational institutions that:

- **Automates attendance** from live camera or uploaded video using YOLOv8 person detection
- **Analyses engagement** by combining visual motion, participant presence, and audio activity signals
- **Generates teaching recommendations** using a rule-based engine (+ optional Google Gemini)
- **Runs entirely locally** — no student data leaves your machine

---

## Architecture

```
Browser (HTML/CSS/JS + Chart.js)
       │
Flask API Gateway (Python)
       ├── Session Routes         → CRUD + video upload + async processing
       ├── Attendance Routes      → Read & manual correction
       ├── Engagement Routes      → Windowed metrics
       ├── Recommendation Routes  → AI/rule-based suggestions
       └── Report Routes          → CSV export + health check
       │
Services Layer
       ├── VideoProcessor         → YOLOv8 detection + centroid tracker
       ├── AudioProcessor         → librosa VAD + ffmpeg extraction
       ├── EngagementService      → Weighted signal fusion
       ├── AttendanceService      → DB persistence
       ├── RecommendationService  → Rule engine + optional Gemini
       ├── AIGateway              → Gemini adapter
       └── TTSService             → pyttsx3 offline TTS
       │
Storage
       ├── SQLite (sessions, participants, metrics, recommendations, audit_log)
       └── Local filesystem (uploads, processed, reports, generated_audio)
```

---

## Installation

### Prerequisites

- Python 3.10+
- `pip`
- `ffmpeg` on PATH (for audio extraction from video)
- NVIDIA GPU optional but recommended for YOLOv8

### Steps

```bash
# 1. Clone / navigate to project
cd multimodal-attendance-agent

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env       # Windows
# cp .env.example .env       # Linux/macOS
# Edit .env as needed

# 5. Initialise database
python scripts/initialize_db.py

# Optional: seed demo data
python scripts/initialize_db.py --seed

# 6. Run the application
python app.py
```

Open **http://localhost:5000** in your browser.

---

## YOLOv8 Model Download

On first run with `CV_BACKEND=yolov8`, the `yolov8n.pt` model (~6 MB) downloads automatically from Ultralytics servers. For a fully offline deployment, pre-download it:

```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

Then copy `yolov8n.pt` to the project directory and set `YOLO_MODEL=yolov8n.pt` in `.env`.

---

## Configuration

All settings are in `.env`. Key options:

| Variable | Default | Description |
|---|---|---|
| `CV_BACKEND` | `yolov8` | `yolov8` \| `haar` \| `hog` |
| `ATTENDANCE_THRESHOLD_SECONDS` | `120` | Min presence for attendance mark |
| `FRAME_SAMPLE_RATE` | `5` | Process every Nth frame |
| `GEMINI_API_KEY` | *(blank)* | Leave blank for offline-only mode |
| `CODE_EXEC_ENABLED` | `false` | Enable sandbox code execution |
| `DATA_RETENTION_DAYS` | `90` | Auto-delete sessions after N days |
| `FACIAL_RECOGNITION_ENABLED` | `false` | Requires explicit institutional consent |

---

## Usage

### 1. Create a Session

1. Go to **Sessions** → **New Session**
2. Enter session name, subject, instructor
3. Upload a video recording (MP4/AVI/MOV/MKV/WebM, ≤ 500 MB)
4. Click **Create & Process** — processing runs in the background

### 2. Monitor Processing

A progress overlay shows real-time status. Large videos may take several minutes.

### 3. Review Attendance

Navigate to **Attendance** for the session. All participants are tracked anonymously by default. You can:
- Manually mark participants present/absent
- Assign a display name
- Flag records for review

### 4. Explore Engagement

**Engagement Analytics** shows per-minute composite scores, motion, presence, and audio activity charts.

> ⚠️ Engagement scores are approximate behavioural indicators, **not** measurements of student attention or understanding. Always use with human judgement.

### 5. AI Teaching Suggestions

**AI Suggestions** shows rule-based recommendations linked to measured evidence. Each card shows:
- The observed pattern
- The measured evidence it is based on
- A specific, actionable suggestion
- A confidence level

### 6. Export Report

Download a CSV report from the **Report** page or via `/api/sessions/<id>/report`.

---

## Privacy & Security

| Principle | Implementation |
|---|---|
| **Local processing** | All video and audio analysis runs on your machine |
| **No cloud by default** | Gemini integration is opt-in and disabled by default |
| **Anonymous tracking** | Participants identified by track ID only |
| **No facial recognition** | Disabled by default; requires explicit authorisation |
| **Data minimisation** | Configurable retention; delete sessions individually |
| **Audit logging** | All admin actions recorded in `audit_logs` table |
| **API key security** | Keys in `.env`, never in frontend JavaScript |
| **Upload validation** | File type, size, and path traversal checks |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/sessions` | GET | List all sessions |
| `/api/sessions` | POST | Create session |
| `/api/sessions/<id>` | GET | Session details |
| `/api/sessions/<id>` | PATCH | Update session |
| `/api/sessions/<id>` | DELETE | Delete session + all data |
| `/api/sessions/<id>/video` | POST | Upload video |
| `/api/sessions/<id>/process` | POST | Start processing |
| `/api/sessions/<id>/progress` | GET | Processing progress |
| `/api/sessions/<id>/attendance` | GET | Attendance records |
| `/api/sessions/<id>/attendance/<pid>` | PATCH | Update participant |
| `/api/sessions/<id>/engagement` | GET | Engagement metrics |
| `/api/sessions/<id>/recommendations` | GET | Teaching suggestions |
| `/api/sessions/<id>/report` | GET | Download CSV report |
| `/api/health` | GET | System dependency check |

---

## Troubleshooting

**YOLOv8 download fails offline:**
Pre-download the model file and set `YOLO_MODEL` to its local path.

**ffmpeg not found:**
Install from [ffmpeg.org](https://ffmpeg.org) and ensure it is on your system PATH.

**Audio analysis disabled:**
Install `librosa` and `soundfile`: `pip install librosa soundfile`

**Processing stuck:**
Check `storage/app.log` for errors. Verify the video file is a supported format.

**Database locked:**
SQLite WAL mode is enabled. Ensure only one Flask process runs at a time in development.

---

## Limitations & Responsible Use

- Engagement scores **do not** reflect student intelligence, motivation, or wellbeing
- Attendance **must not** be the sole basis for academic penalties without human review
- The system is designed for **pilot use with human oversight**
- Accuracy depends on video quality, camera angle, and lighting conditions
- Anonymous tracking does not guarantee perfect separation of identities in crowded frames

---

## Project Structure

```
multimodal-attendance-agent/
├── app.py                  # Flask entry point
├── config.py               # Configuration
├── requirements.txt
├── .env.example
├── frontend/
│   ├── templates/          # Jinja2 HTML templates
│   └── static/             # CSS + JS
├── routes/                 # Flask blueprints
├── services/               # Business logic
├── models/                 # Database schema
├── utils/                  # Shared utilities
├── storage/                # Local data (auto-created)
├── tests/                  # Unit tests
└── scripts/                # DB init + seed
```

---

*Built with Flask · OpenCV · YOLOv8 · librosa · Chart.js · SQLite*

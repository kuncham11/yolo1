# CROWDGUARD AI: Multi-Camera Crowd Monitoring & Threat Analysis

[![Python Version](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Framework](https://img.shields.io/badge/Framework-Flask_3.0-green.svg)](https://flask.palletsprojects.com)
[![Status](https://img.shields.io/badge/Phase_1-Operational_Control_Room-cyan.svg)]()
[![Platform](https://img.shields.io/badge/OS-Windows_11-purple.svg)]()

> **"AI-Based Multi-Camera Crowd Monitoring, Weapon Detection, and Abnormal Behaviour Analysis System"**

---

## 1. Project Overview
**CROWDGUARD AI** is a college-level, enterprise-grade AI surveillance and threat-analysis platform. It is engineered to monitor multiple CCTV video feeds simultaneously, providing real-time AI perception, behaviour analytics, and automated incident triage.

### Core Capabilities
- **Person Detection & Tracking**: YOLOv11 and ByteTrack ID association.
- **Crowd Dynamics**: Real-time count and density classification (`NORMAL`, `MODERATE`, `HIGH`).
- **Weapon Detection Adapter**: Multi-frame persistent weapon verification with dedicated fallback `DEMO MODE`.
- **Temporal Action Recognition**: Multi-frame video clip violence detection.
- **Abnormal Movement Engine**: Running sprint detection, loitering dwell calculation, sudden motion, and crowd surge coherent motion.
- **Restricted Zone Protection**: Geofenced entry violation alerts with cooldown deduplication.
- **Threat Fusion & Risk Scoring**: 0–100 heuristic severity engine (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Control Room Interface**: Dark-themed security operations dashboard with live HUD overlays, Chart.js telemetry, and alert dispatch.

---

## 2. AI Architecture
```text
VIDEO INPUT (Webcam / MP4 / RTSP)
     │
     ▼
VIDEO STREAM MANAGER
     │
     ▼
FRAME PREPROCESSING
     │
     ├───► PERSON DETECTION (YOLOv11) ───► BYTETRACK ───► TRACKS ──► MOVEMENT / LOITERING / ZONES
     │                                                                      │
     └───► WEAPON DETECTION (Dedicated Model / Demo Mode)                   │
                                                                            ▼
                                                                     VIOLENCE MODEL
                                                                            │
                                                                            ▼
                                                                      THREAT FUSION
                                                                            │
                                                                            ▼
                                                                       RISK ENGINE
                                                                            │
                                                                   ┌────────┴────────┐
                                                                   ▼                 ▼
                                                              ALERT SYSTEM       DASHBOARD (Flask UI)
                                                                   │
                                                                   ▼
                                                                MongoDB
```

---

## 3. Project Directory Structure
```text
CrowdGuardAI/
├── app.py                     # Main Flask entrypoint
├── config.py                  # Centralized configuration & environment loader
├── requirements.txt           # Python dependencies
├── .env                       # Active environment configuration
├── .env.example               # Environment template
├── README.md                  # System manual and documentation
│
├── routes/                    # Modular Flask Blueprints
│   ├── auth.py                # Authentication and session handlers
│   ├── cameras.py             # Camera CRUD and stream metadata
│   ├── alerts.py              # Threat dispatch and alert management
│   └── analytics.py           # Dashboard statistics and Chart.js feeds
│
├── templates/                 # Dark Security Control-Room HTML5 Templates
│   ├── base.html              # Master layout with cyber HUD and sidebar
│   ├── login.html             # Security clearance login screen
│   ├── dashboard.html         # 2x2 CCTV live grid, KPI cards & active threats
│   ├── cameras.html           # Multi-camera grid and registration modal
│   ├── camera_detail.html     # Deep camera HUD with overlay toggles
│   ├── threats.html           # Threat center with Ack/Resolve actions
│   ├── behaviour.html         # Anomaly frequency charts & weight matrices
│   ├── history.html           # Forensic event history with multi-attribute filters
│   ├── analytics.html         # Longitudinal footfall and risk charts
│   ├── settings.html          # Configurable confidence and heuristic weights
│   └── 404.html               # Custom 404 error page
│
├── static/                    # Frontend assets
│   ├── css/
│   │   └── style.css          # Control-room dark theme styling
│   └── js/
│       ├── dashboard.js       # Live chart initialization & telemetry polling
│       ├── cameras.js         # Camera registration and stream operations
│       ├── alerts.js          # Threat triage (ACK, Resolve, False Positive)
│       └── analytics.js       # Chart.js analytics visualizations
│
├── models/                    # Model weights storage
│   ├── person/                # YOLOv11 person weights
│   ├── weapon/                # Weapon detector weights
│   └── violence/              # Temporal violence action weights
│
├── cameras/                   # Stream manager and camera worker processes
├── detection/                 # Object detection adapters
├── tracking/                  # ByteTrack integration
├── behaviour/                 # Movement, loitering, and zone engines
├── violence/                  # Temporal clip action recognition
├── risk/                      # Multi-signal risk fusion engine
├── alerts/                    # Alert deduplication and manager
├── database/                  # MongoDB schemas and client
└── tests/                     # Automated PyTest test suites
    └── test_api.py            # API endpoint and route tests
```

---

## 4. Installation & Setup (Windows 11)

### Step 1: Open PowerShell / Terminal in Project Directory
```powershell
cd C:\Users\Rohith\Desktop\project3
```

### Step 2: Create and Activate Python Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell restricts script execution, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first)*

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
```

---

## 5. Running the Application

### Run with Python:
```powershell
python app.py
```

### Open in Browser:
Navigate to:
```text
http://127.0.0.1:5000/
```

### Security Clearance Credentials (Demo Mode):
- **Username**: `admin`
- **Password**: `password123`

---

## 6. Running Automated Tests
```powershell
pytest tests/
```

---

## 7. Roadmap & Next Phases
- [x] **Phase 1**: Flask App, Control Room Dashboard, Dark CCTV Theme, Mock Streams & REST APIs.
- [ ] **Phase 2**: MongoDB Persistence Layer (Cameras, Alerts, Behavior Events).
- [ ] **Phase 3**: YOLOv11 Person Detection Model.
- [ ] **Phase 4**: ByteTrack Multi-Object Persistent Tracking.
- [ ] **Phase 5**: Crowd Counting & Density Classifier.
- [ ] **Phase 6**: Geofenced Restricted Area Intrusion Detection.
- [ ] **Phase 7**: Movement Analysis (Running & Loitering Detection).
- [ ] **Phase 8**: Dedicated Weapon Detection Adapter & Demo Mode.
- [ ] **Phase 9**: Temporal Violence Recognition Adapter & Demo Mode.
- [ ] **Phase 10**: Advanced Abnormal Behavior (Crowd Surge & Accumulation).
- [ ] **Phase 11**: Multi-Signal Threat Fusion.
- [ ] **Phase 12**: 0–100 Risk Scoring Engine.
- [ ] **Phase 13**: Alert Deduplication & Dispatch Manager.
- [ ] **Phase 14**: Multi-Camera Real-Time OpenCV Video Pipelines.
- [ ] **Phase 15**: Live Analytics & Forensic Reporting.
- [ ] **Phase 16**: Final Optimization, PyTest Suite & Demonstration Scenarios.

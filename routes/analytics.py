import os
import time
from flask import Blueprint, jsonify, render_template, request
from werkzeug.utils import secure_filename
from database.mongo import db_manager
from cameras.stream_manager import stream_manager, CameraWorker
from audio.audio_analyzer import audio_analyzer

analytics_bp = Blueprint("analytics", __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'aac', 'm4a', 'ogg', 'flac'}

def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

def allowed_audio(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

@analytics_bp.route("/analytics")
def analytics_view():
    return render_template("analytics.html")

@analytics_bp.route("/behaviour")
def behaviour_view():
    uploaded_cam = db_manager.get_camera("CCTV-UPLOAD")
    alerts = db_manager.get_alerts()
    
    loitering_count = sum(1 for a in alerts if "LOITERING" in a.get("event_type", ""))
    running_count = sum(1 for a in alerts if "RUNNING" in a.get("event_type", "") or "SUDDEN" in a.get("event_type", ""))
    intrusion_count = sum(1 for a in alerts if "RESTRICTED" in a.get("event_type", "") or "ZONE" in a.get("event_type", ""))
    abnormal_count = sum(1 for a in alerts if "ABNORMAL" in a.get("event_type", "") or "DIRECTION" in a.get("event_type", ""))
    surge_count = sum(1 for a in alerts if "SURGE" in a.get("event_type", "") or "CROWD" in a.get("event_type", ""))
    violence_count = sum(1 for a in alerts if "VIOLENCE" in a.get("event_type", ""))

    return render_template(
        "behaviour.html",
        uploaded_camera=uploaded_cam,
        loitering_count=loitering_count,
        running_count=running_count,
        intrusion_count=intrusion_count,
        abnormal_count=abnormal_count,
        surge_count=surge_count,
        violence_count=violence_count
    )

@analytics_bp.route("/settings")
def settings_view():
    return render_template("settings.html")

@analytics_bp.route("/api/upload_audio", methods=["POST"])
def upload_audio_track():
    """
    Upload an MP3/WAV/AAC audio file to run Acoustic Threat & Decibel Analysis.
    """
    if 'audio_file' not in request.files:
        return jsonify({"status": "error", "message": "No audio file provided"}), 400

    file = request.files['audio_file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    if file and allowed_audio(file.filename):
        filename = secure_filename(file.filename)
        base, ext = os.path.splitext(filename)
        unique_filename = f"{base}_{int(time.time())}{ext}"
        audio_dir = os.path.join(UPLOAD_FOLDER, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        save_path = os.path.join(audio_dir, unique_filename)
        file.save(save_path)

        camera_id = request.form.get("camera_id", "CCTV-01")
        # Run Acoustic Threat Analyzer
        analysis_result = audio_analyzer.analyze_file(save_path, camera_id=camera_id)
        analysis_result["audio_url"] = f"/uploads/audio/{unique_filename}"
        return jsonify(analysis_result)

    return jsonify({"status": "error", "message": "Unsupported audio format. Please upload MP3, WAV, AAC, or OGG."}), 400

@analytics_bp.route("/api/upload_cctv", methods=["POST"])
def upload_cctv_video():
    """
    Upload an MP4 / video file to run AI Behaviour Analysis & Threat Extraction.
    """
    if 'video_file' not in request.files:
        return jsonify({"status": "error", "message": "No video file provided"}), 400

    file = request.files['video_file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    if file and allowed_video(file.filename):
        filename = secure_filename(file.filename)
        # Unique timestamped filename
        base, ext = os.path.splitext(filename)
        unique_filename = f"{base}_{int(time.time())}{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(save_path)

        camera_id = "CCTV-UPLOAD"
        camera_name = f"Uploaded: {filename}"
        
        # Register or update CCTV-UPLOAD in MongoDB
        cam_doc = {
            "camera_id": camera_id,
            "name": camera_name,
            "location": "Uploaded Forensic Sandbox",
            "source_type": "Video File",
            "stream_url": save_path,
            "status": "ONLINE",
            "enabled": True,
            "resolution": "1920x1080",
            "fps_limit": 30,
            "people_count": 0,
            "density": "NORMAL",
            "risk_level": "LOW",
            "risk_score": 0,
            "latest_event": "Footage Loaded - AI Analysis Running"
        }

        existing = db_manager.get_camera(camera_id)
        if existing:
            db_manager.update_camera(camera_id, cam_doc)
        else:
            db_manager.add_camera(cam_doc)

        # Stop existing worker if running and spawn new worker on the uploaded file
        old_worker = stream_manager.get_worker(camera_id)
        if old_worker:
            old_worker.stop()

        new_worker = CameraWorker(
            camera_id=camera_id,
            name=camera_name,
            stream_url=save_path,
            source_type="Video File",
            fps_limit=30,
            detector=stream_manager.detector
        )
        stream_manager.workers[camera_id] = new_worker
        new_worker.start()

        return jsonify({
            "status": "success",
            "message": f"Footage '{filename}' uploaded and queued for AI Behaviour Analysis.",
            "camera_id": camera_id,
            "stream_url": f"/api/cameras/{camera_id}/stream",
            "file_path": save_path
        })

    return jsonify({"status": "error", "message": "Unsupported file format. Please upload MP4, AVI, or MOV."}), 400

@analytics_bp.route("/api/llm_analyze_frame", methods=["POST"])
def llm_analyze_frame_route():
    """
    Triggers Multi-Modal LLM Vision analysis on a specific camera stream or uploaded frame
    to identify exact person counts, location bounding boxes, and detect weapons (guns, knives).
    """
    from detection.llm_vision import llm_vision
    payload = request.get_json() or {}
    camera_id = payload.get("camera_id", "CCTV-UPLOAD")

    worker = stream_manager.get_worker(camera_id)
    if not worker:
        worker = stream_manager.get_worker("CCTV-01")

    frame = None
    detections = []
    if worker:
        if worker.current_frame is not None:
            frame = worker.current_frame
        detections = worker.get_detections()

    analysis = llm_vision.analyze_frame(frame, camera_id=camera_id, active_detections=detections)
    return jsonify(analysis)


@analytics_bp.route("/api/dashboard/summary", methods=["GET"])
def get_dashboard_summary():
    cameras = db_manager.get_cameras()
    alerts = db_manager.get_alerts()

    online_count = sum(1 for c in cameras if c.get("status") == "ONLINE")
    total_cameras = len(cameras)
    total_people = sum(c.get("people_count", 0) for c in cameras)
    active_threats = sum(1 for a in alerts if a.get("status") in ("NEW", "ACKNOWLEDGED"))
    
    # Calculate highest risk index across all cameras
    highest_score = max((c.get("risk_score", 0) for c in cameras), default=0)
    if highest_score >= 81:
        highest_level = "CRITICAL"
    elif highest_score >= 61:
        highest_level = "HIGH"
    elif highest_score >= 31:
        highest_level = "MEDIUM"
    else:
        highest_level = "LOW"

    # Density breakdown
    density_counts = {"NORMAL": 0, "MODERATE": 0, "HIGH": 0}
    for c in cameras:
        d = c.get("density", "NORMAL")
        if d in density_counts:
            density_counts[d] += 1

    return jsonify({
        "status": "success",
        "database_connected": db_manager.is_connected(),
        "cameras_online": f"{online_count}/{total_cameras}",
        "total_cameras": total_cameras,
        "online_count": online_count,
        "total_people_detected": total_people,
        "active_threats_count": active_threats,
        "highest_risk_level": highest_level,
        "highest_risk_score": highest_score,
        "system_status": "OPTIMAL" if db_manager.is_connected() else "STANDALONE (In-Memory Fallback)",
        "crowd_density_breakdown": density_counts,
        "hourly_people_flow": [24, 38, 55, 78, 110, 142, 126, total_people],
        "hourly_timestamps": ["16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:00"],
        "threat_distribution": {
            "Weapon Flags": sum(1 for a in alerts if "WEAPON" in a.get("event_type", "")),
            "Zone Intrusion": sum(1 for a in alerts if "RESTRICTED" in a.get("event_type", "") or "ZONE" in a.get("event_type", "")),
            "Loitering": sum(1 for a in alerts if "LOITERING" in a.get("event_type", "")),
            "Running/Sudden": sum(1 for a in alerts if "RUNNING" in a.get("event_type", "") or "SUDDEN" in a.get("event_type", "")),
            "Possible Violence": sum(1 for a in alerts if "VIOLENCE" in a.get("event_type", ""))
        },
        "behaviour_statistics": {
            "Loitering": sum(1 for a in alerts if "LOITERING" in a.get("event_type", "")),
            "Running": sum(1 for a in alerts if "RUNNING" in a.get("event_type", "") or "SUDDEN" in a.get("event_type", "")),
            "Restricted Entry": sum(1 for a in alerts if "RESTRICTED" in a.get("event_type", "") or "ZONE" in a.get("event_type", "")),
            "Abnormal Movement": sum(1 for a in alerts if "ABNORMAL" in a.get("event_type", "") or "DIRECTION" in a.get("event_type", "")),
            "Crowd Surge": sum(1 for a in alerts if "SURGE" in a.get("event_type", "") or "CROWD" in a.get("event_type", "")),
            "Possible Violence": sum(1 for a in alerts if "VIOLENCE" in a.get("event_type", ""))
        }
    })

@analytics_bp.route("/api/behaviour/live", methods=["GET"])
def get_behaviour_live_stream():
    """
    Returns real-time behaviour anomaly events, active track counts,
    and instantaneous risk scoring for the active surveillance stream.
    """
    camera_id = request.args.get("camera_id", "CCTV-UPLOAD")
    worker = stream_manager.get_worker(camera_id)
    if not worker:
        worker = stream_manager.get_worker("CCTV-01")

    active_tracks = worker.get_detections() if worker else []
    active_count = len(active_tracks)
    
    # Extract instantaneous behaviour anomalies
    events = []
    if worker:
        with worker.lock:
            events = list(worker.latest_events)
    
    # Calculate current live risk score
    cam_doc = db_manager.get_camera(camera_id) or {}
    alerts = db_manager.get_alerts()
    
    loitering_count = sum(1 for a in alerts if "LOITERING" in a.get("event_type", ""))
    running_count = sum(1 for a in alerts if "RUNNING" in a.get("event_type", "") or "SUDDEN" in a.get("event_type", ""))
    intrusion_count = sum(1 for a in alerts if "RESTRICTED" in a.get("event_type", "") or "ZONE" in a.get("event_type", ""))
    abnormal_count = sum(1 for a in alerts if "ABNORMAL" in a.get("event_type", "") or "DIRECTION" in a.get("event_type", ""))
    surge_count = sum(1 for a in alerts if "SURGE" in a.get("event_type", "") or "CROWD" in a.get("event_type", ""))
    violence_count = sum(1 for a in alerts if "VIOLENCE" in a.get("event_type", ""))

    # Base risk score calculation
    base_risk = 0
    if events:
        base_risk = max((e.get("risk_weight", 15) for e in events), default=15)
    elif active_count > 20:
        base_risk = 65
    elif active_count > 10:
        base_risk = 40
    else:
        base_risk = 15

    risk_level = "CRITICAL" if base_risk >= 80 else ("HIGH" if base_risk >= 60 else ("MEDIUM" if base_risk >= 30 else "LOW"))

    return jsonify({
        "status": "success",
        "camera_id": camera_id,
        "active_people_count": active_count,
        "risk_score": base_risk,
        "risk_level": risk_level,
        "events": events,
        "counts": {
            "loitering": loitering_count,
            "running": running_count,
            "intrusion": intrusion_count,
            "abnormal": abnormal_count,
            "surge": surge_count,
            "violence": violence_count
        }
    })


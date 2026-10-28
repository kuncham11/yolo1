import base64
import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None

from flask import Blueprint, request, jsonify, render_template, Response, redirect, url_for
from database.mongo import db_manager
from cameras.stream_manager import stream_manager

cameras_bp = Blueprint("cameras", __name__)

@cameras_bp.route("/cameras")
def cameras_view():
    cameras = db_manager.get_cameras()
    return render_template("cameras.html", cameras=cameras)

@cameras_bp.route("/camera/<camera_id>")
def camera_detail_view(camera_id):
    cam = db_manager.get_camera(camera_id)
    if not cam:
        cameras = db_manager.get_cameras()
        cam = cameras[0] if cameras else None
    if not cam:
        return redirect(url_for("cameras.cameras_view"))
    return render_template("camera_detail.html", camera=cam)

@cameras_bp.route("/api/cameras", methods=["GET"])
def get_cameras():
    cameras = db_manager.get_cameras()
    camera_list = []
    for cam in cameras:
        c_copy = dict(cam)
        cid = c_copy.get("camera_id")
        worker = stream_manager.get_worker(cid)
        if worker:
            with worker.lock:
                dets = list(worker.latest_detections)
                worker_fps = round(worker.fps_actual, 1)
            c_copy["people_count"] = len(dets)
            motion_count = sum(1 for d in dets if d.get("velocity", 0.0) > 1.5)
            c_copy["motion_count"] = motion_count
            c_copy["motion_status"] = "MOTION DETECTED" if motion_count > 0 else "STATIONARY"
            c_copy["fps_actual"] = worker_fps
        else:
            c_copy.setdefault("motion_count", 0)
            c_copy.setdefault("motion_status", "IDLE")
        camera_list.append(c_copy)

    return jsonify({
        "status": "success",
        "count": len(camera_list),
        "database_connected": db_manager.is_connected(),
        "data": camera_list
    })

@cameras_bp.route("/api/cameras", methods=["POST"])
def add_camera():
    payload = request.get_json() or {}
    if not payload.get("name") or not payload.get("stream_url"):
        return jsonify({"status": "error", "message": "Camera name and stream URL are required"}), 400

    new_cam = db_manager.add_camera(payload)
    # Synchronize worker in stream_manager
    cid = new_cam.get("camera_id")
    if cid:
        stream_manager.register_or_update_worker(
            camera_id=cid,
            name=new_cam.get("name", "CCTV Feed"),
            stream_url=new_cam.get("stream_url", "0"),
            source_type=new_cam.get("source_type", "Webcam"),
            fps_limit=new_cam.get("fps_limit", 30)
        )

    return jsonify({
        "status": "success",
        "message": "Camera registered successfully in MongoDB",
        "data": new_cam
    }), 201

@cameras_bp.route("/api/cameras/<camera_id>", methods=["PUT"])
def update_camera(camera_id):
    payload = request.get_json() or {}
    cam = db_manager.get_camera(camera_id)
    if not cam:
        return jsonify({"status": "error", "message": "Camera not found"}), 404

    updated_cam = db_manager.update_camera(camera_id, payload)
    # Synchronize worker if updated
    if updated_cam:
        stream_manager.register_or_update_worker(
            camera_id=camera_id,
            name=updated_cam.get("name", cam.get("name")),
            stream_url=updated_cam.get("stream_url", cam.get("stream_url")),
            source_type=updated_cam.get("source_type", cam.get("source_type", "Webcam")),
            fps_limit=updated_cam.get("fps_limit", cam.get("fps_limit", 30))
        )

    return jsonify({
        "status": "success",
        "message": "Camera updated successfully",
        "data": updated_cam
    })

@cameras_bp.route("/api/cameras/<camera_id>", methods=["DELETE"])
def delete_camera(camera_id):
    success = db_manager.delete_camera(camera_id)
    if success:
        stream_manager.stop_worker(camera_id)
        return jsonify({"status": "success", "message": f"Camera {camera_id} deleted successfully"})
    return jsonify({"status": "error", "message": "Camera not found"}), 404

@cameras_bp.route("/api/database/clear", methods=["POST"])
def clear_database_data():
    """
    Clears all stored cameras, alerts, behaviour events, and detections.
    """
    db_manager.clear_all_data()
    for cid in list(stream_manager.workers.keys()):
        stream_manager.stop_worker(cid)
    return jsonify({
        "status": "success",
        "message": "All stored cameras and surveillance telemetry cleared."
    })

@cameras_bp.route("/api/cameras/laptop/status", methods=["GET"])
def get_laptop_camera_status():
    """
    Checks hardware accessibility of laptop webcam / local camera devices.
    """
    status_info = stream_manager.test_webcam_available()
    worker = stream_manager.get_worker("CCTV-01")
    is_active = bool(worker and not worker.is_synthetic)
    return jsonify({
        "status": "success",
        "hardware_test": status_info,
        "is_active_streaming": is_active,
        "active_camera_id": "CCTV-01" if is_active else None
    })

@cameras_bp.route("/api/cameras/laptop/activate", methods=["POST"])
def activate_laptop_camera():
    """
    Activates the laptop camera on a specific camera node (default CCTV-01) for live behaviour detection.
    """
    payload = request.get_json() or {}
    camera_id = payload.get("camera_id", "CCTV-01")
    dev_index = int(payload.get("device_index", 0))

    result = stream_manager.activate_laptop_webcam(camera_id=camera_id, device_index=dev_index)
    return jsonify({
        "status": "success",
        "data": result,
        "message": f"Laptop camera connected to node {camera_id}."
    })

@cameras_bp.route("/api/cameras/<camera_id>/ingest_frame", methods=["POST"])
def ingest_camera_frame(camera_id):
    """
    Ingest a base64 or multipart frame from client browser webcam to run real-time behaviour detection.
    """
    worker = stream_manager.get_worker(camera_id)
    if not worker:
        worker = stream_manager.register_or_update_worker(
            camera_id=camera_id,
            name=f"Webcam ({camera_id})",
            stream_url="0",
            source_type="Webcam"
        )

    raw_bytes = None
    if request.is_json:
        data = request.get_json() or {}
        b64_str = data.get("frame") or data.get("image_base64", "")
        if b64_str:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            try:
                raw_bytes = base64.b64decode(b64_str)
            except Exception as e:
                return jsonify({"status": "error", "message": f"Invalid base64 frame: {e}"}), 400
    elif 'frame' in request.files:
        raw_bytes = request.files['frame'].read()

    if raw_bytes and cv2 is not None:
        try:
            nparr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                worker.ingest_frame(img)
                return jsonify({
                    "status": "success",
                    "camera_id": camera_id,
                    "detections_count": len(worker.latest_detections),
                    "events_count": len(worker.latest_events),
                    "events": worker.latest_events
                })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Frame decoding error: {e}"}), 500

    return jsonify({"status": "error", "message": "No valid frame image received"}), 400

@cameras_bp.route("/api/cameras/<camera_id>/status", methods=["GET"])
def get_camera_status(camera_id):
    cam = db_manager.get_camera(camera_id)
    if cam:
        worker = stream_manager.get_worker(camera_id)
        return jsonify({
            "status": "success",
            "data": cam,
            "worker_active": bool(worker and worker.running),
            "is_synthetic": worker.is_synthetic if worker else True,
            "fps_actual": round(worker.fps_actual, 1) if worker else 0.0,
            "database_connected": db_manager.is_connected()
        })
    return jsonify({"status": "error", "message": "Camera not found"}), 404

@cameras_bp.route("/api/cameras/<camera_id>/preview")
@cameras_bp.route("/api/cameras/<camera_id>/snapshot")
def camera_preview_image(camera_id):
    """
    Returns a single JPEG snapshot frame. Does not hold an infinite stream.
    Used for card thumbnails to prevent browser HTTP connection starvation.
    """
    worker = stream_manager.get_worker(camera_id)
    if not worker:
        cam = db_manager.get_camera(camera_id)
        if cam:
            worker = stream_manager.register_or_update_worker(
                camera_id=camera_id,
                name=cam.get("name", f"Camera {camera_id}"),
                stream_url=cam.get("stream_url", "0"),
                source_type=cam.get("source_type", "Webcam"),
                fps_limit=cam.get("fps_limit", 30)
            )
    if worker:
        frame_bytes = worker.get_jpeg_frame()
        return Response(frame_bytes, mimetype="image/jpeg")
    return Response(b'', mimetype="image/jpeg", status=404)

@cameras_bp.route("/api/cameras/<camera_id>/stream")
def camera_video_stream(camera_id):
    """
    Real-time MJPEG live video feed endpoint with YOLOv11 person detection overlays.
    """
    return Response(
        stream_manager.generate_mjpeg_stream(camera_id),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@cameras_bp.route("/api/cameras/<camera_id>/detections", methods=["GET"])
def get_camera_detections(camera_id):
    """
    Fetch active real-time person detections for a specific camera.
    """
    worker = stream_manager.get_worker(camera_id)
    if worker:
        dets = worker.get_detections()
        return jsonify({
            "status": "success",
            "camera_id": camera_id,
            "count": len(dets),
            "detections": dets
        })
    return jsonify({"status": "error", "message": "Camera stream worker not found"}), 404

@cameras_bp.route("/api/cameras/<camera_id>/behaviour", methods=["GET"])
def get_camera_behaviour(camera_id):
    """
    Fetch live behaviour anomaly telemetry, kinematics, and events for a camera.
    Includes real-time person count and motion detection status without default person IDs.
    """
    worker = stream_manager.get_worker(camera_id)
    cam = db_manager.get_camera(camera_id) or {}
    if worker:
        with worker.lock:
            events = list(worker.latest_events)
            dets = list(worker.latest_detections)
            fps = round(worker.fps_actual, 1)
            is_synth = worker.is_synthetic

        motion_count = sum(1 for d in dets if d.get("velocity", 0.0) > 1.5)
        motion_status = "MOTION DETECTED" if motion_count > 0 else "STATIONARY"

        # Sanitize event descriptions to not leak default person track IDs
        cleaned_events = []
        import re
        for evt in events:
            e_copy = dict(evt)
            desc = e_copy.get("description", "")
            desc = re.sub(r'Track\s*#\d+', 'Identified Person', desc)
            e_copy["description"] = desc
            cleaned_events.append(e_copy)

        return jsonify({
            "status": "success",
            "camera_id": camera_id,
            "people_count": len(dets),
            "motion_count": motion_count,
            "motion_status": motion_status,
            "events": cleaned_events,
            "fps": fps,
            "is_synthetic": is_synth,
            "density": cam.get("density", "NORMAL"),
            "risk_score": cam.get("risk_score", 15),
            "risk_level": cam.get("risk_level", "LOW")
        })
    return jsonify({"status": "error", "message": "Camera worker not found"}), 404

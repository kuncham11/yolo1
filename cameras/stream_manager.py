import os
import time
import threading
import logging
from config import Config
from detection.person_detector import PersonDetector
from detection.weapon_detector import WeaponDetector
from violence.action_model import ViolenceDetector
from detection.face_recognizer import FaceRecognizer
from detection.utils import draw_person_boxes, create_camera_standby_frame, create_synthetic_feed_frame, CV2_AVAILABLE
from tracking.tracker import ByteTracker
from behaviour.abnormal import BehaviourEngine
from detection.accident_detector import accident_detector, AccidentDetector
from database.mongo import db_manager

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger("CrowdGuard.StreamManager")

# Minimal valid 1x1 fallback JPEG header and payload
FALLBACK_JPEG_BYTES = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08'
    b'\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' '
    b'",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00'
    b'\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
    b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
)

class CameraWorker:
    """
    Dedicated background worker thread for an individual CCTV camera feed.
    Captures frames from Webcams or MP4 files, runs YOLOv11 person detection,
    runs dedicated WeaponDetector adapter, runs temporal ViolenceDetector,
    maintains ByteTrack persistent track IDs and kinematics, processes real-time
    behaviour anomaly detection, draws high-tech HUD overlays, and yields MJPEG streams.
    """
    def __init__(self, camera_id, name, stream_url, source_type="Webcam", fps_limit=30, detector=None, weapon_detector=None, violence_detector=None, face_recognizer=None, accident_detector_inst=None):
        self.camera_id = camera_id
        self.name = name
        self.stream_url = stream_url
        self.source_type = source_type
        self.fps_limit = fps_limit
        self.detector = detector
        self.weapon_detector = weapon_detector or WeaponDetector(model_path=Config.WEAPON_MODEL_PATH)
        self.violence_detector = violence_detector or ViolenceDetector(model_path=Config.VIOLENCE_MODEL_PATH)
        self.face_recognizer = face_recognizer or FaceRecognizer(model_path=Config.FACE_MODEL_PATH)
        self.accident_detector = accident_detector_inst or accident_detector or AccidentDetector()
        self.tracker = ByteTracker(
            iou_threshold=float(os.getenv("IOU_THRESHOLD", 0.35)),
            high_conf_thresh=float(os.getenv("CONFIDENCE_THRESHOLD", 0.45)),
            max_lost_frames=30
        )
        self.behaviour_engine = BehaviourEngine(camera_id=self.camera_id)

        self.running = False
        self.cap = None
        self.current_frame = None
        self.external_frame = None
        self.last_external_frame_time = 0.0
        self.latest_detections = []
        self.latest_weapons = []
        self.latest_accidents = []
        self.latest_faces = []
        self.latest_violence_label = "NORMAL"
        self.latest_events = []
        self.fps_actual = 0.0
        self.is_synthetic = False
        self.tick = 0
        self.lock = threading.Lock()
        self.thread = None
        self.read_fail_count = 0

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_capture_loop, daemon=True)
            self.thread.start()
            logger.info(f"Started camera worker for {self.camera_id} ({self.name})")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        logger.info(f"Stopped camera worker for {self.camera_id}")

    def _open_capture(self):
        if not CV2_AVAILABLE or cv2 is None:
            self.is_synthetic = True
            return

        try:
            # Handle integer webcam indices (e.g. "0" for laptop webcam)
            url_str = str(self.stream_url).strip()
            if url_str.isdigit():
                dev_idx = int(url_str)
                # First try CAP_DSHOW on Windows for fast and reliable DirectShow initialization
                if hasattr(cv2, 'CAP_DSHOW'):
                    self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
                # Fallback to default backend if CAP_DSHOW didn't open
                if not self.cap or not self.cap.isOpened():
                    self.cap = cv2.VideoCapture(dev_idx)
                # If index 0 failed and requested dev_idx was 0, probe index 1
                if (not self.cap or not self.cap.isOpened()) and dev_idx == 0:
                    self.cap = cv2.VideoCapture(1, cv2.CAP_DSHOW) if hasattr(cv2, 'CAP_DSHOW') else cv2.VideoCapture(1)
            else:
                self.cap = cv2.VideoCapture(str(self.stream_url))

            if not self.cap or not self.cap.isOpened():
                logger.warning(f"Could not open video stream '{self.stream_url}' for {self.camera_id}. Using synthetic feed.")
                self.is_synthetic = True
            else:
                self.is_synthetic = False
                try:
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                except Exception:
                    pass
                logger.info(f"Video capture opened successfully for {self.camera_id} (source: {self.stream_url})")
        except Exception as e:
            logger.error(f"Error opening camera {self.camera_id}: {e}")
            self.is_synthetic = True

    def switch_source(self, stream_url, source_type="Webcam", name=None, fps_limit=None):
        """
        Dynamically changes camera source (e.g. to laptop webcam '0' or video file).
        """
        with self.lock:
            self.stream_url = stream_url
            self.source_type = source_type
            if name:
                self.name = name
            if fps_limit:
                self.fps_limit = int(fps_limit)
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            self.external_frame = None
            self._open_capture()

    def ingest_frame(self, frame_bgr):
        """
        Ingest a raw frame from client browser webcam or external stream.
        """
        with self.lock:
            self.external_frame = frame_bgr
            self.last_external_frame_time = time.time()
            self.is_synthetic = False

    def _run_capture_loop(self):
        self._open_capture()
        last_time = time.time()
        frame_interval = 1.0 / max(1, self.fps_limit)

        while self.running:
            start_loop = time.time()
            self.tick += 1
            raw_frame = None
            ret = False

            # Check if an external frame was recently ingested (e.g. from browser webcam)
            with self.lock:
                if self.external_frame is not None and (start_loop - self.last_external_frame_time < 2.5):
                    raw_frame = self.external_frame.copy()
                    ret = True
                    self.is_synthetic = False

            if not ret and not self.is_synthetic and self.cap and self.cap.isOpened():
                try:
                    ret, raw_frame = self.cap.read()
                except Exception:
                    ret = False

                if not ret:
                    if self.source_type == "Video File":
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        try:
                            ret, raw_frame = self.cap.read()
                        except Exception:
                            ret = False
                    elif str(self.stream_url).strip().isdigit():
                        self.read_fail_count += 1
                        # If hardware webcam fails to grab frames repeatedly, transition gracefully to synthetic feed
                        if self.read_fail_count > 8:
                            logger.warning(f"Webcam {self.camera_id} could not grab frames (camera in use by another app or permissions restricted). Switching to synthetic surveillance feed.")
                            self.is_synthetic = True
                            if self.cap:
                                try:
                                    self.cap.release()
                                except Exception:
                                    pass
                                self.cap = None
                else:
                    self.read_fail_count = 0

            if ret and raw_frame is not None:
                # Resize to standard processing resolution if large
                h, w = raw_frame.shape[:2]
                if w > 1280:
                    raw_frame = cv2.resize(raw_frame, (1280, 720))

                # Run YOLOv11 person detection
                if self.detector:
                    raw_detections = self.detector.detect(raw_frame, camera_id=self.camera_id)
                else:
                    raw_detections = []

                # Run dedicated WeaponDetector adapter
                weapons, wpn_event = self.weapon_detector.process_frame(raw_frame, camera_id=self.camera_id)

                # Run temporal action recognition & violence detector
                v_label, v_conf, v_event = self.violence_detector.process_frame(raw_frame, camera_id=self.camera_id)

                # Run ByteTrack multi-object association for persistent track IDs
                detections = self.tracker.update(raw_detections, camera_id=self.camera_id)

                # Run AI Accident & Fall Detector
                accidents, acc_event = self.accident_detector.process_tracks_and_frame(detections, frame=raw_frame, camera_id=self.camera_id)

                # Run Face Recognition & Identification
                faces = self.face_recognizer.detect_and_recognize(raw_frame, camera_id=self.camera_id)

                # Overlay bounding boxes, persistent IDs, weapon warning boxes, accident boxes & surveillance HUD
                frame = draw_person_boxes(
                    raw_frame,
                    detections,
                    weapons=weapons,
                    accidents=accidents,
                    camera_id=self.camera_id,
                    fps=self.fps_actual,
                    show_hud=True
                )
                if faces:
                    frame = self.face_recognizer.draw_face_boxes(frame, faces)
            else:
                faces = []
                weapons = []
                accidents = []
                detections = []
                # Clean pitch-black CCTV standby frame until camera is activated
                frame, _ = create_camera_standby_frame(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    tick=self.tick,
                    draw_overlay=True
                )

            # Run Behaviour Engine on active tracks (running, loitering, surge, restricted entry)
            behavior_events = self.behaviour_engine.process_frame_tracks(detections)

            # Update FPS calculations
            now = time.time()
            dt = now - last_time
            last_time = now
            if dt > 0:
                self.fps_actual = (self.fps_actual * 0.9) + ((1.0 / dt) * 0.1)

            with self.lock:
                self.current_frame = frame
                self.latest_detections = detections
                self.latest_weapons = weapons
                self.latest_accidents = accidents
                self.latest_faces = faces
                self.latest_events = behavior_events

            # Update database telemetry & detection history periodically (every ~30 frames / 1s)
            if self.tick % 30 == 0:
                active_count = len(detections)
                latest_evt_desc = behavior_events[0]["description"] if behavior_events else "Normal Flow"
                self._sync_telemetry(active_count, latest_evt=latest_evt_desc)
                for det in detections:
                    db_manager.log_detection({
                        "camera_id": self.camera_id,
                        "track_id": det.get("track_id"),
                        "object_type": "person",
                        "confidence": det.get("confidence"),
                        "bbox": det.get("bbox"),
                        "centroid": det.get("centroid"),
                        "velocity": det.get("velocity"),
                        "direction": det.get("direction"),
                        "timestamp": det.get("timestamp")
                    })

            # Maintain target FPS limit
            elapsed = time.time() - start_loop
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _sync_telemetry(self, people_count, latest_evt="Normal Flow"):
        density = "NORMAL"
        if people_count > Config.DENSITY_MODERATE_MAX:
            density = "HIGH"
        elif people_count > Config.DENSITY_NORMAL_MAX:
            density = "MODERATE"

        update_doc = {
            "people_count": people_count,
            "density": density,
            "status": "ONLINE"
        }
        if latest_evt != "Normal Flow":
            update_doc["latest_event"] = latest_evt

        db_manager.update_camera(self.camera_id, update_doc)

    def get_jpeg_frame(self):
        with self.lock:
            frame_to_encode = self.current_frame
            if frame_to_encode is None:
                # Provide instant warm-up black standby frame so browser never hangs or gets 0 bytes
                frame_to_encode, _ = create_camera_standby_frame(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    tick=self.tick
                )

            if not CV2_AVAILABLE or cv2 is None or frame_to_encode is None:
                return FALLBACK_JPEG_BYTES
            try:
                ret, jpeg = cv2.imencode('.jpg', frame_to_encode, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ret:
                    return jpeg.tobytes()
            except Exception as e:
                logger.error(f"JPEG encoding error: {e}")
        return FALLBACK_JPEG_BYTES

    def get_detections(self):
        with self.lock:
            return list(self.latest_detections)

    def get_faces(self):
        with self.lock:
            return list(self.latest_faces)

    def get_weapons(self):
        with self.lock:
            return list(self.latest_weapons)

    def get_accidents(self):
        with self.lock:
            return list(self.latest_accidents)


class StreamManager:
    """
    Central Video Stream Coordinator.
    Spawns and manages workers for CCTV nodes (CCTV-01 to CCTV-04).
    """
    def __init__(self):
        self.workers = {}
        self.detector = PersonDetector(
            model_path=Config.PERSON_MODEL_PATH,
            conf_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", 0.45)),
            device="cpu"
        )
        self._init_streams()

    def _init_streams(self):
        # Register workers from database / seed configs
        cameras = db_manager.get_cameras()
        for cam in cameras:
            cid = cam.get("camera_id")
            name = cam.get("name", "CCTV Feed")
            source_url = cam.get("stream_url", "0")
            source_type = cam.get("source_type", "Webcam")
            fps = int(cam.get("fps_limit", 30))

            worker = CameraWorker(
                camera_id=cid,
                name=name,
                stream_url=source_url,
                source_type=source_type,
                fps_limit=fps,
                detector=self.detector
            )
            self.workers[cid] = worker
            # Automatically start CCTV-01 (or all configured cameras)
            worker.start()

    def get_worker(self, camera_id):
        return self.workers.get(camera_id)

    def generate_mjpeg_stream(self, camera_id):
        """
        Yields multipart MJPEG stream frames for live browser display.
        """
        worker = self.get_worker(camera_id)
        if not worker:
            cam = db_manager.get_camera(camera_id)
            if cam:
                worker = CameraWorker(
                    camera_id=camera_id,
                    name=cam.get("name", f"Camera {camera_id}"),
                    stream_url=cam.get("stream_url", "0"),
                    source_type=cam.get("source_type", "Video File" if camera_id == "CCTV-UPLOAD" else "Webcam"),
                    fps_limit=int(cam.get("fps_limit", 30)),
                    detector=self.detector
                )
                self.workers[camera_id] = worker
                worker.start()
            else:
                # Create a fallback placeholder worker
                worker = CameraWorker(
                    camera_id=camera_id,
                    name=f"Camera {camera_id}",
                    stream_url="0",
                    source_type="Webcam",
                    fps_limit=30,
                    detector=self.detector
                )
                self.workers[camera_id] = worker
                worker.start()

        while True:
            frame_bytes = worker.get_jpeg_frame()
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.033) # ~30 FPS

    def test_webcam_available(self, device_indices=(0, 1)):
        """
        Tests if local laptop camera is physically available and can be captured.
        """
        results = []
        if not CV2_AVAILABLE or cv2 is None:
            return {"available": False, "devices": [], "reason": "OpenCV not available"}

        # If a worker already has webcam opened on index 0 or 1, report it directly to avoid hardware lock collision
        for cid, w in self.workers.items():
            if str(w.stream_url).strip() in ("0", "1") and w.cap and w.cap.isOpened():
                try:
                    dev_idx = int(str(w.stream_url).strip())
                    return {
                        "available": True,
                        "devices": [{"device_index": dev_idx, "accessible": True}],
                        "default_index": dev_idx
                    }
                except ValueError:
                    pass

        for idx in device_indices:
            cap = None
            try:
                cap = cv2.VideoCapture(idx)
                if cap and cap.isOpened():
                    results.append({"device_index": idx, "accessible": True})
                    cap.release()
            except Exception as e:
                logger.error(f"Error testing webcam index {idx}: {e}")
                if cap:
                    try:
                        cap.release()
                    except Exception:
                        pass
        return {
            "available": len(results) > 0,
            "devices": results,
            "default_index": results[0]["device_index"] if results else None
        }

    def activate_laptop_webcam(self, camera_id="CCTV-01", device_index=0):
        """
        Switches specified camera (default CCTV-01) or registers dedicated camera to host laptop webcam.
        """
        dev_str = str(device_index)
        cam_doc = {
            "camera_id": camera_id,
            "name": f"Laptop Webcam ({camera_id})",
            "location": "Local Host Station",
            "source_type": "Webcam",
            "stream_url": dev_str,
            "status": "ONLINE",
            "enabled": True,
            "resolution": "1280x720",
            "fps_limit": 30
        }
        existing = db_manager.get_camera(camera_id)
        if existing:
            db_manager.update_camera(camera_id, cam_doc)
        else:
            db_manager.add_camera(cam_doc)

        worker = self.get_worker(camera_id)
        if worker:
            worker.switch_source(stream_url=dev_str, source_type="Webcam", name=cam_doc["name"])
        else:
            worker = CameraWorker(
                camera_id=camera_id,
                name=cam_doc["name"],
                stream_url=dev_str,
                source_type="Webcam",
                fps_limit=30,
                detector=self.detector
            )
            self.workers[camera_id] = worker
            worker.start()

        return {
            "success": True,
            "camera_id": camera_id,
            "device_index": device_index,
            "is_synthetic": worker.is_synthetic,
            "stream_url": f"/api/cameras/{camera_id}/stream",
            "message": f"Laptop webcam activated on node {camera_id}."
        }

    def register_or_update_worker(self, camera_id, name, stream_url, source_type="Webcam", fps_limit=30):
        worker = self.get_worker(camera_id)
        if worker:
            worker.switch_source(stream_url=str(stream_url), source_type=source_type, name=name, fps_limit=fps_limit)
        else:
            worker = CameraWorker(
                camera_id=camera_id,
                name=name,
                stream_url=str(stream_url),
                source_type=source_type,
                fps_limit=int(fps_limit),
                detector=self.detector
            )
            self.workers[camera_id] = worker
            worker.start()
        return worker

    def stop_worker(self, camera_id):
        worker = self.workers.pop(camera_id, None)
        if worker:
            worker.stop()

    def clear_threat_overlays(self):
        """
        Clears weapons and accident warning overlays from all active camera workers.
        """
        for worker in self.workers.values():
            with worker.lock:
                worker.latest_weapons = []
                worker.latest_accidents = []

# Singleton StreamManager
stream_manager = StreamManager()

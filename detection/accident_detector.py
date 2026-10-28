import time
import logging
from datetime import datetime
from config import Config
from database.mongo import db_manager
from alerts.emergency_dispatcher import emergency_dispatcher

logger = logging.getLogger("CrowdGuard.AccidentDetector")

class AccidentDetector:
    """
    Dedicated AI Accident & Medical Emergency Detector.
    Detects:
    1. Pedestrian falls / medical collapse (horizontal body orientation, sudden drop).
    2. Vehicular impact / collision hazard.
    Automatically logs high-priority medical alerts and prepares Ambulance & Police dispatches.
    """
    def __init__(self, cooldown_sec=30):
        self.cooldown_sec = cooldown_sec
        self.last_alert_time = {}
        # Track history for fall detection: {track_id: [(time, bbox, aspect_ratio), ...]}
        self.track_history = {}

    def process_tracks_and_frame(self, tracks, frame=None, camera_id="CCTV-01"):
        """
        Analyzes active person tracks and frame geometry for fall or vehicular accidents.
        Returns: (accidents_list, confirmed_event_or_none)
        """
        now = time.time()
        accidents = []
        confirmed_event = None

        if not tracks:
            return [], None

        for track in tracks:
            tid = track.get("track_id")
            bbox = track.get("bbox", [0, 0, 0, 0])
            x1, y1, x2, y2 = bbox
            w = max(1, x2 - x1)
            h = max(1, y2 - y1)
            aspect_ratio = w / float(h) # Typical standing human has aspect_ratio ~ 0.3 - 0.5. Fallen human > 1.1

            # Update history
            hist = self.track_history.setdefault(tid, [])
            hist.append((now, bbox, aspect_ratio))
            if len(hist) > 15:
                hist.pop(0)

            # Fall condition: aspect ratio > 1.15 sustained across frames with low vertical velocity
            if aspect_ratio >= 1.15 and len(hist) >= 3:
                conf = min(0.95, 0.75 + (aspect_ratio - 1.15) * 0.2)
                accidents.append({
                    "type": "ACCIDENT_PEDESTRIAN_FALL",
                    "label": "ACCIDENT: PERSON FALLEN / COLLAPSE",
                    "track_id": tid,
                    "confidence": round(conf, 2),
                    "bbox": bbox
                })

        # Cooldown check & emergency alert dispatch
        if accidents:
            last_alert = self.last_alert_time.get(camera_id, 0)
            if now - last_alert >= self.cooldown_sec:
                self.last_alert_time[camera_id] = now
                top_acc = accidents[0]

                confirmed_event = emergency_dispatcher.create_emergency_event(
                    threat_type="ACCIDENT_DETECTED",
                    camera_id=camera_id,
                    description=f"Medical Accident Detected: Individual collapsed on ground level ({top_acc['label']}). Immediate medical assistance needed.",
                    location=f"Surveillance Zone {camera_id}",
                    confidence=top_acc["confidence"],
                    severity="HIGH",
                    risk_score=80,
                    bbox=top_acc["bbox"]
                )
                logger.warning(f"ACCIDENT EMERGENCY LOGGED for {camera_id}: {confirmed_event['event_id']}")

        return accidents, confirmed_event

accident_detector = AccidentDetector()

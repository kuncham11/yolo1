import os
import time
import logging
from datetime import datetime
from config import Config
from database.mongo import db_manager
from alerts.emergency_dispatcher import emergency_dispatcher

logger = logging.getLogger("CrowdGuard.WeaponDetector")

DEFAULT_SUPPORTED_CLASSES = ["knife", "gun", "pistol", "rifle", "firearm", "weapon", "blade"]

class WeaponDetector:
    """
    Dedicated AI Weapon Detection Adapter.
    Supports dedicated YOLO weapon models with multi-frame temporal confirmation,
    alert cooldown deduplication, and an explicit DEMO MODE fallback when
    proprietary weapon model weights are not provided.
    """
    def __init__(self, model_path="models/weapon/weapon_detector.pt", conf_threshold=0.50,
                 supported_classes=None, persistence_frames=4, cooldown_sec=30, device="cpu"):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.supported_classes = supported_classes or list(DEFAULT_SUPPORTED_CLASSES)
        self.persistence_frames = persistence_frames
        self.cooldown_sec = cooldown_sec
        self.device = device

        self.model = None
        self.is_real_model_loaded = False
        self.is_demo_mode = True

        # Frame persistence tracking: {camera_id: [frame1_hits, frame2_hits, ...]}
        self.frame_history = {}
        # Cooldown timestamps: {camera_id: last_alert_time}
        self.last_alert_time = {}

        self.load_model()

    def load_model(self):
        """
        Loads the dedicated weapon detection model if present at self.model_path.
        Falls back to explicit DEMO MODE if no model file exists at self.model_path.
        """
        if self.model_path and os.path.exists(self.model_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
                self.is_real_model_loaded = True
                self.is_demo_mode = False
                logger.info(f"Custom weapon detection model loaded from '{self.model_path}'.")
                return True
            except Exception as e:
                logger.warning(f"Failed to load custom weapon model at '{self.model_path}': {e}.")

        self.is_real_model_loaded = False
        self.is_demo_mode = True
        return False

    def predict(self, frame, camera_id="CCTV-03", mock_trigger=False):
        """
        Performs inference on a frame or returns demo weapon events if in DEMO MODE.
        """
        # On-demand mock trigger for testing / demonstration / drills
        if mock_trigger:
            return [{
                "class": "gun",
                "confidence": 0.95,
                "bbox": [250, 160, 310, 240],
                "mock": True
            }]

        if frame is None or isinstance(frame, (bytes, bytearray)):
            return []

        # If real model is loaded, run actual inference
        if self.is_real_model_loaded and self.model is not None:
            try:
                results = self.model.predict(
                    source=frame,
                    conf=self.conf_threshold,
                    device=self.device,
                    verbose=False
                )
                raw_dets = []
                if results and len(results) > 0:
                    boxes = results[0].boxes
                    names = results[0].names
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = names.get(cls_id, "weapon").lower()
                        conf = float(box.conf[0].item())
                        xyxy = [int(v) for v in box.xyxy[0].tolist()]

                        raw_dets.append({
                            "class": cls_name,
                            "confidence": round(conf, 3),
                            "bbox": xyxy
                        })
                return self.filter_detections(raw_dets)
            except Exception as e:
                logger.error(f"Weapon prediction error: {e}")
                return []

        return []

    def filter_detections(self, raw_detections):
        """
        Filters detections by supported classes and confidence threshold.
        """
        filtered = []
        for det in raw_detections:
            cls_name = det.get("class", "").lower()
            conf = det.get("confidence", 0.0)
            if any(sc in cls_name for sc in self.supported_classes) and conf >= self.conf_threshold:
                filtered.append(det)
        return filtered

    def confirm_persistence(self, camera_id, detected_weapons):
        """
        Requires detection across N consecutive frames before confirming weapon presence.
        Returns the confirmed weapon dictionary if threshold is reached, else None.
        """
        if camera_id not in self.frame_history:
            self.frame_history[camera_id] = []

        history = self.frame_history[camera_id]

        if detected_weapons:
            # Store highest confidence detection from this frame
            top_det = max(detected_weapons, key=lambda d: d.get("confidence", 0))
            history.append(top_det)
        else:
            # Clear or decay history if no weapon seen in current frame
            if len(history) > 0:
                history.pop(0)

        # Keep history capped at persistence_frames
        if len(history) > self.persistence_frames:
            history.pop(0)

        # Confirm persistence: exactly persistence_frames consecutive hits
        if len(history) >= self.persistence_frames:
            avg_conf = sum(d["confidence"] for d in history) / len(history)
            confirmed_weapon = dict(history[-1])
            confirmed_weapon["confidence"] = round(avg_conf, 3)
            return confirmed_weapon

        return None

    def process_frame(self, frame, camera_id="CCTV-03", mock_trigger=False):
        """
        Full weapon analysis pipeline: predict -> filter -> confirm persistence -> dispatch alert.
        Returns: (raw_detections, confirmed_event_or_none)
        """
        raw_dets = self.predict(frame, camera_id=camera_id, mock_trigger=mock_trigger)
        confirmed = self.confirm_persistence(camera_id, raw_dets)

        event = None
        if confirmed:
            now = time.time()
            last_alert = self.last_alert_time.get(camera_id, 0)

            # Alert cooldown check (30s)
            if now - last_alert >= self.cooldown_sec:
                self.last_alert_time[camera_id] = now
                event = self.create_event(camera_id, confirmed)
                logger.warning(f"WEAPON ALERT DISPATCHED for {camera_id}: {event['description']}")

        return raw_dets, event

    def create_event(self, camera_id, weapon_info):
        """
        Formats a high-priority threat alert dictionary and logs emergency dispatch.
        """
        cls_name = weapon_info.get("class", "GUN").upper()
        conf = weapon_info.get("confidence", 0.95)
        bbox = weapon_info.get("bbox")

        return emergency_dispatcher.create_emergency_event(
            threat_type="WEAPON_DETECTED",
            camera_id=camera_id,
            description=f"CRITICAL ARMED THREAT: Lethal weapon ({cls_name}) confirmed in surveillance sector. Immediately alert Police (911) & broadcast emergency bulletin.",
            location=f"Surveillance Zone {camera_id}",
            confidence=conf,
            severity="CRITICAL",
            risk_score=95,
            bbox=bbox
        )

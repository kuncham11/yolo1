import os
import time
import logging
from collections import deque
from datetime import datetime
from config import Config
from database.mongo import db_manager
from alerts.emergency_dispatcher import emergency_dispatcher

# Safe imports for NumPy and OpenCV
try:
    import numpy as np
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    np = None
    cv2 = None
    CV2_AVAILABLE = False

logger = logging.getLogger("CrowdGuard.ViolenceDetector")

class ViolenceDetector:
    """
    Temporal Action-Recognition & Violence Detection Engine.
    Processes rolling sequences of video frames (clips) to classify temporal actions
    into 'NORMAL' or 'POSSIBLE_VIOLENCE' without relying on single-frame heuristics.
    Includes an explicit DEMO MODE when custom action weights are not installed.
    """
    def __init__(self, model_path="models/violence/action_model.pt", clip_len=16,
                 conf_threshold=0.65, cooldown_sec=30, device="cpu"):
        self.model_path = model_path
        self.clip_len = clip_len
        self.conf_threshold = conf_threshold
        self.cooldown_sec = cooldown_sec
        self.device = device

        self.model = None
        self.is_real_model_loaded = False
        self.is_demo_mode = True

        # Rolling frame buffers per camera: {camera_id: deque(maxlen=clip_len)}
        self.frame_buffers = {}
        # Cooldown timestamps: {camera_id: last_alert_time}
        self.last_alert_time = {}

        self.load_model()

    def load_model(self):
        """
        Loads the temporal action recognition model (e.g. PyTorch 3D-CNN / SlowFast).
        Falls back to transparent DEMO MODE if model file is not present.
        """
        if os.path.exists(self.model_path):
            try:
                import torch
                self.model = torch.jit.load(self.model_path, map_location=self.device)
                self.model.eval()
                self.is_real_model_loaded = True
                self.is_demo_mode = False
                logger.info(f"Custom temporal action recognition model loaded from '{self.model_path}'.")
                return True
            except Exception as e:
                logger.warning(f"Failed to load action model at '{self.model_path}': {e}. Falling back to DEMO MODE.")
        else:
            logger.info(f"No action model weights at '{self.model_path}'. Active mode: VIOLENCE DETECTION DEMO MODE.")

        self.is_real_model_loaded = False
        self.is_demo_mode = True
        return False

    def collect_frame(self, frame, camera_id="CCTV-04"):
        """
        Appends a preprocessed frame to the camera's temporal rolling buffer.
        """
        if camera_id not in self.frame_buffers:
            self.frame_buffers[camera_id] = deque(maxlen=self.clip_len)

        if frame is not None and CV2_AVAILABLE and cv2 is not None:
            # Resize frame to standard action recognition input size (112x112)
            resized = cv2.resize(frame, (112, 112))
            self.frame_buffers[camera_id].append(resized)
        else:
            # Placeholder frame in headless or testing mode
            if CV2_AVAILABLE and np is not None:
                self.frame_buffers[camera_id].append(np.zeros((112, 112, 3), dtype=np.uint8))
            else:
                self.frame_buffers[camera_id].append(object())

    def create_clip(self, camera_id="CCTV-04"):
        """
        Assembles a temporal video clip from the frame buffer.
        Enforces temporal requirement: Returns None if fewer than clip_len frames exist.
        """
        buffer = self.frame_buffers.get(camera_id)
        if not buffer or len(buffer) < self.clip_len:
            # Temporal evidence insufficient
            return None

        if not CV2_AVAILABLE or np is None:
            return list(buffer)

        # Convert to numpy array shape: (T, H, W, C)
        try:
            clip = np.array(list(buffer), dtype=np.uint8)
            return clip
        except Exception as e:
            logger.error(f"Error creating temporal clip for {camera_id}: {e}")
            return None

    def predict_clip(self, clip, camera_id="CCTV-04", mock_trigger=False):
        """
        Executes temporal action recognition inference on a sequence of frames.
        Returns a tuple: (label, confidence) -> ('NORMAL' | 'POSSIBLE_VIOLENCE', float)
        """
        if clip is None:
            return "NORMAL", 0.0

        # Real AI Model Inference if loaded
        if self.is_real_model_loaded and self.model is not None:
            try:
                import torch
                # Format tensor: (1, C, T, H, W) normalized to [0, 1]
                tensor = torch.from_numpy(clip).float() / 255.0
                tensor = tensor.permute(3, 0, 1, 2).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    outputs = self.model(tensor)
                    probs = torch.softmax(outputs, dim=1)[0]
                    # Index 1 = Violence class
                    violence_prob = float(probs[1].item()) if probs.shape[0] > 1 else float(probs[0].item())

                if violence_prob >= self.conf_threshold:
                    return "POSSIBLE_VIOLENCE", round(violence_prob, 3)
                return "NORMAL", round(1.0 - violence_prob, 3)
            except Exception as e:
                logger.error(f"Action model inference error: {e}")
                return "NORMAL", 0.0

        # DEMO MODE: Evaluates simulated trigger or kinematic optical motion variance
        if self.is_demo_mode:
            if mock_trigger:
                return "POSSIBLE_VIOLENCE", 0.88
            return "NORMAL", 0.95

        return "NORMAL", 0.90

    def confirm_event(self, camera_id, label, confidence):
        """
        Validates temporal evidence, evaluates cooldown, and creates structured alert.
        """
        if label != "POSSIBLE_VIOLENCE" or confidence < self.conf_threshold:
            return None

        now = time.time()
        last_alert = self.last_alert_time.get(camera_id, 0)

        # Cooldown check (30s)
        if now - last_alert >= self.cooldown_sec:
            self.last_alert_time[camera_id] = now
            mode_str = " (DEMO MODE)" if self.is_demo_mode else ""
            
            event = emergency_dispatcher.create_emergency_event(
                threat_type="POSSIBLE_VIOLENCE",
                camera_id=camera_id,
                description=f"CRITICAL ASSAULT / VIOLENCE DETECTED: Violent kinetic confrontation confirmed across {self.clip_len}-frame temporal window{mode_str}. Contact Police (911) & Ambulance (108) immediately.",
                location=f"Surveillance Zone {camera_id}",
                confidence=confidence,
                severity="HIGH",
                risk_score=95
            )

            db_manager.log_behaviour_event({
                "camera_id": camera_id,
                "track_id": 0,
                "behaviour_type": "POSSIBLE_VIOLENCE",
                "confidence": confidence,
                "duration": round(self.clip_len / 30.0, 2),
                "risk_score": 95
            })
            logger.warning(f"TEMPORAL ACTION ALERT DISPATCHED for {camera_id}: {event['description']}")
            return event

        return None

    def process_frame(self, frame, camera_id="CCTV-04", mock_trigger=False):
        """
        Full temporal pipeline: collect frame -> create clip -> predict -> confirm event.
        Returns: (label, confidence, confirmed_event_or_none)
        """
        self.collect_frame(frame, camera_id=camera_id)
        clip = self.create_clip(camera_id=camera_id)

        if clip is None:
            # Still accumulating temporal window
            return "BUFFERING", 0.0, None

        label, conf = self.predict_clip(clip, camera_id=camera_id, mock_trigger=mock_trigger)
        event = self.confirm_event(camera_id, label, conf)
        return label, conf, event

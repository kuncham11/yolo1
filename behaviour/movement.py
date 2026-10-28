import math
from config import Config

class MovementAnalyzer:
    """
    Analyzes individual track kinematics:
    1. Running detection (high sustained velocity)
    2. Sudden movement (abrupt velocity spike/acceleration)
    3. Wrong-direction flow (against expected corridor angle)
    """
    def __init__(self, running_thresh=18.0, sudden_delta_thresh=12.0):
        self.running_thresh = running_thresh
        self.sudden_delta_thresh = sudden_delta_thresh
        # History of track velocities for acceleration tracking: {track_id: [v1, v2, ...]}
        self.velocity_history = {}
        self.running_frame_counts = {}

    def analyze_track(self, track_dict, expected_direction=None):
        """
        Analyzes a single track dictionary from ByteTracker.
        Returns a list of detected movement anomaly events (if any).
        """
        events = []
        track_id = track_dict["track_id"]
        camera_id = track_dict.get("camera_id", "CCTV-01")
        vel = track_dict.get("velocity", 0.0)
        direction = track_dict.get("direction", "Stationary")

        # Track velocity history for acceleration
        if track_id not in self.velocity_history:
            self.velocity_history[track_id] = []
            self.running_frame_counts[track_id] = 0

        history = self.velocity_history[track_id]
        history.append(vel)
        if len(history) > 15:
            history.pop(0)

        # 1. Running Detection (Sustained velocity above threshold for >= 4 frames)
        if vel >= self.running_thresh:
            self.running_frame_counts[track_id] += 1
            if self.running_frame_counts[track_id] >= 4:
                events.append({
                    "behaviour_type": "POSSIBLE_RUNNING",
                    "camera_id": camera_id,
                    "track_id": track_id,
                    "confidence": min(1.0, 0.70 + (vel / 40.0) * 0.3),
                    "description": f"Identified person exhibiting sustained high velocity motion ({vel:.1f} px/f).",
                    "risk_weight": Config.WEIGHT_RUNNING
                })
        else:
            self.running_frame_counts[track_id] = max(0, self.running_frame_counts[track_id] - 1)

        # 2. Sudden Movement (Abrupt acceleration spike in recent frames)
        if len(history) >= 3:
            vel_delta = abs(history[-1] - history[-3])
            if vel_delta >= self.sudden_delta_thresh and history[-1] > 10.0:
                events.append({
                    "behaviour_type": "POSSIBLE_SUDDEN_MOVEMENT",
                    "camera_id": camera_id,
                    "track_id": track_id,
                    "confidence": min(1.0, 0.65 + (vel_delta / 25.0) * 0.35),
                    "description": f"Identified person exhibiting sudden acceleration spike (delta: {vel_delta:.1f} px/f).",
                    "risk_weight": Config.WEIGHT_ABNORMAL_MOVEMENT // 2
                })

        # 3. Wrong Direction Flow Detection
        if expected_direction and direction not in ("Stationary", expected_direction):
            # If direction is opposite or conflicting
            opposites = {
                "East": ["West", "North-West", "South-West"],
                "West": ["East", "North-East", "South-East"],
                "North": ["South", "South-East", "South-West"],
                "South": ["North", "North-East", "North-West"]
            }
            if expected_direction in opposites and direction in opposites[expected_direction] and vel > 3.0:
                events.append({
                    "behaviour_type": "POSSIBLE_WRONG_DIRECTION",
                    "camera_id": camera_id,
                    "track_id": track_id,
                    "confidence": 0.80,
                    "description": f"Identified person moving {direction} against expected flow ({expected_direction}).",
                    "risk_weight": 10
                })

        return events

    def cleanup_track(self, track_id):
        self.velocity_history.pop(track_id, None)
        self.running_frame_counts.pop(track_id, None)

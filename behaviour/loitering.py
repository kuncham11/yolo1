import time
import math
from config import Config

class LoiteringDetector:
    """
    Detects possible loitering behaviour based on:
    - Time spent inside a designated surveillance zone / camera view
    - Net displacement (distance between initial and current centroid)
    """
    def __init__(self, time_threshold_sec=45, max_displacement=40.0):
        self.time_threshold_sec = time_threshold_sec
        self.max_displacement = max_displacement
        # {track_id: {"first_seen_time": float, "initial_centroid": (cx, cy), "last_alert_time": float}}
        self.track_stats = {}

    def analyze_track(self, track_dict):
        """
        Evaluates a single track dictionary for loitering indicators.
        """
        track_id = track_dict["track_id"]
        camera_id = track_dict.get("camera_id", "CCTV-01")
        cx, cy = track_dict["centroid"]
        now = time.time()

        if track_id not in self.track_stats:
            self.track_stats[track_id] = {
                "first_seen_time": now,
                "initial_centroid": (cx, cy),
                "last_alert_time": 0
            }
            return None

        stats = self.track_stats[track_id]
        dwell_duration = now - stats["first_seen_time"]
        init_cx, init_cy = stats["initial_centroid"]
        net_displacement = math.hypot(cx - init_cx, cy - init_cy)

        # Loitering condition: Long dwell time + minimal net displacement
        if dwell_duration >= self.time_threshold_sec and net_displacement <= self.max_displacement:
            # Cooldown check: 30 seconds between repeat loitering logs
            if now - stats["last_alert_time"] > 30.0:
                stats["last_alert_time"] = now
                mins = int(dwell_duration // 60)
                secs = int(dwell_duration % 60)
                dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

                return {
                    "behaviour_type": "POSSIBLE_LOITERING",
                    "camera_id": camera_id,
                    "track_id": track_id,
                    "confidence": min(0.95, 0.70 + (dwell_duration / 120.0) * 0.25),
                    "duration_sec": round(dwell_duration, 1),
                    "displacement": round(net_displacement, 1),
                    "description": f"Track #{track_id} dwelling in area for {dur_str} with low displacement ({net_displacement:.1f}px).",
                    "risk_weight": Config.WEIGHT_LOITERING
                }

        return None

    def cleanup_track(self, track_id):
        self.track_stats.pop(track_id, None)

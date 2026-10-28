import time
import math
from datetime import datetime
from config import Config
from behaviour.movement import MovementAnalyzer
from behaviour.loitering import LoiteringDetector
from behaviour.zones import is_point_in_rect, is_point_in_polygon
from database.mongo import db_manager
from alerts.emergency_dispatcher import emergency_dispatcher

class BehaviourEngine:
    """
    Central Multi-Signal Behaviour Analysis Engine.
    Coordinates individual track kinematics, zone geofencing, crowd surge,
    and accumulation analytics into structured anomaly events.
    """
    def __init__(self, camera_id="CCTV-01"):
        self.camera_id = camera_id
        self.movement_analyzer = MovementAnalyzer(
            running_thresh=float(Config.RUNNING_VELOCITY_THRESHOLD if hasattr(Config, 'RUNNING_VELOCITY_THRESHOLD') else 18.0)
        )
        self.loitering_detector = LoiteringDetector(
            time_threshold_sec=int(Config.LOITERING_TIME_THRESHOLD_SEC if hasattr(Config, 'LOITERING_TIME_THRESHOLD_SEC') else 45)
        )
        # Designated restricted zone: [x1, y1, x2, y2]
        self.restricted_zones = {
            "CCTV-04": [400, 50, 600, 320], # Vault Corridor zone on CCTV-04
            "CCTV-03": [480, 200, 640, 360]  # Restricted Kitchen access on CCTV-03
        }
        self.expected_flow_directions = {
            "CCTV-01": "East" # North gate entry flow
        }
        self.last_crowd_count = 0
        self.last_alert_timestamps = {} # {event_key: timestamp} for alert deduplication

    def process_frame_tracks(self, tracks):
        """
        Analyzes all active tracks on the current frame.
        Returns a list of generated behavior anomaly events.
        """
        events = []
        now = time.time()
        active_directions = []
        active_high_speed_count = 0

        for track in tracks:
            # 1. Kinematics (Running, Sudden, Wrong Direction)
            exp_dir = self.expected_flow_directions.get(self.camera_id)
            mov_events = self.movement_analyzer.analyze_track(track, expected_direction=exp_dir)
            events.extend(mov_events)

            # 2. Loitering
            loiter_event = self.loitering_detector.analyze_track(track)
            if loiter_event:
                events.append(loiter_event)

            # 3. Restricted Zone Intrusion
            zone_rect = self.restricted_zones.get(self.camera_id)
            if zone_rect and is_point_in_rect(track["centroid"], zone_rect):
                events.append({
                    "behaviour_type": "RESTRICTED_AREA_ENTRY",
                    "camera_id": self.camera_id,
                    "track_id": track["track_id"],
                    "confidence": 0.92,
                    "description": f"Identified person breached designated restricted geofence perimeter.",
                    "risk_weight": Config.WEIGHT_RESTRICTED_ENTRY
                })

            # Record stats for crowd surge / coherence
            vel = track.get("velocity", 0.0)
            dir_str = track.get("direction", "Stationary")
            if vel >= 10.0 and dir_str != "Stationary":
                active_high_speed_count += 1
                active_directions.append(dir_str)

        # 4. Crowd Surge Detection (Multiple people rapidly moving in coherent direction)
        if active_high_speed_count >= 3 and len(active_directions) >= 3:
            # Check direction coherence (majority moving in same general direction)
            most_common_dir = max(set(active_directions), key=active_directions.count)
            coherence_ratio = active_directions.count(most_common_dir) / len(active_directions)
            if coherence_ratio >= 0.6:
                events.append({
                    "behaviour_type": "POSSIBLE_CROWD_SURGE",
                    "camera_id": self.camera_id,
                    "track_id": 0,
                    "confidence": 0.85,
                    "description": f"Rapid crowd velocity surge detected toward {most_common_dir} ({active_high_speed_count} individuals).",
                    "risk_weight": Config.WEIGHT_HIGH_DENSITY + 10
                })

        # 5. Crowd Accumulation Detection
        current_count = len(tracks)
        if current_count >= 15 and (current_count - self.last_crowd_count) >= 8:
            events.append({
                "behaviour_type": "CROWD_ACCUMULATION",
                "camera_id": self.camera_id,
                "track_id": 0,
                "confidence": 0.80,
                "description": f"Rapid crowd accumulation detected ({current_count} active tracks).",
                "risk_weight": Config.WEIGHT_HIGH_DENSITY
            })
        self.last_crowd_count = current_count

        # Persist and dispatch events to database / alert system
        self._dispatch_events(events)
        return events

    def _dispatch_events(self, events):
        """
        Dispatches behavior events to MongoDB and creates deduplicated alerts.
        """
        now = time.time()
        for evt in events:
            b_type = evt["behaviour_type"]
            t_id = evt.get("track_id", 0)
            dedup_key = f"{self.camera_id}:{b_type}:{t_id}"

            # Log to behaviour_events collection
            db_manager.log_behaviour_event({
                "camera_id": self.camera_id,
                "track_id": t_id,
                "behaviour_type": b_type,
                "confidence": evt.get("confidence", 0.8),
                "duration": evt.get("duration_sec", 0),
                "risk_score": evt.get("risk_weight", 10),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            # Check alert cooldown (e.g. 30 seconds between identical alerts)
            last_alert = self.last_alert_timestamps.get(dedup_key, 0)
            if now - last_alert >= Config.ALERT_COOLDOWN_SEC:
                self.last_alert_timestamps[dedup_key] = now
                
                # Severity classification
                weight = evt.get("risk_weight", 10)
                if weight >= 40:
                    severity = "CRITICAL"
                elif weight >= 20:
                    severity = "HIGH"
                elif weight >= 10:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                if b_type in ("POSSIBLE_CROWD_SURGE", "MASS_PANIC_STAMPEDE_RISK"):
                    emergency_dispatcher.create_emergency_event(
                        threat_type=b_type,
                        camera_id=self.camera_id,
                        description=f"CROWD DISASTER / STAMPEDE HAZARD: {evt.get('description', 'High velocity crowd surge.')} Alert Police & Ambulance.",
                        location=f"Surveillance Zone {self.camera_id}",
                        confidence=evt.get("confidence", 0.85),
                        severity="CRITICAL",
                        risk_score=weight
                    )
                else:
                    db_manager.add_alert({
                        "camera_id": self.camera_id,
                        "camera_name": f"Node {self.camera_id}",
                        "event_type": b_type,
                        "severity": severity,
                        "confidence": evt.get("confidence", 0.8),
                        "risk_score": weight,
                        "description": evt.get("description", "Behavior anomaly flagged.")
                    })

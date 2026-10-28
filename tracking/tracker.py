import math
import time
from collections import deque
from datetime import datetime

def calculate_iou(box1, box2):
    """
    Computes Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2].
    """
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = max(0, box1[2] - box1[0]) * max(0, box1[3] - box1[1])
    area2 = max(0, box2[2] - box2[0]) * max(0, box2[3] - box2[1])
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0
    return intersection / union

def get_direction_label(dx, dy, min_displacement=2.0):
    """
    Determines 8-direction compass heading or Stationary from (dx, dy).
    """
    dist = math.hypot(dx, dy)
    if dist < min_displacement:
        return "Stationary"

    # Angle in degrees (0 to 360)
    angle = (math.degrees(math.atan2(dy, dx)) + 360) % 360

    if 337.5 <= angle or angle < 22.5:
        return "East"
    elif 22.5 <= angle < 67.5:
        return "South-East"
    elif 67.5 <= angle < 112.5:
        return "South"
    elif 112.5 <= angle < 157.5:
        return "South-West"
    elif 157.5 <= angle < 202.5:
        return "West"
    elif 202.5 <= angle < 247.5:
        return "North-West"
    elif 247.5 <= angle < 292.5:
        return "North"
    else:
        return "North-East"


class Track:
    """
    Represents an individual tracked person over time.
    Maintains persistent track ID, centroid history, velocity, direction, and lifetime.
    """
    _next_id = 1

    def __init__(self, bbox, confidence, camera_id="CCTV-01"):
        self.track_id = Track._next_id
        Track._next_id += 1

        self.camera_id = camera_id
        self.bbox = list(bbox)
        self.confidence = float(confidence)
        
        cx = int((bbox[0] + bbox[2]) / 2)
        cy = int((bbox[1] + bbox[3]) / 2)
        self.centroid = (cx, cy)
        self.previous_centroid = (cx, cy)
        self.centroid_history = deque(maxlen=60) # Store up to 60 previous centroids
        self.centroid_history.append((cx, cy, time.time()))

        self.velocity = 0.0 # Pixel displacement per frame
        self.direction = "Stationary"
        self.hits = 1
        self.lost_frames = 0
        self.is_confirmed = False
        self.zone = "General Area"
        self.status = "ACTIVE"
        
        self.first_seen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_seen = self.first_seen

    def update(self, bbox, confidence):
        self.bbox = list(bbox)
        self.confidence = float(confidence)

        cx = int((bbox[0] + bbox[2]) / 2)
        cy = int((bbox[1] + bbox[3]) / 2)
        
        self.previous_centroid = self.centroid
        self.centroid = (cx, cy)
        now_ts = time.time()
        self.centroid_history.append((cx, cy, now_ts))

        # Calculate instantaneous velocity & direction
        dx = cx - self.previous_centroid[0]
        dy = cy - self.previous_centroid[1]
        instant_speed = math.hypot(dx, dy)
        
        # Smoothed moving average velocity
        self.velocity = (self.velocity * 0.7) + (instant_speed * 0.3)
        self.direction = get_direction_label(dx, dy)

        self.hits += 1
        self.lost_frames = 0
        if self.hits >= 3:
            self.is_confirmed = True
        self.last_seen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def mark_missed(self):
        self.lost_frames += 1
        if self.lost_frames > 5:
            self.status = "LOST"

    def to_dict(self):
        return {
            "track_id": self.track_id,
            "camera_id": self.camera_id,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "centroid": self.centroid,
            "previous_centroid": self.previous_centroid,
            "velocity": round(self.velocity, 2),
            "direction": self.direction,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "zone": self.zone,
            "status": self.status,
            "is_confirmed": self.is_confirmed
        }


class ByteTracker:
    """
    ByteTrack Association Tracker for Multi-Person CCTV Surveillance.
    Associates high-confidence detections and low-confidence detections across frames
    to maintain persistent track IDs through occlusions.
    """
    def __init__(self, iou_threshold=0.35, high_conf_thresh=0.45, max_lost_frames=30):
        self.iou_threshold = iou_threshold
        self.high_conf_thresh = high_conf_thresh
        self.max_lost_frames = max_lost_frames
        self.tracks = []

    def update(self, detections, camera_id="CCTV-01"):
        """
        Takes raw detections from PersonDetector and updates persistent tracks.
        """
        if not detections:
            for t in self.tracks:
                t.mark_missed()
            self._prune_tracks()
            return [t.to_dict() for t in self.tracks if t.is_confirmed]

        # Partition detections into High Confidence and Low Confidence
        high_dets = [d for d in detections if d.get("confidence", 0) >= self.high_conf_thresh]
        low_dets = [d for d in detections if d.get("confidence", 0) < self.high_conf_thresh]

        unmatched_tracks = list(self.tracks)
        unmatched_dets = list(high_dets)

        # Stage 1: Match high confidence detections with active tracks using IoU
        matched_stage1 = []
        for t in list(unmatched_tracks):
            best_iou = 0.0
            best_det = None
            for d in unmatched_dets:
                iou = calculate_iou(t.bbox, d["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_det = d

            if best_iou >= self.iou_threshold and best_det is not None:
                t.update(best_det["bbox"], best_det["confidence"])
                matched_stage1.append(t)
                unmatched_tracks.remove(t)
                unmatched_dets.remove(best_det)

        # Stage 2: Match remaining tracks with low confidence detections (recovering occluded tracks)
        for t in list(unmatched_tracks):
            best_iou = 0.0
            best_det = None
            for d in low_dets:
                iou = calculate_iou(t.bbox, d["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_det = d

            if best_iou >= (self.iou_threshold * 0.75) and best_det is not None:
                t.update(best_det["bbox"], best_det["confidence"])
                unmatched_tracks.remove(t)
                low_dets.remove(best_det)

        # Mark any remaining unmatched tracks as missed
        for t in unmatched_tracks:
            t.mark_missed()

        # Stage 3: Initialize new tracks for unassigned high confidence detections
        for d in unmatched_dets:
            new_track = Track(d["bbox"], d["confidence"], camera_id=camera_id)
            self.tracks.append(new_track)

        self._prune_tracks()
        return [t.to_dict() for t in self.tracks if t.is_confirmed or t.hits >= 2]

    def _prune_tracks(self):
        """
        Removes tracks that have been lost for longer than max_lost_frames.
        """
        self.tracks = [t for t in self.tracks if t.lost_frames <= self.max_lost_frames]

    def get_active_count(self):
        return sum(1 for t in self.tracks if t.lost_frames == 0 and (t.is_confirmed or t.hits >= 2))

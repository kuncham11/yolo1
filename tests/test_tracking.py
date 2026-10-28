import pytest
from tracking.tracker import ByteTracker, Track, calculate_iou, get_direction_label
from database.mongo import db_manager

def test_calculate_iou():
    box1 = [0, 0, 10, 10]
    box2 = [0, 0, 10, 10]
    assert calculate_iou(box1, box2) == 1.0

    box3 = [5, 5, 15, 15]
    iou = calculate_iou(box1, box3)
    assert 0.14 < iou < 0.15 # 25 / 175 = 0.1428

    box4 = [20, 20, 30, 30]
    assert calculate_iou(box1, box4) == 0.0

def test_direction_label():
    assert get_direction_label(0, 0) == "Stationary"
    assert get_direction_label(10, 0) == "East"
    assert get_direction_label(-10, 0) == "West"
    assert get_direction_label(0, 10) == "South"
    assert get_direction_label(0, -10) == "North"

def test_track_lifecycle_and_kinematics():
    init_box = [100, 100, 200, 300]
    t = Track(init_box, confidence=0.92, camera_id="CCTV-01")
    assert t.centroid == (150, 200)
    assert t.velocity == 0.0
    assert t.is_confirmed is False

    # Simulate frame 2: person moved right (East)
    moved_box = [110, 100, 210, 300]
    t.update(moved_box, confidence=0.94)
    assert t.centroid == (160, 200)
    assert t.previous_centroid == (150, 200)
    assert t.direction == "East"
    assert t.velocity > 0

    # Simulate frame 3: confirmed track
    moved_box2 = [120, 100, 220, 300]
    t.update(moved_box2, confidence=0.95)
    assert t.is_confirmed is True

def test_bytetracker_persistent_id():
    tracker = ByteTracker(iou_threshold=0.3, max_lost_frames=5)

    # Frame 1: Person A and Person B detected
    frame1_dets = [
        {"bbox": [50, 50, 100, 150], "confidence": 0.90},
        {"bbox": [300, 50, 350, 150], "confidence": 0.88}
    ]
    tracks_f1 = tracker.update(frame1_dets)
    # Both tracks initialized
    assert len(tracker.tracks) == 2
    id_a = tracker.tracks[0].track_id
    id_b = tracker.tracks[1].track_id
    assert id_a != id_b

    # Frame 2: Person A and Person B slightly moved
    frame2_dets = [
        {"bbox": [54, 52, 104, 152], "confidence": 0.92},
        {"bbox": [305, 51, 355, 151], "confidence": 0.89}
    ]
    tracks_f2 = tracker.update(frame2_dets)
    # IDs must persist across frames!
    assert tracker.tracks[0].track_id == id_a
    assert tracker.tracks[1].track_id == id_b

def test_bytetracker_pruning():
    tracker = ByteTracker(iou_threshold=0.3, max_lost_frames=2)
    tracker.update([{"bbox": [50, 50, 100, 150], "confidence": 0.90}])
    assert len(tracker.tracks) == 1

    # Empty frames exceeding max_lost_frames
    tracker.update([])
    tracker.update([])
    tracker.update([])
    assert len(tracker.tracks) == 0

def test_mongo_detection_logging():
    log_doc = {
        "camera_id": "CCTV-01",
        "track_id": 99,
        "object_type": "person",
        "confidence": 0.94,
        "bbox": [100, 100, 150, 250],
        "centroid": (125, 175),
        "velocity": 4.5,
        "direction": "North-East"
    }
    res = db_manager.log_detection(log_doc)
    assert res["track_id"] == 99
    assert res["camera_id"] == "CCTV-01"

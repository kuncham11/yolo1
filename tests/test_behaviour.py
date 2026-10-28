import time
import pytest
from behaviour.movement import MovementAnalyzer
from behaviour.loitering import LoiteringDetector
from behaviour.zones import is_point_in_rect, is_point_in_polygon
from behaviour.abnormal import BehaviourEngine
from database.mongo import db_manager

def test_zone_containment():
    rect = [100, 100, 300, 300]
    assert is_point_in_rect((150, 150), rect) is True
    assert is_point_in_rect((50, 50), rect) is False
    assert is_point_in_rect((350, 350), rect) is False

    poly = [(0, 0), (100, 0), (100, 100), (0, 100)]
    assert is_point_in_polygon((50, 50), poly) is True
    assert is_point_in_polygon((150, 50), poly) is False

def test_running_detection():
    analyzer = MovementAnalyzer(running_thresh=18.0)
    track_dict = {
        "track_id": 10,
        "camera_id": "CCTV-01",
        "velocity": 22.0,
        "direction": "East"
    }

    # Needs 4 consecutive frames above threshold
    events = []
    for _ in range(4):
        events = analyzer.analyze_track(track_dict)

    assert len(events) >= 1
    assert events[0]["behaviour_type"] == "POSSIBLE_RUNNING"
    assert "sustained high velocity" in events[0]["description"]

def test_sudden_movement_detection():
    analyzer = MovementAnalyzer(running_thresh=30.0, sudden_delta_thresh=12.0)
    track_dict = {"track_id": 11, "camera_id": "CCTV-01", "velocity": 2.0, "direction": "Stationary"}
    analyzer.analyze_track(track_dict)
    analyzer.analyze_track(track_dict)

    # Sudden jump in velocity
    spike_dict = {"track_id": 11, "camera_id": "CCTV-01", "velocity": 20.0, "direction": "East"}
    events = analyzer.analyze_track(spike_dict)
    assert any(e["behaviour_type"] == "POSSIBLE_SUDDEN_MOVEMENT" for e in events)

def test_wrong_direction_detection():
    analyzer = MovementAnalyzer()
    track_dict = {"track_id": 12, "camera_id": "CCTV-01", "velocity": 5.0, "direction": "West"}
    events = analyzer.analyze_track(track_dict, expected_direction="East")
    assert len(events) == 1
    assert events[0]["behaviour_type"] == "POSSIBLE_WRONG_DIRECTION"

def test_loitering_detection():
    detector = LoiteringDetector(time_threshold_sec=1, max_displacement=20.0)
    track_dict = {
        "track_id": 15,
        "camera_id": "CCTV-02",
        "centroid": (200, 200)
    }

    # First frame initializes stats
    detector.analyze_track(track_dict)
    time.sleep(1.1)

    # Second frame with minimal movement
    track_dict2 = {
        "track_id": 15,
        "camera_id": "CCTV-02",
        "centroid": (205, 202)
    }
    event = detector.analyze_track(track_dict2)
    assert event is not None
    assert event["behaviour_type"] == "POSSIBLE_LOITERING"
    assert event["track_id"] == 15

def test_behaviour_engine_crowd_surge_and_alerts():
    engine = BehaviourEngine(camera_id="CCTV-01")
    # Simulate 4 people moving fast toward East
    tracks = [
        {"track_id": 1, "centroid": (100, 100), "velocity": 14.0, "direction": "East"},
        {"track_id": 2, "centroid": (120, 100), "velocity": 15.0, "direction": "East"},
        {"track_id": 3, "centroid": (140, 100), "velocity": 16.0, "direction": "East"},
        {"track_id": 4, "centroid": (160, 100), "velocity": 14.5, "direction": "East"}
    ]

    events = engine.process_frame_tracks(tracks)
    surge_event = next((e for e in events if e["behaviour_type"] == "POSSIBLE_CROWD_SURGE"), None)
    assert surge_event is not None
    assert "Rapid crowd velocity surge" in surge_event["description"]

    # Verify that an alert was dispatched to MongoDB
    alerts = db_manager.get_alerts(camera_id="CCTV-01")
    assert any(a["event_type"] == "POSSIBLE_CROWD_SURGE" for a in alerts)

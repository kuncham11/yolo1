import time
import pytest
from detection.weapon_detector import WeaponDetector
from database.mongo import db_manager

def test_weapon_detector_demo_mode_fallback():
    detector = WeaponDetector(model_path="models/weapon/non_existent_weights.pt")
    assert detector.is_demo_mode is True
    assert detector.is_real_model_loaded is False

def test_filter_detections():
    detector = WeaponDetector(conf_threshold=0.60, supported_classes=["gun", "knife"])
    raw_dets = [
        {"class": "gun", "confidence": 0.85, "bbox": [10, 10, 50, 50]},
        {"class": "knife", "confidence": 0.55, "bbox": [60, 60, 90, 90]}, # Below conf
        {"class": "bottle", "confidence": 0.95, "bbox": [100, 100, 130, 130]} # Unsupported class
    ]
    filtered = detector.filter_detections(raw_dets)
    assert len(filtered) == 1
    assert filtered[0]["class"] == "gun"

def test_multi_frame_persistence_confirmation():
    detector = WeaponDetector(persistence_frames=4, cooldown_sec=10)
    camera_id = "CCTV-TEST-WPN"

    sample_wpn = [{"class": "gun", "confidence": 0.92, "bbox": [100, 100, 150, 150]}]

    # Frame 1 to 3: Should NOT confirm
    assert detector.confirm_persistence(camera_id, sample_wpn) is None
    assert detector.confirm_persistence(camera_id, sample_wpn) is None
    assert detector.confirm_persistence(camera_id, sample_wpn) is None

    # Frame 4: 4th consecutive frame -> CONFIRMED!
    confirmed = detector.confirm_persistence(camera_id, sample_wpn)
    assert confirmed is not None
    assert confirmed["class"] == "gun"
    assert confirmed["confidence"] >= 0.90

def test_weapon_alert_cooldown_and_dispatch():
    detector = WeaponDetector(persistence_frames=2, cooldown_sec=5)
    camera_id = "CCTV-COOLDOWN-TEST"
    dummy_frame = b"dummy_frame"

    # Frame 1
    raw1, evt1 = detector.process_frame(dummy_frame, camera_id=camera_id, mock_trigger=True)
    assert evt1 is None # Persistence not reached

    # Frame 2: Persistence reached -> Alert dispatched
    raw2, evt2 = detector.process_frame(dummy_frame, camera_id=camera_id, mock_trigger=True)
    assert evt2 is not None
    assert evt2["event_type"] == "WEAPON_DETECTED"
    assert evt2["severity"] == "CRITICAL"

    # Frame 3: Persistence is maintained, but within cooldown window -> No duplicate alert!
    raw3, evt3 = detector.process_frame(dummy_frame, camera_id=camera_id, mock_trigger=True)
    assert evt3 is None

    # Verify MongoDB alert was stored
    alerts = db_manager.get_alerts(camera_id=camera_id)
    assert len(alerts) >= 1
    assert alerts[0]["event_type"] == "WEAPON_DETECTED"

import time
import pytest
from violence.action_model import ViolenceDetector
from database.mongo import db_manager

def test_violence_detector_demo_mode():
    detector = ViolenceDetector(model_path="models/violence/non_existent.pt")
    assert detector.is_demo_mode is True
    assert detector.is_real_model_loaded is False

def test_temporal_clip_requirement_enforcement():
    detector = ViolenceDetector(clip_len=16)
    camera_id = "CCTV-TEMP-TEST"

    # Frame 1 to 15: Must return None (Strictly rejects single-frame / short clips!)
    for i in range(15):
        detector.collect_frame(None, camera_id=camera_id)
        assert detector.create_clip(camera_id=camera_id) is None

    # Frame 16: Exactly meets temporal window requirement -> returns clip
    detector.collect_frame(None, camera_id=camera_id)
    clip = detector.create_clip(camera_id=camera_id)
    assert clip is not None
    assert len(clip) == 16

def test_violence_prediction_and_cooldown():
    detector = ViolenceDetector(clip_len=4, cooldown_sec=10)
    camera_id = "CCTV-VIO-COOLDOWN"

    # Collect 4 frames to fill temporal window
    for _ in range(4):
        detector.collect_frame(None, camera_id=camera_id)

    # 1. Normal prediction
    clip = detector.create_clip(camera_id=camera_id)
    label, conf = detector.predict_clip(clip, camera_id=camera_id, mock_trigger=False)
    assert label == "NORMAL"

    # 2. Trigger Possible Violence
    label_v, conf_v = detector.predict_clip(clip, camera_id=camera_id, mock_trigger=True)
    assert label_v == "POSSIBLE_VIOLENCE"
    assert conf_v >= 0.80

    # 3. Confirm and Dispatch Alert
    event = detector.confirm_event(camera_id, label_v, conf_v)
    assert event is not None
    assert event["event_type"] == "POSSIBLE_VIOLENCE"
    assert event["severity"] == "HIGH"
    assert "temporal window" in event["description"]

    # 4. Immediate repeat event within cooldown window must be suppressed!
    event_repeat = detector.confirm_event(camera_id, label_v, conf_v)
    assert event_repeat is None

    # 5. Verify MongoDB alert collection
    alerts = db_manager.get_alerts(camera_id=camera_id)
    assert len(alerts) >= 1
    assert alerts[0]["event_type"] == "POSSIBLE_VIOLENCE"

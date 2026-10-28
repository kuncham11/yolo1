import pytest
from app import create_app
from alerts.emergency_dispatcher import emergency_dispatcher
from detection.accident_detector import AccidentDetector
from database.mongo import db_manager

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_emergency_dispatcher_event_creation_and_agencies():
    gun_event = emergency_dispatcher.create_emergency_event(
        threat_type="WEAPON_FIREARM_DETECTED",
        camera_id="CCTV-01",
        description="Armed suspect carrying handgun",
        severity="CRITICAL",
        confidence=0.98
    )
    assert gun_event is not None
    assert "POLICE" in gun_event["target_agencies"]
    assert "AMBULANCE" in gun_event["target_agencies"]
    assert "TV_CHANNEL" in gun_event["target_agencies"]
    assert gun_event["dispatch_status"]["POLICE"] == "PENDING"

    res = emergency_dispatcher.dispatch_agency(gun_event["event_id"], "POLICE", "Dispatched SWAT unit")
    assert res["success"] is True
    assert gun_event["dispatch_status"]["POLICE"]["status"] == "DISPATCHED"

    all_res = emergency_dispatcher.dispatch_all(gun_event["event_id"])
    assert all_res["AMBULANCE"]["success"] is True
    assert all_res["TV_CHANNEL"]["success"] is True

def test_accident_detector_fall_and_emergency_alert():
    detector = AccidentDetector(cooldown_sec=5)
    camera_id = "CCTV-ACCIDENT-TEST"

    standing_track = [{"track_id": 101, "bbox": [100, 100, 140, 220]}]
    acc1, evt1 = detector.process_tracks_and_frame(standing_track, camera_id=camera_id)
    assert len(acc1) == 0
    assert evt1 is None

    fallen_track = [{"track_id": 102, "bbox": [100, 100, 260, 180]}]
    detector.process_tracks_and_frame(fallen_track, camera_id=camera_id)
    detector.process_tracks_and_frame(fallen_track, camera_id=camera_id)
    acc3, evt3 = detector.process_tracks_and_frame(fallen_track, camera_id=camera_id)

    assert len(acc3) == 1
    assert acc3[0]["type"] == "ACCIDENT_PEDESTRIAN_FALL"
    assert evt3 is not None
    assert "AMBULANCE" in evt3["target_agencies"]
    assert "POLICE" in evt3["target_agencies"]

def test_emergency_api_simulation_and_dispatch(client):
    sim_resp = client.post("/api/alerts/simulate_threat", json={
        "threat_type": "GUN",
        "camera_id": "CCTV-01"
    })
    assert sim_resp.status_code == 201
    sim_data = sim_resp.get_json()
    assert sim_data["status"] == "success"
    event_id = sim_data["data"]["event_id"]

    act_resp = client.get("/api/alerts/active_emergency")
    assert act_resp.status_code == 200
    act_data = act_resp.get_json()
    assert act_data["has_active_emergency"] is True
    assert act_data["emergency"]["event_id"] == event_id

    disp_resp = client.post("/api/alerts/dispatch", json={
        "event_id": event_id,
        "agency": "AMBULANCE",
        "notes": "Emergency paramedic response"
    })
    assert disp_resp.status_code == 200
    disp_data = disp_resp.get_json()
    assert disp_data["status"] == "success"

    tv_resp = client.post("/api/alerts/dispatch", json={
        "event_id": event_id,
        "agency": "TV_CHANNEL",
        "notes": "Public safety EAS broadcast"
    })
    assert tv_resp.status_code == 200

    # 5. Stop Emergency via API
    stop_resp = client.post("/api/alerts/stop_emergency", json={"event_id": event_id})
    assert stop_resp.status_code == 200
    stop_data = stop_resp.get_json()
    assert stop_data["status"] == "success"

    # Verify active emergency is now None / stopped
    act_after = client.get("/api/alerts/active_emergency")
    assert act_after.status_code == 200
    assert act_after.get_json()["has_active_emergency"] is False
import io
import pytest
import numpy as np
from app import create_app
from detection.llm_vision import LLMVisionEngine, llm_vision

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_llm_vision_local_analysis():
    engine = LLMVisionEngine()
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    res = engine.analyze_frame(dummy_frame, camera_id="CCTV-03")

    assert res["status"] == "success"
    assert res["person_count"] >= 1
    assert len(res["persons"]) >= 1
    assert "bbox" in res["persons"][0]
    assert "risk_items" in res
    assert res["threat_level"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "SAFE")
    assert res["risk_score"] > 0
    assert "forensic_summary" in res

def test_llm_vision_knife_detection():
    engine = LLMVisionEngine()
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    res = engine.analyze_frame(dummy_frame, camera_id="CCTV-04")

    assert res["status"] == "success"
    risk_types = [item["item_type"] for item in res["risk_items"]]
    assert "knife" in risk_types

def test_api_llm_analyze_frame_endpoint(client):
    res = client.post('/api/llm_analyze_frame', json={"camera_id": "CCTV-01"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "person_count" in data
    assert "persons" in data
    assert "threat_level" in data

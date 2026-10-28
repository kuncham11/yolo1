import pytest
from app import create_app
from detection.person_detector import PersonDetector
from cameras.stream_manager import CameraWorker, stream_manager

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_person_detector_init():
    detector = PersonDetector(conf_threshold=0.50, device="cpu")
    assert detector.conf_threshold == 0.50
    assert detector.device == "cpu"
    # Should handle empty input gracefully
    assert detector.detect(None) == []

def test_camera_worker_synthetic_fallback():
    worker = CameraWorker(
        camera_id="CCTV-TEST",
        name="Test Camera",
        stream_url="non_existent_feed.mp4",
        source_type="Video File",
        fps_limit=30
    )
    worker.start()
    assert worker.running is True
    # Test getting detections
    dets = worker.get_detections()
    assert isinstance(dets, list)
    worker.stop()
    assert worker.running is False

def test_api_camera_detections(client):
    from database.mongo import db_manager
    db_manager.add_camera({
        "camera_id": "CCTV-01",
        "name": "Main Entrance Gate",
        "stream_url": "0",
        "source_type": "Webcam"
    })
    stream_manager.activate_laptop_webcam("CCTV-01", 0)
    response = client.get('/api/cameras/CCTV-01/detections')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['camera_id'] == 'CCTV-01'
    assert 'detections' in data
    assert 'count' in data

def test_mjpeg_stream_generator():
    gen = stream_manager.generate_mjpeg_stream("CCTV-01")
    # Fetch first chunk from generator
    chunk = next(gen)
    assert b'--frame' in chunk
    assert b'Content-Type: image/jpeg' in chunk

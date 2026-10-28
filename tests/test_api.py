import pytest
from app import create_app
from database.mongo import db_manager

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_check(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert 'database' in data
    assert 'connected' in data['database']

def test_login_page_renders(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'CROWDGUARD' in response.data

def test_dashboard_page_renders(client):
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b'Surveillance Matrix' in response.data

def test_api_cameras_crud(client):
    # 1. GET Cameras
    response = client.get('/api/cameras')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    initial_count = data['count']

    # 2. POST Camera
    new_cam = {
        "camera_id": "CCTV-99",
        "name": "Perimeter Gate 9",
        "location": "South Perimeter",
        "source_type": "RTSP",
        "stream_url": "rtsp://192.168.1.100:554/live",
        "fps_limit": 25
    }
    post_res = client.post('/api/cameras', json=new_cam)
    assert post_res.status_code == 201
    assert post_res.get_json()['data']['camera_id'] == 'CCTV-99'

    # 3. PUT Camera
    put_res = client.put('/api/cameras/CCTV-99', json={"name": "Updated Perimeter Gate 9"})
    assert put_res.status_code == 200
    assert put_res.get_json()['data']['name'] == "Updated Perimeter Gate 9"

    # 4. DELETE Camera
    del_res = client.delete('/api/cameras/CCTV-99')
    assert del_res.status_code == 200

def test_api_alerts_create_and_workflow(client):
    # 1. Create Alert
    new_alert = {
        "event_id": "EVT-TEST-1",
        "camera_id": "CCTV-01",
        "camera_name": "Main Entrance Gate",
        "event_type": "TEST_ANOMALY",
        "severity": "HIGH",
        "confidence": 0.91,
        "risk_score": 70,
        "description": "Automated test incident."
    }
    create_res = client.post('/api/alerts', json=new_alert)
    assert create_res.status_code == 201
    assert create_res.get_json()['data']['event_id'] == 'EVT-TEST-1'

    # 2. Acknowledge Alert
    ack_res = client.post('/api/alerts/EVT-TEST-1/ack', json={"officer_name": "Test Officer"})
    assert ack_res.status_code == 200
    assert ack_res.get_json()['data']['status'] == 'ACKNOWLEDGED'

    # 3. Resolve Alert
    resolve_res = client.post('/api/alerts/EVT-TEST-1/resolve')
    assert resolve_res.status_code == 200
    assert resolve_res.get_json()['data']['status'] == 'RESOLVED'

    # 4. False Positive Alert
    fp_res = client.post('/api/alerts/EVT-TEST-1/false_positive')
    assert fp_res.status_code == 200
    assert fp_res.get_json()['data']['status'] == 'FALSE_POSITIVE'

def test_api_dashboard_summary(client):
    response = client.get('/api/dashboard/summary')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'total_people_detected' in data
    assert 'cameras_online' in data
    assert 'threat_distribution' in data

def test_api_upload_cctv(client):
    import io
    data = {
        'video_file': (io.BytesIO(b'dummy_mp4_content_stream'), 'test_cctv_footage.mp4')
    }
    response = client.post('/api/upload_cctv', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data['status'] == 'success'
    assert res_data['camera_id'] == 'CCTV-UPLOAD'
    assert '/api/cameras/CCTV-UPLOAD/stream' in res_data['stream_url']

def test_api_laptop_camera_status(client):
    response = client.get('/api/cameras/laptop/status')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'hardware_test' in data

def test_api_laptop_camera_activate(client):
    response = client.post('/api/cameras/laptop/activate', json={"camera_id": "CCTV-01", "device_index": 0})
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['data']['camera_id'] == 'CCTV-01'

def test_api_camera_behaviour(client):
    response = client.get('/api/cameras/CCTV-01/behaviour')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'people_count' in data
    assert 'events' in data

def test_api_camera_ingest_frame(client):
    # Minimal 1x1 valid base64 JPEG
    import base64
    tiny_jpeg = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08'
        b'\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' '
        b'",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00'
        b'\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
        b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
    )
    b64_str = base64.b64encode(tiny_jpeg).decode('utf-8')
    response = client.post('/api/cameras/CCTV-01/ingest_frame', json={"frame": b64_str})
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['camera_id'] == 'CCTV-01'


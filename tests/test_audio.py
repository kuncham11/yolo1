import io
import os
import wave
import struct
import pytest
from app import create_app
from audio.audio_analyzer import AudioAnalyzer, audio_analyzer

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def create_synthetic_wav(tmp_path, filename="gunshot_test.wav", duration_sec=1.5, sample_rate=44100):
    wav_path = str(tmp_path / filename)
    n_samples = int(duration_sec * sample_rate)
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        
        raw_frames = bytearray()
        for i in range(n_samples):
            val = int(28000 * (1.0 if i < 1000 else 0.05))
            raw_frames.extend(struct.pack('<h', val))
        wf.writeframes(raw_frames)
    return wav_path

def test_audio_analyzer_synthetic_wav(tmp_path):
    wav_path = create_synthetic_wav(tmp_path, "gunshot_event.wav")
    analyzer = AudioAnalyzer()
    res = analyzer.analyze_file(wav_path, camera_id="CCTV-01")
    
    assert res["status"] == "success"
    assert res["filename"] == "gunshot_event.wav"
    assert res["duration_sec"] > 0
    assert res["peak_decibel_db"] > 70.0
    assert len(res["timeline_labels"]) > 0
    assert len(res["decibel_levels"]) > 0
    assert len(res["detected_threats"]) > 0
    
    event_types = [t["event_type"] for t in res["detected_threats"]]
    assert "GUNSHOT_ACOUSTIC_SIGNATURE" in event_types

def test_audio_analyzer_mp3_fallback(tmp_path):
    mp3_path = str(tmp_path / "ambient_crowd.mp3")
    with open(mp3_path, "wb") as f:
        f.write(b"ID3" + b"\x00\x00\x00" + b"\x00" * 4000)
    
    analyzer = AudioAnalyzer()
    res = analyzer.analyze_file(mp3_path, camera_id="CCTV-02")
    
    assert res["status"] == "success"
    assert res["filename"] == "ambient_crowd.mp3"
    assert res["peak_decibel_db"] >= 30.0
    assert "detected_threats" in res

def test_api_upload_audio_endpoint(client):
    data = {
        'audio_file': (io.BytesIO(b'ID3_SAMPLE_MP3_AUDIO_STREAM_DATA'), 'panic_scream_alert.mp3'),
        'camera_id': 'CCTV-01'
    }
    response = client.post('/api/upload_audio', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data['status'] == 'success'
    assert res_data['filename'].startswith('panic_scream_alert')
    assert 'audio_url' in res_data
    assert 'timeline_labels' in res_data
    assert 'decibel_levels' in res_data
    assert 'detected_threats' in res_data
    
    types = [t["event_type"] for t in res_data["detected_threats"]]
    assert "DISTRESS_VOCALIZATION_SCREAM" in types

def test_api_upload_audio_invalid_file(client):
    data = {
        'audio_file': (io.BytesIO(b'some_binary'), 'document.pdf')
    }
    response = client.post('/api/upload_audio', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    res_data = response.get_json()
    assert res_data['status'] == 'error'

import pytest
import numpy as np
import cv2
from detection.face_recognizer import FaceRecognizer

def test_face_recognizer_init():
    recognizer = FaceRecognizer(model_path="models/face/best.pt")
    assert recognizer is not None
    assert isinstance(recognizer.known_faces, dict)

def test_face_recognizer_register_person():
    recognizer = FaceRecognizer(model_path="models/face/best.pt")
    success = recognizer.register_person("Test_User", role="Security Admin", access_level="Level 4")
    assert success is True
    assert "Test_User" in recognizer.known_faces
    assert recognizer.known_faces["Test_User"]["role"] == "Security Admin"

def test_face_recognizer_detect_and_draw():
    recognizer = FaceRecognizer(model_path="models/face/best.pt")
    # Create synthetic test frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw simple face-like circle
    cv2.circle(frame, (320, 240), 50, (200, 200, 200), -1)

    faces = recognizer.detect_and_recognize(frame, camera_id="CCTV-01")
    assert isinstance(faces, list)

    # Test drawing on mock faces
    mock_faces = [{
        "name": "Rohith",
        "confidence": 0.95,
        "is_known": True,
        "role": "System Administrator",
        "bbox": [200, 150, 400, 350],
        "camera_id": "CCTV-01"
    }]
    drawn_frame = recognizer.draw_face_boxes(frame, mock_faces)
    assert drawn_frame is not None
    assert drawn_frame.shape == (480, 640, 3)

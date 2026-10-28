"""
CROWDGUARD AI - Face Recognition Dataset Preparation Script for YOLO Training.

This utility prepares face recognition datasets in YOLO format:
1. Option A (Automated Camera Capture): Automatically captures N face samples per person from webcam.
2. Option B (Directory of Photos): Reads photos grouped by person name (e.g., raw_faces/<Person_Name>/*.jpg).
3. Detects face bounding boxes and converts coordinates to normalized YOLO format:
   <class_id> <x_center> <y_center> <width> <height>
4. Automatically splits into 80% train / 20% validation sets.
5. Generates the standard data.yaml ready for YOLOv8/YOLOv11 training.

Usage:
  python scripts/prepare_face_dataset.py --capture --person "Rohith" --samples 60
  python scripts/prepare_face_dataset.py --from-folder "raw_faces" --output "dataset/face_yolo"
"""

import os
import sys
import glob
import math
import yaml
import shutil
import random
import argparse
from pathlib import Path

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: OpenCV is required for dataset preparation. Install with 'pip install opencv-python'")


def get_face_detector():
    """Returns OpenCV's Haar Cascade or DNN face detector for auto-annotation."""
    if not CV2_AVAILABLE:
        return None
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    if os.path.exists(cascade_path):
        return cv2.CascadeClassifier(cascade_path)
    return None


def convert_bbox_to_yolo(bbox, img_w, img_h):
    """
    Converts (x, y, w, h) pixel coordinates to normalized YOLO format:
    (x_center, y_center, width, height) with values between 0.0 and 1.0.
    """
    x, y, bw, bh = bbox
    # Clamp to boundaries
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    bw = max(1, min(bw, img_w - x))
    bh = max(1, min(bh, img_h - y))

    x_center = (x + bw / 2.0) / float(img_w)
    y_center = (y + bh / 2.0) / float(img_h)
    norm_w = bw / float(img_w)
    norm_h = bh / float(img_h)

    return (
        round(float(x_center), 6),
        round(float(y_center), 6),
        round(float(norm_w), 6),
        round(float(norm_h), 6)
    )


def capture_faces_from_webcam(person_name, num_samples=60, output_dir="raw_faces", camera_index=0):
    """
    Captures face images interactively from webcam with live feedback.
    """
    if not CV2_AVAILABLE:
        print("Error: OpenCV is required for webcam capture.")
        return False

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Error: Could not open camera device index {camera_index}.")
        return False

    person_dir = os.path.join(output_dir, person_name.replace(" ", "_"))
    os.makedirs(person_dir, exist_ok=True)

    detector = get_face_detector()
    print(f"\n[INFO] Starting camera capture for person: '{person_name}'")
    print(f"[INFO] Saving to: {person_dir}")
    print("[INFO] Look directly at the camera. Press 'c' to capture, 'a' for auto-capture, 'q' to quit.")

    count = 0
    auto_capture = False
    tick = 0

    while count < num_samples:
        ret, frame = cap.read()
        if not ret:
            break

        tick += 1
        h, w = frame.shape[:2]
        display_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = []
        if detector:
            faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

        for (x, y, fw, fh) in faces:
            cv2.rectangle(display_frame, (x, y), (x + fw, y + fh), (0, 255, 128), 2)
            cv2.putText(display_frame, f"{person_name} ({count}/{num_samples})", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 128), 2)

        # HUD status
        mode_str = "AUTO" if auto_capture else "MANUAL (press 'c')"
        cv2.putText(display_frame, f"Captured: {count}/{num_samples} | Mode: {mode_str}",
                    (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("CrowdGuard - Face Capture", display_frame)

        key = cv2.waitKey(1) & 0xFF
        should_save = False

        if key == ord('q'):
            print("\n[INFO] Capture cancelled by user.")
            break
        elif key == ord('c'):
            should_save = True
        elif key == ord('a'):
            auto_capture = not auto_capture
            print(f"[INFO] Auto capture: {'ENABLED' if auto_capture else 'DISABLED'}")

        if auto_capture and tick % 4 == 0 and len(faces) > 0:
            should_save = True

        if should_save and len(faces) > 0:
            count += 1
            filename = os.path.join(person_dir, f"{person_name}_{count:04d}.jpg")
            cv2.imwrite(filename, frame)
            print(f"Captured sample {count}/{num_samples}: {filename}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n[SUCCESS] Completed capture of {count} photos for '{person_name}'.\n")
    return True


def build_yolo_dataset(raw_dir="raw_faces", output_dir="dataset/face_yolo", val_split=0.2):
    """
    Parses folders in raw_dir, auto-annotates face bounding boxes,
    and structures into YOLO format dataset:
    dataset/face_yolo/
      ├── images/
      │   ├── train/
      │   └── val/
      ├── labels/
      │   ├── train/
      │   └── val/
      └── data.yaml
    """
    if not os.path.exists(raw_dir):
        print(f"Error: Raw faces directory '{raw_dir}' does not exist.")
        return False

    detector = get_face_detector()
    if not detector:
        print("Error: Could not initialize face detector cascade.")
        return False

    # Discover person classes
    person_classes = [d for d in os.listdir(raw_dir) if os.path.isdir(os.path.join(raw_dir, d))]
    person_classes.sort()

    if not person_classes:
        print(f"Error: No person subfolders found in '{raw_dir}'. Example structure: raw_faces/Rohith/*.jpg")
        return False

    print(f"\n[INFO] Found {len(person_classes)} person classes: {person_classes}")

    # Create target directories
    for split in ["train", "val"]:
        os.makedirs(os.path.join(output_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "labels", split), exist_ok=True)

    total_annotated = 0
    class_map = {name: idx for idx, name in enumerate(person_classes)}

    for class_name in person_classes:
        class_id = class_map[class_name]
        folder_path = os.path.join(raw_dir, class_name)
        img_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"]:
            img_files.extend(glob.glob(os.path.join(folder_path, ext)))

        random.shuffle(img_files)
        val_count = int(len(img_files) * val_split)
        train_files = img_files[val_count:]
        val_files = img_files[:val_count]

        print(f"Processing '{class_name}' (ID {class_id}): {len(train_files)} train, {len(val_files)} val")

        for split, files in [("train", train_files), ("val", val_files)]:
            for fpath in files:
                img = cv2.imread(fpath)
                if img is None:
                    continue

                h, w = img.shape[:2]
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))

                if len(faces) == 0:
                    # Fallback: full center crop as approximate face if detector misses
                    faces = [(int(w * 0.2), int(h * 0.15), int(w * 0.6), int(h * 0.6))]

                base_name = f"{class_name}_{Path(fpath).stem}"
                target_img_path = os.path.join(output_dir, "images", split, f"{base_name}.jpg")
                target_label_path = os.path.join(output_dir, "labels", split, f"{base_name}.txt")

                # Copy/Save image
                cv2.imwrite(target_img_path, img)

                # Write YOLO format label
                with open(target_label_path, "w") as lf:
                    for bbox in faces:
                        yolo_coords = convert_bbox_to_yolo(bbox, w, h)
                        lf.write(f"{class_id} {yolo_coords[0]} {yolo_coords[1]} {yolo_coords[2]} {yolo_coords[3]}\n")

                total_annotated += 1

    # Generate data.yaml config file
    abs_output = os.path.abspath(output_dir).replace("\\", "/")
    yaml_config = {
        "path": abs_output,
        "train": "images/train",
        "val": "images/val",
        "nc": len(person_classes),
        "names": person_classes
    }

    yaml_path = os.path.join(output_dir, "data.yaml")
    with open(yaml_path, "w") as yf:
        yaml.dump(yaml_config, yf, default_flow_style=False, sort_keys=False)

    print(f"\n[SUCCESS] Successfully compiled {total_annotated} annotated face samples.")
    print(f"[SUCCESS] Dataset YAML generated at: {yaml_path}")
    print("\nNext step: Run YOLO training:")
    print(f"  python scripts/train_yolo_face.py --data \"{yaml_path}\" --epochs 50 --model yolo11n.pt\n")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare YOLO Face Recognition Dataset")
    parser.add_argument("--capture", action="store_true", help="Capture faces from webcam interactively")
    parser.add_argument("--person", type=str, default="Unknown", help="Person name for capture")
    parser.add_argument("--samples", type=int, default=60, help="Number of face samples to capture")
    parser.add_argument("--from-folder", type=str, default="raw_faces", help="Input raw face photos directory")
    parser.add_argument("--output", type=str, default="dataset/face_yolo", help="YOLO dataset output directory")
    parser.add_argument("--split", type=float, default=0.2, help="Validation split fraction (default: 0.2)")

    args = parser.parse_args()

    if args.capture:
        capture_faces_from_webcam(args.person, num_samples=args.samples, output_dir=args.from_folder)
        # Automatically compile dataset after capture
        build_yolo_dataset(raw_dir=args.from_folder, output_dir=args.output, val_split=args.split)
    else:
        build_yolo_dataset(raw_dir=args.from_folder, output_dir=args.output, val_split=args.split)

"""
CROWDGUARD AI - YOLO Face Recognition Training Script.

Trains a custom YOLO (YOLOv8 or YOLOv11) face recognition model on your dataset:
- Auto-downloads base pretrained backbone (yolo11n.pt or yolov8n.pt).
- Applies tactical data augmentations (flips, scaling, mosaic, HSV color shifts).
- Evaluates validation metrics: mAP50, mAP50-95, precision, and recall.
- Automatically saves and deploys the best checkpoint to models/face/best.pt.

Usage:
  python scripts/train_yolo_face.py --data dataset/face_yolo/data.yaml --epochs 50 --batch 16 --model yolo11n.pt
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

def train_yolo_face(
    data_yaml="dataset/face_yolo/data.yaml",
    model_name="yolo11n.pt",
    epochs=50,
    batch_size=16,
    img_size=640,
    device="cpu",
    project="runs/face_train",
    name="yolo_face_exp",
    deploy_target="models/face/best.pt"
):
    print("=" * 70)
    print(" CROWDGUARD AI: YOLO Face Recognition Model Training Engine")
    print("=" * 70)
    print(f"[CONFIG] Dataset YAML: {data_yaml}")
    print(f"[CONFIG] Base Model:   {model_name}")
    print(f"[CONFIG] Epochs:       {epochs}")
    print(f"[CONFIG] Batch Size:   {batch_size}")
    print(f"[CONFIG] Image Size:   {img_size}x{img_size}")
    print(f"[CONFIG] Device:       {device}")
    print(f"[CONFIG] Save Target:  {deploy_target}")
    print("=" * 70)

    if not os.path.exists(data_yaml):
        print(f"\n[ERROR] Dataset YAML file '{data_yaml}' not found.")
        print("Please prepare your dataset first by running:")
        print("  python scripts/prepare_face_dataset.py --capture --person \"Rohith\" --samples 60")
        return False

    try:
        import torch
        from ultralytics import YOLO
    except ImportError as e:
        print(f"\n[ERROR] Required ML packages missing: {e}")
        print("\nPlease install ultralytics and torch:")
        print("  pip install ultralytics torch torchvision")
        print("\nIf training on a GPU, install PyTorch with CUDA:")
        print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
        return False

    # Check device availability
    if device == "cuda" and not torch.cuda.is_available():
        print("[WARNING] CUDA requested but GPU not detected. Falling back to CPU training.")
        device = "cpu"
    elif torch.cuda.is_available() and device == "cpu":
        print("[TIP] CUDA GPU detected! Using 'cuda' for high-speed hardware acceleration.")
        device = "cuda"

    # Initialize YOLO Model
    print(f"\n[INFO] Loading base model weights: '{model_name}'...")
    try:
        model = YOLO(model_name)
    except Exception as e:
        print(f"[ERROR] Failed to load model weights '{model_name}': {e}")
        return False

    # Start training
    print("\n[INFO] Launching training process...")
    try:
        results = model.train(
            data=data_yaml,
            epochs=epochs,
            batch=batch_size,
            imgsz=img_size,
            device=device,
            project=project,
            name=name,
            exist_ok=True,
            pretrained=True,
            patience=20,          # Early stopping if no improvement for 20 epochs
            save=True,
            plots=True,           # Save confusion matrix, PR curves, F1 curve
            mosaic=0.8,           # Strong mosaic augmentation for robust facial occlusion
            fliplr=0.5,           # Horizontal flip augmentation
            hsv_h=0.015,          # HSV Hue shift
            hsv_s=0.7,            # HSV Saturation shift
            hsv_v=0.4,            # HSV Value shift
            degrees=10.0,         # Rotation variation
            verbose=True
        )

        print("\n" + "=" * 70)
        print(" [SUCCESS] Training completed successfully!")
        print("=" * 70)

        # Validate Model
        print("\n[INFO] Running post-training validation on test split...")
        metrics = model.val()
        print(f"[METRICS] mAP50:      {metrics.box.map50:.4f}")
        print(f"[METRICS] mAP50-95:   {metrics.box.map:.4f}")
        print(f"[METRICS] Precision:  {metrics.box.p[0]:.4f}" if len(metrics.box.p) > 0 else "")
        print(f"[METRICS] Recall:     {metrics.box.r[0]:.4f}" if len(metrics.box.r) > 0 else "")

        # Export and Deploy best weights
        exp_dir = Path(project) / name
        best_weights = exp_dir / "weights" / "best.pt"

        if best_weights.exists():
            os.makedirs(os.path.dirname(deploy_target), exist_ok=True)
            shutil.copy(best_weights, deploy_target)
            print(f"\n[DEPLOYED] Trained weights successfully deployed to: '{deploy_target}'")
            print(f"[INFO] CrowdGuard AI will automatically load this model for live video face recognition!")
        else:
            print(f"[WARNING] Best weights file not found at {best_weights}")

        return True

    except Exception as e:
        print(f"\n[ERROR] An error occurred during YOLO face training: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLO Face Recognition Model")
    parser.add_argument("--data", type=str, default="dataset/face_yolo/data.yaml", help="Path to data.yaml")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Pretrained YOLO weights (e.g. yolo11n.pt, yolov8n.pt)")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Training batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image resolution")
    parser.add_argument("--device", type=str, default="cpu", help="Device to use ('cpu' or 'cuda')")
    parser.add_argument("--output", type=str, default="models/face/best.pt", help="Deployment path for trained weights")

    args = parser.parse_args()

    train_yolo_face(
        data_yaml=args.data,
        model_name=args.model,
        epochs=args.epochs,
        batch_size=args.batch,
        img_size=args.imgsz,
        device=args.device,
        deploy_target=args.output
    )

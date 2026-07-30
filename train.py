from pathlib import Path
from ultralytics import YOLO
import torch


def main():
    ROOT = Path(__file__).parent
    DATA_YAML = ROOT / "fire-and-smoke-detection-1" / "data.yaml"

    if not DATA_YAML.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_YAML}")

    print("=" * 80)
    print("Fire Detection Training")
    print("=" * 80)
    print(f"Dataset : {DATA_YAML}")
    print(f"CUDA    : {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"GPU     : {torch.cuda.get_device_name(0)}")
        print(
            f"VRAM    : {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB"
        )

    print("=" * 80)

    # Load pretrained YOLOv8 Small model
    model = YOLO("yolov8s.pt")
    model.train(
        # Dataset
        data=str(DATA_YAML),

        # Training
        epochs=100,
        imgsz=640,
        batch=4,
        device=0,
        workers=4,

        # Pretrained
        pretrained=True,

        # Performance
        cache=True,
        amp=True,

        # Optimizer
        optimizer="SGD",
        lr0=0.01,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,

        # Learning rate schedule
        cos_lr=True,

        # Early stopping
        patience=20,

        # -------------------------
        # Data Augmentation
        # -------------------------
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,

        degrees=10,
        translate=0.10,
        scale=0.30,
        shear=0.0,

        fliplr=0.5,
        flipud=0.0,

        mosaic=1.0,
        mixup=0.05,
        close_mosaic=15,

        # Save
        project="runs",
        name="fire_detection",

        save=True,
        plots=True,
        verbose=True,

        seed=42,
    )

    print("\n" + "=" * 80)
    print("Training Complete!")
    print("Best model saved at:")
    print(ROOT / "runs" / "fire_detection" / "weights" / "best.pt")
    print("=" * 80)


if __name__ == "__main__":
    main()
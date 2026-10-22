"""Trains the card detector and copies the best weights to models/cards.pt.

Run tools/prepare_dataset.py first.
Usage: python tools/train_yolo.py [--epochs N] [--model yolo11s.pt] [--batch N]
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import REPO_ROOT, load_settings, repo_path  # noqa: E402


def main():
    vision = load_settings()["vision"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=vision["base_model"])
    ap.add_argument("--epochs", type=int, default=vision["epochs"])
    ap.add_argument("--batch", type=int, default=vision["batch"])
    ap.add_argument("--imgsz", type=int, default=vision["imgsz"])
    ap.add_argument("--name", default="cards")
    args = ap.parse_args()

    from ultralytics import YOLO

    data = repo_path(vision["prepared_dir"]) / "data.yaml"
    if not data.exists():
        sys.exit(f"{data} not found - run tools/prepare_dataset.py first")

    model = YOLO(args.model)
    results = model.train(
        data=str(data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=str(REPO_ROOT / "runs"),
        name=args.name,
        exist_ok=False,
        patience=40,
        # Screenshots, not photos: card glyphs must never be mirrored or rotated,
        # and colour carries meaning (red/black suits, yellow highlight).
        fliplr=0.0,
        flipud=0.0,
        degrees=0.0,
        hsv_h=0.0,
        scale=0.25,
        workers=vision["workers"],
    )

    best = Path(results.save_dir) / "weights" / "best.pt"
    dest = repo_path(vision["weights"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, dest)
    print(f"Best weights -> {dest}")


if __name__ == "__main__":
    main()

"""Reading the labelled dataset back as Detections (ground truth, conf = 1.0)."""
from pathlib import Path

from solitaire.config import load_settings, repo_path
from solitaire.vision.detection import Detection


def class_names(dataset_dir: str | Path | None = None) -> list[str]:
    d = Path(dataset_dir or load_settings()["vision"]["dataset_dir"])
    return [n.strip() for n in (d / "classes.txt").read_text().splitlines() if n.strip()]


def split_images(split: str) -> list[Path]:
    """Image paths of a split written by tools/prepare_dataset.py ('train'/'val'/'test'), or 'all'."""
    prepared = repo_path(load_settings()["vision"]["prepared_dir"])
    splits = ["train", "val", "test"] if split == "all" else [split]
    return [Path(p) for s in splits for p in (prepared / f"{s}.txt").read_text().split()]


def label_detections(image_path: Path, names: list[str], width_px: int, height_px: int) -> list[Detection]:
    label_path = image_path.parent.parent / "labels" / f"{image_path.stem}.txt"
    boxes = set()  # set: the export contains a few exact duplicate rows
    for line in label_path.read_text().splitlines():
        if line.strip():
            c, xc, yc, bw, bh = line.split()
            xc, bw = float(xc) * width_px, float(bw) * width_px
            yc, bh = float(yc) * height_px, float(bh) * height_px
            boxes.add(Detection(names[int(c)], 1.0, xc - bw / 2, yc - bh / 2, xc + bw / 2, yc + bh / 2))
    return list(boxes)

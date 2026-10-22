"""Builds a train/val split + data.yaml for the Label Studio YOLO export.

Images are never copied: the split files list absolute paths into the source
dataset, and Ultralytics finds labels by swapping /images/ for /labels/.

Screenshots were taken in sequence during games, so neighbours are near
duplicates. A random split would leak them into val; instead, consecutive
blocks of screenshots go to the same side.

Usage: python tools/prepare_dataset.py [--src DIR]
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import load_settings, repo_path  # noqa: E402

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def shot_number(path: Path) -> int:
    """Label Studio prefixes a hash: '05b89ae1-IMG_0534.PNG' -> 534."""
    m = re.search(r"IMG_(\d+)", path.stem)
    return int(m.group(1)) if m else 0


def main():
    vision = load_settings()["vision"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=vision["dataset_dir"])
    args = ap.parse_args()

    src = Path(args.src)
    out = repo_path(vision["prepared_dir"])
    out.mkdir(parents=True, exist_ok=True)

    names = [n.strip() for n in (src / "classes.txt").read_text().splitlines() if n.strip()]

    images = sorted((p for p in (src / "images").iterdir() if p.suffix.lower() in IMAGE_EXTS),
                    key=lambda p: (shot_number(p), p.name))
    missing = [p.name for p in images if not (src / "labels" / f"{p.stem}.txt").exists()]
    if missing:
        sys.exit(f"{len(missing)} images have no label file, e.g. {missing[:3]}")

    # Space val and test blocks evenly through the sequence so each split gets
    # screenshots from early, middle and late games: a block goes to val/test
    # whenever that split's running quota passes a whole number.
    block = vision["split_block_size"]
    fractions = {"val": vision["val_fraction"], "test": vision["test_fraction"]}
    owed = dict.fromkeys(fractions, 0.0)
    splits = {"train": [], "val": [], "test": []}
    for b in range(0, len(images), block):
        for k, f in fractions.items():
            owed[k] += f
        name = max(owed, key=owed.get)
        if owed[name] >= 1:
            owed[name] -= 1
        else:
            name = "train"
        splits[name] += [p.resolve().as_posix() for p in images[b:b + block]]

    for name, paths in splits.items():
        (out / f"{name}.txt").write_text("\n".join(paths) + "\n")
    data = {
        "path": out.as_posix(),
        "train": "train.txt",
        "val": "val.txt",
        "test": "test.txt",
        "names": dict(enumerate(names)),
    }
    (out / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"{len(names)} classes | " + " | ".join(f"{k} {len(v)}" for k, v in splits.items())
          + f" -> {out / 'data.yaml'}")


if __name__ == "__main__":
    main()

"""Merges a Label Studio YOLO export of the review project back into the dataset.

- Dataset images: their label file is replaced by the reviewed one.
- Live frames: the image is copied into the dataset and its label file added.
Class ids are remapped by name (the export's classes.txt -> the dataset's), and the
dataset's labels/ folder is backed up first, so nothing is lost.

Usage: python tools/merge_review.py EXPORT   (the export's .zip, or the folder it unzips to)
       add --dry-run to see what would change
Then: python tools/prepare_dataset.py && python tools/train_yolo.py
"""
import argparse
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import load_settings  # noqa: E402


def main():
    vision = load_settings()["vision"]
    ap = argparse.ArgumentParser()
    ap.add_argument("export", help="Label Studio YOLO export: .zip or unzipped folder")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    export = Path(args.export)
    if export.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="ls_export_"))
        with zipfile.ZipFile(export) as z:
            z.extractall(tmp)
        export = tmp
    dataset = Path(vision["dataset_dir"])
    review_images = Path(vision["review_dir"]) / "images"

    def names(folder: Path) -> list[str]:
        return [n.strip() for n in (folder / "classes.txt").read_text().splitlines() if n.strip()]

    ds_names, ex_names = names(dataset), names(export)
    unknown = set(ex_names) - set(ds_names)
    if unknown:
        sys.exit(f"export has classes the dataset doesn't: {sorted(unknown)}")
    remap = {i: ds_names.index(n) for i, n in enumerate(ex_names)}

    reviewed = {p.stem: p for p in review_images.iterdir()}
    plan = []   # (label_text, dataset image name, source image to copy or None)
    for lbl in sorted((export / "labels").glob("*.txt")):
        # Label Studio may prefix its own hash to the file name: match the review image by suffix
        stem = next((s for s in reviewed if lbl.stem == s or lbl.stem.endswith("-" + s)), None)
        if stem is None:
            print(f"  ? {lbl.name}: no matching image in {review_images}, skipped")
            continue
        rows = []
        for line in lbl.read_text().splitlines():
            if line.strip():
                c, *box = line.split()
                rows.append(" ".join([str(remap[int(c)]), *box]))
        img = reviewed[stem]
        in_dataset = (dataset / "images" / img.name).exists()
        if not rows:
            print(f"  ? {img.name}: no boxes in the export, skipped")
            continue
        plan.append(("\n".join(rows) + "\n", img.name, None if in_dataset else img))

    updated = sum(src is None for *_, src in plan)
    added = len(plan) - updated
    print(f"{updated} dataset labels to update, {added} new images to add (from {export})")
    if args.dry_run or not plan:
        return

    backup = dataset / f"labels_backup_{datetime.now():%Y%m%d_%H%M%S}"
    shutil.copytree(dataset / "labels", backup)
    print(f"backed up labels -> {backup}")
    for text, name, src in plan:
        if src is not None:
            shutil.copy2(src, dataset / "images" / name)
        (dataset / "labels" / f"{Path(name).stem}.txt").write_text(text)
    print("done. Next: python tools/prepare_dataset.py, then python tools/train_yolo.py")


if __name__ == "__main__":
    main()

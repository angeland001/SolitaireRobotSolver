"""Runs the card detector on screenshot(s), prints detections, saves annotated copies.

Usage: python tools/detect_image.py IMAGE [IMAGE ...] [--out runs/detect_preview] [--conf 0.5]
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import REPO_ROOT  # noqa: E402
from solitaire.vision import CardDetector  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default=str(REPO_ROOT / "runs" / "detect_preview"))
    ap.add_argument("--conf", type=float, default=None)
    ap.add_argument("--weights", default=None)
    args = ap.parse_args()

    detector = CardDetector(args.weights, args.conf)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for path in map(Path, args.images):
        img = cv2.imread(str(path))
        dets = detector.detect(img)
        faceup = sorted((d for d in dets if not d.is_facedown), key=lambda d: (d.x1_px, d.y1_px))
        n_down = sum(d.is_facedown for d in dets)
        print(f"{path.name}: {len(faceup)} face-up, {n_down} face-down")
        print("  " + " ".join(f"{d.label}({d.conf:.2f})" for d in faceup))

        for d in dets:
            color = (128, 128, 128) if d.is_facedown else (0, 200, 0)
            p1, p2 = (int(d.x1_px), int(d.y1_px)), (int(d.x2_px), int(d.y2_px))
            cv2.rectangle(img, p1, p2, color, 3)
            if not d.is_facedown:
                cv2.putText(img, d.label, (p1[0], p1[1] - 6), cv2.FONT_HERSHEY_SIMPLEX,
                            1.0, (0, 0, 255), 2)
        cv2.imwrite(str(out / f"{path.stem}_det.png"), img)
    print(f"Annotated images -> {out}")


if __name__ == "__main__":
    main()

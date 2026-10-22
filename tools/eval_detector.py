"""Game-level accuracy check: is every card on a screenshot read correctly at the
confidence threshold the game loop actually uses?

mAP rewards ranking; the robot needs every box right. For each image this counts
wrong labels, missed cards and phantom boxes, and saves annotated copies of any
image with an error.

Usage: python tools/eval_detector.py [--split val] [--conf 0.5] [--iou 0.5]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import REPO_ROOT, load_settings  # noqa: E402
from solitaire.vision import CardDetector  # noqa: E402
from solitaire.vision.dataset import class_names, label_detections, split_images  # noqa: E402


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def load_truth(image_path: Path, names: list[str], w: int, h: int):
    return [(d.label, d.x1_px, d.y1_px, d.x2_px, d.y2_px)
            for d in label_detections(image_path, names, w, h)]


def main():
    vision = load_settings()["vision"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val")
    ap.add_argument("--conf", type=float, default=vision["conf_threshold"])
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--out", default=str(REPO_ROOT / "runs" / "eval_errors"))
    args = ap.parse_args()

    names = class_names()
    images = split_images(args.split)
    detector = CardDetector(conf=args.conf)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    totals = Counter()
    wrong_pairs, missed, phantom = Counter(), Counter(), Counter()
    perfect = 0
    for path in images:
        img = cv2.imread(str(path))
        h, w = img.shape[:2]
        truth = load_truth(path, names, w, h)
        dets = detector.detect(img)

        # Greedy IoU matching, highest-confidence detections first
        unmatched = list(range(len(truth)))
        errors = []
        for d in sorted(dets, key=lambda d: -d.conf):
            box = (d.x1_px, d.y1_px, d.x2_px, d.y2_px)
            best = max(unmatched, key=lambda i: iou(box, truth[i][1:]), default=None)
            if best is not None and iou(box, truth[best][1:]) >= args.iou:
                unmatched.remove(best)
                t = truth[best][0]
                if t == d.label:
                    totals["correct"] += 1
                else:
                    wrong_pairs[(t, d.label)] += 1
                    errors.append(("wrong", f"{t}->{d.label}", box))
            else:
                phantom[d.label] += 1
                errors.append(("phantom", d.label, box))
        for i in unmatched:
            missed[truth[i][0]] += 1
            errors.append(("missed", truth[i][0], truth[i][1:]))

        totals["truth"] += len(truth)
        if not errors:
            perfect += 1
            continue
        colors = {"wrong": (0, 0, 255), "phantom": (255, 0, 255), "missed": (0, 165, 255)}
        for kind, text, b in errors:
            p1, p2 = (int(b[0]), int(b[1])), (int(b[2]), int(b[3]))
            cv2.rectangle(img, p1, p2, colors[kind], 4)
            cv2.putText(img, f"{kind}: {text}", (p1[0], max(30, p1[1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, colors[kind], 2)
        cv2.imwrite(str(out / f"{path.stem}_errors.png"), img)

    n_wrong, n_missed, n_phantom = sum(wrong_pairs.values()), sum(missed.values()), sum(phantom.values())
    print(f"{args.split}: {len(images)} screenshots, {totals['truth']} cards, conf>={args.conf}")
    print(f"  perfectly read screenshots: {perfect}/{len(images)} ({perfect / len(images):.1%})")
    print(f"  correct {totals['correct']} | wrong label {n_wrong} | missed {n_missed} | phantom {n_phantom}")
    for title, counter in [("wrong label (true->pred)", wrong_pairs), ("missed", missed), ("phantom", phantom)]:
        if counter:
            items = ", ".join(f"{'->'.join(k) if isinstance(k, tuple) else k} x{v}"
                              for k, v in counter.most_common(12))
            print(f"  {title}: {items}")
    if perfect < len(images):
        print(f"  error images -> {out}")


if __name__ == "__main__":
    main()

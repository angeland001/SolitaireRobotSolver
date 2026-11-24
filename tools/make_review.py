"""Builds a small Label Studio project of the images worth a second look.

Three kinds of image go in, each with a `reason` shown next to it in Label Studio:
  label-rule   dataset images whose *hand labels* break the game's rules or needed a
               repair (a strip labelled with the wrong card, a missing foundation...)
  model-vs-label  dataset images where the detector disagrees with the label: either
               the label is wrong (fix it) or the model is (leave the label alone)
  live         frames saved during live games (captures/misreads/ and captures/),
               pre-filled with the detector's guesses; these are new training images

Dataset images arrive with their current labels as annotations (edit them in place).
Live frames arrive with the model's boxes as *predictions*: accept and correct each one,
then Submit. Only submitted tasks are exported.

Writes into vision.review_dir:  images/  tasks.json  labeling_config.xml  review_list.txt
Usage: python tools/make_review.py [--no-model] [--live-conf 0.25]
Then follow README §4.1 "Fixing labels and retraining".
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import REPO_ROOT, load_settings, repo_path  # noqa: E402
from solitaire.state import StateBuilder  # noqa: E402
from solitaire.vision.dataset import class_names, label_detections, split_images  # noqa: E402
from tools.eval_detector import iou  # noqa: E402

ANIMATION = ("between columns", "waiting for flip", "no cards on screen")


def ls_boxes(dets, w, h, with_score=False):
    """Detections -> Label Studio rectangle results (percent of the image)."""
    out = []
    for i, d in enumerate(dets):
        r = {
            "id": f"b{i}", "from_name": "label", "to_name": "image", "type": "rectanglelabels",
            "original_width": w, "original_height": h, "image_rotation": 0,
            "value": {"x": 100 * d.x1_px / w, "y": 100 * d.y1_px / h,
                      "width": 100 * (d.x2_px - d.x1_px) / w, "height": 100 * (d.y2_px - d.y1_px) / h,
                      "rotation": 0, "rectanglelabels": [d.label]},
        }
        if with_score:
            r["score"] = round(d.conf, 3)
        out.append(r)
    return out


def rule_reasons(state) -> list[str]:
    """Problems with a labelled board that animation can't explain."""
    if any(k in i for i in state.issues for k in ANIMATION):
        return []   # mid-animation or a pre-game screen: the rules don't apply
    reasons = [f"label repaired: {where} {r} looks like {t}" for where, r, t in state.repairs]
    return reasons + [f"rule: {i}" for i in state.issues]


def model_reasons(truth, dets, conf) -> list[str]:
    """Where the detector (at the game's threshold) disagrees with the labels."""
    unmatched, out = list(range(len(truth))), []
    for d in sorted(dets, key=lambda d: -d.conf):
        box = (d.x1_px, d.y1_px, d.x2_px, d.y2_px)
        best = max(unmatched, key=lambda i: iou(box, truth[i][1:]), default=None)
        if best is not None and iou(box, truth[best][1:]) >= 0.5:
            unmatched.remove(best)
            if truth[best][0] != d.label:
                out.append(f"model reads {d.label} ({d.conf:.2f}) where the label says {truth[best][0]}")
        else:
            out.append(f"model sees an unlabelled {d.label} ({d.conf:.2f})")
    out += [f"model misses labelled {truth[i][0]}" for i in unmatched]
    return out


def main():
    settings = load_settings()
    vision = settings["vision"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-model", action="store_true", help="skip the model-vs-label pass over the dataset")
    ap.add_argument("--live-conf", type=float, default=0.25, help="detector threshold for live-frame pre-labels")
    args = ap.parse_args()

    names = class_names()
    out = Path(vision["review_dir"])
    img_out = out / "images"
    img_out.mkdir(parents=True, exist_ok=True)
    root = out.parent    # LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT
    builder = StateBuilder()
    from solitaire.vision import CardDetector
    detector = CardDetector()          # model-vs-label pass, and live-frame pre-labels

    tasks, listing = [], []

    def add(src: Path, kind: str, reasons: list[str], annotations=None, predictions=None):
        dst = img_out / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        task = {"data": {"image": f"/data/local-files/?d={dst.relative_to(root).as_posix()}",
                         "kind": kind, "reason": " | ".join(reasons)}}
        if annotations is not None:
            task["annotations"] = [{"result": annotations}]
        if predictions is not None:
            task["predictions"] = [{"model_version": "cards.pt", "result": predictions}]
        tasks.append(task)
        listing.append(f"[{kind}] {src.name}\n" + "\n".join(f"    {r}" for r in reasons))

    # 1 + 2: the dataset
    for path in split_images("all"):
        img = cv2.imread(str(path))
        h, w = img.shape[:2]
        truth_dets = label_detections(path, names, w, h)
        reasons = rule_reasons(builder.build(truth_dets, w, h))
        kind = "label-rule"
        if not args.no_model:
            truth = [(d.label, d.x1_px, d.y1_px, d.x2_px, d.y2_px) for d in truth_dets]
            m = model_reasons(truth, detector.detect(img), vision["conf_threshold"])
            if m and not reasons:
                kind = "model-vs-label"
            reasons += m
        if reasons:
            add(path, kind, reasons, annotations=ls_boxes(truth_dets, w, h))

    # 3: live frames (misread captures + frames saved with `s` in live_view)
    live_dirs = [repo_path(settings["game"]["misread_dir"]), REPO_ROOT / "captures"]
    live_detector = CardDetector(conf=args.live_conf)
    for d in live_dirs:
        for path in sorted(d.glob("*.png")):
            img = cv2.imread(str(path))
            h, w = img.shape[:2]
            note = path.with_suffix(".json")
            why = ["live frame: label every card"]
            if note.exists():
                info = json.loads(note.read_text())
                why += [f"{c['true']} read as {c['read']} (check by eye, the tag can be wrong)"
                        for c in info.get("confusions", [])] + info.get("issues", [])[:3]
            add(path, "live", why, predictions=ls_boxes(live_detector.detect(img), w, h, with_score=True))

    (out / "tasks.json").write_text(json.dumps(tasks, indent=1))
    labels = "\n".join(f'    <Label value="{n}"/>' for n in names)
    (out / "labeling_config.xml").write_text(
        '<View>\n  <Header value="$reason"/>\n  <Image name="image" value="$image" zoom="true"/>\n'
        f'  <RectangleLabels name="label" toName="image">\n{labels}\n  </RectangleLabels>\n</View>\n')
    (out / "review_list.txt").write_text("\n".join(listing) + "\n")
    kinds = {k: sum(t["data"]["kind"] == k for t in tasks) for k in ("label-rule", "model-vs-label", "live")}
    print(f"{len(tasks)} images to review -> {out}")
    for k, n in kinds.items():
        print(f"  {n:3d}  {k}")
    print(f"List with reasons: {out / 'review_list.txt'}")
    print(f"Label Studio document root: {root}")


if __name__ == "__main__":
    main()

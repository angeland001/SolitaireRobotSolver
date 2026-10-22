"""Builds a GameState for every dataset screenshot and reports which fail validation.

--source labels  uses the hand labels: tests the layout + rules on their own.
--source model   uses the detector: tests the whole vision pipeline.

Usage: python tools/check_states.py [--source labels|model] [--split all|train|val] [--show N]
"""
import argparse
import re
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import REPO_ROOT  # noqa: E402
from solitaire.state import Card, StateBuilder  # noqa: E402
from solitaire.vision.dataset import class_names, label_detections, split_images  # noqa: E402


def png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        return struct.unpack(">II", f.read(24)[16:24])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["labels", "model"], default="labels")
    ap.add_argument("--split", default="all")
    ap.add_argument("--show", type=int, default=3, help="print this many failing states in full")
    ap.add_argument("--image", help="print the state for one screenshot and exit")
    args = ap.parse_args()

    builder = StateBuilder()
    names = class_names()
    detector = None
    if args.source == "model":
        from solitaire.vision import CardDetector
        detector = CardDetector()

    def state_for(path: Path):
        w, h = png_size(path)
        dets = detector.detect(path) if detector else label_detections(path, names, w, h)
        return builder.build(dets, w, h)

    if args.image:
        print(state_for(Path(args.image)))
        return

    images = split_images(args.split)
    kinds, shown, report = Counter(), 0, []
    for path in images:
        state = state_for(path)
        if state.is_valid:
            continue
        report.append(f"{path.name}\n" + "\n".join(f"    {i}" for i in state.issues))
        kinds.update({issue_kind(i) for i in state.issues})
        if shown < args.show:
            shown += 1
            print(f"--- {path.name}\n{state}\n")

    out = REPO_ROOT / "runs" / f"state_issues_{args.source}_{args.split}.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(report) + "\n")
    print(f"{args.source}/{args.split}: {len(images) - len(report)}/{len(images)} screenshots give a valid state")
    for k, n in kinds.most_common():
        print(f"  {n:4d}  {k}")
    print(f"Per-image issues -> {out}")


def issue_kind(issue: str) -> str:
    """'column 3: 6d cannot sit on Qs' -> 'column N: <card> cannot sit on <card>'."""
    words = []
    for w in issue.split():
        core = w.rstrip(":")
        try:
            Card.parse(core)
            words.append("<card>" + w[len(core):])
        except ValueError:
            words.append(re.sub(r"\d+(\.\d+)?", "N", w) if any(c.isdigit() for c in w) else w)
    return " ".join(words)


if __name__ == "__main__":
    main()

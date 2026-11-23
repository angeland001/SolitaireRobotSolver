"""Runs solver v1 on dataset screenshots (offline, no plotter) and shows what it would play.

Usage:
  python tools/solve_states.py --image PATH      board + every scored move for one screenshot
  python tools/solve_states.py [--source labels|model] [--split all|val] [--show N]
                                                 the chosen move for every valid board
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import load_settings  # noqa: E402
from solitaire.solver import Solver, rank_moves  # noqa: E402
from solitaire.state import StateBuilder  # noqa: E402
from solitaire.vision.dataset import class_names, label_detections, split_images  # noqa: E402
from tools.check_states import png_size  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["labels", "model"], default="labels")
    ap.add_argument("--split", default="all")
    ap.add_argument("--image", help="show the board and all scored moves for one screenshot")
    ap.add_argument("--show", type=int, default=5, help="print this many boards with their move")
    args = ap.parse_args()

    settings = load_settings()
    builder, names = StateBuilder(), class_names()
    detector = None
    if args.source == "model":
        from solitaire.vision import CardDetector
        detector = CardDetector()

    def state_for(path: Path):
        w, h = png_size(path)
        dets = detector.detect(path) if detector else label_detections(path, names, w, h)
        return builder.build(dets, w, h)

    if args.image:
        state = state_for(Path(args.image))
        print(state, "\n")
        if not state.is_valid:
            print("invalid state: the solver would wait and re-read")
            return
        for score, move in rank_moves(state, settings["solver"]["weights"]):
            print(f"  {score:6.1f}  {move}")
        print(f"\nchosen: {Solver(settings).choose_move(state)}")
        return

    kinds, shown, valid = Counter(), 0, 0
    for path in split_images(args.split):
        state = state_for(path)
        if not state.is_valid:
            continue
        valid += 1
        move = Solver(settings).choose_move(state)
        if move is None:
            kinds["none (stuck / Finish)"] += 1
        elif move.is_stock:
            kinds["recycle" if move.is_recycle else "draw"] += 1
        else:
            kinds[f"{move.src} -> {move.dst} ({move.method})"] += 1
        if shown < args.show:
            shown += 1
            print(f"--- {path.name}\n{state}\n=> {move}\n")
    print(f"{valid} valid boards, chosen move by kind:")
    for k, n in kinds.most_common():
        print(f"  {n:4d}  {k}")


if __name__ == "__main__":
    main()

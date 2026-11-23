"""Which cards does the detector get wrong live? Tallies the misread frames saved by
solitaire.main and live_view.py (game.misread_dir), so you know which cards to
collect and label more screenshots of.

Usage: python tools/misread_report.py [--dir captures/misreads]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import load_settings, repo_path  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=load_settings()["game"]["misread_dir"])
    args = ap.parse_args()
    folder = repo_path(args.dir)
    files = sorted(folder.glob("*.json"))
    if not files:
        print(f"No misread frames in {folder} yet. Play a game with solitaire.main or watch one with live_view.py.")
        return

    pairs, cards, frames_per_card = Counter(), Counter(), {}
    for f in files:
        for c in json.loads(f.read_text())["confusions"]:
            pairs[(c["true"], c["read"])] += 1
            cards[c["true"]] += 1
            frames_per_card.setdefault(c["true"], []).append(f.with_suffix(".png").name)

    print(f"{len(files)} misread frames in {folder}\n")
    print("Cards to collect more screenshots of (most misread first):")
    for card, n in cards.most_common():
        print(f"  {card:>3}  {n:3d} frames   e.g. {frames_per_card[card][0]}")
    print("\nConfusions (true -> read):")
    for (t, r), n in pairs.most_common():
        print(f"  {t:>3} -> {r:<3} {n:3d}")
    print("\nThe PNGs are full 1640x2360 screens: import them into Label Studio, label, add to the dataset, retrain.")


if __name__ == "__main__":
    main()

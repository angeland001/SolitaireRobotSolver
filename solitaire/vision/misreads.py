"""Find frames the detector misread, using the stable board as the answer key.

When multi-frame agreement settles on a board, any frame from the settling window
that has the same card *at the same place* under a different label was a misread
(usually the shimmer effect, README §4.1). Those frames are saved with the
confusion ("7d read as 6s") so they can be labelled and added to the dataset;
tools/misread_report.py tallies them.

Frames from before a move (the old board) are cut off: only frames after the last
valid frame that disagreed with the stable board are compared, and a frame must
match the stable board almost box for box, so moved cards don't count as misreads.
"""
import json
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from solitaire.state.game_state import GameState
from solitaire.vision.detection import Detection


def card_boxes(state: GameState) -> list[Detection]:
    dets = [p.det for p in state.foundations if p] + [p.det for p in state.waste]
    dets += [p.det for col in state.tableau for p in col.faceup]
    return dets


def confusions(frame: GameState, stable: GameState, max_dist_px: float,
               min_matched: float = 0.85, max_wrong: int = 2) -> list[tuple[str, str]]:
    """(true label, read label) for cards read differently at the same place.
    Empty when the frame doesn't line up with the stable board (it's another board)."""
    truth, read = card_boxes(stable), card_boxes(frame)
    if not truth or not read:
        return []
    # A label that is a real card on the board (or under a foundation top) is an
    # animation frame, not a misread: the old foundation card under one flying in,
    # or a card passing over another (first live game, 2026-11-23: all 9 "misreads").
    known = {str(c) for c in stable.visible_cards()} | {str(c) for c in stable.foundation_cards()}
    centres = np.array([d.center_px for d in truth])
    pairs, matched = [], 0
    for d in read:
        dist = np.hypot(*(centres - np.array(d.center_px)).T)
        i = int(dist.argmin())
        if dist[i] > max_dist_px:
            continue
        matched += 1
        if truth[i].label != d.label:
            if d.label in known:
                return []          # the frame shows cards in motion: skip it whole
            pairs.append((truth[i].label, d.label))
    if matched < min_matched * len(read) or len(pairs) > max_wrong:
        return []
    return pairs


class MisreadRecorder:
    """Keeps the recent frames (state + image); call settled(stable) whenever a stable
    board is accepted. Saves PNG + JSON per misread frame into out_dir."""

    def __init__(self, out_dir: Path, max_dist_px: float = 40, keep: int = 60):
        self.out_dir = out_dir
        self.max_dist_px = max_dist_px
        self.frames: deque[tuple[GameState, np.ndarray]] = deque(maxlen=keep)
        self.saved = 0

    def add(self, state: GameState, image: np.ndarray) -> None:
        self.frames.append((state, image))

    def settled(self, stable: GameState) -> list[tuple[str, str]]:
        frames = list(self.frames)
        self.frames.clear()
        # Drop everything up to the last valid frame that shows a different board.
        start = 0
        for i, (s, _) in enumerate(frames):
            if s.is_valid and s.signature != stable.signature:
                start = i + 1
        found = []
        for s, image in frames[start:]:
            if s.signature == stable.signature:
                continue
            pairs = confusions(s, stable, self.max_dist_px)
            if pairs:
                self._save(s, image, pairs)
                found += pairs
        return found

    def _save(self, state: GameState, image: np.ndarray, pairs: list[tuple[str, str]]) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stem = self.out_dir / f"{datetime.now():%Y%m%d_%H%M%S_%f}"
        cv2.imwrite(str(stem.with_suffix(".png")), image)
        stem.with_suffix(".json").write_text(json.dumps({
            "confusions": [{"true": t, "read": r} for t, r in pairs],
            "issues": state.issues,
        }, indent=1))
        self.saved += 1

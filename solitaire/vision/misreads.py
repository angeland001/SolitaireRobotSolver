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


def mismatch_confusion(move, before: GameState, after: GameState) -> tuple[str, str] | None:
    """A move whose destination received a card that wasn't on the board before: the
    source card was misread in every frame (multi-frame agreement can't catch that).
    Returns (true, read), e.g. ('2d', '2h'). None if the mismatch has another cause."""
    if move.card is None:
        return None
    if move.dst == "tableau":
        old = {p.card for p in before.tableau[move.dst_index].faceup}
        new = [p.card for p in after.tableau[move.dst_index].faceup if p.card not in old]
    elif move.dst == "foundation":
        old = {p.card for p in before.foundations if p}
        new = [p.card for p in after.foundations if p and p.card not in old]
    else:
        return None
    if len(new) != 1 or new[0] == move.card.card or new[0] in set(before.visible_cards()):
        return None
    return str(new[0]), str(move.card.card)


class MisreadRecorder:
    """Keeps the recent frames (state + image); call settled(stable) whenever a stable
    board is accepted. Saves PNG + JSON per misread frame into out_dir. JSON `kind`:
    misread (one frame disagreed with the stable board), mismatch (the stable board
    itself was wrong, found when a move landed a different card), unreadable (no
    stable board could be read at all)."""

    def __init__(self, out_dir: Path, max_dist_px: float = 40, keep: int = 60):
        self.out_dir = out_dir
        self.max_dist_px = max_dist_px
        self.frames: deque[tuple[GameState, np.ndarray]] = deque(maxlen=keep)
        self.stable_images: deque[np.ndarray] = deque(maxlen=2)  # previous, latest stable board
        self._last_repaired: list[tuple[str, str]] = []   # save a repaired card once, not every board
        self.saved = 0

    def add(self, state: GameState, image: np.ndarray) -> None:
        self.frames.append((state, image))

    def save_unreadable(self) -> None:
        if self.frames:
            state, image = self.frames[-1]
            self._save(state, image, [], "unreadable")

    def save_mismatch(self, before: GameState, true: str, read: str) -> None:
        """Saves the image of the board before the move (the one that was misread)."""
        if len(self.stable_images) == 2:
            self._save(before, self.stable_images[0], [(true, read)], "mismatch")

    def save_mismatch_frames(self, before: GameState, after: GameState, note: str) -> None:
        """Every MISMATCH whose misread card can't be named (mismatch_confusion found no
        pair): saves the board before and after the move, so a person can see what was
        really there. Seen 2026-11-24: the top waste card (8d) went undetected and the
        card under it (Qd) was taken for the top, so every tap played the wrong card."""
        if len(self.stable_images) == 2:
            self._save(before, self.stable_images[0], [], "mismatch", note + " (board before the move)")
            self._save(after, self.stable_images[1], [], "mismatch", note + " (board after the move)")

    def settled(self, stable: GameState) -> list[tuple[str, str]]:
        frames = list(self.frames)
        self.frames.clear()
        for s, image in reversed(frames):
            if s.signature == stable.signature:
                self.stable_images.append(image)
                break
        # A card the builder had to repair was misread on the stable frames themselves.
        repaired = [(t, r) for _, r, t in stable.repairs]
        if repaired and self.stable_images and repaired != self._last_repaired:
            self._save(stable, self.stable_images[-1], repaired, "repaired")
        self._last_repaired = repaired
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
                self._save(s, image, pairs, "misread")
                found += pairs
        return found

    def _save(self, state: GameState, image: np.ndarray, pairs: list[tuple[str, str]], kind: str,
              note: str = "") -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stem = self.out_dir / f"{datetime.now():%Y%m%d_%H%M%S_%f}_{kind}"
        cv2.imwrite(str(stem.with_suffix(".png")), image)
        stem.with_suffix(".json").write_text(json.dumps({
            "kind": kind,
            "note": note,
            "confusions": [{"true": t, "read": r} for t, r in pairs],
            "issues": state.issues,
            "board": str(state),
        }, indent=1))
        self.saved += 1

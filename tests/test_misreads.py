"""Misread detection against the stable board."""
import json

import numpy as np
from boards import board

from solitaire.state import Card, PlacedCard
from solitaire.vision.detection import Detection
from solitaire.vision.misreads import MisreadRecorder, confusions


def at(label, cx, cy):
    return PlacedCard(Card.parse(label), Detection(label, 1.0, cx - 50, cy - 20, cx + 50, cy + 20))


def layout(labels, issues=None):
    """One face-up card per column at fixed places."""
    s = board(["# " + l for l in labels], issues=issues)
    for i, l in enumerate(labels):
        s.tableau[i].faceup = [at(l, 300 + 170 * i, 800)]
    return s


TRUE = layout(["7d", "9c", "Qh", "3s"])
SHIMMER = layout(["6s", "9c", "Qh", "3s"], issues=["column 1: ..."])   # 7d misread as 6s
OTHER_BOARD = layout(["7d", "8h", "Jc", "4d"])                          # most cards differ: a different board


def test_confusion_found_at_same_place():
    assert confusions(SHIMMER, TRUE, 40) == [("7d", "6s")]


def test_cards_in_motion_are_not_misreads():
    # 9s just moved onto 10h: a frame still showing 10h where 9s now sits is animation.
    after = layout(["9s", "9c", "Qh", "3s"])
    after.tableau[4].faceup = [at("10h", 980, 800)]
    frame = layout(["10h", "9c", "Qh", "3s"])
    assert confusions(frame, after, 40) == []


def test_mismatch_confusion_finds_a_consistent_misread():
    from solitaire.solver import legal_moves
    from solitaire.vision.misreads import mismatch_confusion
    before = board(["3c"], waste="2h")
    move = next(m for m in legal_moves(before) if m.src == "waste" and m.dst == "tableau")
    after = board(["3c 2d"], waste="6d")      # the waste card was really 2d
    assert mismatch_confusion(move, before, after) == ("2d", "2h")
    assert mismatch_confusion(move, before, board(["3c 2h"])) is None


def test_a_different_board_is_not_a_misread():
    assert confusions(OTHER_BOARD, TRUE, 40) == []


def test_recorder_saves_only_after_the_old_board(tmp_path):
    rec = MisreadRecorder(tmp_path)
    img = np.zeros((4, 4, 3), np.uint8)
    old = layout(["7d", "9c", "Qh", "4h"])   # valid, previous board: resets the window
    for s in (SHIMMER, old, SHIMMER, TRUE, TRUE):
        rec.add(s, img)
    assert rec.settled(TRUE) == [("7d", "6s")]   # only the SHIMMER after `old` counts
    saved = list(tmp_path.glob("*.json"))
    assert len(saved) == 1 and json.loads(saved[0].read_text())["confusions"] == [{"true": "7d", "read": "6s"}]

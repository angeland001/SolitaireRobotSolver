"""Solver v1 on hand-built boards. Run: python -m pytest tests"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import load_settings  # noqa: E402
from solitaire.solver import Solver, legal_moves  # noqa: E402
from solitaire.state import Card, Column, GameState, PlacedCard  # noqa: E402
from solitaire.vision.detection import FACEDOWN, Detection  # noqa: E402

SETTINGS = load_settings()


def det(label: str) -> Detection:
    return Detection(label, 1.0, 0, 0, 0, 0)


def placed(label: str) -> PlacedCard:
    return PlacedCard(Card.parse(label), det(label))


def board(tableau: list[str], foundations: str = "", waste: str = "", stock: bool = True) -> GameState:
    """tableau: one string per column, '#' per face-down card then face-up labels,
    e.g. '## 9s 8h'. foundations: top cards, e.g. 'Ah 2s'."""
    cols = []
    for spec in tableau + [""] * (7 - len(tableau)):
        words = spec.split()
        down = [w for w in words if set(w) == {"#"}]
        n_down = sum(len(w) for w in down)
        cols.append(Column([det(FACEDOWN)] * n_down, [placed(w) for w in words if w not in down]))
    f = [placed(w) for w in foundations.split()]
    return GameState(
        foundations=f + [None] * (4 - len(f)),
        waste=[placed(w) for w in waste.split()],
        stock=det(FACEDOWN) if stock else None,
        tableau=cols,
    )


def best(state: GameState, solver: Solver | None = None):
    return (solver or Solver(SETTINGS)).choose_move(state)


def test_ace_from_waste_goes_up_by_tap():
    m = best(board(["## 9s"], waste="4c Ah"))
    assert (m.src, m.dst, str(m.card), m.method) == ("waste", "foundation", "Ah", "tap")


def test_reveal_beats_waste_to_tableau():
    # 8h can go on 9s from the waste, but moving 7c onto 8d turns over a card.
    m = best(board(["### 7c", "8d", "9s"], waste="8h"))
    assert (m.src, m.src_index, m.dst_index) == ("tableau", 0, 1)


def test_tap_goes_left_most_so_other_column_needs_drag():
    s = board(["Ks", "9c", "Kc", "## 8h"])
    targets = {m.dst_index: m.method for m in legal_moves(s) if str(m.card) == "8h"}
    assert targets == {1: "tap"}  # only 9c takes 8h
    s = board(["9c", "Ks", "9s", "## 8h"])
    targets = {m.dst_index: m.method for m in legal_moves(s) if str(m.card) == "8h"}
    assert targets == {0: "tap", 2: "drag"}


def test_tableau_move_is_drag_when_foundation_is_legal():
    s = board(["## 2h", "3s"], foundations="Ah")
    to_col = [m for m in legal_moves(s) if str(m.card) == "2h" and m.dst == "tableau"]
    assert to_col and to_col[0].method == "drag"
    assert best(s).dst == "foundation"


def test_draw_when_nothing_useful():
    m = best(board(["## 9s", "## 4d"], waste="2c"))
    assert m.is_stock and not m.is_recycle


def test_lone_king_is_not_shuffled_between_empty_columns():
    assert best(board(["Ks Qh", "", "## 5c"])).is_stock


def test_empty_a_column_only_for_a_waiting_king():
    full = ["# 9c", "# 9s", "# 9d", "# 9h"]  # no spare empty column, nothing playable
    s = board(["Qh", "Kc", "## Ks", *full])  # Ks sits on face-down cards
    m = best(s)
    assert (str(m.card), m.dst_index) == ("Qh", 1)
    assert best(board(["Qh", "Kc", "## 3d", *full])).is_stock


def test_split_run_only_to_free_a_foundation_card():
    # 5d under 4s: moving 4s onto 5h exposes 5d, and 4d is already up.
    s = board(["Kc 5d 4s", "## 5h"], foundations="4d")
    m = best(s)
    assert (str(m.card), m.dst_index) == ("4s", 1)
    s2 = board(["Kc 5d 4s", "## 5h"])
    assert best(s2).is_stock


def test_recycle_only_after_progress():
    s = board(["## 9s"], waste="2c 3d 4h", stock=False)
    solver = Solver(SETTINGS)
    m = best(s, solver)
    assert m.is_recycle  # fresh solver: can't know the last pass, so it allows one recycle
    solver.executed(m)
    assert best(s, solver) is None  # a whole pass with no play: the next pass is identical

    solver.executed(best(board(["### 7c", "8d"]), solver))  # something was played this pass
    assert best(s, solver).is_recycle


def test_recycle_limit():
    s = board(["## 9s"], waste="2c 3d 4h", stock=False)
    solver = Solver({"solver": {**SETTINGS["solver"], "max_recycles": 1}})
    solver.recycles_used, solver.played_since_recycle = 1, True
    assert best(s, solver) is None


def test_invalid_state_is_refused():
    s = board(["## 9s"])
    s.issues.append("card seen twice")
    with pytest.raises(ValueError):
        best(s)

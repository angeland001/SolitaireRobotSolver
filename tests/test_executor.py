"""Executor planning + dispatch, with a scale-only calibration and a fake plotter."""
import numpy as np
import pytest
from boards import board

from solitaire.calibration import Calibration
from solitaire.config import load_settings
from solitaire.executor import Executor
from solitaire.solver import legal_moves
from solitaire.solver.moves import DRAW, RECYCLE
from solitaire.state import Card, PlacedCard
from solitaire.vision.detection import Detection

SETTINGS = load_settings()
W, H = SETTINGS["screen"]["width_px"], SETTINGS["screen"]["height_px"]
LAY = SETTINGS["layout"]
CAL = Calibration(np.diag([0.1, 0.1, 1.0]), 0.0, 0, "test")   # 10 px = 1 mm


def at(label: str, cx: float, cy: float) -> PlacedCard:
    return PlacedCard(Card.parse(label), Detection(label, 1.0, cx - 50, cy - 20, cx + 50, cy + 20))


class FakePlotter:
    def __init__(self):
        self.calls = []

    def tap(self, x, y):
        self.calls.append(("tap", round(x, 3), round(y, 3)))

    def drag(self, x0, y0, x1, y1):
        self.calls.append(("drag", round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)))


def test_tap_move_taps_the_card_strip():
    s = board(["## 9s", "## 8h"])
    s.tableau[0].faceup = [at("9s", 300, 800)]
    s.tableau[1].faceup = [at("8h", 480, 820)]
    move = next(m for m in legal_moves(s) if str(m.card) == "8h")
    plotter = FakePlotter()
    action = Executor(CAL, plotter, SETTINGS).execute(move, s)
    assert action.kind == "tap" and action.points_px == ((480.0, 820.0),)
    assert plotter.calls == [("tap", 48.0, 82.0)]


def test_drag_to_exposed_card_and_to_empty_column():
    s = board(["Kc", "9c", "Ks", "9s", "## 8h"])
    s.tableau[3].faceup = [at("9s", 640, 700)]
    s.tableau[4].faceup = [at("8h", 820, 760)]
    to_9s = next(m for m in legal_moves(s) if str(m.card) == "8h" and m.dst_index == 3)
    assert to_9s.method == "drag"   # tap would go to 9c in column 2
    a = Executor(CAL, None, SETTINGS).plan(to_9s, s)
    assert a.kind == "drag" and a.points_px == ((820.0, 760.0), (640.0, 700.0))

    s2 = board(["Qh", "", "## Kd"])
    s2.tableau[2].faceup = [at("Kd", 640, 750)]
    king = next(m for m in legal_moves(s2) if str(m.card) == "Kd" and m.dst_index == 3)
    assert king.method == "drag"    # tap would pick the left-most empty column (2)
    a = Executor(CAL, None, SETTINGS).plan(king, s2)
    expected = (LAY["column_x"][3] * W, (LAY["tableau_top_y"] + LAY["card_height"] / 2) * H)
    assert a.points_px[1] == pytest.approx(expected)


def test_stock_taps():
    ex = Executor(CAL, None, SETTINGS)
    s = board(["## 9s"])
    assert ex.plan(DRAW, s).points_px == (s.stock.center_px,)
    empty = board(["## 9s"], waste="2c", stock=False)
    assert ex.plan(RECYCLE, empty).points_px[0] == pytest.approx((LAY["stock_x"] * W, LAY["stock_y"] * H))


def test_finish_button_and_mm_conversion():
    a = Executor(CAL, None, SETTINGS).plan_button("finish")
    x, y = LAY["finish_button"]
    assert a.points_mm[0] == pytest.approx((x * W / 10, y * H / 10))


def test_off_screen_point_is_refused():
    s = board(["## 9s"])
    s.waste = [at("8h", -500, 400)]   # a bad box must never become a tap off the glass
    move = next(m for m in legal_moves(s) if m.src == "waste")
    with pytest.raises(ValueError):
        Executor(CAL, None, SETTINGS).plan(move, s)

"""Move -> where to touch the screen -> plotter tap or drag.

plan() is pure: it turns a solver Move (plus the board it was chosen on) into an
Action holding screen points in normalised pixels and the same points in plotter mm.
perform() sends an Action to the plotter. Keeping them apart lets the game loop's
--dry-run show exactly what would be touched without a plotter connected.

Touch points:
- a card: the centre of its detection box. For a covered card that box is its visible
  strip, so the tap can't land on the card below.
- a tableau destination: the centre of the exposed card's box, or, for an empty
  column, a card's height below the column top (layout.tableau_top_y).
- the stock: its box centre, or layout stock_x/stock_y when it shows the recycle icon.
- a foundation: layout foundation_x[slot], foundation_y.
- Finish / Undo: layout finish_button / undo_button.
"""
from dataclasses import dataclass

from solitaire.calibration import Calibration
from solitaire.config import load_settings
from solitaire.solver.moves import FOUNDATION, TABLEAU, Move
from solitaire.state import GameState


@dataclass(frozen=True)
class Action:
    kind: str                                    # tap | drag
    points_px: tuple[tuple[float, float], ...]   # tap: (at,); drag: (from, to)
    points_mm: tuple[tuple[float, float], ...]
    label: str

    def __str__(self) -> str:
        px = " -> ".join(f"({x:.0f}, {y:.0f})px" for x, y in self.points_px)
        mm = " -> ".join(f"({x:.1f}, {y:.1f})mm" for x, y in self.points_mm)
        return f"{self.label}: {self.kind} {px} = {mm}"


class Executor:
    """plotter: a solitaire.plotter.Grbl, or None for planning only (dry run)."""

    def __init__(self, calibration: Calibration, plotter=None, settings: dict | None = None):
        settings = settings or load_settings()
        self.cal = calibration
        self.plotter = plotter
        self.layout = settings["layout"]
        self.width_px = settings["screen"]["width_px"]
        self.height_px = settings["screen"]["height_px"]

    # ---- planning (no plotter) ----------------------------------------------
    def _frac(self, x: float, y: float) -> tuple[float, float]:
        return x * self.width_px, y * self.height_px

    def _action(self, kind: str, points_px: list[tuple[float, float]], label: str) -> Action:
        for x, y in points_px:
            if not (0 <= x <= self.width_px and 0 <= y <= self.height_px):
                raise ValueError(f"{label}: ({x:.0f}, {y:.0f})px is off the screen")
        pts_px = tuple((float(x), float(y)) for x, y in points_px)
        pts_mm = tuple(self.cal.px_to_mm(x, y) for x, y in pts_px)
        return Action(kind, pts_px, pts_mm, label)

    def stock_point(self, state: GameState) -> tuple[float, float]:
        if state.stock is not None:
            return state.stock.center_px
        return self._frac(self.layout["stock_x"], self.layout["stock_y"])

    def destination_point(self, state: GameState, move: Move) -> tuple[float, float]:
        lay = self.layout
        if move.dst == FOUNDATION:
            return self._frac(lay["foundation_x"][move.dst_index], lay["foundation_y"])
        if move.dst == TABLEAU:
            col = state.tableau[move.dst_index]
            if col.exposed is not None:
                return col.exposed.det.center_px
            return self._frac(lay["column_x"][move.dst_index], lay["tableau_top_y"] + lay["card_height"] / 2)
        raise ValueError(f"no destination point for {move}")

    def plan(self, move: Move, state: GameState) -> Action:
        """Where to touch for this move, on the board it was chosen on."""
        if move.is_stock:
            return self._action("tap", [self.stock_point(state)], str(move))
        src = move.card.det.center_px
        if move.method == "tap":
            return self._action("tap", [src], str(move))
        return self._action("drag", [src, self.destination_point(state, move)], str(move))

    def plan_button(self, name: str) -> Action:
        """name: 'finish' or 'undo'."""
        x, y = self.layout[f"{name}_button"]
        return self._action("tap", [self._frac(x, y)], f"press {name.capitalize()}")

    # ---- doing --------------------------------------------------------------
    def perform(self, action: Action) -> None:
        if self.plotter is None:
            raise RuntimeError("no plotter connected (dry run)")
        if action.kind == "tap":
            self.plotter.tap(*action.points_mm[0])
        elif action.kind == "drag":
            (x0, y0), (x1, y1) = action.points_mm
            self.plotter.drag(x0, y0, x1, y1)
        else:
            raise ValueError(f"unknown action kind {action.kind!r}")

    def execute(self, move: Move, state: GameState) -> Action:
        action = self.plan(move, state)
        self.perform(action)
        return action

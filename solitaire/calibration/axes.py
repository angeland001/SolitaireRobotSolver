"""Which way each plotter axis moves the pencil across the iPad screen.

Found once by plotter_console.py's `direction` test and saved to
config/plotter_axes.json, e.g. {"+x": "down", "+y": "right"}. Directions are as
seen looking at the iPad in portrait, camera edge at the top. This lets jog
commands be given in screen terms ("left 5") and catches CoreXY problems:
if one axis moves diagonally or both move along the same line, the firmware
isn't set up for CoreXY.
"""
import json
from pathlib import Path

from solitaire.config import REPO_ROOT

AXES_PATH = REPO_ROOT / "config" / "plotter_axes.json"
DIRECTIONS = ("up", "down", "left", "right")
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
HORIZONTAL = {"left", "right"}


def validate(plus_x: str, plus_y: str) -> str | None:
    """Problem description, or None if the two axes are perpendicular."""
    for name, d in (("+X", plus_x), ("+Y", plus_y)):
        if d not in DIRECTIONS:
            return (f"{name} moved '{d}'. A diagonal or two-motor-fighting move means GRBL "
                    "is not compiled for CoreXY (README §1.1).")
    if (plus_x in HORIZONTAL) == (plus_y in HORIZONTAL):
        return f"+X and +Y both move along the same line ({plus_x}/{plus_y}); check CoreXY / wiring."
    return None


class Axes:
    def __init__(self, plus_x: str, plus_y: str):
        problem = validate(plus_x, plus_y)
        if problem:
            raise ValueError(problem)
        self.plus_x, self.plus_y = plus_x, plus_y

    @classmethod
    def load(cls, path: Path = AXES_PATH) -> "Axes":
        if not path.exists():
            raise FileNotFoundError(f"{path} missing - run `direction` in tools/plotter_console.py")
        data = json.loads(path.read_text())
        return cls(data["+x"], data["+y"])

    def save(self, path: Path = AXES_PATH):
        path.write_text(json.dumps({"+x": self.plus_x, "+y": self.plus_y}, indent=2) + "\n")

    def screen_delta(self, direction: str, mm: float) -> tuple[float, float]:
        """Plotter (dx, dy) that moves the pencil `mm` in a screen direction."""
        if direction == self.plus_x:
            return mm, 0.0
        if direction == OPPOSITE[self.plus_x]:
            return -mm, 0.0
        if direction == self.plus_y:
            return 0.0, mm
        if direction == OPPOSITE[self.plus_y]:
            return 0.0, -mm
        raise ValueError(direction)

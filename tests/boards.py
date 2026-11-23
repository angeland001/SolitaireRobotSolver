"""Hand-built GameStates for tests (no screenshots, no detector)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.state import Card, Column, GameState, PlacedCard  # noqa: E402
from solitaire.vision.detection import FACEDOWN, Detection  # noqa: E402


def det(label: str, x: float = 0) -> Detection:
    return Detection(label, 1.0, x, 0, x, 0)


def placed(label: str) -> PlacedCard:
    return PlacedCard(Card.parse(label), det(label))


def board(tableau: list[str], foundations: str = "", waste: str = "", stock: bool = True,
          issues: list[str] | None = None) -> GameState:
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
        issues=list(issues or []),
    )

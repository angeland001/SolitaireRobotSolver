"""Detections -> GameState, using the fixed screen layout in config/settings.yaml.

Anything that doesn't fit the layout or the rules is recorded in state.issues
instead of raising: a frame caught mid-animation is normal, and the caller
decides whether to re-read.
"""
from collections import Counter

from solitaire.config import load_settings
from solitaire.state.cards import Card
from solitaire.state.game_state import Column, GameState, PlacedCard
from solitaire.vision.detection import Detection


class StateBuilder:
    def __init__(self, layout: dict | None = None):
        self.layout = layout or load_settings()["layout"]

    def build(self, dets: list[Detection], width_px: int, height_px: int) -> GameState:
        lay = self.layout
        issues: list[str] = []
        foundations: list[PlacedCard | None] = [None] * len(lay["foundation_x"])
        waste: list[PlacedCard] = []
        stock: Detection | None = None
        tableau = [Column() for _ in lay["column_x"]]

        for d in sorted(dets, key=lambda d: d.y1_px):
            x = d.center_px[0] / width_px
            if d.y1_px / height_px > lay["bottom_y"]:
                continue
            card = None if d.is_facedown else Card.parse(d.label)

            if d.y1_px / height_px < lay["top_row_max_y"]:
                wx0, wx1 = lay["waste_x_range"]
                if wx0 <= x <= wx1:
                    if card is None:
                        issues.append("face-down card in the waste fan")
                    else:
                        waste.append(PlacedCard(card, d))
                elif abs(x - lay["stock_x"]) <= lay["column_tolerance"]:
                    if card is not None:
                        issues.append(f"face-up {card} on the stock")
                    stock = d
                else:
                    slot = self._nearest(x, lay["foundation_x"])
                    if slot is None:
                        issues.append(f"{d.label} in the top row outside any slot (x={x:.3f})")
                    elif card is None:
                        issues.append(f"face-down card on foundation {slot + 1}")
                    elif foundations[slot] is not None:
                        issues.append(f"two cards on foundation {slot + 1}")
                    else:
                        foundations[slot] = PlacedCard(card, d)
                continue

            i = self._nearest(x, lay["column_x"])
            if i is None:
                issues.append(f"{d.label} between columns (x={x:.3f}) - moving?")
                continue
            col = tableau[i]
            if card is None:
                if col.faceup:
                    issues.append(f"column {i + 1}: face-down card below a face-up card")
                col.facedown.append(d)
            else:
                col.faceup.append(PlacedCard(card, d))

        waste.sort(key=lambda p: p.det.x1_px)
        state = GameState(foundations, waste, stock, tableau, issues)
        self._check_rules(state)
        return state

    def _nearest(self, x: float, centres: list[float]) -> int | None:
        i = min(range(len(centres)), key=lambda i: abs(x - centres[i]))
        return i if abs(x - centres[i]) <= self.layout["column_tolerance"] else None

    @staticmethod
    def _check_rules(state: GameState) -> None:
        issues = state.issues

        seen = Counter(state.visible_cards())
        issues += [f"{c} seen {n} times" for c, n in seen.items() if n > 1]

        suits = [p.card.suit for p in state.foundations if p]
        if len(suits) != len(set(suits)):
            issues.append("two foundations with the same suit")
        buried = state.foundation_cards() - {p.card for p in state.foundations if p}
        issues += [f"{c} is visible but should be inside a foundation"
                   for c in seen if c in buried]

        if len(state.waste) > 3:
            issues.append(f"{len(state.waste)} cards in the waste fan (max 3)")

        for i, col in enumerate(state.tableau, 1):
            for upper, lower in zip(col.faceup, col.faceup[1:]):
                if not lower.card.can_stack_on(upper.card):
                    issues.append(f"column {i}: {lower} cannot sit on {upper}")
            if col.facedown and not col.faceup:
                issues.append(f"column {i}: ends face-down - waiting for flip?")

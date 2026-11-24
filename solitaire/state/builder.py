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
    def __init__(self, layout: dict | None = None, repair: dict | None = None):
        settings = None if layout and repair else load_settings()
        self.layout = layout or settings["layout"]
        self.repair = repair or settings["repair"]

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
        self._repair_runs(state)
        self._repair_duplicates(state, self.repair["duplicate_conf_margin"])
        self._check_rules(state)
        return state

    @staticmethod
    def _repair_duplicates(state: GameState, conf_margin: float) -> None:
        """A card read twice: the less confident copy becomes its same-colour sibling
        (d<->h, c<->s) if that card is nowhere on the board, and only if it is clearly
        less confident (by conf_margin); with no clear loser nothing is changed.

        The detector's live mistakes keep rank and colour and swap the suit, mostly on
        shimmering cards (2026-11-23: a shimmering Kd read as Kh at 0.69 while the real
        Kh sat on the waste at 0.95). Every slot that holds a card is a (list, index)
        so it can be replaced."""
        slots = [(state.foundations, i) for i, p in enumerate(state.foundations) if p]
        slots += [(state.waste, i) for i in range(len(state.waste))]
        slots += [(col.faceup, i) for col in state.tableau for i in range(len(col.faceup))]
        sibling = {"d": "h", "h": "d", "c": "s", "s": "c"}
        by_card: dict[Card, list[tuple[list, int]]] = {}
        for lst, i in slots:
            by_card.setdefault(lst[i].card, []).append((lst, i))
        for card, where in by_card.items():
            if len(where) != 2:
                continue
            twin = Card(card.rank, sibling[card.suit])
            if twin in set(state.visible_cards()) | state.foundation_cards():
                continue
            (lst, i), (hi_lst, hi_i) = sorted(where, key=lambda s: s[0][s[1]].det.conf)
            if hi_lst[hi_i].det.conf - lst[i].det.conf < conf_margin:
                continue
            lst[i] = PlacedCard(twin, lst[i].det)
            place = next((f"column {n}" for n, col in enumerate(state.tableau, 1) if col.faceup is lst),
                         "waste" if lst is state.waste else "foundation")
            state.repairs.append((place, str(card), str(twin)))

    @staticmethod
    def _repair_runs(state: GameState) -> None:
        """Fix a covered tableau card the rules pin down exactly.

        Face-up tableau cards always form a valid run in a real game, so a card between
        two cards that fit each other (above one rank higher than it, below one lower,
        alternating colour) must be one of two cards of a known rank and colour. If it
        doesn't fit and exactly one of those two is nowhere else on the board, that is
        the card (2026-11-23: a plain 8d read as 9d in 10d 9s _ 7c, every frame).
        The detection box is kept; the label is replaced and noted in state.repairs."""
        for ci, col in enumerate(state.tableau, 1):
            for i in range(1, len(col.faceup) - 1):
                above, here, below = col.faceup[i - 1].card, col.faceup[i].card, col.faceup[i + 1].card
                if here.can_stack_on(above) and below.can_stack_on(here):
                    continue
                if not (below.rank == above.rank - 2 and below.is_red == above.is_red):
                    continue   # neighbours don't pin it down (or are misread themselves)
                rank = above.rank - 1
                suits = "cs" if above.is_red else "dh"
                elsewhere = set(state.visible_cards()) - {here} | state.foundation_cards()
                fits = [Card(rank, s) for s in suits if Card(rank, s) not in elsewhere]
                if len(fits) == 1:
                    col.faceup[i] = PlacedCard(fits[0], col.faceup[i].det)
                    state.repairs.append((f"column {ci}", str(here), str(fits[0])))

    def _nearest(self, x: float, centres: list[float]) -> int | None:
        i = min(range(len(centres)), key=lambda i: abs(x - centres[i]))
        return i if abs(x - centres[i]) <= self.layout["column_tolerance"] else None

    @staticmethod
    def _check_rules(state: GameState) -> None:
        issues = state.issues

        if not state.visible_cards() and state.stock is None and not any(c.facedown for c in state.tableau):
            # A black or frozen mirror, or a menu, parses as an empty board with no rule
            # broken; the solver would then see no moves and press Finish.
            issues.append("no cards on screen (mirror dropped, or not a game board)")

        facedown = sum(len(c.facedown) for c in state.tableau)
        if state.stock is None and not state.waste and len(state.unseen_cards()) > facedown:
            # Stock shows the recycle icon and the waste reads empty, so every unseen card
            # must be face-down in the tableau. More unseen than that = a card on screen
            # wasn't recognised, usually the waste top (2026-11-23: a shimmering Qd at 0.13;
            # the solver saw no stock, no waste, no move, and pressed Finish).
            issues.append(f"{len(state.unseen_cards()) - facedown} cards unaccounted for with stock and "
                          "waste empty: a card (waste top?) was not recognised")

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

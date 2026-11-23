"""Legal-move generation for the visible board, plus where a tap would send a card.

A Move names piles by index (screen order, left to right), never by position, so
the executor turns it into pixels with the PlacedCard's Detection or the layout.
"""
from dataclasses import dataclass

from solitaire.state import Card, Column, GameState, PlacedCard

STOCK, WASTE, TABLEAU, FOUNDATION = "stock", "waste", "tableau", "foundation"


@dataclass(frozen=True)
class Move:
    src: str                      # stock | waste | tableau
    dst: str                      # foundation | tableau | waste (draw) | stock (recycle)
    card: PlacedCard | None = None  # card to tap/drag (top-most card of a run); None for stock taps
    src_index: int | None = None  # tableau column of the source
    src_depth: int | None = None  # index into that column's faceup list (0 = whole face-up run)
    dst_index: int | None = None  # foundation slot or tableau column
    method: str = "tap"           # tap | drag (drag = the app's tap rule would pick another destination)

    @property
    def is_stock(self) -> bool:
        """A tap on the stock pile: draw 3, or recycle the waste when the stock is empty."""
        return self.card is None

    @property
    def is_recycle(self) -> bool:
        return self.is_stock and self.dst == STOCK

    def __str__(self) -> str:
        if self.is_stock:
            return "recycle waste into stock" if self.is_recycle else "draw from stock"
        src = f"col {self.src_index + 1}" if self.src == TABLEAU else self.src
        dst = f"col {self.dst_index + 1}" if self.dst == TABLEAU else f"foundation {self.dst_index + 1}"
        return f"{self.method} {self.card} ({src} -> {dst})"


DRAW = Move(src=STOCK, dst=WASTE)
RECYCLE = Move(src=WASTE, dst=STOCK)


def foundation_slot(state: GameState, card: Card) -> int | None:
    """Slot the card can go to now: on its suit's rank-1 card, or (Ace) the left-most empty slot."""
    for i, top in enumerate(state.foundations):
        if card.rank == 1 and top is None:
            return i
        if top and top.card.suit == card.suit and top.card.rank == card.rank - 1:
            return i
    return None


def can_place(col: Column, card: Card) -> bool:
    """Tableau rule: on an exposed card one higher and opposite colour, or a King on an empty column."""
    if col.is_empty:
        return card.rank == 13
    top = col.exposed
    return top is not None and card.can_stack_on(top.card)


def is_run(cards: list[PlacedCard]) -> bool:
    return all(b.card.can_stack_on(a.card) for a, b in zip(cards, cards[1:]))


def tap_destination(state: GameState, src: str, src_index: int | None, card: Card,
                    exposed: bool) -> tuple[str, int] | None:
    """Where the app sends a tapped card (README §3.3): a legal foundation first (only the
    exposed card can go there), otherwise the left-most legal tableau column."""
    if exposed:
        slot = foundation_slot(state, card)
        if slot is not None:
            return FOUNDATION, slot
    for i, col in enumerate(state.tableau):
        if src == TABLEAU and i == src_index:
            continue
        if can_place(col, card):
            return TABLEAU, i
    return None


def _with_method(state: GameState, move: Move, exposed: bool) -> Move:
    dest = tap_destination(state, move.src, move.src_index, move.card.card, exposed)
    method = "tap" if dest == (move.dst, move.dst_index) else "drag"
    return Move(move.src, move.dst, move.card, move.src_index, move.src_depth, move.dst_index, method)


def legal_moves(state: GameState) -> list[Move]:
    """Every legal move on the visible board, each marked tap or drag. Foundation -> tableau
    moves are left out (v1 never needs them, and they invite loops)."""
    moves: list[Move] = []

    top = state.waste_top
    if top:
        slot = foundation_slot(state, top.card)
        if slot is not None:
            moves.append(_with_method(state, Move(WASTE, FOUNDATION, top, dst_index=slot), True))
        for i, col in enumerate(state.tableau):
            if can_place(col, top.card):
                moves.append(_with_method(state, Move(WASTE, TABLEAU, top, dst_index=i), True))

    for ci, col in enumerate(state.tableau):
        if not col.faceup:
            continue
        exposed = col.faceup[-1]
        slot = foundation_slot(state, exposed.card)
        if slot is not None:
            m = Move(TABLEAU, FOUNDATION, exposed, ci, len(col.faceup) - 1, slot)
            moves.append(_with_method(state, m, True))
        for depth, placed in enumerate(col.faceup):
            if not is_run(col.faceup[depth:]):
                continue
            is_exposed = depth == len(col.faceup) - 1
            for di, dcol in enumerate(state.tableau):
                if di != ci and can_place(dcol, placed.card):
                    m = Move(TABLEAU, TABLEAU, placed, ci, depth, di)
                    moves.append(_with_method(state, m, is_exposed))

    if state.stock is not None:
        moves.append(DRAW)
    elif state.waste:
        moves.append(RECYCLE)
    return moves

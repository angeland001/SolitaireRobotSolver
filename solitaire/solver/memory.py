"""Draw-3 stock memory (README §3.4): the order of the cards in the stock and waste.

The stock and waste together (the *talon*) are one fixed sequence. Drawing moves a
pointer forward by `draw_count` cards, recycling moves it back to 0, and playing the
waste top removes one card. Nothing else changes the order. So every waste card the
camera sees can be written to its place in the sequence, and after a pass the planner
knows which card each future draw will show.

`talon[:ptr]` is the waste (talon[ptr-1] is its top) and `talon[ptr:]` is the stock.
Unknown cards are None. `ptr` is None while the pointer can't be placed (e.g. the
solver joined mid-pass). It is placed again as soon as the waste is empty, the stock
is empty, or the waste top is a card it already knows.
"""
from solitaire.solver.moves import WASTE, Move
from solitaire.state import Card, GameState


def talon_size(state: GameState) -> int:
    """Cards in the stock + waste: everything not on a foundation or in the tableau."""
    on_board = len(state.foundation_cards()) + sum(len(c.facedown) + len(c.faceup) for c in state.tableau)
    return max(0, 52 - on_board)


class StockMemory:
    def __init__(self, draw_count: int = 3):
        self.draw_count = draw_count
        self.talon: list[Card | None] = []
        self.ptr: int | None = None

    @property
    def ready(self) -> bool:
        return self.ptr is not None

    @property
    def known(self) -> int:
        return sum(c is not None for c in self.talon)

    def observe(self, state: GameState) -> None:
        """Bring the memory in line with a (valid) board read."""
        n = talon_size(state)
        if len(self.talon) != n:
            if self.ptr and len(self.talon) == n + 1:
                # The waste top left without executed(): a tap that landed somewhere unexpected.
                del self.talon[self.ptr - 1]
                self.ptr -= 1
            else:
                self.talon, self.ptr = [None] * n, None
        if self.ptr is not None and not self._consistent(state, n):
            self.ptr = None
        if self.ptr is None:
            self.ptr = self._locate(state, n)
        if self.ptr is None:
            return
        for j, placed in enumerate(reversed(state.waste)):   # the top first
            i = self.ptr - 1 - j
            if i < 0:
                break
            self._write(i, placed.card)

    def executed(self, move: Move) -> None:
        """A move was verified on screen."""
        if self.ptr is None:
            return
        if move.is_recycle:
            self.ptr = 0
        elif move.is_stock:
            self.ptr = min(self.ptr + self.draw_count, len(self.talon))
        elif move.src == WASTE and self.ptr > 0:
            del self.talon[self.ptr - 1]
            self.ptr -= 1

    def _consistent(self, state: GameState, n: int) -> bool:
        if (state.stock is None) != (self.ptr == n) or (not state.waste) != (self.ptr == 0):
            return False
        if len(state.waste) > self.ptr:
            return False
        if state.waste:
            top = state.waste_top.card
            if self.talon[self.ptr - 1] not in (None, top):
                return False
            if any(c == top for i, c in enumerate(self.talon) if i != self.ptr - 1):
                return False
        return True

    def _locate(self, state: GameState, n: int) -> int | None:
        if not state.waste:
            return 0
        if state.stock is None:
            return n
        top = state.waste_top.card
        hits = [i for i, c in enumerate(self.talon) if c == top]
        return hits[0] + 1 if len(hits) == 1 else None

    def _write(self, i: int, card: Card) -> None:
        if self.talon[i] == card:
            return
        for k, c in enumerate(self.talon):
            if c == card:
                self.talon[k] = None
        self.talon[i] = card

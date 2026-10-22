"""What is on the screen right now, as Klondike piles.

Every placed card keeps the Detection it came from, so the executor can tap
its visible strip later.
"""
from dataclasses import dataclass, field

from solitaire.state.cards import FULL_DECK, Card
from solitaire.vision.detection import Detection


@dataclass(frozen=True)
class PlacedCard:
    card: Card
    det: Detection

    def __str__(self) -> str:
        return str(self.card)


@dataclass
class Column:
    facedown: list[Detection] = field(default_factory=list)   # top to bottom on screen
    faceup: list[PlacedCard] = field(default_factory=list)    # top to bottom; last is exposed

    @property
    def exposed(self) -> PlacedCard | None:
        return self.faceup[-1] if self.faceup else None

    @property
    def is_empty(self) -> bool:
        return not self.facedown and not self.faceup


@dataclass
class GameState:
    foundations: list[PlacedCard | None]     # top card of each of the 4 slots, left to right
    waste: list[PlacedCard]                  # visible fan, left to right; last is playable
    stock: Detection | None                  # face-down stock card; None = empty (recycle icon)
    tableau: list[Column]                    # 7 columns, left to right
    issues: list[str] = field(default_factory=list)  # validation problems; empty = trustworthy

    @property
    def is_valid(self) -> bool:
        return not self.issues

    @property
    def waste_top(self) -> PlacedCard | None:
        return self.waste[-1] if self.waste else None

    def foundation_cards(self) -> set[Card]:
        """Every card already on a foundation (a top of 5h implies Ah..5h)."""
        return {Card(r, p.card.suit) for p in self.foundations if p for r in range(1, p.card.rank + 1)}

    def visible_cards(self) -> list[Card]:
        cards = [p.card for p in self.foundations if p]
        cards += [p.card for p in self.waste]
        cards += [p.card for col in self.tableau for p in col.faceup]
        return cards

    def unseen_cards(self) -> set[Card]:
        """Cards that must be face-down in the tableau, in the stock, or under the waste fan."""
        seen = self.foundation_cards() | {p.card for p in self.waste} | {
            p.card for col in self.tableau for p in col.faceup}
        return set(FULL_DECK) - seen

    @property
    def is_won(self) -> bool:
        return all(p and p.card.rank == 13 for p in self.foundations)

    def __str__(self) -> str:
        f = " ".join(f"{str(p):>3}" if p else " --" for p in self.foundations)
        w = " ".join(str(p) for p in self.waste) or "--"
        s = "##" if self.stock else "()"
        lines = [f"F: {f}   W: {w}   S: {s}"]
        for i, col in enumerate(self.tableau, 1):
            down = f"[{len(col.facedown)}] " if col.facedown else ""
            lines.append(f"{i}: {down}{' '.join(map(str, col.faceup))}")
        lines += [f"! {issue}" for issue in self.issues]
        return "\n".join(lines)

"""Card identity. Labels follow the dataset: '<rank><suit>' e.g. '10h', 'Qs', 'Ac'."""
from dataclasses import dataclass

RANKS = {"A": 1, "J": 11, "Q": 12, "K": 13, **{str(n): n for n in range(2, 11)}}
RANK_NAMES = {v: k for k, v in RANKS.items()}
SUITS = "cdhs"
RED_SUITS = "dh"


@dataclass(frozen=True, order=True)
class Card:
    rank: int   # 1 (Ace) .. 13 (King)
    suit: str   # 'c' | 'd' | 'h' | 's'

    @classmethod
    def parse(cls, label: str) -> "Card":
        rank, suit = label[:-1], label[-1]
        if rank not in RANKS or suit not in SUITS:
            raise ValueError(f"not a card label: {label!r}")
        return cls(RANKS[rank], suit)

    @property
    def is_red(self) -> bool:
        return self.suit in RED_SUITS

    def can_stack_on(self, other: "Card") -> bool:
        """Tableau rule: one lower and opposite colour."""
        return self.rank == other.rank - 1 and self.is_red != other.is_red

    def __str__(self) -> str:
        return f"{RANK_NAMES[self.rank]}{self.suit}"


FULL_DECK = frozenset(Card(r, s) for r in range(1, 14) for s in SUITS)

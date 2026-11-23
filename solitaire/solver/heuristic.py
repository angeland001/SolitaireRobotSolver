"""Solver v1: score every legal move with simple Klondike heuristics (README §3.4).

Scoring favours what the app pays for (foundation cards) and what opens the game up
(turning over face-down cards). Moves that change nothing useful get no score at all,
which is also what keeps the solver from shuffling cards back and forth. Taps on the
stock are the fallback when nothing scores.

Weights and the recycle limit live in config/settings.yaml under `solver:`.
"""
from solitaire.config import load_settings
from solitaire.state import Card, GameState
from solitaire.solver.moves import FOUNDATION, TABLEAU, WASTE, Move, foundation_slot, legal_moves


def foundation_ranks(state: GameState) -> dict[str, int]:
    ranks = {s: 0 for s in "cdhs"}
    for top in state.foundations:
        if top:
            ranks[top.card.suit] = top.card.rank
    return ranks


def is_safe_foundation(state: GameState, card: Card) -> bool:
    """Safe = no tableau card could ever need this one to stack on: Aces and 2s always,
    otherwise both opposite-colour suits are up to rank-1 already."""
    if card.rank <= 2:
        return True
    ranks = foundation_ranks(state)
    opposite = "cs" if card.is_red else "dh"
    return all(ranks[s] >= card.rank - 1 for s in opposite)


def king_waiting(state: GameState, exclude_col: int) -> bool:
    """A King that would gain from an empty column: the waste top, or a King heading a
    face-up run that sits on face-down cards (moving it reveals one)."""
    top = state.waste_top
    if top and top.card.rank == 13:
        return True
    for i, col in enumerate(state.tableau):
        if i != exclude_col and col.facedown and col.faceup and col.faceup[0].card.rank == 13:
            return True
    return False


def score_move(state: GameState, move: Move, w: dict) -> float | None:
    """Heuristic value of a non-stock move, or None when it isn't worth making."""
    card = move.card.card
    score: float

    if move.dst == FOUNDATION:
        score = w["foundation"]
        if is_safe_foundation(state, card):
            score += w["safe_foundation"]
        if move.src == TABLEAU:
            col = state.tableau[move.src_index]
            if len(col.faceup) == 1 and col.facedown:
                score += w["reveal"] + w["reveal_per_hidden"] * len(col.facedown)

    elif move.src == WASTE:
        score = w["waste_to_tableau"]

    else:  # tableau -> tableau
        col = state.tableau[move.src_index]
        if move.src_depth == 0 and col.facedown:
            score = w["reveal"] + w["reveal_per_hidden"] * len(col.facedown)
        elif move.src_depth == 0:
            # Empties the column. Only worth it for a King that needs the space,
            # and never for a King-led run (that just moves it to another empty column).
            if card.rank == 13 or not king_waiting(state, move.src_index):
                return None
            score = w["empty_column_for_king"]
        else:
            # Splits a run: only if the card it uncovers can go up right away.
            uncovered = col.faceup[move.src_depth - 1].card
            if foundation_slot(state, uncovered) is None:
                return None
            score = w["unblock_foundation"]

    if move.method == "drag":
        score -= w["drag_penalty"]
    return score


def rank_moves(state: GameState, weights: dict) -> list[tuple[float, Move]]:
    """Scored non-stock moves, best first (ties keep legal_moves order)."""
    scored = []
    for m in legal_moves(state):
        if m.is_stock:
            continue
        s = score_move(state, m, weights)
        if s is not None:
            scored.append((s, m))
    scored.sort(key=lambda sm: -sm[0])
    return scored


class Solver:
    """Picks the next move and remembers what it needs across moves: how many times the
    waste has been recycled, and whether anything was played since the last recycle
    (if not, another pass deals the same cards and the game is stuck).

    Call `executed(move)` once a move has been verified on screen.
    """

    def __init__(self, settings: dict | None = None):
        cfg = (settings or load_settings())["solver"]
        self.weights: dict = cfg["weights"]
        self.max_recycles: int | None = cfg.get("max_recycles")
        self.recycles_used = 0
        # True at start: the solver may join a game mid-pass and can't know what was played,
        # so it allows one recycle before calling the game stuck (costs one pass at worst).
        self.played_since_recycle = True

    def choose_move(self, state: GameState) -> Move | None:
        """Best move, a stock tap if nothing scores, or None when stuck (press Finish)."""
        if not state.is_valid:
            raise ValueError("refusing to plan on an invalid state: " + "; ".join(state.issues))
        ranked = rank_moves(state, self.weights)
        if ranked:
            return ranked[0][1]
        stock_taps = [m for m in legal_moves(state) if m.is_stock]
        if not stock_taps:
            return None
        tap = stock_taps[0]
        if tap.is_recycle:
            if self.max_recycles is not None and self.recycles_used >= self.max_recycles:
                return None
            if not self.played_since_recycle:
                return None
        return tap

    def executed(self, move: Move) -> None:
        if move.is_recycle:
            self.recycles_used += 1
            self.played_since_recycle = False
        elif not move.is_stock:
            self.played_since_recycle = True


def choose_move(state: GameState, settings: dict | None = None) -> Move | None:
    """Stateless one-shot (fresh memory each call). The game loop should keep a Solver."""
    return Solver(settings).choose_move(state)

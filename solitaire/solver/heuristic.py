"""Solver v1: score every legal move with simple Klondike heuristics (README §3.4).

Scoring favours what the app pays for (foundation cards) and what opens the game up
(turning over face-down cards). Moves that change nothing useful get no score at all,
which is also what keeps the solver from shuffling cards back and forth. Taps on the
stock are the fallback when nothing scores.

Weights and the recycle limit live in config/settings.yaml under `solver:`.
"""
from solitaire.config import load_settings
from solitaire.state import Card, GameState
from solitaire.solver import planner
from solitaire.solver.memory import StockMemory
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


def to_move(state: GameState, m: tuple) -> Move | None:
    """The real Move (with its PlacedCard and tap/drag) for a planner move."""
    k = m[0]
    for lm in legal_moves(state):
        if k == "draw" and lm.is_stock and not lm.is_recycle or k == "recycle" and lm.is_recycle:
            return lm
        if lm.is_stock:
            continue
        if (k == "wf" and lm.src == WASTE and lm.dst == FOUNDATION
                or k == "wt" and lm.src == WASTE and lm.dst == TABLEAU and lm.dst_index == m[1]
                or k == "tf" and lm.src == TABLEAU and lm.dst == FOUNDATION and lm.src_index == m[1]
                or k == "tt" and lm.src == TABLEAU and lm.dst == TABLEAU
                and (lm.src_index, lm.src_depth, lm.dst_index) == m[1:]):
            return lm
    return None


class Solver:
    """Picks the next move and remembers what it needs across moves.

    v2 (solver.plan.enabled): a StockMemory of the stock order, a lookahead search over
    it (planner.py), and every position the game has been in (so plans never go back).
    v1, the heuristic ranking below, is the fallback while the stock pointer is unknown
    (joined mid-pass, or a read contradicted the memory) or when a search runs out of
    budget without finding a gain. v1 tracks how many times the waste has been recycled
    and whether anything was played since the last recycle (if not, another pass deals
    the same cards and the game is stuck).

    Call `executed(move)` once a move has been verified on screen.
    """

    def __init__(self, settings: dict | None = None):
        cfg = (settings or load_settings())["solver"]
        self.weights: dict = cfg["weights"]
        self.max_recycles: int | None = cfg.get("max_recycles")
        self.plan_cfg: dict = cfg.get("plan") or {"enabled": False}
        self.memory = StockMemory(cfg.get("draw_count", 3))
        self.history: set = set()
        self.last_plan = ""            # what the last choice was based on, for the log
        self.recycles_used = 0
        # True at start: the solver may join a game mid-pass and can't know what was played,
        # so it allows one recycle before calling the game stuck (costs one pass at worst).
        self.played_since_recycle = True
        # Moves that came back as a MISMATCH, never tried again this game: the same misread
        # repeats every pass (2026-11-24: an undetected waste top made "Qd W->c5" fail 4
        # passes running and cost the game). Keyed by card, source and destination.
        self.blocked: set[tuple] = set()

    @staticmethod
    def _key(move: Move) -> tuple | None:
        if move is None or move.is_stock:
            return None
        return (str(move.card.card), move.src, move.dst, move.dst_index)

    def failed(self, move: Move) -> None:
        """The loop saw this move land somewhere other than predicted (or not at all)."""
        key = self._key(move)
        if key is not None:
            self.blocked.add(key)

    def is_blocked(self, move: Move | None) -> bool:
        return self._key(move) in self.blocked

    def blocked_positions(self, state: GameState, root: tuple, allow_recycle: bool) -> set:
        """The positions the blocked moves would lead to from `root`, for the planner's
        no-revisit set, so no plan starts with a blocked move."""
        if not self.blocked:
            return set()
        return {planner.apply(root, m, self.memory.draw_count) for m in planner.moves(root, allow_recycle)
                if self.is_blocked(to_move(state, m))}

    def choose_move(self, state: GameState) -> Move | None:
        """Best move, a stock tap if nothing scores, or None when stuck (press Finish)."""
        if not state.is_valid:
            raise ValueError("refusing to plan on an invalid state: " + "; ".join(state.issues))
        self.memory.observe(state)
        self.last_plan = ""
        if self.plan_cfg.get("enabled") and self.memory.ready:
            root = planner.from_state(state, self.memory.talon, self.memory.ptr)
            allow = self.max_recycles is None or self.recycles_used < self.max_recycles
            avoid = self.history | self.blocked_positions(state, root, allow)
            plan = planner.search(root, self.plan_cfg, self.memory.draw_count, allow, avoid)
            self.history.add(root)
            stats = (f"{plan.nodes} positions{'' if plan.exhaustive else ', budget hit'}, "
                     f"stock {self.memory.known}/{len(self.memory.talon)} known")
            if plan.gain > 0:
                move = to_move(state, plan.line[0])
                if move is not None:
                    self.last_plan = (f"plan +{plan.gain:.1f} ({stats}): "
                                      f"{planner.describe(root, plan.line, limit=20, draw_count=self.memory.draw_count)}")
                    return move
            elif plan.exhaustive:
                self.last_plan = f"stuck: no line gains anything ({stats})"
                return None
            self.last_plan = f"heuristic v1 ({stats})"
        else:
            self.last_plan = "heuristic v1 (stock position unknown)"
        return self._heuristic_move(state)

    def _heuristic_move(self, state: GameState) -> Move | None:
        ranked = [(s, m) for s, m in rank_moves(state, self.weights) if not self.is_blocked(m)]
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
        self.memory.executed(move)
        if move.is_recycle:
            self.recycles_used += 1
            self.played_since_recycle = False
        elif not move.is_stock:
            self.played_since_recycle = True


def choose_move(state: GameState, settings: dict | None = None) -> Move | None:
    """Stateless one-shot (fresh memory each call). The game loop should keep a Solver."""
    return Solver(settings).choose_move(state)

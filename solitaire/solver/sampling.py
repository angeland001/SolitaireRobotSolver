"""Solver v3 (README §3.4): sample the hidden cards, plan each sample with full
information, and play the move that does best on average.

What is hidden is known as a *set*: every card not on a foundation, not face-up in the
tableau and not yet seen in the stock memory. A *world* deals that set at random into
the face-down slots (tableau and unknown talon positions). In a world everything is
known, so a beam search can plan through flips and draws. Each search reports, for
every move playable now, the best line value it found starting with that move. The
values are averaged over the worlds and the best average is played. A move that only
works if a hidden card happens to be the right one scores well in a few worlds and
badly in the rest, so it loses to a move that is good whatever is hidden.

**Peeking with Undo.** The app's Undo takes back the last move only (a second move
makes the first one permanent). So a move that turns over a face-down card can be
played, the new card read, and the move undone: the robot now knows that column's top
hidden card, and every later world deals it there. v3 asks for a peek (`peek_col`)
when a column could be turned over now, isn't the column the best move turns over
anyway, and its best flip move is within `peek_margin` of the best move (it is a real
alternative). Peeks cost plotter time (a move + Undo), so `max_peeks` caps them.

Everything else (stock memory, positions already played, v1 fallback, stuck) is v2's
`Solver`; when the sampled search finds nothing that gains, v2 decides, including
whether the game is stuck.

The world is a small immutable simulation with cards as ints (rank << 2 | suit index):
  found  4 foundation ranks, in SUITS order (c d h s)
  cols   7 x (face-down cards, face-up cards), each a tuple of ints
  talon  the talon, every card known
  ptr    the stock pointer (talon[:ptr] is the waste)
Moves use the planner's tuples, so `heuristic.to_move` turns them into real Moves.

Settings: config/settings.yaml -> solver.v3 (search limits), weights from solver.plan.
"""
import random
import time
from typing import Callable

from solitaire.config import load_settings
from solitaire.solver import planner
from solitaire.solver.heuristic import Solver, to_move
from solitaire.state import Card, GameState
from solitaire.state.cards import FULL_DECK, SUITS

SI = {s: i for i, s in enumerate(SUITS)}
RED = (False, True, True, False)
NEG = float("-inf")


def enc(card: Card) -> int:
    return card.rank << 2 | SI[card.suit]


def dec(c: int) -> Card:
    return Card(c >> 2, SUITS[c & 3])


def _fits(c: int, col: tuple) -> bool:
    down, up = col
    if not up:
        return not down and c >> 2 == 13
    t = up[-1]
    return c >> 2 == (t >> 2) - 1 and RED[c & 3] != RED[t & 3]


def _to_found(found: tuple, c: int) -> bool:
    return found[c & 3] == (c >> 2) - 1


def _inc(found: tuple, c: int) -> tuple:
    f = list(found)
    f[c & 3] = c >> 2
    return tuple(f)


def moves(s: tuple, allow_recycle: bool = True) -> list[tuple]:
    """Same move set and pruning as planner.moves, on a fully known world."""
    found, cols, talon, ptr = s
    out = []
    w = talon[ptr - 1] if ptr else None
    if w is not None:
        if _to_found(found, w):
            out.append(("wf",))
        for di, col in enumerate(cols):
            if _fits(w, col):
                out.append(("wt", di))
    for ci, (down, up) in enumerate(cols):
        if not up:
            continue
        if _to_found(found, up[-1]):
            out.append(("tf", ci))
        for depth, c in enumerate(up):
            if depth == 0:
                if not down and c >> 2 == 13:
                    continue
            else:
                under = up[depth - 1]
                if not (_to_found(found, under) or (w is not None and w >> 2 == (under >> 2) - 1
                                                    and RED[w & 3] != RED[under & 3])):
                    continue
            for di, col in enumerate(cols):
                if di != ci and _fits(c, col):
                    out.append(("tt", ci, depth, di))
    if ptr < len(talon):
        out.append(("draw",))
    elif talon and allow_recycle:
        out.append(("recycle",))
    return out


def apply(s: tuple, m: tuple, draw_count: int = 3) -> tuple:
    found, cols, talon, ptr = s
    k = m[0]
    if k == "draw":
        return found, cols, talon, min(ptr + draw_count, len(talon))
    if k == "recycle":
        return found, cols, talon, 0
    if k in ("wf", "wt"):
        c = talon[ptr - 1]
        talon = talon[:ptr - 1] + talon[ptr:]
        if k == "wf":
            found = _inc(found, c)
        else:
            down, up = cols[m[1]]
            cols = cols[:m[1]] + ((down, up + (c,)),) + cols[m[1] + 1:]
        return found, cols, talon, ptr - 1
    ci = m[1]
    down, up = cols[ci]
    if k == "tf":
        found = _inc(found, up[-1])
        moving, remain = (), up[:-1]
    else:
        moving, remain = up[m[2]:], up[:m[2]]
    if not remain and down:
        down, remain = down[:-1], (down[-1],)
    new = list(cols)
    new[ci] = (down, remain)
    if k == "tt":
        dd, dup = cols[m[3]]
        new[m[3]] = (dd, dup + moving)
    return found, tuple(new), talon, ptr


def is_drag(s: tuple, m: tuple) -> bool:
    """planner.is_drag on a world."""
    found, cols, talon, ptr = s
    if m[0] not in ("wt", "tt"):
        return False
    if m[0] == "wt":
        c, src, exposed, di = talon[ptr - 1], None, True, m[1]
    else:
        up = cols[m[1]][1]
        c, src, exposed, di = up[m[2]], m[1], m[2] == len(up) - 1, m[3]
    if exposed and _to_found(found, c):
        return True
    for j, col in enumerate(cols):
        if j != src and _fits(c, col):
            return j != di
    return True


def evaluate(s: tuple, w: dict) -> float:
    found, cols, talon, _ = s
    excess = sum(max(0, found[i] - min(found[a], found[b]) - 2) for i, (a, b) in planner.OPPOSITE.items())
    down = sum(len(d) for d, _ in cols)
    empty = sum(1 for d, up in cols if not d and not up)
    return (w["foundation"] * sum(found) - w["unsafe_foundation"] * excess - w["reveal"] * down
            - w["talon_played"] * len(talon) + w["empty_column"] * empty)


def first_move_values(root: tuple, first: list[tuple], w: dict, draw_count: int = 3,
                      allow_recycle: bool = True) -> dict[tuple, float]:
    """Beam search over one world (like planner.search). For each move in `first` (the
    moves playable now), the best line value found that starts with it."""
    cost = lambda s, m: w["move_cost"] + (w["drag_cost"] if is_drag(s, m) else 0.0)  # noqa: E731
    e0 = evaluate(root, w)
    seen = {root: 0.0}
    best: dict[tuple, float] = {}
    frontier = []
    for m in first:
        c = apply(root, m, draw_count)
        cv = evaluate(c, w) - e0 - cost(root, m)
        best[m] = cv
        if cv > seen.get(c, NEG):
            seen[c] = cv
            frontier.append((cv, c, m))
    for depth in range(1, w["max_depth"]):
        if not frontier:
            break
        weight = max(0.1, 1.0 - w["discount"] * depth)
        children: dict = {}
        for v, s, m0 in frontier:
            e = evaluate(s, w)
            for m in moves(s, allow_recycle):
                c = apply(s, m, draw_count)
                cv = v + (evaluate(c, w) - e) * weight - cost(s, m)
                if cv <= seen.get(c, NEG):
                    continue
                seen[c] = cv
                children[c] = (cv, c, m0)
                if cv > best[m0]:
                    best[m0] = cv
        frontier = sorted(children.values(), key=lambda t: -t[0])[:w["beam_width"]]
    return best


def flipped_column(root_v2: tuple, m: tuple) -> int | None:
    """The column a move turns a face-down card over in, if any."""
    cols = root_v2[1]
    if m[0] == "tf" and cols[m[1]][0] and len(cols[m[1]][1]) == 1:
        return m[1]
    if m[0] == "tt" and m[2] == 0 and cols[m[1]][0]:
        return m[1]
    return None


class SolverV3(Solver):
    """v2's Solver with the move choice made over sampled worlds, and Undo peeks.

    After `choose_move`, `peek_col` is the column being peeked at when the returned move
    is a peek: play it, read the card it turns over, pass it to `record_peek`, then
    press Undo (and do NOT call `executed`). Otherwise `peek_col` is None.
    """

    def __init__(self, settings: dict | None = None, seed: int | None = None,
                 clock: Callable[[], float] = time.monotonic):
        settings = settings or load_settings()
        super().__init__(settings)
        self.v3: dict = settings["solver"]["v3"]
        self.rng = random.Random(seed)
        self.clock = clock
        self.peeked: dict[int, tuple[Card, int]] = {}   # col -> (its top hidden card, face-down count then)
        self.peek_col: int | None = None
        self.peeks_used = 0

    def record_peek(self, col: int, card: Card, facedown: int) -> None:
        """`card` is the top face-down card of `col` while that column has `facedown` cards."""
        self.peeked[col] = (card, facedown)
        self.peeks_used += 1

    def sample_world(self, state: GameState) -> tuple | None:
        """One random deal of the unseen cards that matches everything known, or None when
        the counts don't add up (a misread the validator missed)."""
        talon, ptr = self.memory.talon, self.memory.ptr
        known = state.foundation_cards() | {p.card for c in state.tableau for p in c.faceup}
        known |= {c for c in talon if c is not None}
        fixed = {ci: card for ci, (card, _) in self.peeked.items()}
        if known & set(fixed.values()):
            return None
        unseen = [enc(c) for c in FULL_DECK - known - set(fixed.values())]
        slots = sum(len(c.facedown) for c in state.tableau) - len(fixed) + sum(c is None for c in talon)
        if len(unseen) != slots:
            return None
        self.rng.shuffle(unseen)
        found = [0, 0, 0, 0]
        for p in state.foundations:
            if p:
                found[SI[p.card.suit]] = p.card.rank
        cols = []
        for ci, col in enumerate(state.tableau):
            n = len(col.facedown)
            if ci in fixed:
                down = tuple(unseen.pop() for _ in range(n - 1)) + (enc(fixed[ci]),)
            else:
                down = tuple(unseen.pop() for _ in range(n))
            cols.append((down, tuple(enc(p.card) for p in col.faceup)))
        tal = tuple(enc(c) if c is not None else unseen.pop() for c in talon)
        return tuple(found), tuple(cols), tal, ptr

    def choose_move(self, state: GameState):
        self.peek_col = None
        if not state.is_valid:
            raise ValueError("refusing to plan on an invalid state: " + "; ".join(state.issues))
        self.memory.observe(state)
        if not (self.v3.get("enabled") and self.plan_cfg.get("enabled") and self.memory.ready):
            return super().choose_move(state)
        # A peeked card stays valid while its column keeps the same number of face-down cards.
        self.peeked = {ci: (card, n) for ci, (card, n) in self.peeked.items()
                       if len(state.tableau[ci].facedown) == n}

        dc = self.memory.draw_count
        allow = self.max_recycles is None or self.recycles_used < self.max_recycles
        root = planner.from_state(state, self.memory.talon, self.memory.ptr)
        first = [m for m in planner.moves(root, allow) if planner.apply(root, m, dc) not in self.history
                 and not self.is_blocked(to_move(state, m))]
        if not first:
            return super().choose_move(state)
        w = {**self.plan_cfg, "beam_width": self.v3["beam_width"], "max_depth": self.v3["max_depth"]}

        t0 = self.clock()
        per_world: list[dict] = []
        for _ in range(self.v3["samples"]):
            world = self.sample_world(state)
            if world is None:
                break
            per_world.append(first_move_values(world, first, w, dc, allow))
            if self.clock() - t0 > self.v3["max_seconds"]:
                break
        if not per_world:
            return super().choose_move(state)
        n = len(per_world)
        mean = {m: sum(v[m] for v in per_world) / n for m in first}
        best = max(first, key=lambda m: mean[m])
        if mean[best] <= 0:
            return super().choose_move(state)    # v2 decides: a longer line, or stuck

        stats = f"{n} worlds, {self.clock() - t0:.2f} s, stock {self.memory.known}/{len(self.memory.talon)} known"
        peek = self._peek_choice(root, first, mean, best)
        if peek is not None:
            col, m = peek
            move = to_move(state, m)
            if move is not None and move.src_index == col:
                self.peek_col = col
                self.last_plan = (f"v3 PEEK col {col + 1} ({planner.describe(root, [m], draw_count=dc)}, "
                                  f"then Undo): {mean[m]:+.1f} vs best {mean[best]:+.1f} ({stats})")
                return move

        move = to_move(state, best)
        if move is None:
            return super().choose_move(state)
        self.history.add(root)
        ranked = sorted(first, key=lambda m: -mean[m])[:3]
        alts = ", ".join(f"{planner.describe(root, [m], draw_count=dc)} {mean[m]:+.1f}" for m in ranked)
        self.last_plan = f"v3 ({stats}): {alts}"
        return move

    def _peek_choice(self, root: tuple, first: list[tuple], mean: dict, best: tuple) -> tuple[int, tuple] | None:
        if not self.v3.get("peek") or self.peeks_used >= self.v3["max_peeks"]:
            return None
        margin = self.v3.get("peek_margin")
        skip = flipped_column(root, best)        # turned over by the move we'd play anyway
        options: dict[int, tuple] = {}
        for m in first:
            col = flipped_column(root, m)
            if col is None or col == skip or col in self.peeked:
                continue
            if col not in options or mean[m] > mean[options[col]]:
                options[col] = m
        options = {c: m for c, m in options.items() if margin is None or mean[best] - mean[m] <= margin}
        if not options:
            return None
        col = max(options, key=lambda c: mean[options[c]])
        return col, options[col]

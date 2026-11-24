"""Solver v2 lookahead (README §3.4): a best-first search over what is known.

The board is copied into a small immutable simulation:
  found  4 foundation ranks, in SUITS order (c d h s)
  cols   7 x (face-down count, face-up cards); a None card is one just turned over
         in the plan (unknown: nothing can go on it or move it)
  talon  the stock memory's sequence; an int stands for an unknown card
  ptr    the stock memory's pointer

Moves are the ones the executor can make (no foundation -> tableau). A line's value adds
up the change in `evaluate` after each move (foundation cards, cards turned over, cards
out of the talon, empty columns, minus foundation cards that run too far ahead of the
other colour), plus a bonus for drawing an unknown card into view. Gains count a
little less the later they come (`discount`), and every move costs a little time.
The search (a beam search, see `search`) returns the best line found. Its first move is played, and the next board
read is planned again from scratch. If the whole reachable space was searched and no
line gains anything, the game is stuck.

`avoid` holds positions the real game has already been in, so the plan never walks
back into one (no shuffling cards back and forth across replans).

Weights and limits: config/settings.yaml -> solver.plan.
"""
import time
from dataclasses import dataclass, field
from typing import Callable

from solitaire.state import Card, GameState
from solitaire.state.cards import SUITS

SI = {s: i for i, s in enumerate(SUITS)}
OPPOSITE = {0: (1, 2), 1: (0, 3), 2: (0, 3), 3: (1, 2)}   # c: d h, d: c s, h: c s, s: d h

Sim = tuple   # (found, cols, talon, ptr)


def from_state(state: GameState, talon: list[Card | None], ptr: int) -> Sim:
    found = [0, 0, 0, 0]
    for p in state.foundations:
        if p:
            found[SI[p.card.suit]] = p.card.rank
    cols = tuple((len(c.facedown), tuple(p.card for p in c.faceup)) for c in state.tableau)
    tal = tuple(c if c is not None else i for i, c in enumerate(talon))
    return tuple(found), cols, tal, ptr


def _fits(card: Card, col: tuple) -> bool:
    d, up = col
    if not up:
        return d == 0 and card.rank == 13
    top = up[-1]
    return top is not None and card.rank == top.rank - 1 and card.is_red != top.is_red


def _to_found(found: tuple, card: Card) -> bool:
    return found[SI[card.suit]] == card.rank - 1


def _waste_top(talon: tuple, ptr: int) -> Card | None:
    if ptr == 0:
        return None
    c = talon[ptr - 1]
    return None if isinstance(c, int) else c


def moves(s: Sim, allow_recycle: bool = True) -> list[tuple]:
    """('wf',) ('wt', col) ('tf', col) ('tt', col, depth, col) ('draw',) ('recycle',)"""
    found, cols, talon, ptr = s
    out = []
    w = _waste_top(talon, ptr)
    if w is not None:
        if _to_found(found, w):
            out.append(("wf",))
        for di, col in enumerate(cols):
            if _fits(w, col):
                out.append(("wt", di))
    for ci, (d, up) in enumerate(cols):
        if not up or up[0] is None:
            continue
        if _to_found(found, up[-1]):
            out.append(("tf", ci))
        for depth, card in enumerate(up):
            if depth == 0:
                if d == 0 and card.rank == 13:
                    continue    # a King already heading an empty column gains nothing by moving
            else:
                # Split a run only to free the card under it: for a foundation, or for the waste top.
                under = up[depth - 1]
                if not (_to_found(found, under) or (w is not None and w.rank == under.rank - 1
                                                    and w.is_red != under.is_red)):
                    continue
            for di, col in enumerate(cols):
                if di != ci and _fits(card, col):
                    out.append(("tt", ci, depth, di))
    if ptr < len(talon):
        out.append(("draw",))
    elif talon and allow_recycle:
        out.append(("recycle",))
    return out


def _inc(found: tuple, card: Card) -> tuple:
    f = list(found)
    f[SI[card.suit]] = card.rank
    return tuple(f)


def apply(s: Sim, m: tuple, draw_count: int = 3) -> Sim:
    found, cols, talon, ptr = s
    k = m[0]
    if k == "draw":
        return found, cols, talon, min(ptr + draw_count, len(talon))
    if k == "recycle":
        return found, cols, talon, 0
    if k in ("wf", "wt"):
        card = talon[ptr - 1]
        talon = talon[:ptr - 1] + talon[ptr:]
        if k == "wf":
            found = _inc(found, card)
        else:
            d, up = cols[m[1]]
            cols = cols[:m[1]] + ((d, up + (card,)),) + cols[m[1] + 1:]
        return found, cols, talon, ptr - 1
    ci = m[1]
    d, up = cols[ci]
    if k == "tf":
        found = _inc(found, up[-1])
        moving, remain = (), up[:-1]
    else:
        moving, remain = up[m[2]:], up[:m[2]]
    if not remain and d:
        d, remain = d - 1, (None,)     # turned over: unknown until the real board shows it
    new = list(cols)
    new[ci] = (d, remain)
    if k == "tt":
        dd, dup = cols[m[3]]
        new[m[3]] = (dd, dup + moving)
    return found, tuple(new), talon, ptr


def is_drag(s: Sim, m: tuple) -> bool:
    """Would the app's tap rule (foundation first, else left-most column) send it elsewhere?"""
    found, cols, talon, ptr = s
    if m[0] not in ("wt", "tt"):
        return False
    if m[0] == "wt":
        card, src, exposed, di = talon[ptr - 1], None, True, m[1]
    else:
        up = cols[m[1]][1]
        card, src, exposed, di = up[m[2]], m[1], m[2] == len(up) - 1, m[3]
    if exposed and _to_found(found, card):
        return True
    for j, col in enumerate(cols):
        if j != src and _fits(card, col):
            return j != di
    return True


def evaluate(s: Sim, w: dict) -> float:
    found, cols, talon, _ = s
    excess = sum(max(0, found[i] - min(found[a], found[b]) - 2) for i, (a, b) in OPPOSITE.items())
    down = sum(d for d, _ in cols)
    empty = sum(1 for d, up in cols if not d and not up)
    return (w["foundation"] * sum(found) - w["unsafe_foundation"] * excess - w["reveal"] * down
            - w["talon_played"] * len(talon) + w["empty_column"] * empty)


@dataclass
class Plan:
    line: list[tuple] = field(default_factory=list)   # the best line; line[0] is played now
    gain: float = 0.0                                   # its value; <= 0 means nothing worth doing
    exhaustive: bool = True                             # every reachable position was searched
    nodes: int = 0


def search(root: Sim, w: dict, draw_count: int = 3, allow_recycle: bool = True,
           avoid: set | frozenset = frozenset(), clock: Callable[[], float] = time.monotonic) -> Plan:
    """Beam search, one move deep at a time: each depth keeps the `beam_width` best lines.
    (Best-first on line value chases long draw chains, each draw peeking a new card,
    and never comes back for a short tableau move.) Exhaustive = nothing was ever cut
    from a beam and the lines ran out before `max_depth`."""
    t0 = clock()
    frontier = [(0.0, root, (), frozenset())]       # (value, sim, line, unknown stock cards seen)
    seen = {root: 0.0}
    best = Plan()
    for depth in range(w["max_depth"]):
        weight = max(0.1, 1.0 - w["discount"] * depth)
        children: dict = {}
        for v, s, line, peeked in frontier:
            best.nodes += 1
            e = evaluate(s, w)
            for m in moves(s, allow_recycle):
                c = apply(s, m, draw_count)
                if c in avoid:
                    continue
                gain = evaluate(c, w) - e
                pk = peeked
                if m[0] == "draw":
                    top = c[2][c[3] - 1]
                    if isinstance(top, int) and top not in peeked:
                        gain += w["peek"]
                        pk = peeked | {top}
                cv = v + gain * weight - w["move_cost"] - (w["drag_cost"] if is_drag(s, m) else 0.0)
                if cv <= seen.get(c, float("-inf")):
                    continue
                seen[c] = cv
                children[c] = (cv, c, line + (m,), pk)
                if cv > best.gain + 1e-9:
                    best.line, best.gain = list(line + (m,)), cv
        if not children:
            return best
        frontier = sorted(children.values(), key=lambda t: -t[0])
        if len(frontier) > w["beam_width"]:
            frontier = frontier[:w["beam_width"]]
            best.exhaustive = False
        if clock() - t0 > w["max_seconds"]:
            best.exhaustive = False
            return best
    best.exhaustive = False
    return best


def describe(root: Sim, line: list[tuple], limit: int = 10, draw_count: int = 3) -> str:
    """'draw(Qd), Qd W->c1, 2d W->F, ...' for the log."""
    parts, s = [], root
    for m in line[:limit]:
        found, cols, talon, ptr = s
        k = m[0]
        if k in ("draw", "recycle"):
            s = apply(s, m, draw_count)
            if k == "draw":
                top = s[2][s[3] - 1]
                parts.append(f"draw({'?' if isinstance(top, int) else top})")
            else:
                parts.append("recycle")
            continue
        if k in ("wf", "wt"):
            card, src = talon[ptr - 1], "W"
        else:
            up = cols[m[1]][1]
            card, src = (up[-1] if k == "tf" else up[m[2]]), f"c{m[1] + 1}"
        dst = "F" if k in ("wf", "tf") else f"c{m[-1] + 1}"
        parts.append(f"{card} {src}->{dst}")
        s = apply(s, m, draw_count)
    more = f" ... (+{len(line) - limit})" if len(line) > limit else ""
    return ", ".join(parts) + more

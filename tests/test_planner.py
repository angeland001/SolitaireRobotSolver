"""Solver v2: stock memory + lookahead planner. Run: python -m pytest tests"""
from boards import board

from solitaire.config import load_settings
from solitaire.solver import Solver
from solitaire.solver.memory import StockMemory, talon_size
from solitaire.solver.moves import DRAW
from solitaire.state import Card

SETTINGS = load_settings()

# 7 columns, 21 face-down + 7 face-up cards, so the stock + waste hold 24 cards.
# Nothing can go on a King but a Queen, or on a 2 but an Ace.
BLOCKED = ["Kc", "# Kd", "## Kh", "### Ks", "#### 2c", "##### 2d", "###### 2h"]
FILLER = [Card.parse(f"{r}{s}") for r in range(3, 11) for s in "cdhs"]   # 3..10: playable nowhere here


def solver_with(stock: list[Card], ptr: int) -> Solver:
    s = Solver(SETTINGS)
    s.memory.talon, s.memory.ptr = list(stock), ptr
    return s


def test_talon_size():
    assert talon_size(board(BLOCKED)) == 24


def test_memory_follows_draws_and_plays():
    mem = StockMemory(3)
    mem.observe(board(BLOCKED))                       # fresh deal: waste empty -> pointer at 0
    assert mem.ready and mem.ptr == 0 and mem.known == 0
    mem.executed(DRAW)
    mem.observe(board(BLOCKED, waste="9c"))
    assert mem.ptr == 3 and mem.talon[2] == Card.parse("9c")
    mem.executed(DRAW)
    mem.observe(board(BLOCKED, waste="5h"))
    assert mem.talon[5] == Card.parse("5h")
    # 5h is played but lands somewhere unexpected (executed() not called): the board holds
    # one more card, so the memory drops the waste top itself. 7d was under it.
    mem.observe(board(["Kc 5h"] + BLOCKED[1:], waste="7d"))
    assert len(mem.talon) == 23 and mem.ptr == 5 and Card.parse("5h") not in mem.talon
    assert mem.talon[4] == Card.parse("7d")


def test_memory_realigns_on_a_known_waste_top():
    mem = StockMemory(3)
    mem.talon, mem.ptr = list(FILLER[:24]), 0
    mem.observe(board(BLOCKED, waste=str(FILLER[8])))  # someone drew three times by hand
    assert mem.ptr == 9


def test_memory_waits_when_joining_mid_pass():
    mem = StockMemory(3)
    mem.observe(board(BLOCKED, waste="9c"))            # stock and waste both non-empty: pointer unknown
    assert not mem.ready
    mem.observe(board(BLOCKED, waste="9c", stock=False))
    assert mem.ready and mem.ptr == 24 and mem.talon[23] == Card.parse("9c")


def test_stuck_when_no_line_gains_anything():
    stock = FILLER[:24]
    s = board(BLOCKED, waste=str(stock[-1]), stock=False)
    assert Solver({**SETTINGS, "solver": {**SETTINGS["solver"], "plan": {"enabled": False}}}
                  ).choose_move(s).is_recycle    # v1 can't tell, so it recycles once
    solver = solver_with(stock, 24)
    assert solver.choose_move(s) is None
    assert solver.last_plan.startswith("stuck")


def test_plays_a_waste_card_to_shift_the_draws_onto_a_buried_ace():
    # Draw-3 shows positions 2, 5, 8, ... Ac sits at 3 and never shows, unless Qd (at 2)
    # is played: then the next pass is shifted by one and Ac comes up.
    stock = FILLER[:22]
    stock.insert(2, Card.parse("Qd"))
    stock.insert(3, Card.parse("Ac"))
    solver = solver_with(stock, 0)
    m = solver.choose_move(board(BLOCKED))
    assert m == DRAW
    assert "Qd W->c1" in solver.last_plan and "Ac W->F" in solver.last_plan


def test_reveal_beats_an_unsafe_foundation_card():
    # 5h could go up, but 4c can only reveal its column by going onto 5h.
    s = board(["5h", "## 4c"], foundations="4h")
    m = Solver(SETTINGS).choose_move(s)
    assert (str(m.card), m.dst, m.dst_index) == ("4c", "tableau", 0)


def test_a_pass_already_played_is_not_played_again():
    # Unknown stock, but the pass from the start was already played (positions in
    # history): the planner gains nothing by repeating it and calls it stuck.
    stock = FILLER[:24]
    solver = solver_with(stock, 24)
    s = board(BLOCKED, waste=str(stock[-1]), stock=False)
    assert solver.choose_move(s) is None
    solver = solver_with([None] * 24, 0)
    assert solver.choose_move(board(BLOCKED)) == DRAW   # unknown cards: drawing shows them

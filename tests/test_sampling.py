"""Solver v3: sampled worlds, the world simulation, and the Undo peek in the v3 loop."""
import random
import sys
from pathlib import Path

from boards import board
from test_main import SETTINGS, RecordingExecutor, ScriptedReader

from solitaire.main_v3 import GameLoopV3
from solitaire.solver import planner
from solitaire.solver.moves import DRAW
from solitaire.solver.sampling import SolverV3, dec, enc, moves
from solitaire.state import Card
from solitaire.state.cards import FULL_DECK

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.simulate_games import Game  # noqa: E402

FAST = {**SETTINGS, "solver": {**SETTINGS["solver"],
                               "v3": {**SETTINGS["solver"]["v3"], "samples": 3, "beam_width": 10, "max_depth": 10}}}


def _world_cards(world) -> list[Card]:
    found, cols, talon, _ = world
    cards = [Card(r, "cdhs"[i]) for i, top in enumerate(found) for r in range(1, top + 1)]
    cards += [dec(c) for down, up in cols for c in down + up]
    return cards + [dec(c) for c in talon]


def _solver_on(game: Game, seed: int = 0) -> SolverV3:
    solver = SolverV3(FAST, seed=seed)
    solver.memory.observe(game.state())
    return solver


def test_world_deals_every_card_once_and_keeps_what_is_seen():
    game = Game(random.Random(3))
    state = game.state()
    solver = _solver_on(game)
    for _ in range(5):
        world = solver.sample_world(state)
        cards = _world_cards(world)
        assert len(cards) == 52 and set(cards) == FULL_DECK
        for col, (down, up) in zip(state.tableau, world[1]):
            assert len(down) == len(col.facedown)
            assert [dec(c) for c in up] == [p.card for p in col.faceup]


def test_peeked_card_is_always_on_top_of_its_column():
    game = Game(random.Random(4))
    solver = _solver_on(game)
    hidden = game.down[5][-1]
    solver.record_peek(5, hidden, len(game.down[5]))
    for _ in range(10):
        assert solver.sample_world(game.state())[1][5][0][-1] == enc(hidden)


def test_world_moves_match_the_planner_at_the_root():
    for seed in range(20):
        game = Game(random.Random(seed))
        solver = _solver_on(game)
        for _ in range(seed % 7):       # a few draws, so the waste has a top
            game.play(DRAW)
            solver.executed(DRAW)
            solver.memory.observe(game.state())
        state = game.state()
        root = planner.from_state(state, solver.memory.talon, solver.memory.ptr)
        assert moves(solver.sample_world(state)) == planner.moves(root)


def test_v3_plays_a_whole_simulated_game():
    from tools.simulate_v3 import play
    r = play(("v3", 7, FAST, 400))
    assert r["result"] in ("won", "stuck") and r["cards"] >= 0


class PeekFirst(SolverV3):
    """Asks for a peek at column 1 (the Ah flip) on its first call, then plays normally."""

    def choose_move(self, state):
        move = super().choose_move(state)
        if self.peeks_used == 0 and not getattr(self, "_asked", False):
            self._asked = True
            self.peek_col = 0
        return move


START = board(["## Ah", "## 9s"])
AFTER_ACE = board(["# 5c", "## 9s"], foundations="Ah")
WON = board([], foundations="Kc Kd Kh Ks", stock=False)


def test_peek_plays_reads_and_undoes():
    ex = RecordingExecutor()
    solver = PeekFirst(FAST)
    seen = []
    solver.record_peek = lambda col, card, n: seen.append((col, str(card), n)) or SolverV3.record_peek(solver, col, card, n)
    gl = GameLoopV3(ScriptedReader([START, AFTER_ACE, START, AFTER_ACE, WON]), solver, ex, FAST, log=lambda m: None)
    assert gl.run() == "won"
    assert seen == [(0, "5c", 2)] and gl.peeks == 1
    assert [d.split()[0] for d in ex.done] == ["tap", "press", "tap", "draw"]
    assert ex.done[1] == "press Undo"


def test_peek_that_does_not_undo_carries_on_from_the_real_board():
    ex = RecordingExecutor()
    other = board(["# 5c", "## 9s"], foundations="Ah", waste="Kd")    # Undo didn't happen; something else did
    gl = GameLoopV3(ScriptedReader([START, AFTER_ACE, other, WON]), PeekFirst(FAST), ex, FAST, log=lambda m: None)
    assert gl.run() == "won"


def test_v3_never_replays_a_blocked_move():
    game = Game(random.Random(5))
    solver = _solver_on(game)
    state = game.state()
    first = solver.choose_move(state)
    assert first is not None and not first.is_stock
    assert solver.failed(first, suspect=True)
    again = solver.choose_move(state)
    assert again is None or str(again) != str(first)

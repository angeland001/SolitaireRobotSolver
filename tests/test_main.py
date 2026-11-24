"""GameLoop with a scripted screen and a recording executor (no YOLO, no plotter)."""
import numpy as np
from boards import board

from solitaire.calibration import Calibration
from solitaire.config import load_settings
from solitaire.executor import Executor
from solitaire.main import GameLoop, landed
from solitaire.solver import Solver
from solitaire.state import Card, PlacedCard
from solitaire.vision.detection import Detection

SETTINGS = load_settings()
CAL = Calibration(np.diag([0.1, 0.1, 1.0]), 0.0, 0, "test")

START = board(["## Ah", "## 9s"])                       # Ah should go up
AFTER_ACE = board(["# 5c", "## 9s"], foundations="Ah")  # the flip revealed 5c
WON = board([], foundations="Kc Kd Kh Ks", stock=False)
STUCK = board(["## 9s", "## 4d"], waste="2c", stock=False)


class ScriptedReader:
    """read()/read_change() hand out the next board from a list; None = nothing stable."""

    def __init__(self, boards):
        self.boards = list(boards)
        self.last_issues = ["scripted"]

    def _next(self):
        return self.boards.pop(0) if self.boards else None

    def read(self):
        return self._next()

    def read_change(self, before):
        after = self._next()
        return after, after is not None and after.signature != before.signature


class RecordingExecutor(Executor):
    def __init__(self):
        super().__init__(CAL, None, SETTINGS)
        self.done = []

    def perform(self, action):
        self.done.append(action.label)

    def hover(self, action):
        self.done.append("hover " + action.label)


def loop(boards, dry_run=False, settings=SETTINGS, aim_check=None):
    ex = RecordingExecutor()
    gl = GameLoop(ScriptedReader(boards), Solver(settings), ex, settings, dry_run=dry_run,
                  log=lambda m: None, aim_check=aim_check)
    return gl, ex


def test_failed_aim_check_never_taps():
    gl, ex = loop([START, AFTER_ACE, WON], aim_check=lambda action: False)
    assert gl.run() == "stopped at the aim check"
    assert len(ex.done) == 1 and ex.done[0].startswith("hover tap Ah")


def test_aim_check_is_asked_once():
    asked = []
    gl, ex = loop([START, AFTER_ACE, WON], aim_check=lambda a: asked.append(a) or True)
    assert gl.run() == "won" and len(asked) == 1
    assert [d.split()[0] for d in ex.done] == ["hover", "tap", "draw"]


def test_plays_until_won():
    gl, ex = loop([START, AFTER_ACE, WON])
    # after the ace, 5c has nothing to do, so the solver draws; the next board is the win
    assert gl.run() == "won"
    assert ex.done[0].startswith("tap Ah") and ex.done[1] == "draw from stock"
    assert gl.moves_made == 2 and gl.mismatches == 0


def test_stuck_presses_finish_only_when_enabled():
    for press, reason, done in ((True, "stuck (Finish)", ["press Finish"]), (False, "stuck", [])):
        settings = {**SETTINGS, "solver": {**SETTINGS["solver"], "max_recycles": 0},
                    "game": {**SETTINGS["game"], "press_finish": press}}
        gl, ex = loop([STUCK], settings=settings)
        assert gl.run() == reason and ex.done == done


def test_missed_taps_stop_the_loop():
    gl, ex = loop([START] * 10)
    assert "stopped registering" in gl.run()
    assert len(ex.done) == SETTINGS["game"]["max_missed_moves"] + 1


def test_retries_are_nudged_along_the_card():
    s = board(["## Ah", "## 9s"])
    s.tableau[0].faceup = [PlacedCard(Card.parse("Ah"), Detection("Ah", 1.0, 250, 800, 350, 880))]
    ex = RecordingExecutor()
    ys = []
    ex.perform = lambda action: ys.append(action.points_px[0][1])
    gl = GameLoop(ScriptedReader([s] * 10), Solver(SETTINGS), ex, SETTINGS, log=lambda m: None)
    gl.run()
    assert ys == [840 + n * 80 for n in SETTINGS["game"]["retry_nudges"]]   # middle, lower, higher


def test_repeated_misses_re_aim_and_continue():
    asked = []
    gl, ex = loop([START, START, START, START, START, AFTER_ACE, WON],
                  aim_check=lambda a: asked.append(a.label) or True)
    assert gl.run() == "won"
    assert len(asked) == 2      # first-tap check, then the re-aim after 3 misses


def test_mismatch_is_counted_not_fatal():
    elsewhere = board(["## 9s", "## Ah"])  # board changed, but Ah isn't on a foundation
    gl, _ = loop([START, elsewhere, WON])
    assert gl.run() == "won" and gl.mismatches == 1


def test_no_board_stops():
    gl, ex = loop([])
    assert gl.run().startswith("no stable board") and ex.done == []


def test_dry_run_never_touches():
    gl, ex = loop([START, AFTER_ACE, WON], dry_run=True)
    assert gl.run() == "won" and ex.done == []


def test_landed():
    from solitaire.solver import legal_moves
    move = next(m for m in legal_moves(START) if str(m.card) == "Ah")
    assert landed(move, START, AFTER_ACE)
    assert not landed(move, START, START)

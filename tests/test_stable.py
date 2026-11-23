"""Multi-frame agreement, driven by scripted reads and a fake clock."""
from dataclasses import replace

from boards import board, det

from solitaire.state import StabilityTracker, StableReader

A = board(["## 9s", "Kd"], waste="4c")
B = board(["## 9s", "Kd"], waste="7h")                # one card differs (a misread, or the next draw)
BAD = board(["## 9s"], issues=["7d seen 2 times"])    # mid-animation / invalid frame
CFG = {"stability": {"agree_frames": 3, "read_timeout_s": 1.0, "change_timeout_s": 1.0,
                     "frame_interval_s": 0.0}}


class Script:
    """read_state() that replays a list of states; each read advances a fake clock 0.1 s."""

    def __init__(self, states):
        self.states, self.t, self.reads = list(states), 0.0, 0

    def __call__(self):
        self.t += 0.1
        self.reads += 1
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]

    def reader(self):
        return StableReader(self, CFG, clock=lambda: self.t, sleep=lambda s: None)


def test_signature_ignores_box_positions():
    moved = replace(A, stock=det("facedown", x=123))
    assert moved.signature == A.signature
    assert B.signature != A.signature


def test_tracker_needs_n_identical_valid_reads():
    t = StabilityTracker(3)
    assert t.push(A) is None and t.push(A) is None
    assert t.push(A) is A


def test_tracker_resets_on_disagreement_and_invalid():
    t = StabilityTracker(3)
    for s in (A, A, B, A, A, BAD, A, A):
        assert t.push(s) is None
    assert t.push(A) is A


def test_read_skips_a_shimmer_misread():
    script = Script([A, B, A, A, A])
    assert script.reader().read() is A
    assert script.reads == 5


def test_read_times_out_when_nothing_settles():
    script = Script([BAD])
    r = script.reader()
    assert r.read() is None
    assert r.last_issues == ["7d seen 2 times"]


def test_read_change_returns_new_board():
    script = Script([A, A, A, BAD, B, B, B])
    state, changed = script.reader().read_change(A)
    assert changed and state is B


def test_read_change_reports_a_missed_tap():
    script = Script([A])
    state, changed = script.reader().read_change(A)
    assert not changed and state is A

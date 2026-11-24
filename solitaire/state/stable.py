"""Multi-frame agreement: trust a board only once several consecutive reads match.

One frame can be wrong in two ways that a single read can't tell apart from a real
board: a card mid-animation, and a misread (mostly cards with the holographic
shimmer, README §4.1). The shimmer moves and animations end, so requiring
`agree_frames` *valid* reads in a row with the same signature removes both. Invalid reads
in between (up to `max_invalid_between` in a row) are skipped, not counted: a covered
card whose strip the detector only sometimes finds (game of 2026-11-24: a `6d` strip
missing on some frames, "5c cannot sit on 7c") would otherwise never let a board settle.
A *valid* read that disagrees still starts the count again.

StabilityTracker is the pure part (feed it states). StableReader drives a frame
source with timeouts and is what the game loop uses. Settings: `stability:`.
"""
import time
from typing import Callable

from solitaire.config import load_settings
from solitaire.state.game_state import GameState


class StabilityTracker:
    def __init__(self, agree_frames: int, max_invalid_between: int = 0):
        if agree_frames < 1:
            raise ValueError("agree_frames must be >= 1")
        self.agree_frames = agree_frames
        self.max_invalid_between = max_invalid_between
        self.reset()

    def reset(self) -> None:
        self.streak = 0
        self.invalid_run = 0
        self._signature: tuple | None = None

    def push(self, state: GameState) -> GameState | None:
        """Add one read. Returns the state once `agree_frames` valid reads agree with no
        valid read disagreeing in between, else None. Invalid reads are skipped, but more
        than `max_invalid_between` of them in a row break the streak."""
        if not state.is_valid:
            self.invalid_run += 1
            if self.invalid_run > self.max_invalid_between:
                self.reset()
            return None
        self.invalid_run = 0
        sig = state.signature
        if sig == self._signature:
            self.streak += 1
        else:
            self._signature, self.streak = sig, 1
        return state if self.streak >= self.agree_frames else None


class StableReader:
    """Reads frames until the board is stable.

    read_state: one capture -> detect -> build, returning a GameState.
    clock/sleep are injectable so tests run without real time.
    """

    def __init__(self, read_state: Callable[[], GameState], settings: dict | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        cfg = (settings or load_settings())["stability"]
        self.read_state = read_state
        self.agree_frames: int = cfg["agree_frames"]
        self.max_invalid_between: int = cfg.get("max_invalid_between", 0)
        self.read_timeout_s: float = cfg["read_timeout_s"]
        self.change_timeout_s: float = cfg["change_timeout_s"]
        self.frame_interval_s: float = cfg["frame_interval_s"]
        self.clock, self.sleep = clock, sleep
        self.last_issues: list[str] = []   # issues of the most recent invalid read, for messages
        # Timing of the most recent read, in s from its start, for the game log: when a frame
        # first differed from `before` (None: never), when it returned, and frames read.
        self.last_first_change_s: float | None = None
        self.last_elapsed_s: float = 0.0
        self.last_frames: int = 0

    def read(self, timeout_s: float | None = None) -> GameState | None:
        """A stable, valid board, or None if none settled within the timeout (mirror
        dropped, a menu on screen, a misread that keeps changing)."""
        state, _ = self._read(timeout_s if timeout_s is not None else self.read_timeout_s, None)
        return state

    def read_change(self, before: GameState, timeout_s: float | None = None) -> tuple[GameState | None, bool]:
        """After a move: wait for a stable board that differs from `before`.

        Returns (state, changed). On timeout it returns the last stable board it saw with
        changed=False (the tap didn't register, or the app ignored it), or (None, False)
        if nothing settled at all, or if the screen did change (`agree_frames` reads in a
        row unlike `before`, valid or not) but the new board never settled: then the tap
        DID register, and calling it a miss would make the loop touch the screen again
        (game of 2026-11-24: the retry played a second, unplanned move)."""
        return self._read(timeout_s if timeout_s is not None else self.change_timeout_s, before.signature)

    def _read(self, timeout_s: float, differ_from: tuple | None) -> tuple[GameState | None, bool]:
        tracker = StabilityTracker(self.agree_frames, self.max_invalid_between)
        deadline = self.clock() + timeout_s
        last_stable: GameState | None = None
        differ_run, saw_change = 0, False
        start = self.clock()
        self.last_first_change_s, self.last_frames = None, 0
        while True:
            raw = self.read_state()
            self.last_frames += 1
            self.last_elapsed_s = self.clock() - start
            if not raw.is_valid:
                self.last_issues = list(raw.issues)
            if differ_from is not None:
                differ_run = differ_run + 1 if raw.signature != differ_from else 0
                if differ_run == 1 and self.last_first_change_s is None:
                    self.last_first_change_s = self.last_elapsed_s
                saw_change = saw_change or differ_run >= self.agree_frames
            state = tracker.push(raw)
            if state is not None:
                if differ_from is None or state.signature != differ_from:
                    return state, True
                last_stable = state
            if self.clock() >= deadline:
                if saw_change:
                    return None, False
                return last_stable, False
            if self.frame_interval_s:
                self.sleep(self.frame_interval_s)

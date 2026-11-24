"""The game loop (README §3.5): read a stable board, choose a move, touch the screen,
check the board changed the way it should, repeat.

  python -m solitaire.main --dry-run   suggest moves over the live mirror; you play them by hand
  python -m solitaire.main             the plotter plays

Start it on a dealt board (menus and the pre-game screen are for a person).
Stop it any time with Ctrl+C; the pencil lifts and parks on the zero.

The loop stops when the board is won, when the solver is stuck (it presses Finish
first if game.press_finish), when no stable board can be read game.max_unreadable
times in a row, or when a move leaves the board unchanged more than
game.max_missed_moves times (the tap didn't register: check pen-down, or re-zero).
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from solitaire.config import load_settings, repo_path
from solitaire.executor import Action, Executor
from solitaire.solver import Move, Solver
from solitaire.solver.moves import FOUNDATION, TABLEAU
from solitaire.state import GameState, StableReader


def landed(move: Move, before: GameState, after: GameState) -> bool:
    """Did the move do what the solver expected? Stock taps only need the board to change."""
    if move.is_stock:
        return after.signature != before.signature
    card = move.card.card
    if move.dst == FOUNDATION:
        return any(p and p.card.suit == card.suit and p.card.rank >= card.rank for p in after.foundations)
    if move.dst == TABLEAU:
        return any(p.card == card for p in after.tableau[move.dst_index].faceup)
    return False


class GameLoop:
    """The loop itself, with every piece injected so it runs on fakes in tests.

    dry_run: never touches the screen; prints the suggestion and waits for you to play.
    """

    def __init__(self, reader: StableReader, solver: Solver, executor: Executor, settings: dict,
                 dry_run: bool = False, log: Callable[[str], None] = print,
                 aim_check: Callable[[Action], bool] | None = None,
                 on_stable: Callable[[GameState], None] | None = None,
                 on_unreadable: Callable[[], None] | None = None,
                 on_mismatch: Callable[[Move, GameState, GameState], None] | None = None):
        """aim_check: called once, with the raised pencil over the first target; return
        False to stop (the zero is off). on_stable: sees every board the reader accepts."""
        self.reader, self.solver, self.executor = reader, solver, executor
        self.cfg = settings["game"]
        self.dry_run = dry_run
        self.log = log
        self.aim_check = aim_check
        self.aimed = False            # the first-tap aim check has been done
        self.on_stable = on_stable or (lambda s: None)
        self.on_unreadable = on_unreadable or (lambda: None)
        self.on_mismatch = on_mismatch or (lambda m, b, a: None)
        self.moves_made = 0
        self.mismatches = 0

    def _read_change(self, before: GameState) -> tuple[GameState | None, bool]:
        after, changed = self.reader.read_change(before)
        if after is not None:
            self.on_stable(after)
        return after, changed

    def _read(self) -> GameState | None:
        for _ in range(self.cfg["max_unreadable"]):
            state = self.reader.read()
            if state is not None:
                self.on_stable(state)
                return state
            self.log(f"  no stable board yet: {'; '.join(self.reader.last_issues) or 'reads keep changing'}")
        self.on_unreadable()
        return None

    def run(self) -> str:
        """Plays until it stops; returns why it stopped."""
        state = self._read()
        missed = 0
        while True:
            if state is None:
                return "no stable board (mirror dropped, or a menu is on screen)"
            if state.is_won:
                return "won"

            move = self.solver.choose_move(state)
            if move is None:
                self.log(f"\n{state}\n   {getattr(self.solver, 'last_plan', '') or 'stuck'}")
                if self.cfg["press_finish"] and not self.dry_run:
                    action = self.executor.plan_button("finish")
                    self.log(f"stuck -> {action}")
                    self.executor.perform(action)
                return "stuck (Finish)" if self.cfg["press_finish"] else "stuck"

            nudges = self.cfg["retry_nudges"]
            action = self.executor.plan(move, state, nudge=0.0 if self.dry_run else nudges[min(missed, len(nudges) - 1)])
            self.log(f"\n{state}\n=> {action}")
            if getattr(self.solver, "last_plan", ""):
                self.log(f"   {self.solver.last_plan}")

            if self.dry_run:
                self.log("   (dry run: play it by hand)")
                after, changed = self._read_change(state)
                while not changed:
                    after, changed = self._read_change(state)
                self.moves_made += 1
                # Whatever you played, the solver's stock memory follows the suggestion only if it matched.
                if landed(move, state, after):
                    self.solver.executed(move)
                state = after
                continue

            if self.aim_check is not None and not self.aimed:
                self.aimed = True
                self.executor.hover(action)
                if not self.aim_check(action):
                    return "stopped at the aim check"

            self.executor.perform(action)
            after, changed = self._read_change(state)
            if after is None:
                state = self._read()
                continue
            if not changed:
                missed += 1
                self.log(f"   board unchanged ({missed}/{self.cfg['max_missed_moves']})")
                if missed > self.cfg["max_missed_moves"]:
                    if self.aim_check is None:
                        return "moves stopped registering (check pen-down, re-zero the plotter)"
                    # Probably drift: re-aim on this card, then carry on.
                    target = self.executor.plan(move, state)
                    self.executor.hover(target)
                    if not self.aim_check(target):
                        return "moves stopped registering; stopped at the re-aim"
                    missed = 0
                state = after
                continue
            missed = 0
            self.moves_made += 1
            if landed(move, state, after):
                self.solver.executed(move)
            else:
                # The app's tap rule picked another place than predicted (README §3.3/§6).
                self.mismatches += 1
                self.log(f"   MISMATCH: {move} did not land as predicted; board now:\n{after}")
                self.on_mismatch(move, state, after)
            state = after


def make_read_state(source, normalizer, detector, builder, recorder=None) -> Callable[[], GameState]:
    def read_state() -> GameState:
        screen = normalizer.normalize(source.grab())
        h, w = screen.image.shape[:2]
        state = builder.build(detector.detect(screen.image), w, h)
        if not screen.aspect_ok:
            state.issues.append(f"mirror crop aspect {screen.aspect:.4f} is not the iPad's")
        if recorder is not None:
            recorder.add(state, screen.image)
        return state
    return read_state


def make_aim_check(plotter, axes, log: Callable[[str], None]) -> Callable[[Action], bool]:
    """The first tap of a session goes nowhere until you confirm the pencil is on target.
    If it isn't, you jog it onto the target and that spot becomes the target's mm
    position (a re-zero on the game board itself, no touch page needed)."""
    from solitaire.calibration.axes import DIRECTIONS
    from solitaire.plotter import GrblError

    def aim_check(action: Action) -> bool:
        target = action.points_mm[0]
        print(f"\nAIM CHECK: the raised pencil is over the middle of the card for: {action.label}")
        if input("Is the tip right over that card? [y = play / n = fix it] ").strip().lower().startswith("y"):
            return True
        print("Jog the tip over the card: up/down/left/right [mm] (screen directions), "
              "ok = it's on target now, quit = stop")
        while True:
            parts = input(f"[{plotter.pos_mm[0]:.1f}, {plotter.pos_mm[1]:.1f}] aim > ").split()
            if not parts:
                continue
            if parts[0] in ("quit", "q"):
                return False
            if parts[0] == "ok":
                dx, dy = target[0] - plotter.pos_mm[0], target[1] - plotter.pos_mm[1]
                plotter.set_position(*target)
                log(f"aim corrected by ({dx:+.1f}, {dy:+.1f}) mm: the pencil was that far from where "
                    "the plotter thought. Small and steady = the zero was off; growing during play = skipped steps.")
                return True
            if parts[0] in DIRECTIONS:
                try:
                    plotter.jog(*axes.screen_delta(parts[0], float(parts[1]) if len(parts) > 1 else 2))
                except (GrblError, ValueError) as e:
                    print(f"  {e}")
            else:
                print("  up/down/left/right [mm] | ok | quit")
    return aim_check


def main():
    settings = load_settings()
    pcfg, scr = settings["plotter"], settings["screen"]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="suggest moves only; the plotter isn't used")
    ap.add_argument("--port", default=pcfg["port"], help="COMx, or auto (default from settings)")
    ap.add_argument("--no-aim-check", action="store_true",
                    help="skip hovering over the first target and asking before the first tap")
    args = ap.parse_args()

    # Heavy imports here, so `--help` and the tests don't load YOLO or open ports.
    from solitaire.calibration import Axes, Calibration
    from solitaire.capture import ScreenNormalizer, open_source
    from solitaire.plotter import Grbl, GrblError, PortNotFound, find_port
    from solitaire.state import StateBuilder
    from solitaire.vision import CardDetector
    from solitaire.vision.misreads import MisreadRecorder, mismatch_confusion

    log_dir = repo_path(settings["game"]["log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.now():%Y%m%d_%H%M%S}{'_dry' if args.dry_run else ''}.log"
    log_file = open(log_path, "w", encoding="utf-8")

    def log(msg: str):
        print(msg)
        log_file.write(f"[{datetime.now():%H:%M:%S.%f}"[:-3] + f"] {msg}\n")
        log_file.flush()

    cal = Calibration.load()
    source = open_source(settings["capture"])
    normalizer = ScreenNormalizer(scr, settings["capture"])
    recorder = MisreadRecorder(repo_path(settings["game"]["misread_dir"]))
    reader = StableReader(make_read_state(source, normalizer, CardDetector(), StateBuilder(), recorder), settings)

    def on_stable(state: GameState):
        for true, read in recorder.settled(state):
            log(f"   misread: {true} read as {read} (frame saved for labelling)")

    def on_unreadable():
        recorder.save_unreadable()
        log("   last frame saved for labelling (unreadable board)")

    def on_mismatch(move: Move, before: GameState, after: GameState):
        pair = mismatch_confusion(move, before, after)
        if pair:
            recorder.save_mismatch(before, *pair)
            log(f"   misread on every frame: {pair[0]} read as {pair[1]} (frame saved for labelling)")

    plotter = None
    try:
        if not args.dry_run:
            try:
                port = find_port(args.port, pcfg.get("usb_ids"))
            except PortNotFound as e:
                sys.exit(str(e))
            bounds = cal.screen_bounds_mm(scr["width_px"], scr["height_px"], settings["game"]["bounds_margin_mm"])
            plotter = Grbl(port, pcfg["baud"], pcfg, bounds_mm=bounds)
            log(f"{plotter.banner} on {port}; safe area {tuple(round(b, 1) for b in bounds)} mm")

        loop = GameLoop(reader, Solver(settings), Executor(cal, plotter, settings), settings,
                        dry_run=args.dry_run, log=log, on_stable=on_stable,
                        on_unreadable=on_unreadable, on_mismatch=on_mismatch,
                        aim_check=None if args.no_aim_check or plotter is None
                        else make_aim_check(plotter, Axes.load(), log))
        t0 = time.monotonic()
        try:
            reason = loop.run()
        except KeyboardInterrupt:
            reason = "stopped by you (Ctrl+C)"
        except GrblError as e:
            reason = f"plotter error: {e}"
        log(f"\nStopped: {reason}. {loop.moves_made} moves in {time.monotonic() - t0:.0f} s, "
            f"{loop.mismatches} landed somewhere unexpected, {recorder.saved} misread frames saved. "
            f"Log: {log_path}")
    finally:
        if plotter is not None:
            try:
                # Opening the port resets GRBL and the zero becomes wherever the pencil is,
                # so always park on the zero before letting go.
                plotter.pen_up()
                plotter.move_to(0, 0)
            finally:
                plotter.close()
        source.close()
        log_file.close()


if __name__ == "__main__":
    main()

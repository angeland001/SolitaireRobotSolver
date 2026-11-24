"""The v3 game loop: v2's loop (solitaire/main.py) with solver v3 and Undo peeks.

  python -m solitaire.main_v3 --dry-run   suggest moves; you play them (and the Undos) by hand
  python -m solitaire.main_v3             the plotter plays

Same flags, settings, logs and safety as `python -m solitaire.main`, which stays the
working v2 backup and is not changed by this file.

A peek (README §3.4): the solver asks for a move that turns a face-down card over. The
loop plays it, reads the card that turned over, gives it to the solver, then presses
Undo and checks the board is back as it was. The app's Undo takes back only the last
move, so nothing may be played between the peek and the Undo. If the Undo doesn't
register, it is retried; if the board ends up somewhere else, play carries on from the
board as it really is (the peeked move then simply counts as played).
"""
import solitaire.main as v2
from solitaire.executor import Executor
from solitaire.solver.sampling import SolverV3
from solitaire.state import GameState, StableReader


class GameLoopV3(v2.GameLoop):
    def __init__(self, reader: StableReader, solver: SolverV3, executor: Executor, settings: dict, **kw):
        super().__init__(reader, solver, executor, settings, **kw)
        self.peeks = 0
        self._restart_state: GameState | None = None

    def run(self) -> str:
        """v2's loop, with peeks handled before a move is played for real."""
        solver = self.solver
        inner_choose = solver.choose_move

        def choose_move(state: GameState):
            # Peeks happen here, inside the move choice, so v2's loop never sees them: each
            # peek is played and undone, and the solver chooses again on the same board.
            for _ in range(solver.v3["max_peeks"] + 1):
                move = inner_choose(state)
                if move is None or solver.peek_col is None:
                    return move
                back = self._peek(move, solver.peek_col, state)
                if back is None:
                    raise _BoardMoved()
                if back.signature != state.signature:
                    raise _BoardMoved(back)
            solver.peek_col = None
            return move

        solver.choose_move = choose_move
        try:
            while True:
                try:
                    return super().run()
                except _BoardMoved as e:
                    # The peek or its Undo left a different board: continue from the real one.
                    self.log("   peek did not undo cleanly; carrying on from the board as it is")
                    self._restart_state = e.state
        finally:
            solver.choose_move = inner_choose

    def _read(self):
        # After a peek that didn't undo cleanly, start again from the board it left.
        state = self._restart_state
        if state is not None:
            self._restart_state = None
            return state
        return super()._read()

    def _peek(self, move, col: int, before: GameState) -> GameState | None:
        """Play the flip, read the card, Undo. Returns the board after the Undo (None if unreadable)."""
        action = self.executor.plan(move, before)
        self.log(f"\n{before}\n=> PEEK {action}\n   {self.solver.last_plan}")
        if self.dry_run:
            self.log("   (dry run: play it by hand, then press Undo)")
        else:
            self.executor.perform(action)
        after = self._wait_change(before, retry=None if self.dry_run else action)
        if after is None:
            return None
        n = len(before.tableau[col].facedown)
        column = after.tableau[col]
        if len(column.facedown) == n - 1 and column.faceup:
            card = column.faceup[0].card
            self.solver.record_peek(col, card, n)
            self.peeks += 1
            self.log(f"   peeked: col {col + 1}'s top face-down card is {card}")
        else:
            self.log(f"   peek did not turn col {col + 1} over as expected; board now:\n{after}")
            return after
        undo = self.executor.plan_button("undo")
        self.log(f"   undo -> {undo}" + ("  (dry run: press Undo)" if self.dry_run else ""))
        if not self.dry_run:
            self.executor.perform(undo)
        return self._wait_change(after, retry=None if self.dry_run else undo)

    def _wait_change(self, before: GameState, retry) -> GameState | None:
        """The next stable board that differs from `before`. Live, an unchanged board means
        the touch didn't register, so it is repeated (up to game.max_missed_moves times).
        A dry run waits as long as you take."""
        tries = 0
        while self.dry_run or tries <= self.cfg["max_missed_moves"]:
            tries += 1
            after, changed = self._read_change(before)
            if after is None:
                return self._read()
            if changed:
                return after
            if retry is not None:
                self.log("   board unchanged, touching again")
                self.executor.perform(retry)
        return None


class _BoardMoved(Exception):
    def __init__(self, state: GameState | None = None):
        super().__init__()
        self.state = state


def main():
    v2.Solver = SolverV3        # main() builds its solver and loop from these module names
    v2.GameLoop = GameLoopV3
    print("solver v3 (sampled hidden cards + Undo peeks); `python -m solitaire.main` is the v2 backup")
    v2.main()


if __name__ == "__main__":
    main()

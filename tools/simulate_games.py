"""Plays random Klondike draw-3 deals offline with the real Solver, to compare solver
versions and tune solver weights without the robot.

The solver sees what the camera would see: face-down cards only as a count, and only
the top waste card. Drags are assumed to land where intended, as in the real game.

Usage: python tools/simulate_games.py [--games 50] [--seed 1] [--v1]   (--v1: heuristic only)
"""
import argparse
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import load_settings  # noqa: E402
from solitaire.solver import Move, Solver  # noqa: E402
from solitaire.solver.moves import FOUNDATION, STOCK, TABLEAU, WASTE  # noqa: E402
from solitaire.state import Card, Column, GameState, PlacedCard  # noqa: E402
from solitaire.state.cards import FULL_DECK  # noqa: E402
from solitaire.vision.detection import FACEDOWN, Detection  # noqa: E402

DET = Detection(FACEDOWN, 1.0, 0, 0, 0, 0)


class Game:
    def __init__(self, rng: random.Random, draw_count: int = 3):
        deck = sorted(FULL_DECK)
        rng.shuffle(deck)
        self.down = [[deck.pop() for _ in range(i)] for i in range(7)]
        self.up = [[deck.pop()] for _ in range(7)]
        self.talon, self.ptr = deck, 0
        self.found: list[Card | None] = [None] * 4
        self.draw_count = draw_count

    def state(self) -> GameState:
        pc = lambda c: PlacedCard(c, Detection(str(c), 1.0, 0, 0, 0, 0))  # noqa: E731
        return GameState(
            foundations=[pc(c) if c else None for c in self.found],
            waste=[pc(self.talon[self.ptr - 1])] if self.ptr else [],
            stock=DET if self.ptr < len(self.talon) else None,
            tableau=[Column([DET] * len(d), [pc(c) for c in u]) for d, u in zip(self.down, self.up)],
        )

    def play(self, m: Move) -> None:
        if m.is_recycle:
            self.ptr = 0
            return
        if m.is_stock:
            self.ptr = min(self.ptr + self.draw_count, len(self.talon))
            return
        if m.src == WASTE:
            cards = [self.talon.pop(self.ptr - 1)]
            self.ptr -= 1
        else:
            col = self.up[m.src_index]
            cards = col[m.src_depth:]
            del col[m.src_depth:]
            if not col and self.down[m.src_index]:
                col.append(self.down[m.src_index].pop())
        if m.dst == FOUNDATION:
            self.found[m.dst_index] = cards[-1]
        else:
            self.up[m.dst_index].extend(cards)

    @property
    def on_foundations(self) -> int:
        return sum(c.rank for c in self.found if c)


def play_game(seed: int, settings: dict, max_moves: int = 600) -> tuple[int, int, float]:
    game = Game(random.Random(seed), settings["solver"].get("draw_count", 3))
    solver = Solver(settings)
    think = 0.0
    for n in range(max_moves):
        state = game.state()
        if state.is_won:
            return 52, n, think
        t = time.perf_counter()
        move = solver.choose_move(state)
        think = max(think, time.perf_counter() - t)
        if move is None:
            return game.on_foundations, n, think
        game.play(move)
        solver.executed(move)
    return game.on_foundations, max_moves, think


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--v1", action="store_true", help="heuristic v1 only (planner off)")
    args = ap.parse_args()
    settings = load_settings()
    if args.v1:
        settings["solver"] = {**settings["solver"], "plan": {"enabled": False}}

    results = []
    for g in range(args.games):
        results.append(play_game(args.seed + g, settings))
        print(f"  deal {args.seed + g}: {results[-1][0]:2d} cards up in {results[-1][1]} moves "
              f"(slowest move {results[-1][2]:.2f} s)")
    cards = [r[0] for r in results]
    print(f"{'v1' if args.v1 else 'v2'}: won {sum(c == 52 for c in cards)}/{len(cards)}, "
          f"foundation cards mean {statistics.mean(cards):.1f} median {statistics.median(cards)}, "
          f"moves mean {statistics.mean(r[1] for r in results):.0f}, "
          f"slowest move {max(r[2] for r in results):.2f} s")


if __name__ == "__main__":
    main()

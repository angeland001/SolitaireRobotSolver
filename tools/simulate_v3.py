"""Compares solver v2 and v3 on the same random draw-3 deals, offline and in parallel.

Uses the Game from simulate_games.py: the solver sees only what the camera would see.
A v3 peek is simulated as the app's single-step Undo would give it: the solver is told
the column's top face-down card and the board is left as it was. A peek counts as 2
actions (the move and the Undo).

Usage: python tools/simulate_v3.py [--games 200] [--seed 1] [--solvers v2,v3] [--no-peek]
                                   [--max-actions N]   (stop a game after N actions, a stand-in for the 5-minute clock)
                                   [--set samples=16 --set peek_margin=none ...]   (override solver.v3 values)
"""
import argparse
import multiprocessing as mp
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.config import load_settings  # noqa: E402
from solitaire.solver import Solver  # noqa: E402
from solitaire.solver.sampling import SolverV3  # noqa: E402
from tools.simulate_games import Game  # noqa: E402


def play(job: tuple) -> dict:
    name, seed, settings, max_actions = job
    game = Game(random.Random(seed), settings["solver"].get("draw_count", 3))
    solver = SolverV3(settings, seed=seed) if name == "v3" else Solver(settings)
    actions = peeks = 0
    think = 0.0
    result = "limit"
    while actions < max_actions:
        state = game.state()
        if state.is_won:
            result = "won"
            break
        t = time.perf_counter()
        move = solver.choose_move(state)
        think = max(think, time.perf_counter() - t)
        if move is None:
            result = "stuck"
            break
        col = getattr(solver, "peek_col", None)
        if col is not None:
            solver.record_peek(col, game.down[col][-1], len(game.down[col]))
            peeks += 1
            actions += 2
            continue
        game.play(move)
        solver.executed(move)
        actions += 1
    return {"name": name, "seed": seed, "cards": game.on_foundations, "won": result == "won",
            "result": result, "actions": actions, "peeks": peeks, "think": think}


def parse_value(v: str):
    if v.lower() in ("none", "null"):
        return None
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        return float(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--solvers", default="v2,v3")
    ap.add_argument("--no-peek", action="store_true")
    ap.add_argument("--max-actions", type=int, default=600)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--workers", type=int, default=2,
                    help="parallel games (each v3 move can think for solver.v3.max_seconds; more workers = more CPU)")
    args = ap.parse_args()

    settings = load_settings()
    v3 = dict(settings["solver"]["v3"])
    if args.no_peek:
        v3["peek"] = False
    for kv in args.set:
        k, v = kv.split("=", 1)
        v3[k] = parse_value(v)
    settings["solver"] = {**settings["solver"], "v3": v3}

    names = args.solvers.split(",")
    jobs = [(n, args.seed + g, settings, args.max_actions) for n in names for g in range(args.games)]
    t0 = time.time()
    results = []
    with mp.Pool(args.workers) as pool:
        for r in pool.imap_unordered(play, jobs, chunksize=1):
            results.append(r)
            if len(results) % 10 == 0 or len(results) == len(jobs):
                print(f"  {len(results)}/{len(jobs)} games done, {time.time() - t0:.0f} s", flush=True)
    print(f"{len(jobs)} games in {time.time() - t0:.0f} s; v3 settings: {v3}")
    for n in names:
        rs = [r for r in results if r["name"] == n]
        print(f"{n}: won {sum(r['won'] for r in rs)}/{len(rs)} ({100 * statistics.mean(r['won'] for r in rs):.1f}%), "
              f"foundation cards mean {statistics.mean(r['cards'] for r in rs):.1f}, "
              f"actions mean {statistics.mean(r['actions'] for r in rs):.0f}, "
              f"peeks mean {statistics.mean(r['peeks'] for r in rs):.1f}, "
              f"hit action limit {sum(r['result'] == 'limit' for r in rs)}, "
              f"slowest move {max(r['think'] for r in rs):.2f} s")
    if len(names) == 2:
        a = {r["seed"]: r["won"] for r in results if r["name"] == names[0]}
        b = {r["seed"]: r["won"] for r in results if r["name"] == names[1]}
        print(f"only {names[0]} won {sum(a[s] and not b[s] for s in a)}, only {names[1]} won "
              f"{sum(b[s] and not a[s] for s in a)}")


if __name__ == "__main__":
    main()

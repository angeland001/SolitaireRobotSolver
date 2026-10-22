"""Interactive plotter console: jog, tune the pen, run the direction test.

Usage: python tools/plotter_console.py [--port COM3]

Commands (type `help` inside):
  x 10 / y -5          move along a plotter axis (mm)
  up 5 / down 5 / left 5 / right 5
                       move in SCREEN directions (after `direction` has run)
  step 2               default distance for bare `x`, `left`, ...
  zero                 call the current pencil position (0, 0)
  goto 20 35           absolute move (mm)
  pos                  current position
  penup / pendown      raise / lower the pencil
  servo 70             set pen-down servo value live (M3 S70) to find the touch point
  tap                  pen down, dwell, pen up
  direction            find which way +X and +Y move on the iPad, save to config/plotter_axes.json
  info                 $I firmware build info
  settings             $$ dump, saved to config/grbl_settings.txt
  raw G0 X5            send any G-code line
  quit
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.calibration import Axes  # noqa: E402
from solitaire.calibration.axes import DIRECTIONS, validate  # noqa: E402
from solitaire.config import REPO_ROOT, load_settings  # noqa: E402
from solitaire.plotter import Grbl, GrblError  # noqa: E402


def ask_direction(axis: str) -> str:
    prompt = (f"Which way did the pencil move on the iPad for +{axis}? "
              "[up/down/left/right/diagonal/other]: ")
    while True:
        a = input(prompt).strip().lower()
        if a in DIRECTIONS or a in ("diagonal", "other"):
            return a


def direction_test(g: Grbl, step: float) -> Axes | None:
    print("\nHold the iPad in portrait, camera edge at the top. The pencil stays UP.")
    print(f"It will move +X by {step} mm, then back; then +Y by {step} mm, then back.")
    input("Make sure there's room around the pencil, then press Enter...")
    results = {}
    for axis in ("X", "Y"):
        dx, dy = (step, 0) if axis == "X" else (0, step)
        g.jog(dx, dy)
        results[axis] = ask_direction(axis)
        g.jog(-dx, -dy)
    problem = validate(results["X"], results["Y"])
    if problem:
        print(f"PROBLEM: {problem}")
        return None
    axes = Axes(results["X"], results["Y"])
    axes.save()
    print(f"Saved: +X -> {axes.plus_x}, +Y -> {axes.plus_y}  (config/plotter_axes.json)")
    return axes


def main():
    settings = load_settings()
    pcfg = settings["plotter"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=pcfg["port"])
    args = ap.parse_args()

    try:
        axes = Axes.load()
    except FileNotFoundError:
        axes = None
    step = float(pcfg["jog_step_mm"])

    print(f"Connecting to {args.port}...")
    g = Grbl(args.port, pcfg["baud"], pcfg)
    print(f"{g.banner}\nPencil is UP. Position is (0, 0) until you jog; use `zero` to set the origin.")
    if axes is None:
        print("No direction file yet - run `direction` first.")
    try:
        while True:
            try:
                parts = input(f"[{g.pos_mm[0]:.1f}, {g.pos_mm[1]:.1f}] > ").split()
            except EOFError:
                break
            if not parts:
                continue
            cmd, rest = parts[0].lower(), parts[1:]
            amount = float(rest[0]) if rest else step
            try:
                if cmd in ("quit", "exit", "q"):
                    break
                elif cmd == "help":
                    print(__doc__)
                elif cmd == "x":
                    g.jog(amount, 0)
                elif cmd == "y":
                    g.jog(0, amount)
                elif cmd in DIRECTIONS:
                    if axes is None:
                        print("Run `direction` first.")
                    else:
                        g.jog(*axes.screen_delta(cmd, amount))
                elif cmd == "step":
                    step = amount
                elif cmd == "zero":
                    g.set_zero()
                    print("This position is now (0, 0).")
                elif cmd == "goto":
                    g.move_to(float(rest[0]), float(rest[1]))
                elif cmd == "pos":
                    print(g.pos_mm, g.status())
                elif cmd == "penup":
                    g.pen_up()
                elif cmd == "pendown":
                    g.pen_down()
                elif cmd == "servo":
                    g.pen_down_cmd = f"M3 S{int(amount)}"
                    g.pen_down()
                    print(f"pen-down is now '{g.pen_down_cmd}' for this session; "
                          "put it in config/settings.yaml (plotter.pen_down) once taps register.")
                elif cmd == "tap":
                    g.tap()
                elif cmd == "direction":
                    axes = direction_test(g, step if step >= 10 else 20) or axes
                elif cmd == "info":
                    print("\n".join(g.build_info()))
                elif cmd == "settings":
                    lines = g.settings()
                    out = REPO_ROOT / "config" / "grbl_settings.txt"
                    out.write_text("\n".join(lines) + "\n")
                    print("\n".join(lines) + f"\nsaved to {out}")
                elif cmd == "raw":
                    print("\n".join(g.send(" ".join(rest))) or "ok")
                else:
                    print("unknown command - type `help`")
            except (GrblError, ValueError, IndexError) as e:
                print(f"error: {e}")
    finally:
        g.close()


if __name__ == "__main__":
    main()

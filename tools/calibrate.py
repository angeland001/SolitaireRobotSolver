"""Calibrate screen pixels <-> plotter mm by tapping and watching where taps land.

Needs: plotter connected, config/plotter_axes.json (plotter_console `direction`),
the iPad mirrored to this PC, and tools/touch_target.html open full-screen on
the iPad (it draws a dot wherever it is touched).

  1. You jog the pencil to the top-left, then bottom-right, of the area to calibrate.
  2. The plotter taps a grid between them; each new dot is found in the mirror.
  3. A homography is fitted, checked with fresh taps, and saved to config/calibration.json.
  4. The fit gives the screen's physical size, which is compared with the iPad's
     spec - this checks the capture crop and the 1640x2360 assumption end to end.

Usage: python tools/calibrate.py [--window TITLE | --camera N] [--cols 3 --rows 4]
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.calibration import Axes, Calibration  # noqa: E402
from solitaire.calibration.axes import DIRECTIONS  # noqa: E402
from solitaire.capture import ScreenNormalizer, open_source  # noqa: E402
from solitaire.config import REPO_ROOT, load_settings  # noqa: E402
from solitaire.plotter import Grbl, GrblError  # noqa: E402


class TapFinder:
    """Finds the dot a tap leaves by differencing the screen before and after it."""

    def __init__(self, source, normalizer):
        self.source, self.normalizer = source, normalizer

    def snapshot(self, n: int = 3) -> np.ndarray:
        frames = [cv2.cvtColor(self.normalizer.normalize(self.source.grab()).image, cv2.COLOR_BGR2GRAY)
                  for _ in range(n)]
        return np.median(np.stack(frames), axis=0).astype(np.uint8)

    def find(self, before: np.ndarray, after: np.ndarray) -> tuple[float, float] | None:
        diff = cv2.absdiff(before, after)
        _, mask = cv2.threshold(diff, 60, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, _, stats, centroids = cv2.connectedComponentsWithStats(mask)
        if n < 2:
            return None
        i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        if stats[i, cv2.CC_STAT_AREA] < 150:  # a dot is ~2400 px at native resolution
            return None
        return float(centroids[i][0]), float(centroids[i][1])


def jog_to(g: Grbl, axes: Axes, label: str) -> tuple[float, float]:
    print(f"\nJog the pencil (UP) over the {label} of the area to calibrate.")
    print("  Commands: up/down/left/right [mm], tap (test), ok (accept)")
    while True:
        parts = input(f"[{g.pos_mm[0]:.1f}, {g.pos_mm[1]:.1f}] {label} > ").split()
        if not parts:
            continue
        if parts[0] == "ok":
            return g.pos_mm
        if parts[0] == "tap":
            g.tap()
        elif parts[0] in DIRECTIONS:
            g.jog(*axes.screen_delta(parts[0], float(parts[1]) if len(parts) > 1 else 5))
        else:
            print("  up/down/left/right [mm] | tap | ok")


def tap_and_find(g, finder, x_mm, y_mm):
    g.move_to(x_mm, y_mm)
    before = finder.snapshot()
    g.tap()
    time.sleep(0.4)  # mirror latency
    return finder.find(before, finder.snapshot())


def rezero(g: Grbl, axes: Axes, finder: TapFinder):
    """After a power cycle the plotter's zero is wherever it woke up. One observed
    tap tells us where the pencil really is, via the saved calibration."""
    cal = Calibration.load()
    jog_to(g, axes, "MIDDLE of the touch page")
    before = finder.snapshot()
    g.tap()
    time.sleep(0.4)
    px = finder.find(before, finder.snapshot())
    if px is None:
        sys.exit("Tap not seen - check the touch page and pen-down value.")
    x, y = cal.px_to_mm(*px)
    g.set_position(x, y)
    print(f"Tap landed at ({px[0]:.0f}, {px[1]:.0f}) px -> pencil is at ({x:.1f}, {y:.1f}) mm. Zero restored.")


def main():
    settings = load_settings()
    pcfg, scr = settings["plotter"], settings["screen"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=pcfg["port"])
    ap.add_argument("--window")
    ap.add_argument("--camera", type=int)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--rezero", action="store_true",
                    help="restore the zero after a reset with one tap, using the saved calibration")
    args = ap.parse_args()

    cfg = dict(settings["capture"])
    if args.window:
        cfg.update(source="window", window_title=args.window)
    elif args.camera is not None:
        cfg.update(source="camera", camera_index=args.camera)

    axes = Axes.load()
    source = open_source(cfg)
    normalizer = ScreenNormalizer(scr, cfg)
    first = normalizer.normalize(source.grab())
    if not first.aspect_ok:
        sys.exit(f"Mirror crop aspect {first.aspect:.4f} != iPad 0.6949 - fix capture first "
                 "(check with tools/live_view.py).")
    finder = TapFinder(source, normalizer)
    g = Grbl(args.port, pcfg["baud"], pcfg)
    print(g.banner)
    print("\nOn the iPad: open touch_target.html full-screen (see README §4.3 C).")

    try:
        if args.rezero:
            rezero(g, axes, finder)
            return
        a = jog_to(g, axes, "TOP-LEFT")
        g.set_zero()
        a = (0.0, 0.0)
        b = jog_to(g, axes, "BOTTOM-RIGHT")

        pts_mm, pts_px = [], []
        for v in np.linspace(0, 1, args.rows):
            for u in np.linspace(0, 1, args.cols):
                x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * v
                px = tap_and_find(g, finder, x, y)
                status = f"({px[0]:.0f}, {px[1]:.0f}) px" if px else "NOT FOUND"
                print(f"  tap ({x:6.1f}, {y:6.1f}) mm -> {status}")
                if px:
                    pts_mm.append((x, y))
                    pts_px.append(px)
        g.move_to(0, 0)

        if len(pts_px) < 6:
            sys.exit(f"Only {len(pts_px)} taps were seen; need 6+. Check the touch page, "
                     "the pen-down value, and the mirror.")
        cal = Calibration.fit(pts_px, pts_mm)
        print(f"\nFit: {cal.n_points} points, RMS error {cal.rms_mm:.2f} mm")

        # Check with taps that weren't in the fit, aimed in screen pixels
        w, h = scr["width_px"], scr["height_px"]
        lo = np.array(pts_px).min(axis=0)
        hi = np.array(pts_px).max(axis=0)
        errs = []
        for fu, fv in ((0.25, 0.3), (0.75, 0.5), (0.5, 0.8)):
            target = (lo[0] + (hi[0] - lo[0]) * fu, lo[1] + (hi[1] - lo[1]) * fv)
            got = tap_and_find(g, finder, *cal.px_to_mm(*target))
            if got:
                err_px = float(np.hypot(got[0] - target[0], got[1] - target[1]))
                errs.append(err_px)
                print(f"  check: aimed ({target[0]:.0f}, {target[1]:.0f}) px, "
                      f"hit ({got[0]:.0f}, {got[1]:.0f}) -> off by {err_px:.0f} px")
        g.move_to(0, 0)

        width_mm, height_mm = cal.mm_per_px(w, h)
        spec_w, spec_h = w / scr["ppi"] * 25.4, h / scr["ppi"] * 25.4
        print(f"\nScreen size from the fit: {width_mm:.1f} x {height_mm:.1f} mm "
              f"(iPad spec {spec_w:.1f} x {spec_h:.1f} mm)")
        off = max(abs(width_mm / spec_w - 1), abs(height_mm / spec_h - 1))
        print("  pixel dimensions CONSISTENT" if off < 0.03 else
              f"  MISMATCH {off:.0%}: the capture crop or the screen size setting is wrong")
        x0, x1, y0, y1 = cal.screen_bounds_mm(w, h)
        print(f"Whole screen spans X {x0:.1f}..{x1:.1f} mm, Y {y0:.1f}..{y1:.1f} mm "
              f"from the zero (top-left start corner). Compare with GRBL $130/$131 travel.")

        cal.save()
        print(f"\nSaved {REPO_ROOT / 'config' / 'calibration.json'}"
              + (f" | check taps within {max(errs):.0f} px" if errs else ""))
        print("Remember: the zero is the TOP-LEFT start corner. Re-zero there after any reset.")
    except GrblError as e:
        print(f"Plotter error: {e}")
    finally:
        g.close()
        source.close()


if __name__ == "__main__":
    main()

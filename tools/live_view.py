"""Live card detection on the mirrored iPad screen.

Shows the normalised screen with detections, layout guides and the parsed
game state. The console prints the state whenever it changes.

Keys (in the video window):  q quit | s save frame to captures/ | g toggle guides

Usage:
  python tools/live_view.py --list-windows                 find the AirPlay receiver's title
  python tools/live_view.py --window "Receiver title"      mirror window
  python tools/live_view.py --camera 1                     HDMI capture card / OBS camera
  python tools/live_view.py --image shot.png               a still image, for testing
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from solitaire.capture import ScreenNormalizer, list_windows, open_source  # noqa: E402
from solitaire.config import REPO_ROOT, load_settings  # noqa: E402
from solitaire.state import StateBuilder  # noqa: E402
from solitaire.vision import CardDetector  # noqa: E402

GREEN, GREY, RED, YELLOW, WHITE = (0, 200, 0), (150, 150, 150), (0, 0, 255), (0, 220, 255), (255, 255, 255)


class StillSource:
    def __init__(self, path):
        self.frame = cv2.imread(str(path))

    def grab(self):
        return self.frame.copy()

    def close(self):
        pass


def draw(screen, dets, state, layout, guides, fps):
    img = screen.image.copy()
    h, w = img.shape[:2]
    if guides:
        for cx in layout["column_x"]:
            cv2.line(img, (int(cx * w), int(layout["top_row_max_y"] * h)), (int(cx * w), h), YELLOW, 1)
        cv2.line(img, (0, int(layout["top_row_max_y"] * h)), (w, int(layout["top_row_max_y"] * h)), YELLOW, 1)
        x0, x1 = layout["waste_x_range"]
        cv2.rectangle(img, (int(x0 * w), int(0.12 * h)), (int(x1 * w), int(layout["top_row_max_y"] * h)), YELLOW, 1)
    for d in dets:
        p1, p2 = (int(d.x1_px), int(d.y1_px)), (int(d.x2_px), int(d.y2_px))
        cv2.rectangle(img, p1, p2, GREY if d.is_facedown else GREEN, 3)
        if not d.is_facedown:
            cv2.putText(img, f"{d.label} {d.conf:.2f}", (p1[0] + 4, p1[1] + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, RED, 2)

    cw, ch = screen.raw_size
    lines = [
        f"{fps:4.1f} fps | crop {cw}x{ch} aspect {screen.aspect:.4f} "
        + ("OK" if screen.aspect_ok else "MISMATCH (expected 0.6949)"),
        "state: VALID" if state.is_valid else f"state: INVALID - {state.issues[0]}",
    ]
    for i, text in enumerate(lines):
        y = h - 70 + i * 40
        cv2.putText(img, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 6)
        ok = screen.aspect_ok if i == 0 else state.is_valid
        cv2.putText(img, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 1.1, WHITE if ok else RED, 2)
    return img


def main():
    settings = load_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-windows", action="store_true")
    ap.add_argument("--window", help="part of the mirror window title")
    ap.add_argument("--camera", type=int, help="video device index")
    ap.add_argument("--monitor", type=int)
    ap.add_argument("--image", help="run on a still image instead")
    ap.add_argument("--conf", type=float)
    ap.add_argument("--display-height", type=int, default=1000)
    args = ap.parse_args()

    if args.list_windows:
        for _, title in list_windows():
            print(" ", title)
        return

    cfg = dict(settings["capture"])
    if args.window is not None:
        cfg.update(source="window", window_title=args.window)
    elif args.camera is not None:
        cfg.update(source="camera", camera_index=args.camera)
    elif args.monitor is not None:
        cfg.update(source="monitor", monitor=args.monitor)
    if cfg["source"] == "window" and not cfg["window_title"] and not args.image:
        sys.exit("Set capture.window_title in config/settings.yaml or pass --window/--camera/--monitor")

    source = StillSource(args.image) if args.image else open_source(cfg)
    normalizer = ScreenNormalizer(settings["screen"], cfg)
    detector = CardDetector(conf=args.conf)
    builder = StateBuilder()
    layout = settings["layout"]
    save_dir = REPO_ROOT / "captures"

    guides, last_state, fps, t_prev = True, None, 0.0, time.perf_counter()
    cv2.namedWindow("live", cv2.WINDOW_NORMAL)
    try:
        while True:
            screen = normalizer.normalize(source.grab())
            dets = detector.detect(screen.image)
            state = builder.build(dets, screen.image.shape[1], screen.image.shape[0])

            text = str(state)
            if text != last_state:
                print(f"\n[{datetime.now():%H:%M:%S}] {len(dets)} boxes\n{text}")
                last_state = text

            now = time.perf_counter()
            fps = 0.8 * fps + 0.2 / max(now - t_prev, 1e-6)
            t_prev = now
            view = draw(screen, dets, state, layout, guides, fps)
            scale = args.display_height / view.shape[0]
            cv2.imshow("live", cv2.resize(view, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or cv2.getWindowProperty("live", cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("g"):
                guides = not guides
            if key == ord("s"):
                save_dir.mkdir(exist_ok=True)
                path = save_dir / f"{datetime.now():%Y%m%d_%H%M%S_%f}.png"
                cv2.imwrite(str(path), screen.image)
                print(f"saved {path}")
    finally:
        source.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

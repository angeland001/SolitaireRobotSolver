"""Screen pixels (normalised 1640x2360) <-> plotter millimetres.

A homography fitted from tap pairs. It absorbs axis swaps, inversions, a
slightly rotated iPad and small skew, so nothing about orientation is
hard-coded. Produced by tools/calibrate.py, saved to config/calibration.json.
"""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from solitaire.config import REPO_ROOT

CALIBRATION_PATH = REPO_ROOT / "config" / "calibration.json"


@dataclass
class Calibration:
    px_to_mm_h: np.ndarray      # 3x3
    rms_mm: float               # fit error over the calibration taps
    n_points: int
    created: str

    @classmethod
    def fit(cls, pts_px: list[tuple[float, float]], pts_mm: list[tuple[float, float]]) -> "Calibration":
        if len(pts_px) < 4:
            raise ValueError("need at least 4 point pairs")
        src = np.asarray(pts_px, np.float64)
        dst = np.asarray(pts_mm, np.float64)
        h, _ = cv2.findHomography(src, dst, 0)
        if h is None:
            raise ValueError("points are degenerate (collinear?)")
        cal = cls(h, 0.0, len(src), datetime.now().isoformat(timespec="seconds"))
        err = np.linalg.norm(cal.px_to_mm_many(src) - dst, axis=1)
        cal.rms_mm = float(np.sqrt((err ** 2).mean()))
        return cal

    def px_to_mm_many(self, pts_px) -> np.ndarray:
        pts = np.asarray(pts_px, np.float64).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.px_to_mm_h).reshape(-1, 2)

    def mm_to_px_many(self, pts_mm) -> np.ndarray:
        pts = np.asarray(pts_mm, np.float64).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, np.linalg.inv(self.px_to_mm_h)).reshape(-1, 2)

    def px_to_mm(self, x_px: float, y_px: float) -> tuple[float, float]:
        x, y = self.px_to_mm_many([(x_px, y_px)])[0]
        return float(x), float(y)

    def mm_per_px(self, width_px: int, height_px: int) -> tuple[float, float]:
        """Physical size of the screen implied by the fit (mm across, mm down)."""
        c = self.px_to_mm_many([(0, 0), (width_px, 0), (0, height_px)])
        return float(np.linalg.norm(c[1] - c[0])), float(np.linalg.norm(c[2] - c[0]))

    def screen_bounds_mm(self, width_px: int, height_px: int,
                         margin_mm: float = 0.0) -> tuple[float, float, float, float]:
        """(x_min, x_max, y_min, y_max) in mm covering the screen, shrunk by a margin."""
        c = self.px_to_mm_many([(0, 0), (width_px, 0), (0, height_px), (width_px, height_px)])
        return (float(c[:, 0].min() + margin_mm), float(c[:, 0].max() - margin_mm),
                float(c[:, 1].min() + margin_mm), float(c[:, 1].max() - margin_mm))

    def save(self, path: Path = CALIBRATION_PATH):
        path.write_text(json.dumps({
            "px_to_mm_homography": self.px_to_mm_h.tolist(),
            "rms_mm": self.rms_mm,
            "n_points": self.n_points,
            "created": self.created,
        }, indent=2) + "\n")

    @classmethod
    def load(cls, path: Path = CALIBRATION_PATH) -> "Calibration":
        d = json.loads(path.read_text())
        return cls(np.array(d["px_to_mm_homography"]), d["rms_mm"], d["n_points"], d["created"])

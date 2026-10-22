"""Raw frame -> the iPad screen at native resolution (1640x2360 portrait).

Every downstream module works in these normalised screen pixels, so the
detector, the layout and the calibration all agree no matter how the screen
was captured. The crop is found by trimming the black bars a receiver or
capture card puts around the mirrored image; its aspect ratio is checked
against the iPad's to catch a wrong crop, a rotated screen or a cut-off edge.
"""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ScreenFrame:
    image: np.ndarray                       # BGR, screen width_px x height_px
    crop_raw: tuple[int, int, int, int]     # x, y, w, h of the iPad screen inside the raw frame
    aspect: float                           # measured w/h of the crop
    aspect_ok: bool

    @property
    def raw_size(self) -> tuple[int, int]:
        return self.crop_raw[2], self.crop_raw[3]


class ScreenNormalizer:
    def __init__(self, screen_cfg: dict, capture_cfg: dict):
        self.width_px = screen_cfg["width_px"]
        self.height_px = screen_cfg["height_px"]
        self.expected_aspect = self.width_px / self.height_px
        self.black_threshold = capture_cfg["black_threshold"]
        self.aspect_tolerance = capture_cfg["aspect_tolerance"]
        self.rotate = capture_cfg.get("rotate", 0)

    def find_screen(self, frame: np.ndarray) -> tuple[int, int, int, int]:
        bright = frame.max(axis=2) > self.black_threshold
        cols = np.flatnonzero(bright.mean(axis=0) > 0.25)
        if cols.size == 0:
            return 0, 0, frame.shape[1], frame.shape[0]
        x0, x1 = int(cols[0]), int(cols[-1])

        # Window chrome (e.g. a receiver's own title bar) is lit across the black
        # side bars too; the mirrored screen never is. Drop those rows.
        sides = np.hstack([bright[:, :x0], bright[:, x1 + 1:]])
        chrome = sides.mean(axis=1) > 0.5 if sides.shape[1] >= 4 else np.zeros(len(bright), bool)
        rows = np.flatnonzero((bright[:, x0:x1 + 1].mean(axis=1) > 0.25) & ~chrome)
        if rows.size == 0:
            return x0, 0, x1 - x0 + 1, frame.shape[0]
        y0, y1 = int(rows[0]), int(rows[-1])

        # Still too tall for the iPad's shape (chrome without side bars): keep the
        # bottom-most iPad-shaped region, since title bars sit on top.
        w, h = x1 - x0 + 1, y1 - y0 + 1
        expected_h = round(w / self.expected_aspect)
        if h > expected_h * (1 + self.aspect_tolerance):
            y0 = y1 - expected_h + 1
            h = expected_h
        return x0, y0, w, h

    def normalize(self, frame: np.ndarray) -> ScreenFrame:
        if self.rotate:
            frame = cv2.rotate(frame, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
                                       270: cv2.ROTATE_90_COUNTERCLOCKWISE}[self.rotate])
        x, y, w, h = self.find_screen(frame)
        aspect = w / h
        ok = abs(aspect / self.expected_aspect - 1) <= self.aspect_tolerance
        image = cv2.resize(frame[y:y + h, x:x + w], (self.width_px, self.height_px),
                           interpolation=cv2.INTER_CUBIC if w < self.width_px else cv2.INTER_AREA)
        return ScreenFrame(image, (x, y, w, h), aspect, ok)

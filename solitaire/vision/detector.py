"""YOLO card detector: screen image in, labelled boxes out (in image pixels)."""
from pathlib import Path

import numpy as np
from ultralytics import YOLO

from solitaire.config import load_settings, repo_path
from solitaire.vision.detection import Detection


class CardDetector:
    def __init__(self, weights: str | Path | None = None, conf: float | None = None):
        vision = load_settings()["vision"]
        self.model = YOLO(str(repo_path(weights or vision["weights"])))
        self.conf = conf if conf is not None else vision["conf_threshold"]
        self.imgsz = vision["imgsz"]

    def detect(self, image: np.ndarray | str | Path) -> list[Detection]:
        """Accepts a BGR array (OpenCV convention) or an image path."""
        result = self.model.predict(
            image if isinstance(image, np.ndarray) else str(image),
            imgsz=self.imgsz, conf=self.conf, verbose=False,
            agnostic_nms=True,  # one label per box: overlapping guesses of different cards collapse
        )[0]
        names = result.names
        return [
            Detection(names[int(c)], float(p), *map(float, xyxy))
            for xyxy, c, p in zip(result.boxes.xyxy.tolist(),
                                  result.boxes.cls.tolist(),
                                  result.boxes.conf.tolist())
        ]

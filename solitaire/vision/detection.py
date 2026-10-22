"""Detection record, kept apart from the detector so state code doesn't import YOLO."""
from dataclasses import dataclass

FACEDOWN = "facedown"


@dataclass(frozen=True)
class Detection:
    label: str          # "<rank><suit>" e.g. "10h", "Qs", or "facedown"
    conf: float
    x1_px: float
    y1_px: float
    x2_px: float
    y2_px: float

    @property
    def is_facedown(self) -> bool:
        return self.label == FACEDOWN

    @property
    def center_px(self) -> tuple[float, float]:
        return ((self.x1_px + self.x2_px) / 2, (self.y1_px + self.y2_px) / 2)

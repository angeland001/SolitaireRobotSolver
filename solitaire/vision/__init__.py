from .detection import Detection


def __getattr__(name):
    # Lazy: importing CardDetector pulls in torch/ultralytics, which state code doesn't need.
    if name == "CardDetector":
        from .detector import CardDetector
        return CardDetector
    raise AttributeError(name)


__all__ = ["CardDetector", "Detection"]

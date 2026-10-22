"""Where frames of the iPad screen come from.

- window:  an AirPlay receiver's window on this PC (captured by title, client area only)
- camera:  a video device, e.g. a USB HDMI capture card fed by a USB-C->HDMI adapter,
           or OBS Virtual Camera
- monitor: a whole monitor (fallback when the window can't be found)
"""
import ctypes
import sys
from ctypes import wintypes

import cv2
import mss
import numpy as np

if sys.platform == "win32":
    try:  # physical pixels, so window rects match what mss captures on scaled displays
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        pass
    user32 = ctypes.windll.user32


def list_windows() -> list[tuple[int, str]]:
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(callback, 0)
    return found


class WindowSource:
    """Captures a window's own content with PrintWindow, so it works even when
    other windows cover it (it must not be minimised)."""

    PW_CLIENTONLY_RENDERFULLCONTENT = 0x1 | 0x2

    def __init__(self, title: str):
        matches = [(h, t) for h, t in list_windows() if title.lower() in t.lower()]
        if not matches:
            raise RuntimeError(f"No visible window with {title!r} in its title. "
                               f"Run tools/live_view.py --list-windows to see titles.")
        self.hwnd, self.title = matches[0]
        self.gdi32 = ctypes.windll.gdi32

    def grab(self) -> np.ndarray:
        if user32.IsIconic(self.hwnd):
            raise RuntimeError(f"Window {self.title!r} is minimised - restore it (it can stay behind others)")
        rect = wintypes.RECT()
        user32.GetClientRect(self.hwnd, ctypes.byref(rect))
        w, h = rect.right, rect.bottom
        if w <= 0 or h <= 0:
            raise RuntimeError(f"Window {self.title!r} has no client area")

        gdi = self.gdi32
        hwnd_dc = user32.GetDC(self.hwnd)
        mem_dc = gdi.CreateCompatibleDC(hwnd_dc)
        bitmap = gdi.CreateCompatibleBitmap(hwnd_dc, w, h)
        old = gdi.SelectObject(mem_dc, bitmap)
        try:
            user32.PrintWindow(self.hwnd, mem_dc, self.PW_CLIENTONLY_RENDERFULLCONTENT)
            # BITMAPINFOHEADER for a top-down 32-bit DIB
            header = (ctypes.c_uint32 * 10)(40, w, (-h) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
            buf = np.empty((h, w, 4), np.uint8)
            gdi.GetDIBits(mem_dc, bitmap, 0, h, buf.ctypes.data_as(ctypes.c_void_p), header, 0)
        finally:
            gdi.SelectObject(mem_dc, old)
            gdi.DeleteObject(bitmap)
            gdi.DeleteDC(mem_dc)
            user32.ReleaseDC(self.hwnd, hwnd_dc)
        return buf[:, :, :3].copy()

    def close(self):
        pass


class MonitorSource:
    def __init__(self, index: int = 1):
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[index]

    def grab(self) -> np.ndarray:
        return np.asarray(self.sct.grab(self.monitor))[:, :, :3].copy()

    def close(self):
        self.sct.close()


class CameraSource:
    def __init__(self, index: int, width: int = 1920, height: int = 1080):
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video device {index}")

    def grab(self) -> np.ndarray:
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("Video device returned no frame")
        return frame

    def close(self):
        self.cap.release()


def open_source(cfg: dict):
    kind = cfg["source"]
    if kind == "window":
        return WindowSource(cfg["window_title"])
    if kind == "camera":
        return CameraSource(cfg["camera_index"])
    if kind == "monitor":
        return MonitorSource(cfg["monitor"])
    raise ValueError(f"unknown capture source {kind!r}")

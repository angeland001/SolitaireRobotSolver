"""GRBL 1.1 (servo-pen fork) over USB serial.

Positions are plotter millimetres relative to the work zero set with
set_zero(). There are no limit switches, so the zero is wherever the pencil
was when set_zero() ran - re-zero after any reset or power cycle.

The driver tracks position itself from the absolute moves it sends, so it
doesn't depend on the status-report mask ($10).
"""
import re
import time

import serial


class GrblError(RuntimeError):
    pass


class Grbl:
    def __init__(self, port: str, baud: int = 115200, plotter_cfg: dict | None = None,
                 bounds_mm: tuple[float, float, float, float] | None = None):
        cfg = plotter_cfg or {}
        self.pen_up_cmd = cfg.get("pen_up", "M3 S0")
        self.pen_down_cmd = cfg.get("pen_down", "M3 S90")
        self.settle_s = cfg.get("servo_settle_s", 0.15)
        self.tap_dwell_s = cfg.get("tap_dwell_s", 0.08)
        self.drag_feed = cfg.get("drag_feed", 1500)
        self.bounds_mm = bounds_mm          # (x_min, x_max, y_min, y_max) or None
        self.pos_mm = (0.0, 0.0)

        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.banner = self._wait_banner()
        state = self.status()
        if state.startswith("Alarm"):
            # No homing switches: an alarm at boot only means "position unknown"
            self.send("$X")
        self.send("G21 G90")                # millimetres, absolute
        self.pen_up()

    # ---- low level -------------------------------------------------------
    def _wait_banner(self, timeout_s: float = 4.0) -> str:
        time.sleep(1.5)                     # opening the port resets the Arduino
        self.ser.write(b"\r\n\r\n")
        end = time.time() + timeout_s
        while time.time() < end:
            line = self.ser.readline().decode(errors="replace").strip()
            if line.startswith("Grbl"):
                time.sleep(0.2)
                self.ser.reset_input_buffer()
                return line
        raise GrblError("No GRBL banner - wrong COM port, or the board isn't running GRBL")

    def send(self, line: str, timeout_s: float = 30.0) -> list[str]:
        """Send one line and wait for 'ok'. Returns any other lines GRBL printed."""
        self.ser.write((line.strip() + "\n").encode())
        out, end = [], time.time() + timeout_s
        while time.time() < end:
            resp = self.ser.readline().decode(errors="replace").strip()
            if not resp:
                continue
            if resp == "ok":
                return out
            if resp.startswith(("error", "ALARM")):
                raise GrblError(f"{line!r} -> {resp}")
            out.append(resp)
        raise GrblError(f"Timeout waiting for ok after {line!r}")

    def status(self) -> str:
        """Machine state from a '?' report, e.g. 'Idle', 'Run', 'Alarm'."""
        self.ser.write(b"?")
        end = time.time() + 2
        while time.time() < end:
            resp = self.ser.readline().decode(errors="replace").strip()
            if resp.startswith("<"):
                return re.split(r"[|,>]", resp[1:])[0]
        raise GrblError("No status report")

    def wait_idle(self, timeout_s: float = 30.0):
        end = time.time() + timeout_s
        while time.time() < end:
            if self.status() == "Idle":
                return
            time.sleep(0.03)
        raise GrblError("Plotter never went idle")

    # ---- info ------------------------------------------------------------
    def build_info(self) -> list[str]:
        return self.send("$I")

    def settings(self) -> list[str]:
        return self.send("$$")

    # ---- motion ----------------------------------------------------------
    def set_zero(self):
        """Declare the current pencil position as (0, 0)."""
        self.set_position(0.0, 0.0)

    def set_position(self, x: float, y: float):
        """Declare the current pencil position to be (x, y) mm, without moving."""
        self.send(f"G92 X{x:.3f} Y{y:.3f}")
        self.pos_mm = (x, y)

    def _check(self, x: float, y: float):
        if self.bounds_mm:
            x0, x1, y0, y1 = self.bounds_mm
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                raise GrblError(f"({x:.1f}, {y:.1f}) mm is outside the safe area {self.bounds_mm}")

    def move_to(self, x: float, y: float, wait: bool = True):
        """Pen-up travel at max rate."""
        self._check(x, y)
        self.send(f"G0 X{x:.3f} Y{y:.3f}")
        self.pos_mm = (x, y)
        if wait:
            self.wait_idle()

    def jog(self, dx: float, dy: float):
        x, y = self.pos_mm
        self.move_to(x + dx, y + dy)

    def pen_up(self):
        self.send(self.pen_up_cmd)
        self.send(f"G4 P{self.settle_s:.3f}")

    def pen_down(self):
        self.send(self.pen_down_cmd)
        self.send(f"G4 P{self.settle_s:.3f}")

    def tap(self, x: float | None = None, y: float | None = None):
        if x is not None:
            self.move_to(x, y, wait=False)
        self.pen_down()
        self.send(f"G4 P{self.tap_dwell_s:.3f}")
        self.pen_up()
        self.wait_idle()

    def drag(self, x0: float, y0: float, x1: float, y1: float):
        self._check(x1, y1)
        self.move_to(x0, y0, wait=False)
        self.pen_down()
        self.send(f"G1 X{x1:.3f} Y{y1:.3f} F{self.drag_feed}")
        self.pos_mm = (x1, y1)
        self.pen_up()
        self.wait_idle()

    def close(self):
        try:
            self.pen_up()
            self.wait_idle()
        finally:
            self.ser.close()

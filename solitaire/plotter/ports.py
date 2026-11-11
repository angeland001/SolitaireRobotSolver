"""Find the plotter's COM port.

Windows can give the board a new COM number when it's plugged into a different
USB port, so `plotter.port: auto` looks it up by the USB chip's vendor:product
ID (`plotter.usb_ids`) instead of trusting a fixed number.
"""
from serial.tools import list_ports


class PortNotFound(RuntimeError):
    pass


def _describe_ports() -> str:
    ports = list(list_ports.comports())
    if not ports:
        return "  (no serial ports found - is the USB cable plugged in?)"
    return "\n".join(f"  {p.device}: {p.description} [{p.hwid}]" for p in ports)


def find_port(port: str, usb_ids: list[str] | None = None) -> str:
    """Return a COM port name. `port` is either a fixed name (returned as is) or 'auto'."""
    if str(port).lower() != "auto":
        return port
    wanted = set()
    for uid in usb_ids or []:
        vid, pid = (int(x, 16) for x in uid.split(":"))
        wanted.add((vid, pid))
    matches = [p for p in list_ports.comports() if (p.vid, p.pid) in wanted]
    if len(matches) == 1:
        return matches[0].device
    if not matches:
        raise PortNotFound(
            f"No serial port with USB ID {', '.join(usb_ids or [])}. Ports present:\n"
            f"{_describe_ports()}\nPass --port COMx, or add the plotter's ID to plotter.usb_ids.")
    raise PortNotFound(
        "More than one port matches plotter.usb_ids:\n"
        + "\n".join(f"  {p.device}: {p.description}" for p in matches)
        + "\nPass --port COMx to pick one.")

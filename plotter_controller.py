"""
Python controller for Chinese pen plotter with GRBL firmware
"""
import serial
import time
from typing import List, Tuple


class PenPlotter:
    def __init__(self, port: str = 'COM3', baudrate: int = 115200):
        """
        Initialize connection to the plotter
        
        Args:
            port: Serial port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate: Communication speed (default 115200 for GRBL)
        """
        self.ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset
        
        # Wake up GRBL
        self.ser.write(b"\r\n\r\n")
        time.sleep(2)
        self.ser.flushInput()
        
        print("Plotter connected!")
        self._read_response()
    
    def _send_command(self, command: str) -> str:
        """Send a G-code command and wait for response"""
        self.ser.write((command + '\n').encode())
        return self._read_response()
    
    def _read_response(self) -> str:
        """Read response from GRBL"""
        response = []
        while True:
            line = self.ser.readline().decode().strip()
            if line:
                response.append(line)
                print(f"<- {line}")
                if 'ok' in line or 'error' in line:
                    break
            else:
                break
        return '\n'.join(response)
    
    def home(self):
        """Home the plotter (requires limit switches)"""
        print("Homing...")
        self._send_command("$H")
    
    def move_to(self, x: float, y: float, feed_rate: int = 1000):
        """
        Move to absolute position (pen up)
        
        Args:
            x: X coordinate in mm
            y: Y coordinate in mm
            feed_rate: Movement speed in mm/min
        """
        command = f"G0 X{x} Y{y} F{feed_rate}"
        print(f"Moving to X{x} Y{y}")
        self._send_command(command)
    
    def draw_to(self, x: float, y: float, feed_rate: int = 500):
        """
        Draw line to position (pen down)
        
        Args:
            x: X coordinate in mm
            y: Y coordinate in mm
            feed_rate: Drawing speed in mm/min
        """
        command = f"G1 X{x} Y{y} F{feed_rate}"
        print(f"Drawing to X{x} Y{y}")
        self._send_command(command)
    
    def pen_up(self):
        """Raise the pen (servo up)"""
        print("Pen up")
        self._send_command("M3 S0")  # Servo to up position
        time.sleep(0.5)  # Wait for servo to move
    
    def pen_down(self):
        """Lower the pen (servo down)"""
        print("Pen down")
        self._send_command("M3 S90")  # Servo to down position
        time.sleep(0.5)  # Wait for servo to move
    
    
    
    
    
    def execute_gcode_file(self, filename: str):
        """Execute G-code from a file"""
        print(f"Executing G-code file: {filename}")
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith(';') and not line.startswith('('):
                    self._send_command(line)
                    time.sleep(0.01)  # Small delay between commands
    
    def get_status(self):
        """Get current plotter status"""
        self.ser.write(b'?')
        return self._read_response()
    
    def reset(self):
        """Soft reset the plotter"""
        print("Resetting...")
        self.ser.write(b'\x18')  # Ctrl-X
        time.sleep(2)
        self._read_response()
    
    def close(self):
        """Close the serial connection"""
        self.pen_up()
        self.ser.close()
        print("Connection closed")



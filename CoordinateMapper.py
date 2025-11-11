import numpy as np
from typing import Tuple

class CoordinateMapper:
    def __init__(self):
        # Plotter coordinates (in mm) - will be setd during calibration

        self.plotter_bounds = {
            'x_min': 0,
            'x_max': 200,
            'y_min': 0,
            'y_max': 200
        }

        # iPad screen coordinates (in pixels) - will be set during calibration
        self.ipad_bounds = {
            'x_min': 0,
            'x_max': 2048,
            'y_min':0,
            'y_max': 2732
        }

        self.calibrated = False

    def set_plotter_bounds(self, x_min: float, x_max: float, y_min: float, y_max: float):
        """Set the physical plotter coordinate bounds"""
        self.plotter_bounds = {
            'x_min': x_min,
            'x_max': x_max,
            'y_min': y_min,
            'y_max': y_max
        }

        print(f"Plotter bounds set to: X({x_min}-{x_max}), Y({y_min}-{y_max})")
    
    def set_ipad_bounds(self, x_min: int, x_max: int, y_min: int, y_max: int):
        """Set the iPad screen coordinate bounds (in pixels)"""
        self.ipad_bounds = {
            'x_min': x_min,
            'x_max': x_max,
            'y_min': y_min,
            'y_max': y_max
        }
        self.calibrated = True


        print(f"iPad bounds set to: X({x_min}-{x_max}), Y({y_min}-{y_max})")

    def ipad_to_plotter(self, ipad_x: float, ipad_y: float) -> Tuple[float,float]:
        """Convert iPad screen coordinates to plotter mm coordinates"""
        if not self.calibrated:
            print("Warning: CoordinateMapper not calibrated yet.")
        
        # Normalize IPad coords to 0-1 range
        norm_x = (ipad_x - self.ipad_bounds['x_min']) / \
            (self.ipad_bounds['x_max'] - self.ipad_bounds['x_min'])
        norm_y = (ipad_y - self.ipad_bounds['y_min']) / \
            (self.ipad_bounds['y_max'] - self.ipad_bounds['y_min'])
        
        # Map to plotter coordinates
        plotter_x = self.plotter_bounds['x_min'] + \
            norm_x * (self.plotter_bounds['x_max'] - self.plotter_bounds['x_min'])
        plotter_y = self.plotter_bounds['y_min'] + \
            norm_y * (self.plotter_bounds['y_max'] - self.plotter_bounds['y_min'])
        
        return plotter_x, plotter_y
    
    def plotter_to_ipad(self, plotter_x: float, plotter_y: float) -> Tuple[int, int]:
        """Convert plotter mm coordinates to iPad pixel coordinates"""
        # Normalize plotter coords to 0-1 range
        norm_x = (plotter_x - self.plotter_bounds['x_min']) / \
                 (self.plotter_bounds['x_max'] - self.plotter_bounds['x_min'])
        norm_y = (plotter_y - self.plotter_bounds['y_min']) / \
                 (self.plotter_bounds['y_max'] - self.plotter_bounds['y_min'])
        
        # Map to iPad coordinates
        ipad_x = int(self.ipad_bounds['x_min'] + \
                     norm_x * (self.ipad_bounds['x_max'] - self.ipad_bounds['x_min']))
        ipad_y = int(self.ipad_bounds['y_min'] + \
                     norm_y * (self.ipad_bounds['y_max'] - self.ipad_bounds['y_min']))
        
        return ipad_x, ipad_y
    
    def test_mapping(self):
        """Test corner mappings"""
        print("\n=== Testing Coordinate Mapping ===")
        test_points = [
            ("Top-left", self.ipad_bounds['x_min'], self.ipad_bounds['y_min']),
            ("Top-right", self.ipad_bounds['x_max'], self.ipad_bounds['y_min']),
            ("Bottom-right", self.ipad_bounds['x_max'], self.ipad_bounds['y_max']),
            ("Bottom-left", self.ipad_bounds['x_min'], self.ipad_bounds['y_max']),
            ("Center", 
             (self.ipad_bounds['x_min'] + self.ipad_bounds['x_max']) // 2,
             (self.ipad_bounds['y_min'] + self.ipad_bounds['y_max']) // 2)
        ]
        
        for name, ix, iy in test_points:
            px, py = self.ipad_to_plotter(ix, iy)
            print(f"{name:12s}: iPad({ix:4d}, {iy:4d}) -> Plotter({px:6.2f}, {py:6.2f})")
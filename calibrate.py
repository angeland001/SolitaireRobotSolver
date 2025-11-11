# calibrate.py

import serial
import time
from plotter_controller import PenPlotter
from CoordinateMapper import CoordinateMapper
from PlotterCalibration import PlotterCalibrator


def main():
    # Initialize plotter
    print("Connecting to plotter...")
    plotter = PenPlotter(port='COM3', baudrate=115200)  
    
    # Create mapper and calibrator
    mapper = CoordinateMapper()
    calibrator = PlotterCalibrator(plotter, mapper)
    
    # Run calibration
    success = calibrator.run_full_calibration()
    
    if success:
        print("\n=== CALIBRATION RESULTS ===")
        print(f"Plotter bounds: {mapper.plotter_bounds}")
        print(f"iPad bounds: {mapper.ipad_bounds}")
        
        # Save calibration to file
        save = input("\nSave calibration to file? (y/n): ").lower()
        if save == 'y':
            import json
            calibration_data = {
                'plotter_bounds': mapper.plotter_bounds,
                'ipad_bounds': mapper.ipad_bounds
            }
            with open('calibration.json', 'w') as f:
                json.dump(calibration_data, f, indent=2)
            print("✓ Saved to calibration.json")

if __name__ == "__main__":
    main()
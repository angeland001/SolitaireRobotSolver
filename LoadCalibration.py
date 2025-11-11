import json
from CoordinateMapper import CoordinateMapper

def load_calibration(filename='calibration.json'):
    """Load calibration from file"""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        mapper = CoordinateMapper()
        mapper.plotter_bounds = data['plotter_bounds']
        mapper.ipad_bounds = data['ipad_bounds']
        mapper.calibrated = True
        
        print(f"✓ Loaded calibration from {filename}")
        return mapper
    except FileNotFoundError:
        print(f"Calibration file {filename} not found!")
        return None
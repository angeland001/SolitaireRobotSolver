import json
from Calibration.CoordinateMapper_Swapped import CoordinateMapper

def load_calibration(filename='calibration.json'):
    """
    Load calibration from file
    Automatically handles axis swapping if present in calibration
    """
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Check if axis swapping info is present
        axes_swapped = data.get('axes_swapped', False)
        
        # Create mapper with appropriate axis configuration
        mapper = CoordinateMapper(swap_axes=axes_swapped)
        mapper.plotter_bounds = data['plotter_bounds']
        mapper.ipad_bounds = data['ipad_bounds']
        mapper.calibrated = True
        
        print(f"✓ Loaded calibration from {filename}")
        if axes_swapped:
            print("  ⚠ Axis swap compensation active")
        
        # Display any additional info
        if 'x_inverted' in data and data['x_inverted']:
            print("  ⚠ X-axis inversion noted in calibration")
        if 'y_inverted' in data and data['y_inverted']:
            print("  ⚠ Y-axis inversion noted in calibration")
        
        return mapper
    except FileNotFoundError:
        print(f"❌ Calibration file {filename} not found!")
        return None
    except Exception as e:
        print(f"❌ Error loading calibration: {e}")
        return None

from LoadCalibration import load_calibration
from plotter_controller import PenPlotter

def quick_test():
    """Quick test of plotter with loaded calibration"""
    # Load saved calibration
    mapper = load_calibration()
    if not mapper:
        print("Run calibration first!")
        return
    
    # Connect to plotter
    plotter = PenPlotter(port='COM3', baudrate=115200)
    
    # Test a tap at specific iPad coordinate
    test_x = int(input("Enter iPad X coordinate to test: "))
    test_y = int(input("Enter iPad Y coordinate to test: "))
    
    plotter_x, plotter_y = mapper.ipad_to_plotter(test_x, test_y)
    print(f"Moving to ({plotter_x:.2f}, {plotter_y:.2f})")
    
    plotter.pen_up()
    plotter.move_to(plotter_x, plotter_y)
    
    tap = input("Execute tap? (y/n): ").lower()
    if tap == 'y':
        plotter.pen_down()
        time.sleep(0.2)
        plotter.pen_up()
        print("✓ Tap complete!")

if __name__ == "__main__":
    quick_test()
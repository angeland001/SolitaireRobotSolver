import time
from LoadCalibration_Smart import load_calibration
from SmartPlotterCalibration import PenPlotter

def quick_test():
    """Quick test of plotter with loaded smart calibration"""
    print("="*60)
    print("QUICK CALIBRATION TEST")
    print("="*60)
    
    # Load saved calibration
    mapper = load_calibration()
    if not mapper:
        print("\n❌ Run calibration first!")
        print("   python calibrate_smart.py")
        return
    
    print()
    
    # Connect to plotter
    try:
        plotter = PenPlotter(port='COM3', baudrate=115200)
        print("✓ Plotter connected!\n")
    except Exception as e:
        print(f"❌ Error connecting to plotter: {e}")
        return
    
    # Test a tap at specific iPad coordinate
    print("Enter iPad screen coordinates to test:")
    print("(For reference: center of screen is typically ~1024, 1366)")
    print()
    
    try:
        test_x = int(input("  iPad X coordinate: "))
        test_y = int(input("  iPad Y coordinate: "))
    except ValueError:
        print("❌ Invalid input!")
        plotter.close()
        return
    
    # Convert to plotter coordinates
    plotter_x, plotter_y = mapper.ipad_to_plotter(test_x, test_y)
    
    print(f"\n📐 Coordinate Mapping:")
    print(f"   iPad: ({test_x}, {test_y})")
    print(f"   Plotter: ({plotter_x:.2f}, {plotter_y:.2f})")
    
    # Move to position
    print(f"\n🤖 Moving plotter...")
    plotter.pen_up()
    plotter.move_to(plotter_x, plotter_y)
    
    # Ask to tap
    tap = input("\n👆 Execute tap at this position? (y/n): ").lower()
    if tap == 'y':
        plotter.pen_down()
        time.sleep(0.2)
        plotter.pen_up()
        print("✓ Tap complete!")
    else:
        print("Tap skipped")
    
    # Test another?
    another = input("\n🔄 Test another position? (y/n): ").lower()
    if another == 'y':
        plotter.close()
        quick_test()
        return
    
    plotter.close()
    print("\n✓ Test complete!")

if __name__ == "__main__":
    quick_test()

#!/usr/bin/env python3
"""
iPad Solitaire Plotter Calibration Script (Portrait Mode)
This script calibrates your plotter to work with an iPad in portrait orientation
"""

import json
import sys
import time
from SmartPlotterCalibration import PenPlotter, ImprovedPlotterCalibrator
from CoordinateMapper_Swapped import CoordinateMapper




def main():
    print("="*60)
    print("  PLOTTER CALIBRATION FOR iPAD SOLITAIRE (PORTRAIT)")
    print("="*60)
    print("\nThis script will:")
    print("1. Test your plotter's axis directions")
    print("2. Determine your plotter's working area")
    print("3. Mark corners on your iPad screen")
    print("4. Map iPad pixel coordinates to plotter coordinates")
    print("5. Test the calibration")
    print("\n⚠ IMPORTANT: Ensure your iPad is in PORTRAIT mode!")
    print("             (Taller than wide, home button at bottom)\n")
    
    input("Press Enter to begin calibration...")
    
    # Initialize plotter
    print("\n--- Connecting to Plotter ---")
    try:
        plotter = PenPlotter(port='COM3', baudrate=115200)
        print("✓ Plotter connected successfully!")
    except Exception as e:
        print(f"❌ Error connecting to plotter: {e}")
        print("\nTroubleshooting:")
        print("- Check that plotter is powered on")
        print("- Verify COM port (COM3) is correct")
        print("- Check USB cable connection")
        return
    
    # Create mapper and calibrator
    mapper = CoordinateMapper()
    calibrator = ImprovedPlotterCalibrator(plotter, mapper)
    
    # Run calibration
    try:
        success = calibrator.run_full_calibration()
    except KeyboardInterrupt:
        print("\n\n⚠ Calibration interrupted by user")
        plotter.pen_up()
        plotter.close()
        return
    except Exception as e:
        print(f"\n\n❌ Error during calibration: {e}")
        plotter.pen_up()
        plotter.close()
        return
    
    if success:
        print("\n" + "="*60)
        print("  CALIBRATION RESULTS")
        print("="*60)
        
        print("\n📐 Plotter Bounds (millimeters):")
        pb = mapper.plotter_bounds
        print(f"   X: {pb['x_min']:.1f} to {pb['x_max']:.1f} mm")
        print(f"   Y: {pb['y_min']:.1f} to {pb['y_max']:.1f} mm")
        print(f"   Working area: {pb['x_max']-pb['x_min']:.1f} x {pb['y_max']-pb['y_min']:.1f} mm")
        
        print("\n📱 iPad Bounds (pixels):")
        ib = mapper.ipad_bounds
        print(f"   X: {ib['x_min']} to {ib['x_max']} pixels")
        print(f"   Y: {ib['y_min']} to {ib['y_max']} pixels")
        print(f"   Game area: {ib['x_max']-ib['x_min']} x {ib['y_max']-ib['y_min']} pixels")
        
        # Save calibration to file
        print("\n" + "-"*60)
        save = input("💾 Save calibration to file? (y/n): ").lower()
        if save == 'y':
            calibration_data = {
                'plotter_bounds': mapper.plotter_bounds,
                'ipad_bounds': mapper.ipad_bounds,
                'orientation': 'portrait',
                'device': 'iPad',
                'calibration_date': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            filename = input("   Filename [calibration.json]: ").strip()
            if not filename:
                filename = 'calibration.json'
            
            try:
                with open(filename, 'w') as f:
                    json.dump(calibration_data, f, indent=2)
                print(f"   ✓ Saved to {filename}")
                
                print("\n📝 Next steps:")
                print(f"   1. Use 'LoadCalibration.py' to reload this calibration")
                print(f"   2. Use 'QuickTest.py' to test specific coordinates")
                print(f"   3. Implement your solitaire card detection")
            except Exception as e:
                print(f"   ❌ Error saving file: {e}")
        
        print("\n" + "="*60)
        print("✓ CALIBRATION COMPLETE - READY FOR GAMEPLAY!")
        print("="*60)
    else:
        print("\n❌ Calibration was not completed successfully")
    
    # Clean up
    plotter.pen_up()
    plotter.close()



if __name__ == "__main__":
    import time
    main()

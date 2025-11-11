#!/usr/bin/env python3
"""
Smart iPad Solitaire Plotter Calibration
Automatically detects and compensates for axis swapping
"""

import json
import sys
import time
from Calibration.plotter_controller import PenPlotter
from Calibration.SmartPlotterCalibration import SmartPlotterCalibrator


def main():
    print("="*60)
    print("SMART PLOTTER CALIBRATION")
    print("(Automatic Axis Detection & Compensation)")
    print("="*60)
    print("\nThis script will:")
    print("1. Auto-detect your plotter's axis orientation")
    print("2. Automatically compensate for swapped/inverted axes")
    print("3. Calibrate coordinate mapping for iPad Solitaire")
    print("\n⚠ IMPORTANT: Ensure your iPad is in PORTRAIT mode!\n")
    
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
    
    # Create smart calibrator
    calibrator = SmartPlotterCalibrator(plotter)
    
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
        import traceback
        traceback.print_exc()
        plotter.pen_up()
        plotter.close()
        return
    
    if success:
        print("\n" + "="*60)
        print("CALIBRATION RESULTS")
        print("="*60)
        
        mapper = calibrator.mapper
        
        print("\n🔧 Axis Configuration:")
        if calibrator.axes_swapped:
            print("   ⚠ Axes SWAPPED (auto-compensated)")
        else:
            print("   ✓ Axes NORMAL")
        if calibrator.x_inverted:
            print("   ⚠ X-axis INVERTED (auto-compensated)")
        if calibrator.y_inverted:
            print("   ⚠ Y-axis INVERTED (auto-compensated)")
        
        print("\n📐 Plotter Bounds (millimeters):")
        pb = mapper.plotter_bounds
        print(f"   X: {pb['x_min']:.1f} to {pb['x_max']:.1f} mm")
        print(f"   Y: {pb['y_min']:.1f} to {pb['y_max']:.1f} mm")
        
        print("\n📱 iPad Bounds (pixels):")
        ib = mapper.ipad_bounds
        print(f"   X: {ib['x_min']} to {ib['x_max']} pixels")
        print(f"   Y: {ib['y_min']} to {ib['y_max']} pixels")
        
        # Save calibration
        print("\n" + "-"*60)
        save = input("💾 Save calibration to file? (y/n): ").lower()
        if save == 'y':
            calibration_data = {
                'plotter_bounds': mapper.plotter_bounds,
                'ipad_bounds': mapper.ipad_bounds,
                'axes_swapped': calibrator.axes_swapped,
                'x_inverted': calibrator.x_inverted,
                'y_inverted': calibrator.y_inverted,
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
                
                print("\n📝 To use this calibration:")
                print("   from LoadCalibration_Smart import load_calibration")
                print("   mapper = load_calibration('calibration.json')")
                print("   px, py = mapper.ipad_to_plotter(ipad_x, ipad_y)")
            except Exception as e:
                print(f"   ❌ Error saving file: {e}")
        
        print("\n" + "="*60)
        print("✓ CALIBRATION COMPLETE!")
        print("="*60)
    else:
        print("\n❌ Calibration was not completed successfully")
    
    # Clean up
    plotter.pen_up()
    plotter.close()


if __name__ == "__main__":
    main()

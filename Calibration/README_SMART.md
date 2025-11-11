# 🎯 SMART CALIBRATION SYSTEM - Automatic Axis Detection

## 🚀 What's New?

This **Smart Calibration System** automatically detects and compensates for:
- ✅ **Swapped axes** (X controls Y, Y controls X)
- ✅ **Inverted axes** (X increases left, Y increases up)
- ✅ **Any combination** of the above

**You no longer need to manually figure out axis orientation!**

## 📦 New Files

### Core Files (Use These!)
- **`calibrate_smart.py`** - Main calibration script with auto-detection
- **`CoordinateMapper_Swapped.py`** - Enhanced mapper with axis swap support
- **`SmartPlotterCalibration.py`** - Smart calibrator class
- **`LoadCalibration_Smart.py`** - Load calibration with axis info
- **`QuickTest_Smart.py`** - Test with auto-compensation
- **`plotter_controller.py`** - GRBL interface (unchanged)

### Documentation
- **`README_SMART.md`** - This file
- Previous files still available for reference

## 🚀 Quick Start (3 Steps)

### 1. Install Requirements
```bash
pip install pyserial numpy
```

### 2. Run Smart Calibration
```bash
python calibrate_smart.py
```

### 3. Follow the Interactive Wizard

The script will:
1. **Test your axes** - You just answer what you observe
2. **Auto-detect configuration** - Script figures out the setup
3. **Auto-compensate** - Everything works correctly automatically
4. **Mark corners** - Same as before
5. **Enter coordinates** - Same as before
6. **Test & save** - Verification with compensation active

## 🎮 How It Works

### Axis Detection Process

**Test 1:** Script moves plotter in +X direction
```
You observe:
1. RIGHT  → Normal X-axis ✓
2. DOWN   → X and Y are swapped
3. LEFT   → X-axis inverted
4. UP     → X-axis inverted + swapped
```

**Test 2:** Script moves plotter in +Y direction
```
You observe:
1. RIGHT  → Y and X are swapped
2. DOWN   → Normal Y-axis ✓
3. LEFT   → Y-axis inverted + swapped
4. UP     → Y-axis inverted
```

**Result:** Script automatically detects your configuration!

### Your Specific Case

Based on your description:
- Plotter +X → iPad DOWN (home button direction)
- Plotter +Y → iPad RIGHT (probably)

**Detected Configuration:** Axes Swapped
**Auto-Compensation:** Enabled ✓

## 📐 Coordinate Mapping (Behind the Scenes)

### Normal Configuration
```
iPad X (horizontal) → Plotter X
iPad Y (vertical)   → Plotter Y
```

### Your Configuration (Swapped)
```
iPad X (horizontal) → Plotter Y
iPad Y (vertical)   → Plotter X
```

**The mapper handles this automatically!**

## 📝 Calibration Steps

### Step 1: Axis Detection
```
Moving plotter in +X direction...
What did the plotter do?
1. Moved RIGHT
2. Moved DOWN     ← Your answer
3. Moved LEFT
4. Moved UP

Moving plotter in +Y direction...
What did the plotter do?
1. Moved RIGHT    ← Likely your answer
2. Moved DOWN
3. Moved LEFT
4. Moved UP

Result: ⚠ AXES SWAPPED
→ Will automatically compensate ✓
```

### Step 2-6: Same as Before
- Find plotter bounds
- Mark iPad corners
- Screenshot & measure
- Enter coordinates
- Test & save

## 🎯 Using the Calibration

### In Your Code
```python
from LoadCalibration_Smart import load_calibration
from plotter_controller import PenPlotter

# Load calibration (auto-detects axis swap)
mapper = load_calibration('calibration.json')

# Connect plotter
plotter = PenPlotter(port='COM3')

# Tap center of iPad screen
ipad_x, ipad_y = 1024, 1366
plotter_x, plotter_y = mapper.ipad_to_plotter(ipad_x, ipad_y)

# The mapper automatically handles axis swapping!
plotter.pen_up()
plotter.move_to(plotter_x, plotter_y)  # Goes to correct position
plotter.pen_down()
```

### Quick Test
```bash
python QuickTest_Smart.py
```

## 📊 Calibration File Format

The saved `calibration.json` now includes axis info:

```json
{
  "plotter_bounds": {
    "x_min": 0,
    "x_max": 180,
    "y_min": 0,
    "y_max": 250
  },
  "ipad_bounds": {
    "x_min": 130,
    "x_max": 1260,
    "y_min": 195,
    "y_max": 1310
  },
  "axes_swapped": true,
  "x_inverted": false,
  "y_inverted": false,
  "orientation": "portrait",
  "device": "iPad",
  "calibration_date": "2024-11-11 19:30:00"
}
```

## 🔍 Supported Configurations

The smart system handles **all 8 possible configurations**:

| Config | Plotter +X | Plotter +Y | Status |
|--------|-----------|-----------|--------|
| Normal | RIGHT → | DOWN ↓ | ✓ Auto-detected |
| Swapped | DOWN ↓ | RIGHT → | ✓ Auto-compensated |
| X-Inverted | LEFT ← | DOWN ↓ | ✓ Auto-compensated |
| Y-Inverted | RIGHT → | UP ↑ | ✓ Auto-compensated |
| Swapped+X-Inv | UP ↑ | RIGHT → | ✓ Auto-compensated |
| Swapped+Y-Inv | DOWN ↓ | LEFT ← | ✓ Auto-compensated |
| Both Inverted | LEFT ← | UP ↑ | ✓ Auto-compensated |
| All Three | UP ↑ | LEFT ← | ✓ Auto-compensated |

## ✅ Advantages Over Original System

### Original System
- ❌ Manual axis detection
- ❌ Had to manually swap bounds
- ❌ Had to modify code for axis issues
- ❌ Easy to make mistakes

### Smart System
- ✅ Automatic axis detection
- ✅ Auto-compensation built-in
- ✅ No code modification needed
- ✅ Foolproof - just answer questions

## 🆚 When to Use Which System?

### Use Smart Calibration (`calibrate_smart.py`) If:
- Your plotter has unusual axis orientation (like yours!)
- You're not sure about axis directions
- You want automatic compensation
- You want the easiest setup

### Use Original Calibration (`calibrate_portrait.py`) If:
- Your plotter has standard orientation
- +X goes RIGHT, +Y goes DOWN
- You prefer more manual control

## 🐛 Troubleshooting

### Issue: Not sure which direction is which
**Solution**: The smart system asks you to observe, not guess!
- Just watch where the plotter moves
- Answer honestly
- Script figures it out

### Issue: Plotter moves to wrong positions during testing
**Solution**: 
1. Re-run calibration
2. Answer axis test questions carefully
3. If still wrong, check plotter mechanical setup

### Issue: Calibration seems backwards
**Solution**: 
- Re-measure iPad pixel coordinates carefully
- Ensure you marked all 4 corners correctly
- Verify iPad is in portrait mode

## 📚 Technical Details

### Axis Swap Implementation

When `axes_swapped = True`, the mapper swaps normalized coordinates:

```python
def ipad_to_plotter(self, ipad_x, ipad_y):
    # Normalize to 0-1
    norm_x = (ipad_x - ix_min) / (ix_max - ix_min)
    norm_y = (ipad_y - iy_min) / (iy_max - iy_min)
    
    if self.swap_axes:
        # iPad X → Plotter Y
        # iPad Y → Plotter X
        plotter_x = px_min + norm_y * (px_max - px_min)
        plotter_y = py_min + norm_x * (py_max - py_min)
    else:
        # Normal mapping
        plotter_x = px_min + norm_x * (px_max - px_min)
        plotter_y = py_min + norm_y * (py_max - py_min)
    
    return plotter_x, plotter_y
```

### Inversion Handling

When axes are inverted, the bounds are swapped during calibration:
```python
if self.x_inverted:
    x_min, x_max = x_max, x_min
if self.y_inverted:
    y_min, y_max = y_max, y_min
```

## 🎉 Summary

The Smart Calibration System makes setup **foolproof** for plotters with any axis configuration. Just run the script, answer what you observe, and everything else is automatic!

**For your specific setup (axes swapped):** This system is **perfect** and will handle everything automatically.

## 📞 Next Steps

1. Run: `python calibrate_smart.py`
2. Answer axis test questions honestly
3. Complete calibration as normal
4. Test with: `python QuickTest_Smart.py`
5. Start building your Solitaire player!

Good luck! 🚀

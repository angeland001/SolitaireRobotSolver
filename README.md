# iPad Solitaire Plotter - Portrait Mode Calibration

## Overview
This calibration system maps your plotter's physical coordinates to your iPad's screen coordinates, allowing the plotter to accurately interact with the Solitaire game in portrait mode.

## Your Setup (Based on Image)
- **iPad**: Portrait orientation (tall, home button at bottom)
- **Game**: Solitaire in portrait mode
- **Plotter**: Positioned above iPad with pen mechanism
- **Goal**: Map plotter movements to exact card positions on screen

## Files Included

### Core Files
- `calibrate_portrait.py` - Main calibration script (START HERE)
- `ImprovedPlotterCalibration.py` - Improved calibrator with axis testing
- `CoordinateMapper.py` - Coordinate transformation engine
- `plotter_controller.py` - Low-level plotter control
- `LoadCalibration.py` - Load saved calibration
- `QuickTest.py` - Test specific coordinates

### Documentation
- `CALIBRATION_GUIDE_PORTRAIT.md` - Detailed calibration guide
- `README.md` - This file

## Quick Start Guide

### Prerequisites
1. Python 3.x installed
2. PySerial library: `pip install pyserial`
3. Plotter connected via USB (typically COM3 on Windows)
4. iPad positioned under plotter in portrait mode

### Step 1: Run Calibration

```bash
python calibrate_portrait.py
```

This will guide you through:
1. **Axis Direction Test** - Verifies plotter moves correctly
2. **Working Area Detection** - Finds plotter's reachable bounds
3. **Corner Marking** - Marks 4 corners on iPad screen
4. **Coordinate Entry** - You input pixel coordinates from screenshot
5. **Verification Test** - Tests the mapping accuracy
6. **Save Calibration** - Saves to `calibration.json`

### Step 2: Take Screenshot

When the calibration marks the corners:
1. Press **Power + Volume Up** on iPad to screenshot
2. Transfer screenshot to your computer
3. Open in image viewer/editor
4. Hover over each marked dot and note pixel coordinates

### Step 3: Enter Coordinates

When prompted, enter the game area boundaries:
- **Left edge**: X-coordinate of leftmost card column
- **Right edge**: X-coordinate of rightmost card column
- **Top edge**: Y-coordinate where cards start (below status bar)
- **Bottom edge**: Y-coordinate where cards end

### Step 4: Test and Save

The script will:
- Test mapping at 5 positions
- Optionally mark them to verify accuracy
- Save calibration to JSON file

## Understanding Coordinates

### iPad Portrait Coordinate System
```
(0,0) ───────────────── (2048,0)
  │                         │
  │    GAME AREA:          │
  │   (200,400)───────(1848,400)
  │      │               │  │
  │      │  Solitaire    │  │
  │      │  Game         │  │
  │      │               │  │
  │   (200,2500)────(1848,2500)
  │                         │
(0,2732)────────────────(2048,2732)
```

### Plotter Coordinate System
```
(0,0) ──────────── (180,0)
  │                   │
  │  Working Area     │
  │                   │
(0,250)──────────(180,250)
```

## Troubleshooting

### Problem: Plotter moves wrong direction

**Solution 1: X-axis inverted**
If increasing X moves left instead of right, swap your plotter bounds:
```python
# Before
set_plotter_bounds(0, 180, 0, 250)
# After
set_plotter_bounds(180, 0, 0, 250)  # Swapped x_min and x_max
```

**Solution 2: Y-axis inverted**
If increasing Y moves up instead of down, swap Y bounds:
```python
# Before
set_plotter_bounds(0, 180, 0, 250)
# After
set_plotter_bounds(0, 180, 250, 0)  # Swapped y_min and y_max
```

**Solution 3: Axes swapped**
If X movements affect Y and vice versa, you need to modify CoordinateMapper to swap axes in the mapping functions.

### Problem: Scale is wrong (movements too large/small)

**Check 1**: Verify plotter bounds are correct
- Measure actual distances your plotter can move
- Update bounds in calibration

**Check 2**: Verify iPad pixel coordinates are accurate
- Re-measure from screenshot carefully
- Ensure you're measuring the game area, not full screen

### Problem: Corner marks not visible on iPad

**Solutions**:
- Increase pen-down time in `mark_ipad_corners_portrait()`
- Ensure pen is actually touching screen
- Check servo angles (M3 S0 for up, M3 S90 for down)
- Adjust servo positions if needed

### Problem: COM port not found

**Windows**:
```bash
# Check Device Manager > Ports (COM & LPT)
# Update port in calibrate_portrait.py if needed
```

**Linux/Mac**:
```bash
# Find port with:
ls /dev/tty*
# Update to something like '/dev/ttyUSB0'
```

### Problem: Portrait mode shows landscape dimensions

If width > height in pixel coordinates:
- You may have measured the coordinates incorrectly
- Ensure iPad is actually in portrait mode
- Re-take screenshot and re-measure

## Testing Your Calibration

After calibration, test with `QuickTest.py`:

```bash
python QuickTest.py
```

Test known positions:
1. Top-left Ace foundation pile
2. Center of tableau
3. Specific card position

## Calibration File Format

`calibration.json` contains:
```json
{
  "plotter_bounds": {
    "x_min": 0,
    "x_max": 180,
    "y_min": 0,
    "y_max": 250
  },
  "ipad_bounds": {
    "x_min": 200,
    "x_max": 1848,
    "y_min": 400,
    "y_max": 2500
  },
  "orientation": "portrait",
  "device": "iPad",
  "calibration_date": "2024-XX-XX XX:XX:XX"
}
```

## Expected Values for Standard iPad

### iPad Screen Resolution
- **iPad Air/Pro (11")**: 2048 x 2732 pixels (portrait)
- **iPad (10.2")**: 2160 x 1620 pixels (portrait)
- **iPad mini**: 2048 x 1536 pixels (portrait)

### Typical Game Area (with margins)
```python
ipad_bounds = {
    'x_min': 150,   # Left margin
    'x_max': 1900,  # Right margin
    'y_min': 350,   # Top margin (status bar)
    'y_max': 2600   # Bottom margin
}
```

### Typical Plotter Bounds
```python
# Depends on your specific plotter hardware
plotter_bounds = {
    'x_min': 0,
    'x_max': 180,   # Adjust to your plotter width
    'y_min': 0,
    'y_max': 240    # Adjust to your plotter height
}
```

## Advanced Usage

### Loading Calibration in Your Code

```python
from LoadCalibration import load_calibration
from plotter_controller import PenPlotter

# Load calibration
mapper = load_calibration('calibration.json')

# Connect plotter
plotter = PenPlotter(port='COM3', baudrate=115200)

# Convert iPad coordinates to plotter coordinates
ipad_x, ipad_y = 1024, 1366  # Center of screen
plotter_x, plotter_y = mapper.ipad_to_plotter(ipad_x, ipad_y)

# Move and tap
plotter.pen_up()
plotter.move_to(plotter_x, plotter_y)
plotter.pen_down()
time.sleep(0.2)
plotter.pen_up()
```

### Manual Calibration (If Script Fails)

1. **Manually find plotter bounds**:
   - Move plotter to corners manually
   - Note X,Y coordinates of working area

2. **Create calibration file**:
```python
import json

calibration = {
    'plotter_bounds': {
        'x_min': 0, 'x_max': 180,
        'y_min': 0, 'y_max': 240
    },
    'ipad_bounds': {
        'x_min': 200, 'x_max': 1848,
        'y_min': 400, 'y_max': 2500
    }
}

with open('calibration.json', 'w') as f:
    json.dump(calibration, f, indent=2)
```

## Next Steps After Calibration

1. **Implement Card Detection**
   - Use computer vision or manual input
   - Identify card positions on screen

2. **Implement Game Logic**
   - Solitaire rules
   - Valid move detection
   - Card selection logic

3. **Create Main Controller**
   - Screenshot capture
   - Card recognition
   - Move planning
   - Plotter control

4. **Test Incrementally**
   - Test single card tap
   - Test drag movements
   - Test full game sequence

## Tips for Best Results

1. **Stable iPad Position**
   - Tape iPad down to prevent movement
   - Ensure it doesn't shift during gameplay

2. **Consistent Pen Pressure**
   - Adjust servo angles for reliable taps
   - Test tap duration (0.1-0.3 seconds typically)

3. **Speed Settings**
   - Start with slower movements for accuracy
   - Increase speed once calibration is verified

4. **Lighting**
   - Good lighting helps with screenshots
   - Easier to see marked corners

5. **Regular Re-calibration**
   - Re-calibrate if you move the iPad
   - Re-calibrate if accuracy degrades

## Support

If you encounter issues:
1. Check this README troubleshooting section
2. Review `CALIBRATION_GUIDE_PORTRAIT.md`
3. Verify hardware connections
4. Test plotter manually with G-code commands

## Calibration Checklist

- [ ] Python and pyserial installed
- [ ] Plotter connected and powered
- [ ] iPad in portrait mode with Solitaire running
- [ ] Ran `calibrate_portrait.py`
- [ ] Axis directions tested and correct
- [ ] Plotter bounds determined
- [ ] Corners marked on iPad
- [ ] Screenshot taken and transferred
- [ ] Pixel coordinates measured accurately
- [ ] Coordinates entered into script
- [ ] Test movements verified
- [ ] Calibration saved to JSON
- [ ] Tested with `QuickTest.py`
- [ ] Ready for game implementation!

Good luck with your iPad Solitaire plotter project!

# 🎯 QUICK REFERENCE CARD - Keep This Open During Calibration

## 📋 Pre-Calibration Checklist
```
Hardware:
 [ ] Plotter powered on
 [ ] USB cable connected (COM3)
 [ ] iPad charged and unlocked
 [ ] iPad in PORTRAIT mode
 [ ] Solitaire game open
 [ ] Stylus/pen in plotter
 [ ] iPad taped down (won't move)

Software:
 [ ] Python installed
 [ ] pyserial installed: pip install pyserial
 [ ] Files in same directory
```

## 🚀 Run Command
```bash
python calibrate_portrait.py
```

## 📝 Calibration Steps (Quick Version)

### STEP 1: Axis Test
- Plotter will move to test directions
- Watch carefully:
  - +X should move RIGHT →
  - +Y should move DOWN ↓
- **Note any wrong directions**

### STEP 2: Find Bounds
- Test corner positions
- Answer y/n if position is safe
- Script will suggest bounds
- Confirm or adjust

### STEP 3: Mark Corners
- Script marks 4 dots on iPad
- **Take screenshot NOW**: Power + Volume Up
- Don't move iPad after marking!

### STEP 4: Measure Screenshot
Transfer screenshot to computer and open in:
- **Windows**: Paint (coordinates in bottom bar)
- **Mac**: Preview (Tools > Inspector)
- **Any**: GIMP, Photoshop (Info panel)

Hover over each dot and record:
```
Top-Left dot:     X = _____ , Y = _____
Top-Right dot:    X = _____ , Y = _____
Bottom-Left dot:  X = _____ , Y = _____
Bottom-Right dot: X = _____ , Y = _____

Game Area Bounds (from the dots):
  Left edge   (x_min) = _____ (smallest X)
  Right edge  (x_max) = _____ (largest X)
  Top edge    (y_min) = _____ (smallest Y)
  Bottom edge (y_max) = _____ (largest Y)
```

### STEP 5: Enter Values
When prompted, type the 4 values:
```
Left edge X (x_min):   [smallest X from dots]
Right edge X (x_max):  [largest X from dots]
Top edge Y (y_min):    [smallest Y from dots]
Bottom edge Y (y_max): [largest Y from dots]
```

### STEP 6: Test & Save
- Script tests 5 positions
- Optionally mark each to verify
- Save calibration when prompted
- Done! ✓

## 🔢 Expected Value Ranges

### iPad Portrait (Standard Sizes)
```
Full Screen:  0 to 2048 (width) x 0 to 2732 (height)

Typical Game Area:
  x_min: 100-300   (left margin)
  x_max: 1700-1950 (right margin)
  y_min: 300-500   (top margin + status bar)
  y_max: 2400-2700 (bottom margin)
```

### Plotter (Varies by Hardware)
```
Small Plotter:  0-180mm x 0-240mm
Medium:         0-200mm x 0-300mm
Large:          0-300mm x 0-400mm
```

## ⚠️ Common Issues & Quick Fixes

### Can't see marked dots?
```
Fix 1: Increase M3 S90 value (pen down pressure)
Fix 2: Adjust pen holder height
Fix 3: Check stylus tip is touching
```

### Wrong direction movement?
```
Fix: Don't worry! Note it and continue.
     Will fix by swapping bounds later.

If X moves left instead of right:
  Swap x_min ↔ x_max

If Y moves up instead of down:
  Swap y_min ↔ y_max
```

### COM port error?
```
Fix 1: Check Device Manager (Windows)
Fix 2: Try COM4, COM5, etc.
Fix 3: Install CH340 driver
Fix 4: Update port in script:
       plotter = PenPlotter(port='COM#')
```

### Values seem wrong?
```
Check 1: Is iPad actually in portrait?
         (Taller than wide)
Check 2: Did you measure game area, not full screen?
Check 3: Are coordinates from screenshot accurate?

Validation:
  x_max should be > x_min  ✓
  y_max should be > y_min  ✓
  height should be > width ✓ (portrait)
```

## 🎯 Testing After Calibration

### Test with Known Position
```bash
python QuickTest.py
```

**Good test coordinates** (center of screen):
```
iPad X: 1024
iPad Y: 1366
```

Should move to middle of iPad screen.

### Manual Python Test
```python
from LoadCalibration import load_calibration
from plotter_controller import PenPlotter

mapper = load_calibration()
plotter = PenPlotter(port='COM3')

# Test top-left corner
px, py = mapper.ipad_to_plotter(300, 500)
plotter.pen_up()
plotter.move_to(px, py)
plotter.pen_down()  # Should tap top-left of game
```

## 📐 Coordinate Cheat Sheet

### Portrait iPad Coordinate System
```
     0 ─────────── 2048 (X increases →)
     │
     │  [Status Bar]
     │
   400  ●──────────●  Top of game
     │  │          │
     │  │  GAME    │
     │  │  AREA    │
     │  │          │
  2500  ●──────────●  Bottom of game
     │
  2732
  
  (Y increases ↓)
```

### Plotter Coordinate System (Typical)
```
  0 ─────── 180 (X increases →)
  │
  │  Working
  │  Area
  │
250

(Y increases ↓ or ↑ depending on setup)
```

## 🔧 Emergency Commands

### If Plotter Gets Stuck
```python
# In Python console:
from plotter_controller import PenPlotter
plotter = PenPlotter(port='COM3')
plotter.pen_up()        # Lift pen
plotter.reset()          # Soft reset
plotter.close()          # Disconnect
```

### Manual G-code Commands
```
M3 S0      → Pen up
M3 S90     → Pen down
G0 X50 Y50 → Move to 50,50
$H         → Home (if available)
?          → Status
```

## ✅ Success Indicators

You're calibrated when:
- ✓ All 4 corners marked on iPad
- ✓ Screenshot measurements taken
- ✓ Coordinates entered successfully
- ✓ Test movements land in correct positions
- ✓ calibration.json file created
- ✓ QuickTest.py works correctly

## 📞 Need Help?

1. Check README.md (full troubleshooting)
2. Check VISUAL_GUIDE.md (diagrams)
3. Check CALIBRATION_GUIDE_PORTRAIT.md (detailed steps)

## 💾 After Calibration

Your calibration is saved in: **calibration.json**

To use in your own code:
```python
from LoadCalibration import load_calibration

mapper = load_calibration()
px, py = mapper.ipad_to_plotter(ipad_x, ipad_y)
```

## 🎮 Ready to Play!

Once calibrated:
1. Implement card detection
2. Write game logic
3. Connect to plotter
4. Play Solitaire!

---

**Remember:** Keep iPad taped down after calibration!
Any movement invalidates calibration.

**Good Luck! 🚀**

# 📁 iPad Solitaire Plotter - Portrait Mode Calibration Package

## 🎯 What This Package Does

Calibrates your pen plotter to interact with an iPad running Solitaire in portrait mode by mapping screen pixel coordinates to physical plotter coordinates.

---

## 🚀 START HERE

### New Users - Quick Start (5 minutes)
1. Read: **PROJECT_SUMMARY.md** ← Overview and getting started
2. Run: `python calibrate_portrait.py`
3. Keep open: **QUICK_REFERENCE.md** ← During calibration

### Experienced Users - Jump Right In
```bash
pip install pyserial numpy
python calibrate_portrait.py
```

---

## 📚 File Organization

### 🟢 Essential Files (Start Here)

| File | Purpose | When to Use |
|------|---------|-------------|
| **PROJECT_SUMMARY.md** | Complete overview | First time setup |
| **QUICK_REFERENCE.md** | Quick lookup during calibration | Keep open while calibrating |
| **calibrate_portrait.py** | Main calibration script | Run this to calibrate |
| **QuickTest.py** | Test calibration | After calibration |

### 🟡 Core Python Modules (Auto-used by scripts)

| File | Purpose |
|------|---------|
| **ImprovedPlotterCalibration.py** | Enhanced calibrator class |
| **CoordinateMapper.py** | Coordinate transformation |
| **plotter_controller.py** | GRBL plotter interface |
| **LoadCalibration.py** | Load saved calibration |

### 🔵 Documentation (Reference)

| File | Purpose | When to Use |
|------|---------|-------------|
| **README.md** | Complete user guide + troubleshooting | Problems or questions |
| **CALIBRATION_GUIDE_PORTRAIT.md** | Detailed calibration walkthrough | Want detailed instructions |
| **VISUAL_GUIDE.md** | Diagrams and visual aids | Prefer visual learning |

---

## 📖 Reading Order for Different Users

### Beginner (Never Used Plotters)
1. **PROJECT_SUMMARY.md** - Understand the system
2. **VISUAL_GUIDE.md** - See diagrams
3. **QUICK_REFERENCE.md** - Keep open
4. Run: `calibrate_portrait.py`
5. **README.md** - Troubleshooting if needed

### Intermediate (Used Plotters Before)
1. **PROJECT_SUMMARY.md** - Quick overview
2. **QUICK_REFERENCE.md** - Keep open
3. Run: `calibrate_portrait.py`

### Advanced (Just Want to Calibrate)
1. Run: `calibrate_portrait.py`
2. **QUICK_REFERENCE.md** - If you need it

---

## 🎓 Documentation by Topic

### Understanding the System
- **PROJECT_SUMMARY.md** - Complete overview
- **VISUAL_GUIDE.md** - Diagrams and workflows
- **CALIBRATION_GUIDE_PORTRAIT.md** - Theory and concepts

### Running Calibration
- **QUICK_REFERENCE.md** - Step-by-step checklist
- **calibrate_portrait.py** - The actual script
- **CALIBRATION_GUIDE_PORTRAIT.md** - Detailed process

### Troubleshooting
- **README.md** (Troubleshooting section)
- **QUICK_REFERENCE.md** (Common Issues)
- **VISUAL_GUIDE.md** (Troubleshooting Flowchart)

### Using After Calibration
- **QuickTest.py** - Test specific positions
- **LoadCalibration.py** - Load in your code
- **README.md** (Advanced Usage section)

---

## 🔍 Quick Reference by Question

**"How do I start?"**
→ PROJECT_SUMMARY.md → Run calibrate_portrait.py

**"What coordinates should I enter?"**
→ QUICK_REFERENCE.md (Expected Value Ranges)

**"My plotter moves the wrong direction"**
→ README.md (Troubleshooting) or QUICK_REFERENCE.md (Common Issues)

**"What are the steps again?"**
→ QUICK_REFERENCE.md (Calibration Steps)

**"I want to understand the math"**
→ CALIBRATION_GUIDE_PORTRAIT.md or VISUAL_GUIDE.md

**"How do I test my calibration?"**
→ QuickTest.py

**"How do I use this in my code?"**
→ README.md (Advanced Usage) or PROJECT_SUMMARY.md (After Calibration)

**"I see an error message"**
→ README.md (Troubleshooting) → QUICK_REFERENCE.md (Common Issues)

---

## 🎯 File Descriptions

### Main Scripts

**calibrate_portrait.py** (4.2 KB)
```
The main calibration wizard. This is what you run.
- Connects to plotter
- Tests axis directions  
- Finds working bounds
- Marks iPad corners
- Collects measurements
- Saves calibration
```

**QuickTest.py** (1 KB)
```
Quick testing utility after calibration.
- Loads calibration.json
- Prompts for iPad coordinates
- Moves plotter to position
- Optionally taps
```

### Core Modules

**ImprovedPlotterCalibration.py** (13 KB)
```
Enhanced calibration class with:
- Axis direction testing
- Interactive prompts
- Portrait validation
- Clear feedback
- Better error handling
```

**CoordinateMapper.py** (3.9 KB)
```
Coordinate transformation engine:
- Stores plotter bounds (mm)
- Stores iPad bounds (pixels)
- ipad_to_plotter() conversion
- plotter_to_ipad() conversion
- Test mapping functionality
```

**plotter_controller.py** (3.7 KB)
```
Low-level GRBL interface:
- Serial communication
- G-code commands
- Pen up/down control
- Movement functions
- Status queries
```

**LoadCalibration.py** (604 bytes)
```
Simple utility to load calibration:
- Reads calibration.json
- Returns configured mapper
- Error handling
```

### Documentation

**PROJECT_SUMMARY.md** (9.3 KB)
```
Complete project overview:
- What it does
- How it works
- Getting started
- Expected values
- Next steps
```

**README.md** (8.9 KB)
```
Comprehensive user guide:
- Setup instructions
- Coordinate systems
- Troubleshooting
- Advanced usage
- Tips and tricks
```

**QUICK_REFERENCE.md** (5.8 KB)
```
Quick lookup card:
- Checklist
- Steps summary
- Expected values
- Common fixes
- Emergency commands
```

**CALIBRATION_GUIDE_PORTRAIT.md** (5.2 KB)
```
Detailed calibration guide:
- Setup overview
- Coordinate systems
- Step-by-step process
- Alignment issues
- Troubleshooting
```

**VISUAL_GUIDE.md** (11 KB)
```
Visual aids and diagrams:
- Setup diagrams
- Coordinate mappings
- Step visualizations
- Flowcharts
- Examples
```

---

## 💻 System Requirements

- **Operating System**: Windows, macOS, or Linux
- **Python**: 3.6 or higher
- **Libraries**: pyserial, numpy
- **Hardware**: 
  - Pen plotter with GRBL firmware
  - USB connection (usually COM3 on Windows)
  - iPad (any size, portrait mode)
  - Solitaire app

---

## 📦 Installation

```bash
# Install Python dependencies
pip install pyserial numpy

# Verify plotter connection (Windows)
# Check Device Manager > Ports (COM & LPT)

# Place all files in same directory
# Run calibration
python calibrate_portrait.py
```

---

## 🎮 Workflow Summary

```
1. Setup Hardware
   ↓
2. Run calibrate_portrait.py
   ↓
3. Follow Interactive Wizard
   ├─ Test axes
   ├─ Find bounds
   ├─ Mark corners
   ├─ Take screenshot
   ├─ Measure pixels
   ├─ Enter coordinates
   └─ Test & verify
   ↓
4. Calibration Saved (calibration.json)
   ↓
5. Test with QuickTest.py
   ↓
6. Build Your Game Logic
   ↓
7. Play Solitaire!
```

---

## ✅ Success Checklist

Complete these to ensure successful calibration:

- [ ] All files in same directory
- [ ] Python 3.6+ installed
- [ ] pyserial installed
- [ ] Plotter connected (COM3 or noted)
- [ ] iPad in portrait mode
- [ ] Solitaire app open
- [ ] Ran calibrate_portrait.py
- [ ] Axis directions correct
- [ ] Bounds determined
- [ ] Screenshot taken
- [ ] Pixels measured
- [ ] Coordinates entered
- [ ] Tests passed
- [ ] calibration.json saved
- [ ] QuickTest.py works
- [ ] Ready for development!

---

## 🚨 Most Common Issues

**Issue #1**: Wrong COM port
- **Fix**: Check Device Manager, update in script

**Issue #2**: Axes inverted
- **Fix**: Swap bounds (x_min↔x_max or y_min↔y_max)

**Issue #3**: Can't see marks
- **Fix**: Adjust servo angle M3 S90 value

**Issue #4**: Wrong measurements
- **Fix**: Re-screenshot, measure carefully

---

## 📞 Getting Help

1. Check **README.md** troubleshooting
2. Review **QUICK_REFERENCE.md** common issues
3. Examine **VISUAL_GUIDE.md** flowcharts
4. Verify hardware connections
5. Test with manual G-code commands

---

## 🎯 Key Concepts

**Coordinate Mapping**: Converting iPad screen pixels (2048x2732) to plotter millimeters (180x250)

**Portrait Mode**: iPad orientation where height > width

**Calibration**: Process of determining the transformation between coordinate systems

**Bounds**: Min/max X and Y values for both plotter and iPad coordinate systems

---

## 🔗 Related Topics

After successful calibration, you'll need:
- Card detection (computer vision or manual)
- Game logic (Solitaire rules and solver)
- Move execution (tap and drag commands)
- Integration (connecting all parts)

---

## 📄 License & Usage

This calibration package is provided for personal/educational use. Feel free to modify and adapt for your specific plotter and application.

---

## 🎉 Ready to Begin!

**Start with**: PROJECT_SUMMARY.md

**Then run**: `python calibrate_portrait.py`

**Keep handy**: QUICK_REFERENCE.md

Good luck with your iPad Solitaire plotter! 🚀🎮🤖

---

*Package created: November 2024*
*Target: Portrait iPad Solitaire with GRBL Pen Plotter*

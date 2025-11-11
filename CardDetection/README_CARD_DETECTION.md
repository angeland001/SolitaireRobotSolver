# iPad Solitaire Solver - Card Detection Setup

## 🎯 Current Status

You now have:
- ✅ Plotter calibrated with coordinate mapping
- ✅ Basic card detection framework
- ⏳ Next: Test camera setup and refine card identification

## 📋 Step-by-Step Guide

### Step 1: Test Your Camera Setup

First, verify your camera can see the iPad:

```bash
python test_camera.py
```

**What to do:**
1. Position your camera to view the entire iPad screen
2. Make sure the solitaire game is visible and well-lit
3. Press 'c' to capture test frames
4. Press 'q' when done

**Tips:**
- Use even, overhead lighting (ring light recommended)
- Avoid glare on iPad screen
- Keep camera steady (use mount or tripod)
- Camera should be perpendicular to iPad surface

If camera index 0 doesn't work, try:
```bash
python test_camera.py 1  # Try camera index 1
python test_camera.py 2  # Try camera index 2
```

### Step 2: Test Card Detection

Once camera is positioned correctly:

```bash
python card_detector.py
```

**What to do:**
1. Live feed will show your iPad
2. Press 's' to analyze the current frame
3. Detection results will print to console
4. Green boxes show detected cards (if any)
5. Press 'q' to quit

**Expected Issues at This Stage:**
- ⚠️ Card rank detection is not yet implemented (will show "?")
- ⚠️ Suit detection is simplified (only red vs black)
- ⚠️ May detect false positives from screen elements

### Step 3: Capture Training Images

To improve card detection, we need sample images:

```bash
python test_camera.py
```

While the solitaire game is visible:
1. Press 'c' to capture multiple frames
2. Try to capture different game states
3. Save 5-10 different frames

These will be used to:
- Fine-tune detection parameters
- Create template images for rank recognition
- Test the full pipeline

### Step 4: What We Need to Implement Next

Based on your test results, we'll build:

1. **Enhanced Card Recognition**
   - Template matching for ranks (2-10, J, Q, K, A)
   - Better suit detection (♥️ ♦️ ♣️ ♠️)
   - Handle face-down cards

2. **Game State Parser**
   - Identify card piles (tableau, foundation, stock, waste)
   - Build game state representation
   - Track which cards can be moved

3. **Solitaire Solver**
   - Implement game rules
   - Find optimal moves
   - Generate move sequence

4. **Integration**
   - Connect card detection → solver → plotter
   - Handle move execution
   - Error recovery

## 🔧 Current Files

- `card_detector.py` - Main card detection module
- `test_camera.py` - Simple camera testing tool
- `CoordinateMapper_Swapped.py` - Coordinate conversion (already working!)
- `LoadCalibration_Smart.py` - Load calibration data
- `calibration.json` - Your plotter calibration

## 🐛 Troubleshooting

### Camera not opening
- Check USB connection
- Try different camera indices (0, 1, 2...)
- Check camera permissions in OS settings

### No cards detected
- Improve lighting (no shadows, no glare)
- Adjust `min_card_area` and `max_card_area` in card_detector.py
- Make sure cards are clearly visible
- Check camera focus

### False detections
- This is normal at this stage
- Will be improved with template matching
- Can adjust threshold parameters

## 📝 Next Session Prep

After testing, please provide:

1. **Camera test results:**
   - Does live feed show iPad clearly?
   - What camera index works?
   - Any glare or focus issues?

2. **Card detection results:**
   - How many cards were detected?
   - Any false positives?
   - Are card boundaries accurate?

3. **Sample images:**
   - Share 2-3 captured frames
   - Include different game states if possible

This will help me refine the detection and build the next components!

## 🚀 The Big Picture

```
[Camera Feed] → [Card Detection] → [Game State Parser] 
                                          ↓
[Plotter] ← [Coordinate Mapper] ← [Solitaire Solver]
```

We're currently at the **Card Detection** stage.

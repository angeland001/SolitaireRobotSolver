# Solitaire Robot Solver

A pen plotter holds an Apple Pencil Pro over an iPad and plays Klondike Solitaire by itself. The computer looks at the screen, works out which cards are where, picks the best move, and tells the plotter where to press and drag.

> **This file is the project's source of truth.** Architecture, decisions, conventions, and current status live here. When a decision changes, update this file in the same commit as the code that changes it.

---

## 1. Hardware

| Component | Details | Notes |
|---|---|---|
| Plotter | "LY Drawbot" style **CoreXY** pen plotter, AliExpress DIY kit ([build reference](https://luruke.medium.com/chinese-penplotter-at-55-aka-cnc-v3-shield-toys-diy-ly-drawbot-pen-lettering-corexy-xy-plotter-82f79b28dea1)) | Already assembled |
| Electronics | Arduino UNO (clone) + CNC Shield V3, 2× A4988 drivers, 2× SL42STH34-1334A steppers, 1× pen-lift servo | A4988 VREF set to ~0.6 V in the reference build |
| Firmware | GRBL 1.1h servo fork ([lavolpecheprogramma/grbl-1-1h-servo](https://github.com/lavolpecheprogramma/grbl-1-1h-servo)) compiled with **CoreXY** enabled; serial at **115200 baud** | Pen is a servo driven through spindle PWM: `M3 S<value>` sets its position (prior code used `S0` = up, `S90` = down) |
| Limit switches | **None by default** | Without them, `$H` homing doesn't work. Zero is wherever the gantry sits at power-on (see §1.1) |
| Host connection | USB serial, previously `COM3` on Windows | Port can change; keep it in config |
| Tablet | iPad Air **11"** (M2, 2024), portrait | 820×1180 pt = **1640×2360 px** (confirmed from the dataset's screenshots) |
| Stylus | Apple Pencil Pro, mounted in the pen holder | Must be paired and charged. Air M2 supports Pencil **hover**, which can show previews before contact (see §6) |
| Host computer | Windows 11 PC running Python | |

**Work area check (TODO):** the old `calibration.json` gives a 150×150 mm plotter travel. An 11" iPad's display is about 160×230 mm, so the plotter may not reach the whole screen. Measure the real travel before anything else, and confirm that every tap target in the game falls inside it, in whichever orientation the iPad sits.

### 1.1 Firmware facts and gotchas (from the build reference)

- **Kits ship with the wrong firmware.** The stock board ran plain GRBL v0.9i without CoreXY, so moving X also moved Y. Run `$I` to confirm the board reports 1.1h, then make one X move and one Y move and check that each moves only one axis.
- **CoreXY:** both motors work together on every move, so if one motor is weaker (bad VREF), the result is skewed diagonal motion, not just one slow axis. If moves come out diagonal or lose steps, check VREF first.
- **GRBL settings:** dump them with `$$` and save a copy to `config/grbl_settings.txt` so a reflashed board can be restored. The reference build's tuned settings were only shown as a screenshot; ours are the ones to trust. Settings guide: [Grbl v1.1 Configuration](https://github.com/gnea/grbl/wiki/Grbl-v1.1-Configuration).
- **No homing = no fixed origin.** Without limit switches, `(0,0)` is wherever the gantry was at power-on or reset. **Rule: the session starts by jogging to a physical reference corner and running `G92 X0 Y0`, then calibration (§3.2).** Adding limit switches to the CNC Shield's END STOP pins (as the reference author did) would make this repeatable and enable `$H`. It's optional, but a cheap upgrade.
- **Pen stability matters most** ("make sure the pen is stable", the author's top tip). For us that means the Pencil mount must not wobble or flex, or taps will land off-target or fail to register.

---

## 2. System overview

```
 ┌──────────────┐   screen frames  ┌──────────────┐   detections   ┌──────────────┐
 │   iPad game  │ ───────────────► │    Vision    │ ─────────────► │  Game state  │
 └──────────────┘   (mirroring)    │  (YOLO)      │                │  builder     │
        ▲                          └──────────────┘                └──────┬───────┘
        │ taps / drags                                                    │ Tableau, foundations,
        │ (Apple Pencil)                                                  │ stock, waste
 ┌──────┴───────┐   G-code (mm)    ┌──────────────┐   move (screen px)┌───▼──────────┐
 │  Pen plotter │ ◄─────────────── │  Executor +  │ ◄──────────────── │    Solver    │
 │  (GRBL)      │                  │  coord map   │                   │  / planner   │
 └──────────────┘                  └──────────────┘                   └──────────────┘
```

Each block is its own module with a small, testable interface. Everything above the executor works without the plotter connected, using saved screenshots.

---

## 3. Key design decisions

### 3.1 How the computer sees the game: **screen mirroring, not a camera**

The plotter itself never needs to see the screen. It only needs a **screen-pixel → plotter-mm mapping** (§3.2). The computer is the part that needs to see.

| Option | Pros | Cons |
|---|---|---|
| **AirPlay mirroring to an app window on the PC** (`capture.source: window`) | No hardware to buy | Needs an AirPlay receiver app on Windows (e.g. AirServer, LonelyScreen, or the open-source UxPlay); Wi-Fi latency; campus networks may block AirPlay discovery |
| **HDMI capture card** (`capture.source: camera`) | Most reliable, low latency, no network | Buy a USB-C→HDMI adapter + a USB HDMI capture dongle (UVC); some apps block HDMI output (HDCP), so test first |
| Overhead camera | No pairing; the old prototype used this | Glare, gantry occlusion, perspective correction, worse YOLO accuracy |

The YOLO dataset was built from screenshots of the app, so a mirrored frame is the closest match to the training data. The camera stays as a fallback.

**In use (2026-10-22):** the Windows app **"AirPlay - Screen Mirroring Receiver"** (`capture.window_title`). The window is captured with `PrintWindow`, so it works **even when other windows cover it**, but it must not be minimised. The receiver draws its own grey title bar inside the window; the cropper drops rows that are lit across the black side bars (window chrome), then checks the aspect ratio. First live read: crop 1336×1920, aspect **0.6958 vs 0.6949 expected (0.1%)**, and the game state read correctly, including three shimmering cards.

`solitaire.capture` trims the black bars around the mirror, **checks that the crop has the iPad's aspect ratio** (1640/2360 = 0.6949, within 2%), and resizes it to **1640×2360**. Every module works in these normalised screen pixels. Tested offline: a screenshot shrunk to 750×1080 (what a 1080p capture gives) reads exactly the same as the full-resolution original, so 1080p capture is plenty.

### 3.2 Calibration: screen pixels → plotter mm (implemented)

Three steps, each with its own tool (runbook in §4.4):
1. **Direction test** (`plotter_console.py` → `direction`): moves +X and then +Y with the pencil up, and you say which way it went on the iPad (up/down/left/right). Saved to `config/plotter_axes.json`. A diagonal move, or both axes moving along the same line, means CoreXY isn't set up right (§1.1), and the test refuses to continue. After this, jogging uses screen words (`left 5`).
2. **Grid calibration** (`calibrate.py`): with `tools/touch_target.html` open full screen on the iPad (it draws a dot wherever it's touched), you jog the pencil to the top-left and bottom-right of the area. That top-left point becomes the plotter's **(0, 0)**. The plotter taps a 3×4 grid, each new dot is found by differencing the mirrored frame before and after the tap, and a **homography** (pixels → mm) is fitted, which absorbs axis swaps, inversions, a tilted iPad and skew. Three extra taps aimed by pixel position check the fit. Saved to `config/calibration.json`. (The old `calibration.json` at the repo root is from the 2025 prototype and isn't used.)
3. **Pixel-dimension check** (part of step 2): the fit gives the screen's physical size in mm. It must match the iPad Air 11" spec (1640×2360 px at 264 ppi = **157.8 × 227.1 mm**) within 3%. A mismatch means the capture crop or the screen-size setting is wrong. The tool also prints how many mm the whole screen spans, so you can compare it with the plotter's travel.

- **Re-zero after a power cycle or reset** (`calibrate.py --rezero`): no limit switches means the zero is lost. One tap anywhere on the touch page plus the saved calibration tells the plotter exactly where it is, with no full recalibration.
- **Recalibrate fully** whenever the iPad moves in the cradle.

### 3.3 Interaction: **tap to move** (decided 2026-10-22), drag as fallback

The game has a 5-minute clock, so speed matters. A tap is one short pen-down; a drag needs a slow `G1` stroke.

- **Card move = tap the card.** The app auto-moves a tapped card to a legal **foundation** first, otherwise to the **left-most legal tableau column** (§6). The solver predicts that destination, taps when it's the move we want, and drags only when we want a different destination.
- To move a **run**, tap the run's top-most card, i.e. the visible strip of the highest card in the run.
- **Draw from stock / UI buttons:** single tap.
- **Drag fallback:** when a card has more than one legal destination and the app would pick the wrong one, drag instead: pen down on the source → `G1` to the destination → pen up.
- **Always verify:** after each tap, re-read the screen and confirm the card landed where expected. Record each mismatch so the model of the app's tap rules (§6) gets better.
- Tap timing: pen down → dwell ~50–100 ms → pen up. Tune the dwell until taps register every time without being taken as a long-press.

### 3.4 Solver strategy

Klondike is an **imperfect-information** game: face-down cards are unknown. Most open-source Klondike solvers (e.g. [ShootMe/Klondike-Solver](https://github.com/ShootMe/Klondike-Solver), [Solvitaire](https://github.com/thecharlieblake/Solvitaire)) assume the whole deal is known.

Because the game is timed and scored, the solver ranks moves by **expected score per second**. Each plotter action costs real time, and when no productive move is left it should press **Finish** rather than burn time cycling the stock.

**Draw-3 memory:** the waste fan shows every card each deal turns over. After one full pass through the stock, the robot knows the whole stock and its order. It stores that order and updates it as cards leave the waste, which turns the stock from hidden information into known information. On the first pass it should keep tapping the stock and recording cards, playing only obvious moves (e.g. to the foundations) as they come up.
*Limitation:* the dataset labels only the **top** (playable) waste card, never the two partly covered fan cards under it, so today the model sees one waste card per deal. To learn the full stock order in one pass, label those fan cards' visible strips in new screenshots. Until then, the stock is learned one top card at a time.

Plan:
1. **v1: our own legal-move generator + heuristic ranking** (foundation moves first, moves that reveal face-down cards, empty columns only for Kings, etc.). Recompute from a fresh screen read after every move.
2. **v2: lookahead search** over known cards, treating hidden cards as unknowns (or sampling possible deals and voting on a move).
3. Evaluate the open-source solvers above as a plug-in "planner" behind the same interface.

Whatever the solver is, the interface stays: `choose_move(state) -> Move | None`.

### 3.5 Game flow (control loop)

```
calibrate (once per session)
loop:
    frame  = capture()                      # mirrored screen
    dets   = detect(frame)                  # YOLO boxes + labels
    state  = build_state(dets)              # piles, face-up/down counts
    if not validate(state): retry / ask human
    if state.is_won(): stop
    move   = choose_move(state)
    if move is None: draw from stock, or declare stuck
    execute(move)                           # coord map → G-code
    wait_until_screen_stable()
    verify(expected_state, new_state)       # recover if mismatch
```

**Validation rules** (catch vision errors before they become bad moves): no card shows up twice; face-up cards in tableau runs alternate color and descend; at most 52 cards are accounted for; foundations are in order.

---

## 4. Repository layout (target)

```
SolitaireRobotSolver/
├── README.md                # ← this file (source of truth)
├── CLAUDE.md                # pointer for AI assistants: read README first
├── requirements.txt
├── config/
│   ├── settings.yaml        # serial port, pen angles, feed rates, screen size
│   └── calibration.json     # homography + metadata (generated)
├── solitaire/
│   ├── plotter/             # GRBL serial driver, pen up/down, tap, drag
│   ├── capture/             # mirrored-window grab + crop/rescale
│   ├── vision/              # YOLO inference → Card detections
│   ├── state/               # Card, GameState, StateBuilder (layout + rule checks)
│   ├── solver/              # move generation, heuristics, planners
│   ├── calibration/         # homography fit, touch-logger page
│   └── main.py              # the control loop (§3.5)
├── tools/                   # jog utility, screenshot capture, label helpers
├── models/                  # trained YOLO weights (git-ignored if large)
├── datasets/                # YOLO dataset (or pointer to where it lives)
└── tests/                   # unit tests using saved screenshots
```

Card label convention (fixed by the dataset): **`<rank><suit>`**, with rank in `A 2 3 4 5 6 7 8 9 10 J Q K` (upper case) and suit in `c d h s` (lower case), e.g. `10h`, `Qs`, `Ac`, plus **`facedown`**. That's 53 classes. Class IDs are alphabetical (`10c`=0 … `Qs`=51, `facedown`=52); always map them through `classes.txt`/`data.yaml`, never hard-code them.

### 4.1 Vision: dataset and training

- **Dataset:** Label Studio YOLO export at `C:/Users/rvj412/Downloads/Yolo/YoloSolitaire` (`images/`, `labels/`, `classes.txt`), path set in `config/settings.yaml`. It has 308 full-screen iPad screenshots (1640×2360 PNG) and 10,144 boxes. It stays **outside the repo** (659 MB, and the repo sits in OneDrive).
- **What a box covers:** a fully visible card gets its whole face. A card overlapped in a tableau column or the waste fan gets only its **visible top strip** (rank + suit). Each face-down card's visible strip is its own `facedown` box, so counting `facedown` boxes per column gives the number of hidden cards.
- **Class balance:** ~3,450 `facedown` boxes and 32–200 per card. Aces are the rarest (32–98) because they leave the tableau fast.
- **Purpose:** the screenshots exist only to train and evaluate the YOLO model.
- **Split: train / val / test = 224 / 42 / 42** (≈73/14/14). `tools/prepare_dataset.py` writes `datasets/yolo_solitaire/{train,val,test}.txt` + `data.yaml` (git-ignored) pointing at the source images, so nothing is copied.
  - **train** teaches the model; **val** picks the best epoch during training; **test** is never touched during training and gives the honest final score (`python tools/eval_detector.py --split test`).
  - The screenshots are sequential, so near-duplicates sit next to each other. Blocks of 6 consecutive shots are kept together and spaced evenly through the sequence, which keeps near-duplicates from leaking across splits.
  - Every class appears in every split except `As` in test (only 32 boxes in the whole dataset).
- **Training:** `tools/train_yolo.py` fine-tunes `yolo11s.pt` at `imgsz=1280` and copies the best weights to `models/cards.pt` (git-ignored). Augmentations that would change a card's meaning are **off**: no flips, no rotation, no hue shift (suit colour and the yellow highlight carry information).
- **Inference:** `solitaire.vision.CardDetector(...).detect(img) -> list[Detection]` with boxes in image pixels. To preview: `python tools/detect_image.py <screenshot>`.
- **Evaluation:** `python tools/eval_detector.py [--split val|train]` measures what the robot needs: are **all** cards on a screenshot right at `conf_threshold`? It saves annotated copies of any screenshot with an error to `runs/eval_errors/`. Treat mAP as secondary.

**Model v1 results** (2026-10-21, `runs/cards-2`, yolo11s @1280, batch 4, early-stopped at epoch 102, ~37 s/epoch). *These numbers use the older 248/60 train/val split, which had no test set. The 2026-10-22 re-split moved some v1 training images into test, so **v1 can't be scored on the new test set**. Retrain before quoting test numbers.*

| Split | mAP50 | Card-level accuracy | Screenshots read perfectly |
|---|---|---|---|
| val (60) | 0.992 | 2059/2069 (99.5%) | 46/60 (77%) |
| train (248) | — | 8045/8063 (99.8%) | 217/248 (88%) |

What the errors have in common: most land on cards wearing the app's **holographic pink/rainbow shimmer effect** (an animated overlay on some cards) and on the **"$" stock card**. Plain cards are almost always right. Val's 7 × `7d→6s` errors are one shimmering 7♦ seen in 7 consecutive screenshots. Fixes, in order:
1. **Game loop:** read 2–3 frames and accept a card only when the reads agree (the shimmer moves, so a frame without it usually follows); the §3.5 validation rules catch most of the rest.
2. **Data:** add screenshots where shimmering cards are present, label them, and retrain.

### 4.2 Game state

- `solitaire.state.StateBuilder().build(detections, width_px, height_px) -> GameState` assigns each box by **fixed screen position** (`layout:` in `config/settings.yaml`, measured from the dataset):
  - top row: 4 foundation slots, the waste fan (x 0.55–0.76; right-most card is playable), and the stock (x 0.808);
  - tableau: 7 columns, with each box matched to the nearest column centre within ±0.035 of screen width.
- `GameState` holds `foundations` (top card per slot), `waste`, `stock` (a face-down box, or `None` when the recycle icon shows), `tableau` (per column: face-down strips, then face-up cards top to bottom), and `issues`. Each card keeps its `Detection`, so the executor can tap its visible strip.
- **Validation never raises.** Problems go in `state.issues`, and `state.is_valid` is the gate: the loop doesn't act on an invalid state, it waits and re-reads. Checks: a card seen twice; a tableau run that breaks descending/alternating order; a face-down card below a face-up one; a column ending face-down (flip pending); a box between columns (card in motion); two foundations of one suit; a card visible that should be buried in a foundation; more than 3 waste cards.
- `python tools/check_states.py [--source labels|model] [--split all|val] [--image PATH]` runs the builder over the dataset and writes per-image issues to `runs/state_issues_*.txt`. Results (2026-10-22): **labels 277/308 valid, model 280/308 valid**. The failures are:
  - **mid-animation frames** (a card in flight shows up twice or between columns). Expected; the loop handles them by waiting.
  - the app's **pre-game prize-pick screen** (4 cards in a row at mid-screen). Not a board. **The robot starts only once a dealt board is on screen; menus and pre-game screens are handled by a person.**
  - **labelling mistakes in the dataset**, e.g. `IMG_0450` has a 6♠ labelled `8s` (confirmed), and `IMG_0736` has an oversized `5h` box. The rule checks double as a label auditor: `runs/state_issues_labels_all.txt` is the review list.

### 4.3 Hardware session runbook

Run everything from the repo folder with the venv's Python (`$py = "$env:USERPROFILE\.venvs\solitaire\Scripts\python.exe"` in PowerShell, then `& $py tools\...`).

**A. Live card detection (iPad only, no plotter needed)**
1. Mirror the iPad to the PC (§3.1). For a receiver window: `& $py tools\live_view.py --list-windows` to find its title, then `& $py tools\live_view.py --window "<part of title>"`. For a capture card: `& $py tools\live_view.py --camera 1` (try 0, 1, 2).
2. Check the bottom status line: **aspect OK** means the crop matches the iPad. Yellow guide lines should run down the middle of the 7 columns. `g` toggles guides, `s` saves the frame to `captures/` (useful as future training data), `q` quits.
3. The console prints the parsed game state whenever it changes.
4. Once it works, put the title/index in `config/settings.yaml` → `capture:` so the flags aren't needed.

**B. Plotter bring-up**
1. Plug in the plotter, find its COM port (Device Manager → Ports), and set `plotter.port` in settings.
2. `& $py tools\plotter_console.py`, then:
   - `info` → should say Grbl 1.1h; `settings` → saves `config/grbl_settings.txt` (note `$130`/`$131` = max travel).
   - `direction` → answer which way the pencil moved; saves `config/plotter_axes.json`.
   - Over a blank Notes page or the touch page: `pendown`, then `servo 60`, `servo 70`, … until the Pencil just registers. Put that value in `plotter.pen_down`. Then `tap` a few times to confirm every tap registers.

**C. Calibration**
1. Serve the touch page: `& $py -m http.server 8000 --directory tools`. On the iPad, open Safari at `http://<PC IP>:8000/touch_target.html` (find the IP with `ipconfig`) and use Share → Add to Home Screen, then open it from there for true full screen. If the network blocks this (common on campus Wi-Fi), use a phone hotspot, or a blank Notes page with a thick black marker: the tool only needs a dark mark on white.
2. Keep the mirror running, then `& $py tools\calibrate.py`. Jog to the top-left of the game area, `ok`; bottom-right, `ok`. It taps 12 points, fits, verifies, and prints the size check.
3. After any power cycle or reset: `& $py tools\calibrate.py --rezero`.

### 4.4 Environment

- Python 3.14, venv at `%USERPROFILE%\.venvs\solitaire` (kept **out of OneDrive** so thousands of package files don't sync).
- GPU: RTX PRO 1000 Blackwell (8 GB) needs PyTorch **CUDA 12.8+** wheels: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`, then `pip install -r requirements.txt`.

---

## 5. Status / roadmap

- [x] Plotter assembled
- [x] YOLO dataset of the app's cards collected (308 screenshots, 53 classes; see §4.1)
- [x] Dataset split + training + detector scripts
- [x] Train first model; review per-class metrics and failure cases (§4.1: 99.5% card-level on val)
- [x] App rules: draw-3, limited recycles, tap → foundation else left-most column, points from foundations + early-clear time bonus
- [ ] Remaining app TODO in §6: exact recycle count
- [ ] More labelled screenshots with shimmer-effect cards, the "$" stock card, and the Ace of spades; retrain
- [x] Capture module (window / capture card / monitor) + crop + aspect check; `live_view.py`
- [x] GRBL driver (`tap`, `drag`, zero, soft bounds) + `plotter_console.py` + direction test
- [x] Calibration tool (grid taps → homography → verify → pixel-size check) + `--rezero`
- [x] **Hardware run A:** AirPlay receiver app chosen; first live frame read correctly (§3.1)
- [ ] Watch `live_view.py` through a full game; save (`s`) any frames it misreads for the dataset
- [ ] **Hardware run B:** verify firmware (`$I`, `$$` backup), direction test, tune pen-down value
- [ ] **Hardware run C:** calibrate; confirm the size check passes and the game area is within plotter travel
- [ ] Train/verify YOLO model on mirrored frames
- [x] GameState builder + validation (§4.2)
- [x] Train / val / test split (224 / 42 / 42)
- [ ] Fix dataset label mistakes flagged in `runs/state_issues_labels_all.txt`, then retrain on the new split and score on test
- [ ] Multi-frame agreement: accept a state only when 2–3 consecutive reads match and are valid
- [ ] Heuristic solver v1
- [ ] End-to-end loop on a real game
- [ ] Lookahead solver v2 / external solver integration

---

## 6. Known risks & open questions

- **App: Solitaire Infinite: Win Cash** (iPad). Each game has a **5-minute timer** and is **scored**. The goal is maximum score before time runs out (or **Finish** is pressed), not only clearing the board.
  - **Draw-3 (confirmed 2026-10-22).** Each tap on the stock turns over 3 cards onto the waste fan, and only the top (right-most) one is playable. Tapping the stock again deals the next 3. When the stock is empty (recycle icon), tapping it puts the waste back. **Recycles are limited (confirmed)**, so the stock can't be cycled forever. Every pass counts. **TODO:** exact number of passes, and what the stock shows when no recycles are left.
  - **Tap-to-move rule (confirmed):** a tapped card goes to a **foundation if one is legal**. Otherwise it goes to the **left-most** legal tableau column.
  - **Scoring (confirmed):** points come from **putting cards on the foundations**, plus a **time bonus for clearing the board early**. So the objective is to clear the board as fast as possible, or failing that, get the most foundation cards before the 5 minutes run out.
- What the screenshots show about the layout (portrait):
  - Top bar: timer + gem counter.
  - Row 1, left to right: **4 foundation slots** (empty slots show a faint "A"), the **waste fan** (up to 3 cards visible, overlapping left to right), and the **stock** at the far right (a recycle icon when empty).
  - Row 2: **7 tableau columns**. Face-down cards show as purple strips.
  - Bottom bar: **Pause / Finish / Undo** buttons.
  - Some cards are tinted **yellow** (a hint or selection highlight); the detector has to handle both tints.
  - Some cards carry an animated **holographic pink/rainbow shimmer**. These cause most detector errors (§4.1).
  - The stock's top card varies: purple back, a **"$" card**, or the recycle icon when empty. The timer, gems and stars point to a timed, scored (possibly cash-tournament) app, so moves are against the clock.
- **Pencil hover:** on M2 iPads, the Pencil Pro hovering near the glass can trigger hover UI. Keep pen-up height large enough (>12 mm) or check that the app ignores hover.
- **Touch registration:** the servo has to bring the tip into reliable contact; tilt of the holder matters. A capacitive-tip stylus is the fallback if the Pencil gives trouble.
- **Animations:** the state read must wait for card animations to finish (compare consecutive frames).
- **Plotter reach** vs. screen size (see §1).
- **Origin drift:** with no limit switches, a reset or a stall loses the origin. If taps start missing, re-zero and re-verify calibration before blaming vision.
- **Hidden-information solver:** some deals are unwinnable, so the loop must detect "stuck" and stop cleanly.

---

## 7. Conventions

- Python 3.11+ (prior work used 3.13). Dependencies in `requirements.txt` (`pyserial`, `numpy`, `opencv-python`, `ultralytics`, `mss`/window capture, `pyyaml`).
- **Coordinate spaces are explicit in names:** `*_px` = normalised iPad screen pixels (1640×2360, what the detector and layout use), `*_mm` = plotter millimetres relative to the calibrated zero, `*_raw` = raw capture-frame pixels (only inside `solitaire.capture`). Convert px↔mm only via `solitaire.calibration.Calibration`.
- No hard-coded ports, angles, or sizes in code; they belong in `config/settings.yaml`.
- Every module runs offline on saved screenshots so the plotter isn't needed for development.
- Don't commit `__pycache__/` or large model weights.

---

## 8. History

- **Nov 2025:** first prototype: GRBL controller, interactive "smart" calibration (axis swap/invert detection, min/max bounds), overhead-camera card detection. Saved `calibration.json` (portrait, axes swapped, 150×150 mm travel).
- **Oct 2026:** prototype code removed; restarting with the architecture above. The old code is still in git history (commit `5fc5fe8`) for reference, including `Calibration/plotter_controller.py`.

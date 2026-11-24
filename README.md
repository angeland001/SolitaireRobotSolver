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
| Host connection | USB serial via the UNO clone's CH340 chip (USB ID `1A86:7523`; was `COM7` on 2026-11-09, `COM3` is another device) | The COM number can change with the USB port, so `plotter.port: auto` finds it by USB ID (`solitaire.plotter.find_port`); `--port COMx` overrides |
| Tablet | iPad Air **11"** (M2, 2024), portrait | 820×1180 pt = **1640×2360 px** (confirmed from the dataset's screenshots) |
| Stylus | Apple Pencil Pro, mounted in the pen holder | Must be paired and charged. Air M2 supports Pencil **hover**, which can show previews before contact (see §6) |
| Host computer | Windows 11 PC running Python | |

**Work area check (TODO):** the old `calibration.json` gives a 150×150 mm plotter travel. An 11" iPad's display is about 160×230 mm, so the plotter may not reach the whole screen. Measure the real travel before anything else, and confirm that every tap target in the game falls inside it, in whichever orientation the iPad sits.

### 1.1 Firmware facts and gotchas (from the build reference)

- **Kits ship with the wrong firmware.** The stock board ran plain GRBL v0.9i without CoreXY, so moving X also moved Y. Run `$I` to confirm the board reports 1.1h, then make one X move and one Y move and check that each moves only one axis.
- **CoreXY:** both motors work together on every move, so if one motor is weaker (bad VREF), the result is skewed diagonal motion, not just one slow axis. If moves come out diagonal or lose steps, check VREF first.
- **CoreXY diagonals run one motor at double speed.** GRBL caps X and Y separately (`$110/$111` = 8000 mm/min), so a G0 diagonal drives one motor at up to 16000 mm/min, and it skipped steps (2026-11-11: calibration check taps off by ~40 mm, **equal in X and Y**, the signature of one motor slipping). Pen-up moves therefore use `G1` at `plotter.travel_feed` (3000 mm/min), not `G0`. That alone wasn't enough: the **X+Y motor** still slipped on +X+Y diagonals, where it runs 1.41× the feed rate. So the driver now caps **motor** speed: every move and drag is slowed until the busier motor runs at no more than the feed rate (`Grbl._corexy_feed`; straight moves keep full speed, 45° diagonals drop to ~71%). That didn't fix it either, so **`plotter.axis_moves: true` (default) makes every move and drag go X first, then Y**. No move is diagonal, and straight moves never slipped. It costs a little time per move. **2026-11-16: diagonals back on** (`axis_moves: false`) and feeds raised (`travel_feed` 6000, `drag_feed` 2500 mm/min), with the motor-speed cap still applied. **2026-11-23: `axis_moves: true` again.** Right after a successful `--rezero` and park, the first game move, a +X+Y diagonal from the zero, missed its card. If misses continue with `axis_moves: true`, lower the feeds next. **2026-11-24: `travel_feed` 6000 → 8000** (GRBL's `$110/$111` ceiling) after a clean 70-move v3 game; with `axis_moves` every move is straight. Going higher means raising `$110/$111` on the board too. Drags (`drag_feed` 2500) and acceleration are unchanged. Equal X/Y errors = one CoreXY motor slipping. If it still happens, lower `$120/$121` (acceleration, now 1200), then check that motor's VREF.
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

**In use (2026-11-11): AirServer** (Windows Desktop Edition, paid with a trial). It replaced the free receiver below because that one kept dropping the stream. Its mirror window is titled "AirServer - AirServer Windows Desktop Edition", which matches the first entry in `capture.window_title`. First read: crop 1335×1920, aspect 0.6953 (OK).
**Before that (2026-10-22):** the Windows app **"AirPlay - Screen Mirroring Receiver"** (process `airplay_receiver`). By 2026-11-11 its window title had changed to **"AirMirroring"**, so `capture.window_title` is a list of titles and the first match wins. The window is captured with `PrintWindow`, so it works **even when other windows cover it**, but it must not be minimised. The receiver draws its own grey title bar inside the window; the cropper drops rows that are lit across the black side bars (window chrome), then checks the aspect ratio. Dark rows of the iPad screen itself (e.g. the black status bar above the white touch page) look like letterbox, so a crop that comes out too short is grown back to the iPad's shape from its width, upwards and never into the chrome (fixed 2026-11-11: aspect 0.715 → 0.696). First live read: crop 1336×1920, aspect **0.6958 vs 0.6949 expected (0.1%)**, and the game state read correctly, including three shimmering cards.

`solitaire.capture` trims the black bars around the mirror, **checks that the crop has the iPad's aspect ratio** (1640/2360 = 0.6949, within 2%), and resizes it to **1640×2360**. Every module works in these normalised screen pixels. Tested offline: a screenshot shrunk to 750×1080 (what a 1080p capture gives) reads exactly the same as the full-resolution original, so 1080p capture is plenty.

### 3.2 Calibration: screen pixels → plotter mm (implemented)

Three steps, each with its own tool (runbook in §4.4):
1. **Direction test** (`plotter_console.py` → `direction`): moves +X and then +Y with the pencil up, and you say which way it went on the iPad (up/down/left/right). Saved to `config/plotter_axes.json`. A diagonal move, or both axes moving along the same line, means CoreXY isn't set up right (§1.1), and the test refuses to continue. After this, jogging uses screen words (`left 5`).
2. **Grid calibration** (`calibrate.py`): with `tools/touch_target.html` open full screen on the iPad (it draws a dot wherever it's touched), you jog the pencil to the top-left and bottom-right of the area. That top-left point becomes the plotter's **(0, 0)**. The plotter taps a 3×4 grid, each new dot is found by differencing the mirrored frame before and after the tap, and a **homography** (pixels → mm) is fitted, which absorbs axis swaps, inversions, a tilted iPad and skew. Three extra taps aimed by pixel position check the fit. Saved to `config/calibration.json` **only if** the found dots span at least 3 grid rows and 3 columns and every check tap lands within `calibration.max_check_error_px` (30 px). A fit through dots on only two lines can show a tiny RMS and still miss by centimetres (seen 2026-11-11, after a jog past the end of travel skipped steps). (The old `calibration.json` at the repo root is from the 2025 prototype and isn't used.)
3. **Pixel-dimension check** (part of step 2): the fit gives the screen's physical size in mm. It must match the iPad Air 11" spec (1640×2360 px at 264 ppi = **157.8 × 227.1 mm**) within 3%. A mismatch means the capture crop or the screen-size setting is wrong. The tool also prints how many mm the whole screen spans, so you can compare it with the plotter's travel.

- **Re-zero after a power cycle or reset** (`calibrate.py --rezero`): no limit switches means the zero is lost. One tap anywhere on the touch page plus the saved calibration tells the plotter exactly where it is, with no full recalibration. It then **parks on the zero** (fixed 2026-11-23: it used to leave the pencil mid-page, and since opening the port resets the Arduino, the next program would have taken mid-page as its zero). **Rule: every program that moves the plotter ends parked at (0, 0).**
- **Recalibrate fully** whenever the iPad moves in the cradle.

### 3.3 Interaction: **tap to move** (decided 2026-10-22), drag as fallback

The game has a 5-minute clock, so speed matters. A tap is one short pen-down; a drag needs a slow `G1` stroke.

- **Card move = tap the card.** The app auto-moves a tapped card to a legal **foundation** first, otherwise to the **left-most legal tableau column** (§6). The solver predicts that destination, taps when it's the move we want, and drags only when we want a different destination.
- To move a **run**, tap the run's top-most card, i.e. the visible strip of the highest card in the run.
- **Draw from stock / UI buttons:** single tap.
- **Drag fallback:** when a card has more than one legal destination and the app would pick the wrong one, drag instead: pen down on the source → `G1` to the destination → pen up.
- **Always verify:** after each tap, re-read the screen and confirm the card landed where expected. Record each mismatch so the model of the app's tap rules (§6) gets better.
- Tap timing: pen down → dwell ~50–100 ms → pen up. Tune the dwell until taps register every time without being taken as a long-press.
- **Executor (built 2026-11-23, `solitaire/executor.py`):** `Executor.plan(move, state) -> Action` is pure: it picks the touch points in normalised px and converts them with `Calibration.px_to_mm`. A card is touched at the centre of its box (for a covered card that's its visible strip). A drag ends on the destination's exposed card, or for an empty column at `layout.tableau_top_y + card_height/2`. The stock is its box, or `layout.stock_x/stock_y` when it shows the recycle icon. `plan_button("finish"|"undo")` uses `layout.finish_button/undo_button`. Points off the screen are refused (`ValueError`). `perform(action)` sends it to `Grbl.tap`/`drag`; with `plotter=None` it only plans (dry run). `solve_states.py --image` prints the planned action in px and mm. **Untested on hardware:** whether the app accepts a drag that starts moving straight after pen-down (it may need a short hold first), and the Finish/Undo positions, which were read off one screenshot.

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

**v1 as built (2026-11-23, `solitaire/solver/`):**
- `legal_moves(state)` lists every legal move on the visible board (waste/tableau → foundation, waste → tableau, any face-up run → tableau, then a stock tap: draw, or recycle when the stock shows the recycle icon). Foundation → tableau is left out. Each `Move` is marked **`tap`** when the app's tap rule (`tap_destination`: foundation first, else left-most legal column) sends the card where we want, otherwise **`drag`**. A `Move` carries the `PlacedCard` to touch (the run's top-most card) and pile indices, no coordinates; the executor turns it into pixels.
- `Solver.choose_move(state)` scores the non-stock moves (weights in `settings.yaml` → `solver.weights`): foundation moves, more if *safe* (no tableau card could still need it); moves that reveal a face-down card, more for deeper columns; emptying a column **only** while a King is waiting for it; splitting a run **only** to free a card for the foundation; waste → tableau; minus a penalty for drags. Moves that achieve none of these get no score, which also keeps it from shuffling cards back and forth. With nothing scored it taps the stock. It returns **`None` (press Finish)** when it would recycle with nothing played since the last recycle (the next pass would deal the same cards), or when `solver.max_recycles` is used up. A new `Solver` allows one recycle first, since it may join mid-game. It refuses (`ValueError`) to plan on an invalid state.
- The game loop keeps one `Solver` and calls `solver.executed(move)` after each move is verified on screen.
- Offline check: `python tools/solve_states.py --image <screenshot>` prints the board and every scored move; without `--image` it tallies the chosen move over the dataset (2026-11-23: all 277 valid labelled boards get a move, every pick is a tap). Unit tests: `python -m pytest tests`.

**v2 as built (2026-11-23, `solitaire/solver/memory.py`, `planner.py`; settings `solver.plan`):** v2 is on by default, and v1 is its fallback.
- **Stock memory (`StockMemory`).** The stock and waste together are one fixed sequence (the *talon*). A draw moves a pointer forward 3 cards, a recycle moves it back to 0, and playing the waste top removes one card. Nothing else changes the order. Every waste top the camera sees is written to its place in the sequence, so after one pass the solver knows what each future draw will show. The talon size is 52 − foundations − tableau.
  - The pointer is placed on a fresh deal (waste empty), when the stock is empty, or when the waste top is a card it already knows. A read that contradicts the memory unplaces the pointer until one of those happens again.
  - A waste card that went somewhere unexpected (no `executed()`) is noticed by the count and removed.
- **Lookahead (`planner.search`).** A beam search (300 lines per depth, up to 60 moves, at most 1 s) over a small simulation of the board, with the same move set as the executor (no foundation → tableau).
  - A card turned over in the plan is *unknown*: nothing moves it or goes on it, and an unknown stock card can't be played.
  - A line scores the change in: foundation cards, minus a penalty for each rank a suit runs ahead of the other colour's lower suit + 2 (the "keep 5h down while 4c may need it" rule); face-down cards turned over; cards out of the stock; empty columns. Drawing an unknown stock card into view earns a small bonus. Later gains count slightly less (`discount`), and every move costs a little time (more for a drag).
  - The best line's first move is played, then the next board is planned again from scratch. Positions the game has already been in are never planned into again (no shuffling across replans).
- **Stuck.** When the search covered every reachable position (no beam cut) and no line gains anything, `choose_move` returns `None` and the loop presses **Finish** (`game.press_finish`, back on since the retrain). This is "stuck" in the full sense: no sequence of draws, waste plays that shift the draw-3 alignment, or tableau moves leads anywhere. The v1 rule ("a pass with nothing played") only judged one pass.
- **Fallback to v1:** while the stock pointer is unknown, or when the search hits its budget without a gain.
- **Logging.** Each move logs the plan, e.g. `plan +24.4 (169 positions, stock 24/24 known): draw(Qd), Qd W->c1, draw(3s), …, recycle, draw(Ac), Ac W->F`.
- **Offline benchmark.** `python tools/simulate_games.py [--games N] [--v1]` plays random draw-3 deals through the real `Solver`, seeing only what the camera would (face-down counts, the waste top). On 300 deals (2026-11-23): **v2 won 61 (20%), mean 16.6 foundation cards; v1 won 33 (11%), mean 12.2.** The slowest plan took 0.26 s. Weights were tuned the same way. Tests: `tests/test_planner.py`.
- **Next improvement:** sampling the hidden cards, built as v3 (below).

**v3 as built (2026-11-24, `solitaire/solver/sampling.py`, `solitaire/main_v3.py`; settings `solver.v3`):** a separate entry point, `python -m solitaire.main_v3 [--dry-run]`. `python -m solitaire.main` stays the working v2 backup and is unchanged.
- **Sampled worlds.** The unseen cards are known as a *set* (not on a foundation, not face-up, not in the stock memory). `SolverV3.sample_world` deals that set at random into the face-down tableau slots and unknown talon positions. In a world everything is known, so a beam search (`first_move_values`, `beam_width` 40, `max_depth` 30, weights from `solver.plan`) plans through flips and draws and reports the best line value for each move playable now. Values are averaged over `samples` (12) worlds, within `max_seconds` (2 s) total, and the best average is played. A move that only pays off if a hidden card happens to be right loses to one that is good whatever is hidden.
- **Undo peeks.** The app's Undo takes back the last move only. So a move that turns a face-down card over can be played, the new card read, and the move undone: that column's top hidden card is then known and every later world deals it there (`record_peek`; it stays valid while the column keeps the same face-down count). A peek is asked for (`peek_col`) when a column other than the one the best move flips could be turned over now and its best flip scores within `peek_margin` (15) of the best move. Capped at `max_peeks` (12) per game, since each costs a move + an Undo. `GameLoopV3` plays the peek, reads the card, presses Undo and checks the board came back. If it didn't, play carries on from the board as it is (the peeked move then counts as played). **Confirmed on hardware (2026-11-24):** the first live peek (col 3, read 6h) pressed Undo at `layout.undo_button` and the board came back exactly as before. In that peek the solver then played the same move for real, so it cost a move + Undo without changing the decision; if that keeps happening, lower `peek_margin`.
- Everything else (stock memory, no replanning into past positions, v1 fallback, stuck → Finish) is v2's `Solver`. When no sampled move gains, v2 decides.
- `solver.v3.enabled: false` makes `SolverV3` behave exactly like v2.
- **Offline benchmark:** `python tools/simulate_v3.py [--games N] [--workers 2] [--no-peek] [--set key=value]` plays v2 and v3 on the same deals (a peek counts as 2 actions). **Keep `--workers` low:** each v3 move can think for up to `max_seconds`, and one worker per core maxed out the PC on 2026-11-24 (the default is now 2). **First comparison (2026-11-24, 200 deals, seeds 1–200, 2 workers, 1335 s):** v2 won 40 (20.0%, mean 16.4 foundation cards); v3 won 45 (22.5%, mean 17.0), 0.5 peeks per game, slowest move 0.87 s. Only v3 won 20 deals, only v2 won 15: within noise, so v3 is at least as good, not yet shown better. Tuning runs: `--solvers v3 --set key=value` on the same seeds, compared with v3's 45/200. Tests: `tests/test_sampling.py`.

**Open-source solvers checked for v2 (2026-11-23).** None of them handles hidden cards the way we need, so they would go behind the planner interface, fed one or more *sampled* deals that match what's visible (§3.4 plan 2–3):
| Project | Language | Use for us |
|---|---|---|
| [ShootMe/Klondike-Solver](https://github.com/ShootMe/Klondike-Solver) | C++ | Fast, solves known deals, supports draw 3. Most likely candidate |
| [pyksolve](https://pyksolve.readthedocs.io/en/stable/pyksolve.html) ([repo](https://github.com/tcdude/py-klondike-solver)) | Python (Cython wrapper of the above) | Checked 2026-11-24: v0.0.15 (MIT) has a ready-made Windows package for Python 3.14 and solves a fresh draw-3 deal in ~0.2 s, **but only loads fresh 52-card deals** (`load_solitaire`, deck order). `load_pysol` rejects foundations/waste and doesn't even reload its own output, so it can't take a mid-game position: **not usable for per-move solving as is** |
| [lonelybot](https://github.com/vuonghy2442/lonelybot) | Rust | Solves "thoughtful" (all cards known) and *random* Klondike, the closest match to our hidden-card problem |
| [Solvitaire](https://github.com/thecharlieblake/Solvitaire) | C++ | General patience solver; perfect information only |
| [scottwillmoore/klondike](https://github.com/scottwillmoore/klondike) | Rust | Thoughtful Klondike engine |
| [Blake & Gent, *Winnability of Klondike*](https://arxiv.org/abs/1906.12314) | paper | Background: ~82% of thoughtful deals are winnable; methods for hidden-card play |

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

**As built (2026-11-23, `solitaire/main.py`, settings `game:`):** `GameLoop` reads with `StableReader` (§4.2), asks `Solver`, plans with `Executor`, performs, then `read_change`s. A move counts as **landed** if the card is now in the predicted pile (foundation: its suit's top is at least that rank); then `solver.executed(move)` is called. A changed board where the card went elsewhere is logged as a **MISMATCH** (the tap rule's prediction was wrong, §3.3, or the board was misread) and play continues from the board as it really is. **A move that mismatched is never tried again that game** (`Solver.failed` / `blocked`, keyed by card, source and destination; v1, v2 and v3 all skip it). Added 2026-11-24, after the top waste card (8d) went undetected on every frame, the card under it (Qd) was taken for the top, and "Qd W->c5" was tapped and failed on four passes in a row, 10 MISMATCHes in 44 moves. An unchanged board is retried, each try touching the card a little lower or higher (`retry_nudges`, fractions of its box height). A covered card's visible band is only ~80 px ≈ 8 mm, so a few mm of drift lands on the card above or below, which usually has no move, so nothing happens. After `max_missed_moves` retries it **re-aims**: the raised pencil hovers over the card and you jog it on target (live runs; otherwise it stops). It also stops on a win, **including the app's auto-finish** (2026-11-24): once no tableau card is face down, the app sorts the rest onto the foundations by itself at some point, but its exact condition is unknown: game 1 it did with the stock empty and 1 card on the waste; games 2 and 3 it didn't, with cards left in the stock, or the stock empty and 8 cards on the waste. Two earlier versions of this rule guessed the condition and stopped the robot too early. So the loop **never stops on a board it can read**: it keeps playing, and a board that can't be read after a move that leaves no tableau card face down is taken as the finishing animation and win screen (`main.may_trigger_auto_finish`). If the app never takes over, the robot plays every card up itself. A win prints a **GAME WON** banner and beeps (`game.notify_win`). It also stops when stuck (pressing Finish first if `press_finish`), and after `max_unreadable` failed stable reads. The plotter is opened with `bounds_mm` = the calibrated screen minus `bounds_margin_mm`, and **always parks on the zero on exit** (opening the port resets GRBL, which takes wherever the pencil is as the new zero). Every game writes a log to `runs/games/`.

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
│   ├── executor.py          # Move → touch points (px → mm) → plotter tap/drag (§3.3)
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

#### Fixing labels and retraining (2026-11-23)

Instead of re-importing all 308 images, build a small Label Studio project of the images worth a second look, then merge the fixes back.

1. **Collect live frames first** (the model's weak spot is the mirrored screen, especially shimmering ♦/♥ cards): play with `live_view.py` and press `s` whenever a shimmering card is on screen. `main.py` also saves misreads to `captures/misreads/`.
2. **Build the review set:** `& $py tools\make_review.py`. It writes `C:\Users\rvj412\Downloads\Yolo\review\` (`vision.review_dir`): `images/`, `tasks.json`, `labeling_config.xml`, `review_list.txt`. Three kinds of task, each with a `reason`: **label-rule** (the hand labels break the game's rules or needed a repair: fix the label); **model-vs-label** (the model disagrees: fix the label if *it* is wrong; if the model is wrong, e.g. the shimmering `7d` read as `6s` in IMG_0572–0579, just Submit); **live** (new frames pre-filled with the model's guesses: correct every box).
3. **Start Label Studio with local files allowed.** Label Studio doesn't run on Python 3.14 (an old `django-environ` dependency uses the removed `pkgutil.find_loader`), so it's installed as its own tool with Python 3.12: `uv tool install --python 3.12 label-studio --with "sentry-sdk<3"`. That puts `label-studio` in `~\.local\bin`; sentry-sdk 3.0 crashes it at startup. Then, in PowerShell:
   ```powershell
   $env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"
   $env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = "C:\Users\rvj412\Downloads\Yolo"
   label-studio start
   ```
4. **New project** "Solitaire review": Labeling Setup → Custom template → Code → paste `labeling_config.xml`. Settings → Cloud Storage → Add Source Storage → **Local files**, absolute path `C:\Users\rvj412\Downloads\Yolo\review\images`, Add Storage. **Don't Sync it**: the storage only grants access to the images, and the tasks come from `tasks.json`. A Sync in the default import mode fails ("…PNG is not a JSON/JSONL/Parquet file"), which is harmless; in "Files" mode it would add 60 duplicate, unlabelled tasks. Settings → Annotation → turn on **Use predictions to prelabel tasks**. Then Import → `tasks.json`. In the Data Manager, show the `kind` and `reason` columns to sort the work.
5. **Fix and Submit** every task. A covered card's box is its visible strip (rank + suit); a fully visible card gets its whole face; each face-down strip is its own `facedown` box; only the top waste card is labelled (§4.1).
6. **Export** → YOLO → zip. Then `& $py tools\merge_review.py <zip> --dry-run`, check the counts, and run it again without `--dry-run`. Dataset labels it replaces are backed up to `labels_backup_<time>/` first, and live frames are copied in as new images.
7. **Retrain:** `& $py tools\prepare_dataset.py`, then `& $py tools\train_yolo.py` (≈1 h on the RTX; the previous `models/cards.pt` is kept as `cards_prev_<time>.pt`). Check with `& $py tools\eval_detector.py --split test` and `& $py tools\check_states.py --source model`, and compare with the 2026-11-23 baseline: 292/308 model boards valid.
   - **Review round 1 (2026-11-23, `runs/cards-3`):** 50 labels fixed and 10 live frames added. Labels are now valid on 302/318 boards and the **model on 303/318**. On the val split it reads 1407/1407 cards correctly (0 wrong, 0 missed, 2 phantom face-downs) and mAP50-95 is 0.935. The remaining failures are mostly mid-animation frames, which the loop already waits out. The previous model is kept as `models/cards_prev_20261123_153239.pt`.

### 4.2 Game state

- `solitaire.state.StateBuilder().build(detections, width_px, height_px) -> GameState` assigns each box by **fixed screen position** (`layout:` in `config/settings.yaml`, measured from the dataset):
  - top row: 4 foundation slots, the waste fan (x 0.55–0.76; right-most card is playable), and the stock (x 0.808);
  - tableau: 7 columns, with each box matched to the nearest column centre within ±0.035 of screen width.
- `GameState` holds `foundations` (top card per slot), `waste`, `stock` (a face-down box, or `None` when the recycle icon shows), `tableau` (per column: face-down strips, then face-up cards top to bottom), and `issues`. Each card keeps its `Detection`, so the executor can tap its visible strip.
- **Run repair** (2026-11-23, `StateBuilder._repair_runs`): face-up tableau cards always form a valid run in a real game. So when a covered card doesn't fit, but the cards above and below it fit each other (above = rank+1, below = rank−1, same colour as each other), its rank and colour are known. If only one of the two suits is unseen, the builder replaces the label and records it in `state.repairs` (printed as `~ repaired`). Prompted by the third live game, which stopped because a plain `8d` strip in `10d 9s 8d 7c` was read as `9d` on every frame. Repaired boards are saved for labelling as kind `repaired`. Effect on the dataset: model 280 → 289/308 valid, labels 277 → 280. The label repairs are **dataset labelling mistakes** to fix before retraining: `IMG_0571` col 1 strip labelled `6s` is `7d`, `IMG_0735` col 7 `Jh` is `6h`, `IMG_0590` col 3 `Jc` is `Qd` (all normal ~80 px strips, not cards in flight).
- **Duplicate repair** (2026-11-23, `StateBuilder._repair_duplicates`, `repair.duplicate_conf_margin` 0.15): when a card is read twice, the copy that is clearly less confident (by the margin) becomes its same-colour sibling (♦↔♥, ♣↔♠), if that card is nowhere on the board. The live misreads mostly keep rank and colour and swap the suit, mostly on shimmering cards. Fourth live game: a shimmering `Kd` read as `Kh` at 0.69 while the real `Kh` sat on the waste at 0.95, so every read had "Kh seen 2 times" and it stopped after 8 moves. Without a clear loser (e.g. hand labels, all conf 1.0) nothing changes. Spot check of the model's reads over the dataset: 12 of 13 repairs right (`4s`, the shimmering `7d` read as `6s` ×8, `Qd` ×2). One was wrong: `IMG_0597`, where the detector put more confidence on its `9s`→`9c` misread than on the real `9c`, so the two black 9s swapped places. The rules can't see that, but a later move on either card would show as a MISMATCH. Model reads over the dataset: 280 → 292/308 valid with both repairs.
- **Validation never raises.** Problems go in `state.issues`, and `state.is_valid` is the gate: the loop doesn't act on an invalid state, it waits and re-reads. Checks: **cards unaccounted for**: with the stock showing the recycle icon and the waste empty, every unseen card must be face-down in the tableau. More unseen than that means a card on screen wasn't recognised. Added 2026-11-23 after the fifth live game, where a shimmering waste `Qd` (best guess `Qs` at 0.13) went unseen. The solver saw no stock, no waste and no scored move, and pressed Finish with `Qd`→`Ks` still legal. That game is also why `game.press_finish` is now `false`. On the dataset this rule also flags `IMG_0738`, whose labels are missing three foundation cards. Other checks: no cards on screen at all (a black mirror or a menu would otherwise pass as an empty board, and the solver would press Finish); a card seen twice; a tableau run that breaks descending/alternating order; a face-down card below a face-up one; a column ending face-down (flip pending); a box between columns (card in motion); two foundations of one suit; a card visible that should be buried in a foundation; more than 3 waste cards.
- **Multi-frame agreement** (`solitaire/state/stable.py`, settings `stability:`): a board is trusted only once `agree_frames` (3) consecutive reads are valid and have the same `GameState.signature` (the cards in every pile, ignoring box positions and confidences). That removes both shimmer misreads (§4.1 fix 1) and mid-animation frames. `StabilityTracker` is the pure part; `StableReader(read_state)` loops over frames with timeouts: `read()` returns a stable board or `None` after `read_timeout_s` (mirror dropped, menu on screen; `last_issues` says why), and `read_change(before)` waits up to `change_timeout_s` for a stable board that *differs* from `before`, returning `(state, changed)`. `changed=False` means the tap didn't register. **2026-11-24 changes**, after a game stopped on a board it could have played: (1) invalid reads between agreeing ones are skipped, not a reset (`max_invalid_between`, 3 in a row at most), because a covered `6d` strip the detector found only on some frames ("5c cannot sit on 7c") kept the board from ever settling, and the loop gave up with moves left; (2) when the screen *did* change (`agree_frames` reads in a row unlike the old board) but the new board never settled, `read_change` returns `(None, False)` instead of "unchanged", so the loop re-reads instead of tapping again. Before this, the retry tap played a second, unplanned move (Jh went to column 1). `live_view.py` shows `STABLE` / `settling n/3` and prints the board only when a new one settles.
- `python tools/check_states.py [--source labels|model] [--split all|val] [--image PATH]` runs the builder over the dataset and writes per-image issues to `runs/state_issues_*.txt`. Results (2026-10-22): **labels 277/308 valid, model 280/308 valid**. The failures are:
  - **mid-animation frames** (a card in flight shows up twice or between columns). Expected; the loop handles them by waiting.
  - the app's **pre-game prize-pick screen** (4 cards in a row at mid-screen). Not a board. **The robot starts only once a dealt board is on screen; menus and pre-game screens are handled by a person.**
  - **labelling mistakes in the dataset**, e.g. `IMG_0450` has a 6♠ labelled `8s` (confirmed), and `IMG_0736` has an oversized `5h` box. The rule checks double as a label auditor: `runs/state_issues_labels_all.txt` is the review list.

### 4.3 Hardware session runbook

Run everything from the repo folder with the venv's Python (`$py = "$env:USERPROFILE\.venvs\solitaire\Scripts\python.exe"` in PowerShell, then `& $py tools\...`; the `&` is required).

**Every session (after setup is done once):**
1. Plug in the plotter (USB + power) with the pencil over the iPad's top-left, where it was at calibration. Don't move the iPad in its holder.
2. iPad: Auto-Lock = Never, on the charger. Mirror to **AirServer** on the PC; keep its window open (not minimised; it can sit behind others).
3. Check: `& $py tools\live_view.py` shows **aspect OK**, then `q`.
4. If the plotter was power-cycled or reset since the last calibration: serve the touch page (C.1), then `& $py tools\calibrate.py --rezero` and one tap.
5. Only one program can hold the COM port: close `plotter_console.py` before running `calibrate.py` (or the game loop), and the other way round.

**A. Live card detection (iPad only, no plotter needed)**
1. Mirror the iPad to the PC (§3.1). For a receiver window: `& $py tools\live_view.py --list-windows` to find its title, then `& $py tools\live_view.py --window "<part of title>"`. For a capture card: `& $py tools\live_view.py --camera 1` (try 0, 1, 2).
2. Check the bottom status line: **aspect OK** means the crop matches the iPad. Yellow guide lines should run down the middle of the 7 columns. `g` toggles guides, `s` saves the frame to `captures/` (useful as future training data), `q` quits.
3. The console prints the parsed game state whenever it changes.
4. Once it works, put the title/index in `config/settings.yaml` → `capture:` so the flags aren't needed.

**B. Plotter bring-up**
1. Plug in the plotter. The port is found automatically (`plotter.port: auto`); if it isn't, the error lists every serial port. Then pass `--port COMx` or add the board's USB ID to `plotter.usb_ids`.
2. `& $py tools\plotter_console.py`, then:
   - `info` → should say Grbl 1.1h; `settings` → saves `config/grbl_settings.txt` (note `$130`/`$131` = max travel).
   - `direction` → answer which way the pencil moved; saves `config/plotter_axes.json`.
   - Over a blank Notes page or the touch page: `pendown`, then `servo 60`, `servo 70`, … until the Pencil just registers. Put that value in `plotter.pen_down`. Then `tap` a few times to confirm every tap registers.

**C. Calibration**
1. Serve the touch page: `& $py -m http.server 8000 --directory tools`. On the iPad, open Safari at `http://<PC IP>:8000/touch_target.html` (find the IP with `ipconfig`) and use Share → Add to Home Screen, then open it from there for true full screen. If the network blocks this (common on campus Wi-Fi), use a phone hotspot, or a blank Notes page with a thick black marker: the tool only needs a dark mark on white.
2. Keep the mirror running, then `& $py tools\calibrate.py`. Jog until a `tap` lands ~10–15 mm in from the **screen's** top-left corner, then `ok`. Do the same at the bottom-right (about `down 200`, `right 135` from there), then `ok`. **Jog in steps of ≤150 mm: there are no limit switches, and running past the end of travel skips steps.** It taps 12 points, fits, verifies, and saves only if the check taps land within 30 px. Paste the output to Claude if it refuses.
3. After any power cycle or reset: `& $py tools\calibrate.py --rezero`.

**D. Playing** (mirror running, a dealt board on screen, nothing else holding the COM port)
0. Set `$py` in every new PowerShell window (top of §4.3), or `& $py` fails with "not valid".
1. Dry run first: `& $py -m solitaire.main --dry-run`. It prints each board and the move it would make, with the touch point in px and mm. Play that move by hand on the iPad; it waits for the board to change and suggests the next. Check that the suggestions make sense and the boards print without misreads.
2. Live: `& $py -m solitaire.main`. **The pencil must be at the calibration's top-left zero when it starts** (opening the port resets GRBL, which takes the pencil's position as (0, 0)). If the USB was unplugged or the plotter power-cycled, run `calibrate.py --rezero` first. Before the first tap it hovers the raised pencil over the first target and asks (**aim check**, 2026-11-23, after a first live run tapped empty felt 3 times; `--no-aim-check` skips it). Answer `n` and jog the tip onto the card (`up/down/left/right [mm]`, then `ok`): that spot becomes the target's mm position, a re-zero on the game board itself. The log records the correction in mm. Keep a hand near the plotter's power for the first games. Ctrl+C stops it; the pencil lifts and parks on the zero.
3. **Misreads are collected automatically** (`solitaire/vision/misreads.py`), by `main.py` (dry or live) and `live_view.py`. When a board settles, any frame from the settling window that read a card at the same place under another label is saved to `captures/misreads/` (PNG + JSON, e.g. 7d read as 6s). Two more kinds are saved by `main.py` (2026-11-23, after the second live game): **mismatch**, when a move lands a card that wasn't on the board before at the destination, so the source card was misread on *every* frame and agreement couldn't catch it (seen: waste `2d` read as `2h` throughout); the frame from before the move is saved (any other MISMATCH, since 2026-11-24, saves the frames before *and* after the move, `kind: mismatch` with a `note` naming the move, so no manual screenshots are needed). And **unreadable**, the last frame when no stable board could be read (seen: after `As` left column 6, every read said "column 6 ends face-down" for 15 s, so the revealed card wasn't recognised). `& $py tools\misread_report.py` lists which cards are misread most, with example frames, plus the unreadable boards: label those PNGs, add them to the dataset and retrain (§4.1).
4. **Solver v3:** the same steps with `-m solitaire.main_v3` (§3.4). In a dry run, a `PEEK` line means: play that move, let it read the card, then press **Undo** yourself.
5. The log is in `runs/games/`. Lines marked **MISMATCH** are moves where the app put the card somewhere other than predicted: send them to Claude to correct the tap-rule model (§3.3, §6).

### 4.4 Environment

- Python 3.14, venv at `%USERPROFILE%\.venvs\solitaire` (kept **out of OneDrive** so thousands of package files don't sync).
- GPU: RTX PRO 1000 Blackwell (8 GB) needs PyTorch **CUDA 12.8+** wheels: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`, then `pip install -r requirements.txt`.

---

## 5. Status / roadmap

### Where we are (updated 2026-11-11). Read this first in a new session
**All hardware is working and calibrated. Everything left is software.**

- **Vision:** YOLO model `models/cards.pt` reads boards at ~99.5% card-level accuracy. The owner has decided it's good enough for now (300 more images are already annotated if the shimmer/"$" errors become a real problem; retrain then). `StateBuilder` turns detections into a validated `GameState`.
- **Capture:** iPad mirrored with **AirServer** (the free receiver kept dropping). Crop works (aspect OK), including the iPad's black status bar.
- **Plotter:** GRBL 1.1h on `COM7`, auto-detected by USB ID. Axes: +X = screen down, +Y = screen right. Pen down `M3 S90` registers taps. **Moves go X then Y** (`axis_moves: true`, again since 2026-11-23, after a missed first tap following a diagonal; §1.1).
- **Calibration:** `config/calibration.json` saved 2026-11-11. Check taps land within 14 px (~1.4 mm). The zero is the plotter's power-on position over the iPad's top-left. After a reset, run `calibrate.py --rezero`.
- **Solver v1** (2026-11-23): `solitaire/solver/`, heuristic ranking + tap/drag prediction (§3.4).
- **Solver v2** (2026-11-23): stock memory + lookahead planner (§3.4), on by default. In simulation it wins about 20% of draw-3 deals against v1's 11%. **First game with v2 (2026-11-23): solved the deal.** **Vision retrained (2026-11-23, `runs/cards-3`):** a 49-move dry run read every board correctly. `press_finish` is back on.
- **Solver v3** (2026-11-24): sampled hidden cards + Undo peeks, run with `python -m solitaire.main_v3` (§3.4). **First live game (2026-11-24): solved the deal**, 70 moves in 229 s (~3.3 s per move), no MISMATCH. No peek qualified that game (the best move always led the other flips by more than `peek_margin`), so the Undo button is still untested on hardware. Not yet benchmarked against v2 offline.
- **Multi-frame agreement** (2026-11-23): `StableReader` in `solitaire/state/stable.py` (§4.2). Unit-tested; not yet watched on a live game.
- **Executor** (2026-11-23): `solitaire/executor.py` (§3.3). Unit-tested with a fake plotter; not yet run on the plotter.
- **Game loop** (2026-11-23): `python -m solitaire.main [--dry-run]` (§3.5, runbook §4.3 D). **Dry run works on a live game** (a full game, 52 suggestions, solved well). **First live run failed**: the plotter came back on COM4 after a USB replug, so its zero was wherever the pencil sat, and it tapped empty felt. Added the aim check; `plotter_console.py` now parks on the zero on quit too. A second run, right after a good `--rezero`, still missed at the aim check, so the move itself is suspect (a +X+Y diagonal, §1.1): `axis_moves` is back to `true`, and the aim check can now be corrected by jogging, which logs the error in mm. **First real live game (2026-11-23): ~75 moves played correctly** (foundations, runs, draws, recycles, Kings to empty columns), with no MISMATCH. It stopped on a tap on a covered card's 8 mm strip (Jc, third card in its column) that changed nothing three times, most likely a few mm of drift by then. Added nudged retries and a re-aim instead of stopping. Second live game: 25 moves, stopped when a just-revealed card in column 6 wasn't recognised (now saved as `unreadable`), and one MISMATCH where waste `2d` had been read as `2h` on every frame (now saved as `mismatch`). Third live game: 49 moves in 128 s, stopped on `8d` read as `9d` (now repaired from the run, see §4.2). Fourth: 8 moves, stopped on a shimmering `Kd` read as `Kh` (now the duplicate repair, §4.2). **Pattern across the games: the model confuses ♦/♥ (`2d`, `8d`, `Kd` read as hearts), worst on shimmering cards. Retraining with the saved live frames is the real fix (roadmap: "Train/verify YOLO model on mirrored frames").** Also `change_timeout_s` 2 → 3 s, because one tap registered late and its retry made a second move. The 9 "misreads" it logged were all animation frames; the filter now skips any frame whose label is a real card on the board. The owner reports some live card misreads; misread capture + `misread_report.py` now collect them.
- **Everything is built end to end. What's left is running it live and tuning.**

**Next steps, in order** (the plotter isn't needed until step 4):
1. ~~Multi-frame agreement + wait-until-stable~~ done (§4.2). Check it live: `live_view.py` should show `STABLE` between moves and never print a half-animated board.
2. ~~Solver v1~~ done (§3.4). Tune `solver.weights` once real games are played.
3. ~~Executor~~ done (§3.3). The loop must build `Grbl` with `bounds_mm=calibration.screen_bounds_mm(...)` so a bad point can never drive the pencil off the glass.
4. ~~`solitaire/main.py`~~ built. **Now: run it** (§4.3 D): a `--dry-run` game first, then a live game. Things to watch: drags registering (may need a hold after pen-down), the Finish/Undo positions, MISMATCH lines in the log, and how many moves fit in 5 minutes.
5. Optional robustness: detect when the mirror drops (black/idle frame) and pause, not tap blind.


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
- [x] **Hardware run B** (2026-11-09): `$$` backed up (`$130`=310, `$131`=210 mm travel), direction test (+X → screen down, +Y → screen right, confirmed with taps in the mirror), taps register at `M3 S90`
- [x] **Hardware run C** (2026-11-11, AirServer, `axis_moves` on): 12/12 grid taps found, RMS 0.36 mm, check taps within **14 px** (~1.4 mm), size check 159.4×222.4 mm vs spec 157.8×227.1 (consistent). The screen spans X −11.7..213.2, Y −12.0..152.0 mm from the zero, well inside the 310×210 mm travel. The only parts left of or above the zero are the screen edge strips (status bar, left margin), which hold no tap targets.
- [ ] Train/verify YOLO model on mirrored frames
- [x] GameState builder + validation (§4.2)
- [x] Train / val / test split (224 / 42 / 42)
- [x] Fix dataset label mistakes + label live frames via `tools/make_review.py` → Label Studio → `tools/merge_review.py` (§4.1), then retrain and score (review round 1, 2026-11-23: model 303/318 boards valid)
- [x] Multi-frame agreement: accept a state only when 3 consecutive reads match and are valid (`StableReader`, `tests/test_stable.py`)
- [x] Heuristic solver v1 (`solitaire/solver/`, `tools/solve_states.py`, `tests/test_solver.py`)
- [x] Executor + game loop (`solitaire/executor.py`, `solitaire/main.py`)
- [ ] End-to-end loop on a real game: dry run, then live
- [x] Lookahead solver v2: stock memory + beam search (`solitaire/solver/planner.py`, `memory.py`, `tools/simulate_games.py`, `tests/test_planner.py`)
- [x] Solver v3: sample hidden cards and vote, plus Undo peeks (`solitaire/solver/sampling.py`, `solitaire/main_v3.py`, `tests/test_sampling.py`; §3.4)
- [x] Benchmark v3 against v2 (2026-11-24: 22.5% vs 20.0% on 200 deals, within noise) and live v3 games (6 on 2026-11-24: 2 wins, 2 stuck with Finish, 1 vision stop, 1 stopped early by the first auto-finish rule)
- [ ] Tune v3 search settings (`--set`), then a stronger per-deal search if it pays (§3.4)

---

## 6. Known risks & open questions

- **App: Solitaire Infinite: Win Cash** (iPad). Each game has a **5-minute timer** and is **scored**. The goal is maximum score before time runs out (or **Finish** is pressed), not only clearing the board.
  - **Draw-3 (confirmed 2026-10-22).** Each tap on the stock turns over 3 cards onto the waste fan, and only the top (right-most) one is playable. Tapping the stock again deals the next 3. When the stock is empty (recycle icon), tapping it puts the waste back. **Recycles are limited (confirmed)**, so the stock can't be cycled forever. Every pass counts. **TODO:** exact number of passes, and what the stock shows when no recycles are left.
  - **Empty columns take Kings only (confirmed 2026-11-24).** The solver already assumes this, so a game the robot calls stuck is really stuck (2026-11-24: Finish with Q♥ J♠ 10♦ 9♠ in the stock, blocked behind a face-down K♣).
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

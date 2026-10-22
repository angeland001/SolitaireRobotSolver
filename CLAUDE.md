# CLAUDE.md

Read `README.md` before any work in this repo. It is the source of truth for architecture, decisions, conventions, and status.

- Follow the decisions in README §3 unless the user changes them. If they do, update the README in the same change.
- Tick off roadmap items in README §5 as they are completed, and resolve the TODOs in §1/§4/§6 as the user answers them.
- Keep coordinate spaces explicit (`_px` normalised screen, `_mm` plotter, `_raw` capture frame) and put config values in `config/settings.yaml`, never in code.

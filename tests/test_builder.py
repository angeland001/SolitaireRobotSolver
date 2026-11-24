"""StateBuilder rule-based repairs."""
from boards import board

from solitaire.state import StateBuilder


def test_card_pinned_by_its_run_is_repaired():
    # the 2026-11-23 case: 10d 9s [8d read as 9d] 7c, with 8h visible in column 3 and 9d in column 2
    s = board(["Kc", "Kh Qs Jd 10s 9d", "# 8h 7s", "Ks", "10d 9s 9d 7c"])
    StateBuilder._repair_runs(s)
    assert [str(p) for p in s.tableau[4].faceup] == ["10d", "9s", "8d", "7c"]
    assert s.repairs == [("column 5", "9d", "8d")]


def test_duplicate_becomes_its_sibling_suit():
    # shimmering Kd in column 2 read as Kh (low confidence) while the real Kh is on the waste
    from dataclasses import replace
    s = board(["8d", "# Kh", "3c"], waste="Kh")
    col = s.tableau[1]
    col.faceup[0] = replace(col.faceup[0], det=replace(col.faceup[0].det, conf=0.69))
    StateBuilder._repair_duplicates(s, 0.15)
    assert str(s.tableau[1].faceup[0]) == "Kd" and str(s.waste[0]) == "Kh"
    assert s.repairs == [("column 2", "Kh", "Kd")]


def test_duplicate_left_alone_when_sibling_is_visible():
    s = board(["Kd", "# Kh"], waste="Kh")
    StateBuilder._repair_duplicates(s, 0.15)
    assert s.repairs == []


def test_missing_waste_card_makes_the_board_invalid():
    # Foundations hold everything up to 9s; 10s Js Qs Ks are out. Stock and waste read empty.
    tops = "Kc Kd Kh 9s"
    ok = board(["# Ks", "Qs", "Js"], foundations=tops, stock=False)    # 10s is the face-down card
    StateBuilder._check_rules(ok)
    assert ok.is_valid
    missing = board(["Ks", "Qs", "Js"], foundations=tops, stock=False)  # 10s is nowhere: unrecognised
    StateBuilder._check_rules(missing)
    assert any("unaccounted" in i for i in missing.issues)


def test_duplicate_left_alone_without_a_clear_loser():
    s = board(["8d", "# Kh"], waste="Kh")      # both copies at conf 1.0 (like hand labels)
    StateBuilder._repair_duplicates(s, 0.15)
    assert s.repairs == []


def test_no_repair_when_two_cards_could_fit():
    s = board(["Kc", "Kh", "Qs", "Ks", "10d 9s 9d 7c"])   # 8d and 8h both unseen
    StateBuilder._repair_runs(s)
    assert str(s.tableau[4].faceup[2]) == "9d" and s.repairs == []


def test_no_repair_when_neighbours_disagree():
    s = board(["Kc", "Kh", "Qs", "Ks", "10d 9s 9d 6c"])   # 10d .. 6c can't bracket one card
    StateBuilder._repair_runs(s)
    assert s.repairs == []

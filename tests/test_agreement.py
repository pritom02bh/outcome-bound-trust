"""D42: agreement between an independent annotator and our labels (kappa, raw agreement, slot agreement)."""
import csv

import pytest

from eval import agreement as ag


def test_kappa_matches_a_hand_computed_case():
    # 10 items: both yes 4, both no 3, ours yes/theirs no 2, ours no/theirs yes 1.
    a = ["yes"] * 6 + ["no"] * 4
    b = ["yes"] * 4 + ["no"] * 2 + ["yes"] + ["no"] * 3
    k = ag.kappa(a, b)
    po, pe = 0.7, 0.6 * 0.5 + 0.4 * 0.5
    assert k["raw_agreement"] == pytest.approx(po) and k["kappa"] == pytest.approx((po - pe) / (1 - pe), abs=1e-4)
    assert not k["degenerate"]


def test_constant_labels_are_flagged_degenerate():
    k = ag.kappa(["yes"] * 40, ["yes"] * 39 + ["no"])
    assert k["degenerate"] and k["raw_agreement"] == pytest.approx(39 / 40) and k["kappa"] == 0.0
    assert ag.kappa(["yes"] * 5, ["yes"] * 5)["kappa"] is None          # expected agreement 1: undefined


def _write(path, header, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_spotcheck_and_enron_against_our_files(tmp_path):
    ours_s, theirs_s = tmp_path / "s.csv", tmp_path / "s_t.csv"
    _write(ours_s, ["id", "kind", "message", "template", "slots", "looks_correct"],
           [["t1", "offer", "m1", "", "", "yes"], ["t2", "offer", "m2", "", "", "yes"]])
    _write(theirs_s, ["row", "id", "message", "template", "slots", "looks_correct"],
           [[1, "t1", "m1", "", "", "yes"], [2, "t2", "m2", "", "", "no"]])
    s = ag.spotcheck(theirs_s, ours_s)
    assert s["raw_agreement"] == 0.5 and s["disagreements"] == [{"id": "t2", "ours": "yes", "theirs": "no"}]
    cols = ["is_commitment", "has_delivery_claim", "qty", "deadline", "has_price_claim", "price", "valid_until", "notes"]
    ours_e, theirs_e = tmp_path / "e.csv", tmp_path / "e_t.csv"
    _write(ours_e, ["message", "stratum", *cols],
           [["a", "price", "yes", "no", "", "", "yes", "174", "2001-12-27", ""],
            ["b", "price", "no", "no", "", "", "no", "", "", "borderline; deal record"],
            ["c", "price", "yes", "no", "", "", "yes", "132", "2002-03-20 / 2001-12-15", ""]])
    _write(theirs_e, ["row", "message", *cols],
           [[1, "a", "yes", "no", "", "", "yes", "$174", "2001-12-27", ""],
            [2, "b", "yes", "no", "", "", "yes", "8", "", ""],
            [3, "c", "yes", "no", "", "", "yes", "132.00", "2001-12-15 / 2002-03-20", ""]])
    e = ag.enron(theirs_e, ours_e)
    assert e["raw_agreement"] == pytest.approx(2 / 3, abs=1e-4) and [d["row"] for d in e["disagreements"]] == [2]
    assert e["slot_agreement_on_rows_both_yes"]["price"] == {"rows": 2, "agree": 2}       # $174 = 174; 132.00 = 132
    assert e["slot_agreement_on_rows_both_yes"]["valid_until"] == {"rows": 2, "agree": 2}  # both dates, any order


def test_refuses_a_reordered_or_unfinished_file(tmp_path):
    cols = ["is_commitment", "has_delivery_claim", "qty", "deadline", "has_price_claim", "price", "valid_until", "notes"]
    ours, theirs = tmp_path / "e.csv", tmp_path / "e_t.csv"
    _write(ours, ["message", "stratum", *cols], [["a", "p", "no", *[""] * 7], ["b", "p", "no", *[""] * 7]])
    _write(theirs, ["row", "message", *cols], [[1, "b", "no", *[""] * 7], [2, "a", "no", *[""] * 7]])
    with pytest.raises(ValueError, match="line up"):
        ag.enron(theirs, ours)
    _write(theirs, ["row", "message", *cols], [[1, "a", "no", *[""] * 7], [2, "b", "", *[""] * 7]])
    with pytest.raises(ValueError, match="without is_commitment"):
        ag.enron(theirs, ours)


def test_the_blind_files_match_our_order_and_hide_our_labels():
    blind = list(csv.DictReader(open(ag.ROOT / "annotation" / "enron_blind.csv", newline="")))
    ours = list(csv.DictReader(open(ag.ROOT / "data" / "enron_candidates.csv", newline="")))
    assert [r["message"] for r in blind] == [r["message"] for r in ours] and len(blind) == 100
    assert not any(r[c] for r in blind for c in ag.SLOTS + ("is_commitment", "notes")) and "stratum" not in blind[0]
    spot = list(csv.DictReader(open(ag.ROOT / "annotation" / "spotcheck_blind.csv", newline="")))
    assert len(spot) == 40 and not any(r["looks_correct"] for r in spot) and "kind" not in spot[0]

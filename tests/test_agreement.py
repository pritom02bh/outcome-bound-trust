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
    key, theirs_s = tmp_path / "key.csv", tmp_path / "s_t.csv"
    _write(key, ["row", "source", "id", "our_label"],
           [[1, "v2", "test001", "yes"], [2, "v1_seeded", "test029", "no"], [3, "v2", "test002", "yes"],
            [4, "v1_seeded", "test030", "no"]])
    _write(theirs_s, ["row", "message", "template", "slots", "looks_correct"],
           [[1, "m", "", "", "yes"], [2, "m", "", "", "no"], [3, "m", "", "", "no"], [4, "m", "", "", "yes"]])
    s = ag.spotcheck(theirs_s, key)
    assert s["all"]["n"] == 4 and s["all"]["raw_agreement"] == 0.5 and s["all"]["kappa"] == 0.0
    assert s["v2"]["n"] == 2 and s["v2"]["degenerate"] and [d["row"] for d in s["v2"]["disagreements"]] == [3]
    assert s["seeded"]["n"] == 2 and s["seeded"]["detection_rate"] == 0.5
    assert s["seeded"]["disagreements"] == [{"row": 4, "source": "v1_seeded", "id": "test030", "ours": "no",
                                             "theirs": "yes", "message": "m", "recorded": ""}]
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
    key = list(csv.DictReader(open(ag.ROOT / "data" / "annotation_spotcheck_key.csv", newline="")))
    assert len(spot) == 50 and not any(r["looks_correct"] for r in spot)
    assert list(spot[0]) == ["row", "message", "template", "slots", "looks_correct"]      # nothing marks origin
    assert [r["row"] for r in spot] == [r["row"] for r in key]
    assert sum(r["source"] == "v1_seeded" for r in key) == 10 and {r["our_label"] for r in key if r["source"] == "v2"} == {"yes"}
    v2 = {r["message"] for r in csv.DictReader(open(ag.ROOT / "data" / "spotcheck.csv", newline=""))}
    assert sum(r["message"] in v2 for r in spot) == 40


def test_returned_row_only_file_is_lined_up_with_the_blind_file_and_never_reordered(tmp_path):
    blind = tmp_path / "blind.csv"
    _write(blind, ["row", "message", "looks_correct"], [[1, "a", ""], [2, "b", ""], [3, "c", ""]])
    ok = tmp_path / "ok.csv"
    _write(ok, ["Row", "looks_correct"], [[1, "yes"], [2, "no"], [3, "yes"]])
    rows = ag.read_returned(ok, blind)
    assert [(r["row"], r["message"], r["looks_correct"]) for r in rows] == [("1", "a", "yes"), ("2", "b", "no"),
                                                                            ("3", "c", "yes")]
    for bad in ([[2, "no"], [1, "yes"], [3, "yes"]], [[1, "yes"], [2, "no"]], [[1, "yes"], [1, "no"], [3, "yes"]]):
        f = tmp_path / "bad.csv"
        _write(f, ["Row", "looks_correct"], bad)
        with pytest.raises(ValueError):
            ag.read_returned(f, blind)

"""D34: Enron real-text check. How the frozen extractor treats calendar dates and non-widget items, the stratified
sample, and the per-stratum metrics."""
import csv
import json

import pytest

from eval import enron_eval, enron_prep
from obt.extractor import LLMExtractor, RuleExtractor
from obt.llm import LLM
from obt.types import Message


def fake(claims):
    return LLMExtractor(LLM("fake", "f", fake=lambda s, u: json.dumps({"claims": claims})))


def statuses(ext, text):
    return [c.status for c in ext.extract(Message(msg_hash="h", counterparty="S_main", round=3, text=text))]


D = lambda q, b, item="widget": {"template": "DELIVERY", "item": item, "qty": q, "by_round": b}  # noqa: E731
P = lambda p, u, item="widget": {"template": "PRICE", "item": item, "unit_price": p, "valid_until": u}  # noqa: E731


@pytest.mark.parametrize("text,claims", [
    ("We will deliver 500 barrels by May 15.", [D(500, 15)]),                 # calendar date, non-widget unit
    ("We will deliver 500 barrels by May 15.", [D(500, 15, item="barrels")]),  # non-widget item
    ("Please ship 20 units no later than 12/31.", [D(20, 31), D(20, 12)]),    # a unit qty, but a calendar date
    ("The price is $4.25 per MMBtu, firm through Friday.", [P(4.25, 5)]),     # price with a weekday validity
    ("Our offer of $3.10 is good until 5/15.", [P(3.10, 15), P(3.10, 5)]),
])
def test_calendar_dates_and_non_widget_items_are_untestable(text, claims):
    assert set(statuses(fake(claims), text)) == {"UNTESTABLE"}
    assert set(statuses(RuleExtractor(), text)) <= {"UNTESTABLE"}


def test_stratified_sample(tmp_path):
    cands = [(f"We will deliver {i} units by May {i % 28 + 1}.", True, False) for i in range(80)]
    cands += [(f"Price ${i}.00 valid through Friday.", False, True) for i in range(120)]
    cands += [(f"Deliver {i} units by May 2 at $5 firm through Friday.", True, True) for i in range(5)]
    rows, meta = enron_prep.stratified(cands, per_stratum=50, seed=7)
    strata = [r[1] for r in rows]
    assert strata.count("delivery") == 50 and strata.count("price") == 50
    assert all(("deliver" in m.lower()) == (s == "delivery") for m, s in rows)   # both-flag rows are delivery
    assert meta == {"delivery": {"pool": 85, "sampled": 50}, "price": {"pool": 120, "sampled": 50}, "seed": 7,
                    "rule": "delivery-like (including rows that are also price-like) vs price-only"}
    assert enron_prep.stratified(cands, per_stratum=50, seed=7) == (rows, meta)


def test_columns_put_is_commitment_before_the_slot_columns():
    assert enron_prep.COLUMNS == ["message", "stratum", "is_commitment", "has_delivery_claim", "qty", "deadline",
                                  "has_price_claim", "price", "valid_until", "notes"]


def _labels(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=enron_prep.COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in enron_prep.COLUMNS})


def test_per_stratum_metrics(tmp_path):
    f = tmp_path / "labels.csv"
    _labels(f, [
        # A real commitment the schema can't express: marked UNTESTABLE (coverage limit), nothing recorded.
        {"message": "We will deliver 500 barrels by May 15.", "stratum": "delivery", "is_commitment": "yes",
         "has_delivery_claim": "yes", "qty": "500", "deadline": "May 15"},
        # A non-commitment in round wording that an extractor could record: counts as recorded-from-non-commitment
        # and as a wrong claim.
        {"message": "Last year 20 units arrived by round 4.", "stratum": "delivery", "is_commitment": "no"},
        {"message": "Price ${p} valid through Friday.".replace("{p}", "4.00"), "stratum": "price",
         "is_commitment": "yes", "has_price_claim": "yes", "price": "4.00", "valid_until": "Friday"},
    ])

    def llm(system, user):
        if "arrived by round 4" in user:
            return json.dumps({"claims": [D(20, 4)]})
        return json.dumps({"claims": []})
    rep = enron_eval.evaluate(f, LLMExtractor(LLM("fake", "f", fake=llm)))
    d, p = rep["delivery"], rep["price"]
    assert d["rows"] == 2 and d["wrong_claims_recorded"] == 1 and d["recorded_from_non_commitments"] == 1
    assert d["commitment_claims"] == 1 and d["commitment_claims_untestable"] == 1
    assert p["wrong_claims_recorded"] == 0 and p["commitment_claims_untestable"] == 1
    assert "pooled" not in rep                                       # reported per stratum only


def test_unlabeled_rows_are_refused(tmp_path):
    f = tmp_path / "labels.csv"
    _labels(f, [{"message": "We will deliver 5 units by May 1.", "stratum": "delivery"}])
    with pytest.raises(ValueError, match="is_commitment"):
        enron_eval.evaluate(f, RuleExtractor())

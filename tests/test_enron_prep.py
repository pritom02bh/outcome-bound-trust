"""Enron candidate extraction (D31): no labels, no model calls; deterministic sample with empty label columns."""
import csv
import io
import tarfile

from eval import enron_prep as ep


def _mail(body: str, subject: str = "s") -> bytes:
    return (f"Message-ID: <x>\nFrom: a@enron.com\nTo: b@enron.com\nSubject: {subject}\n"
            f"Content-Type: text/plain\n\n{body}").encode()


def _tar(path, mails: dict[str, bytes]):
    with tarfile.open(path, "w:gz") as t:
        for name, data in mails.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))


def test_candidate_rules():
    assert ep.is_delivery("We will deliver 500 barrels by May 15.")
    assert ep.is_delivery("Please ship 20 units no later than 12/31.")
    assert not ep.is_delivery("We have 500 barrels in storage.")          # no deadline
    assert not ep.is_delivery("Let's meet by Friday.")                     # no quantity
    assert ep.is_price("The price is $4.25 per MMBtu, valid through Friday.")
    assert not ep.is_price("It cost $4.25.")                               # no validity
    assert not ep.is_price("Valid until Friday.")                          # no price


def test_quoted_and_forwarded_text_is_dropped():
    body = ("We will deliver 50 tons by June 3.\n\n> We will deliver 99 tons by June 9.\n"
            "-----Original Message-----\nWe can ship 70 units by Monday.")
    sents = ep.own_sentences(body)
    assert any("50 tons" in s for s in sents)
    assert not any("99 tons" in s or "70 units" in s for s in sents)


def test_extract_dedupes_and_writes_an_unlabeled_sample(tmp_path):
    arc = tmp_path / "mail.tar.gz"
    _tar(arc, {
        "maildir/a/sent/1.": _mail("We will deliver 500 barrels by May 15. Thanks."),
        "maildir/b/inbox/2.": _mail("We will deliver 500 barrels by May 15."),              # duplicate
        "maildir/c/inbox/3.": _mail("Price is $3.10/MMBtu, good until Friday. See you."),
        "maildir/d/inbox/4.": _mail("Lunch at noon?"),
    })
    out = tmp_path / "cands.csv"
    meta = ep.extract(arc, out, n=100, seed=1)
    rows = list(csv.DictReader(out.open()))
    assert [r["message"] for r in rows].count("We will deliver 500 barrels by May 15.") == 1
    assert len(rows) == 2 and meta["unique_candidates"] == 2 and meta["messages_scanned"] == 4
    assert list(rows[0]) == ep.COLUMNS
    assert {r["stratum"] for r in rows} == {"delivery", "price"}                     # filled by code
    assert all(all(r[k] == "" for k in list(r)[2:]) for r in rows)                 # every label empty
    assert ep.extract(arc, tmp_path / "again.csv", n=100, seed=1) == meta
    assert (tmp_path / "again.csv").read_bytes() == out.read_bytes()


def test_quoted_printable_bodies_are_decoded(tmp_path):
    raw = (b"Message-ID: <x>\nFrom: a@enron.com\nSubject: s\nContent-Type: text/plain; charset=us-ascii\n"
           b"Content-Transfer-Encoding: quoted-printable\n\n"
           b"We will deliver 500 barrels by May 15.=20 The price is $4.2=\n"
           b"5 per MMBtu, firm through Friday.\n")
    arc = tmp_path / "qp.tar.gz"
    _tar(arc, {"maildir/a/sent/1.": raw})
    out = tmp_path / "c.csv"
    ep.extract(arc, out, n=10, seed=1)
    msgs = [r["message"] for r in csv.DictReader(out.open())]
    assert "The price is $4.25 per MMBtu, firm through Friday." in msgs
    assert not any("=20" in m or "=\n" in m for m in msgs)


def test_undeclared_quoted_printable_is_decoded_too(tmp_path):
    raw = (b"Message-ID: <x>\nFrom: a@enron.com\nSubject: s\nContent-Type: text/plain; charset=us-ascii\n"
           b"Content-Transfer-Encoding: 7bit\n\n"
           b"The price is $4.2=\n5 per MMBtu, firm=20through Friday. If x = 5 then y.\n")
    arc = tmp_path / "qp7.tar.gz"
    _tar(arc, {"maildir/a/sent/1.": raw})
    out = tmp_path / "c.csv"
    ep.extract(arc, out, n=10, seed=1)
    msgs = [r["message"] for r in csv.DictReader(out.open())]
    assert "The price is $4.25 per MMBtu, firm through Friday." in msgs

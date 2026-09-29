"""Enron candidate sentences for a real-text extractor test (user request; DECISIONS D31). No labeling, no models.

    python -m eval.enron_prep          # downloads the CMU corpus to runs/enron/, writes data/enron_candidates.csv

Source: the CMU Enron Email Dataset, release of May 7, 2015 (`enron_mail_20150507.tar.gz`), the standard public
version; URL, size and sha256 are recorded next to the output. Each message's own text is kept: quoted lines (">")
and everything after an "Original Message" or forward marker are dropped, so every sentence was written by the
message's sender. A sentence is a candidate if it looks like a delivery commitment (a quantity with a unit and a
deadline expression) or a price commitment (a dollar amount and a validity word). Candidates are deduplicated on
normalized text and 100 are sampled with a fixed seed; every label column is left empty for the user.
"""
from __future__ import annotations

import csv
import email
import email.policy
import hashlib
import json
import quopri
import random
import re
import tarfile
import urllib.request
from pathlib import Path

from obt.llm import RUNS

URL = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"
VERSION = "CMU Enron Email Dataset, release 2015-05-07 (enron_mail_20150507.tar.gz)"
ARCHIVE = RUNS / "enron" / "enron_mail_20150507.tar.gz"
OUT = Path(__file__).resolve().parent.parent / "data" / "enron_candidates.csv"
# `stratum` is filled by code (D34); every other column after `message` is a label for the user.
COLUMNS = ["message", "stratum", "is_commitment", "has_delivery_claim", "qty", "deadline", "has_price_claim", "price",
           "valid_until", "notes"]
CANDIDATES = RUNS / "enron" / "candidates_all.jsonl"
PER_STRATUM = 50
SEED = 20260929

_UNIT = (r"units?|pieces?|pcs|cases?|boxes|tons?|tonnes?|barrels?|bbls?|gallons?|mw|mwh|mmbtu|dth|decatherms?|"
         r"contracts?|lots?|cars?|loads?|pallets?|items?|copies|licenses?|servers?|computers?|laptops?|pcs|phones?|"
         r"cartridges?|monitors?|printers?|meters?|megawatts?|kwh")
_QTY = re.compile(rf"\b\d[\d,]*(?:\.\d+)?\s*(?:{_UNIT})\b", re.I)
_DATE = (r"(?:\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b|\b\d{1,2}/\d{1,2}"
         r"(?:/\d{2,4})?\b|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight|next week|"
         r"end of (?:the )?(?:day|week|month)|eod|eow|eom)\b)")
_DEADLINE = re.compile(rf"\b(?:by|no later than|on or before|before|until|deliver\w*|ship\w*|arriv\w*|due)\b"
                       rf"[^.;]{{0,40}}?{_DATE}", re.I)
_PRICE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
_VALID = re.compile(r"\b(?:valid|good (?:until|through|thru|till|for)|firm|guaranteed|expires?|expiration|"
                    r"effective|through|thru|until|till|holds?)\b", re.I)
_CUT = re.compile(r"^-{3,}\s*(?:original message|forwarded by)|^-{5,} forwarded|^_{5,}|^from:\s", re.I | re.M)
_QP_SIGNS = re.compile(rb"=(?:20|09|3D|\r?\n)")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def is_delivery(s: str) -> bool:
    return bool(_QTY.search(s) and _DEADLINE.search(s))


def is_price(s: str) -> bool:
    return bool(_PRICE.search(s) and _VALID.search(s))


def own_sentences(body: str) -> list[str]:
    """The sender's own sentences: stop at the first forward/reply marker, drop quoted lines."""
    m = _CUT.search(body)
    if m:
        body = body[:m.start()]
    lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith(">")]
    text = " ".join(" ".join(lines).split())
    return [s.strip() for s in _SENT.split(text) if 20 <= len(s.strip()) <= 400]


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9$./ ]", " ", s.lower()).split())


EXPECTED_BYTES = 443_254_787          # the server's Content-Length for this release


def download(url: str = URL, dest: Path = ARCHIVE, expected: int = EXPECTED_BYTES, attempts: int = 8) -> dict:
    """Resumable: continues a partial download with HTTP Range requests and accepts the file only at full size."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    for _ in range(attempts):
        if dest.exists():
            break
        have = tmp.stat().st_size if tmp.exists() else 0
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
        try:
            with urllib.request.urlopen(req, timeout=120) as r, tmp.open("ab" if have else "wb") as f:
                if have and r.status != 206:          # server ignored the range: start over
                    f.seek(0)
                    f.truncate()
                while chunk := r.read(1 << 20):
                    f.write(chunk)
        except OSError:
            continue
        if tmp.stat().st_size == expected:
            tmp.replace(dest)
    if not dest.exists() or dest.stat().st_size != expected:
        got = tmp.stat().st_size if tmp.exists() else 0
        raise RuntimeError(f"download incomplete after {attempts} attempts: {got} of {expected} bytes")
    h = hashlib.sha256()
    with dest.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {"url": url, "version": VERSION, "bytes": dest.stat().st_size, "sha256": h.hexdigest()}


def stratum(delivery: bool, price: bool) -> str:
    # A sentence that looks like both is a delivery candidate: those are the rarer stratum.
    return "delivery" if delivery else "price"


def stratified(cands: list[tuple[str, bool, bool]], per_stratum: int = PER_STRATUM,
               seed: int = SEED) -> tuple[list[tuple[str, str]], dict]:
    """per_stratum random delivery-like and per_stratum random price-only candidates (D34)."""
    pools = {"delivery": sorted(c for c in cands if c[1]), "price": sorted(c for c in cands if c[2] and not c[1])}
    rng = random.Random(seed)
    rows: list[tuple[str, str]] = []
    meta: dict = {}
    for name in ("delivery", "price"):
        take = rng.sample(pools[name], min(per_stratum, len(pools[name])))
        rows += [(s, name) for s, _, _ in take]
        meta[name] = {"pool": len(pools[name]), "sampled": len(take)}
    rng.shuffle(rows)
    meta["seed"] = seed
    meta["rule"] = "delivery-like (including rows that are also price-like) vs price-only"
    return rows, meta


def write_rows(rows: list[tuple[str, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for s, st in rows:
            w.writerow([s, st] + [""] * (len(COLUMNS) - 2))


def extract(archive: Path, out: Path = OUT, n: int = 100, seed: int = SEED, per_stratum: int | None = None,
            save: Path | None = None) -> dict:
    seen: dict[str, tuple[str, bool, bool]] = {}
    scanned = sentences = 0
    with tarfile.open(archive, "r:gz") as t:
        for m in t:
            if not m.isfile():
                continue
            f = t.extractfile(m)
            if f is None:
                continue
            try:
                msg = email.message_from_bytes(f.read(), policy=email.policy.compat32)
                if msg.is_multipart():
                    continue
                # Decode transfer encodings (quoted-printable leaves "=20" and soft line breaks otherwise).
                raw = msg.get_payload(decode=True) or b""
                # Some bodies carry quoted-printable text under a 7bit header (pasted or forwarded): decode it too.
                if _QP_SIGNS.search(raw):
                    raw = quopri.decodestring(raw)
                body = raw.decode(msg.get_content_charset() or "latin-1", errors="replace")
            except Exception:
                continue
            scanned += 1
            for s in own_sentences(body):
                sentences += 1
                d, p = is_delivery(s), is_price(s)
                if (d or p) and _norm(s) not in seen:
                    seen[_norm(s)] = (s, d, p)
    cands = sorted(seen.values())                     # sorted, so the seeded sample doesn't depend on tar order
    if save is not None:
        save.parent.mkdir(parents=True, exist_ok=True)
        save.write_text("".join(json.dumps(c) + "\n" for c in cands))
    stats = {"messages_scanned": scanned, "sentences": sentences, "unique_candidates": len(cands),
             "delivery_like": sum(d for _, d, _ in cands), "price_like": sum(p for _, _, p in cands), "seed": seed}
    if per_stratum is not None:
        rows, strata = stratified(cands, per_stratum, seed)
        stats["strata"] = strata
    else:
        rows = [(s, stratum(d, p)) for s, d, p in random.Random(seed).sample(cands, min(n, len(cands)))]
    write_rows(rows, out)
    stats["sampled"] = len(rows)
    return stats


def main() -> None:
    src = download()
    meta = extract(ARCHIVE, per_stratum=PER_STRATUM, save=CANDIDATES)
    meta = {"source": src, **meta, "rules": {"delivery": "quantity with a unit + deadline expression",
                                             "price": "dollar amount + validity word"}}
    OUT.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()

"""Score the clinician verification sheets (test category 3).

    python validation/clinician_verification/score_sheets.py

Reads degerlendirici_A.csv and degerlendirici_B.csv. If no row has a decision
the status is NOT_PERFORMED and no rate is reported. Otherwise it reports,
per reviewer and for the agreed rows, the share of values judged correct,
wrong, incomplete/unclear and not in the source, plus raw agreement and
Cohen's kappa between A and B. Rows on which A and B disagree are listed for
adjudication; they are not counted as correct or wrong.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from build_sheet import DECISIONS  # noqa: E402


def read_decisions(path: str) -> Dict[str, Dict[str, str]]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return {row["item_id"]: row for row in csv.DictReader(fh)}


def _decision(row: Optional[Dict[str, str]]) -> str:
    return ((row or {}).get("karar") or "").strip().lower()


def _rates(decisions: List[str]) -> Dict[str, object]:
    counts = Counter(decisions)
    total = len(decisions)
    return {"n": total, **{d: counts[d] for d in DECISIONS},
            **{f"{d}_orani": round(counts[d] / total, 4) if total else None for d in DECISIONS}}


def cohen_kappa(a: List[str], b: List[str]) -> Optional[float]:
    if not a:
        return None
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if expected == 1 else round((observed - expected) / (1 - expected), 4)


def score(sheet_a: str, sheet_b: str) -> Dict[str, object]:
    rows_a, rows_b = read_decisions(sheet_a), read_decisions(sheet_b)
    invalid = sorted({i for rows in (rows_a, rows_b) for i, r in rows.items()
                      if _decision(r) and _decision(r) not in DECISIONS})
    dec_a = {i: _decision(r) for i, r in rows_a.items() if _decision(r) in DECISIONS}
    dec_b = {i: _decision(r) for i, r in rows_b.items() if _decision(r) in DECISIONS}
    total_items = len(set(rows_a) | set(rows_b))
    if not dec_a and not dec_b:
        return {"status": "NOT_PERFORMED", "items": total_items, "invalid_decisions": invalid,
                "note": "Hiçbir satırda hekim kararı yok; bağımsız klinik doğrulama yapılmamıştır."}
    both = sorted(set(dec_a) & set(dec_b))
    pairs_a, pairs_b = [dec_a[i] for i in both], [dec_b[i] for i in both]
    agreed = [dec_a[i] for i in both if dec_a[i] == dec_b[i]]
    disagreements = [i for i in both if dec_a[i] != dec_b[i]]
    complete = len(both) == total_items and not invalid
    return {
        "status": "COMPLETE" if complete else "PARTIAL",
        "items": total_items,
        "reviewer_A": _rates(list(dec_a.values())),
        "reviewer_B": _rates(list(dec_b.values())),
        "double_reviewed": len(both),
        "raw_agreement": round(len(agreed) / len(both), 4) if both else None,
        "cohen_kappa": cohen_kappa(pairs_a, pairs_b),
        "agreed": _rates(agreed),
        "needs_adjudication": disagreements,
        "invalid_decisions": invalid,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=HERE)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    result = score(os.path.join(args.dir, "degerlendirici_A.csv"), os.path.join(args.dir, "degerlendirici_B.csv"))
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

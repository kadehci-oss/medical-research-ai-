"""Build the field-level sheet for independent clinician verification (test category 3).

    python validation/clinician_verification/build_sheet.py            # writes the sheets
    python validation/clinician_verification/build_sheet.py --seed 7   # different row order

One row per value the engine extracted from a PubMed abstract: design, total
participants, arm sizes, event counts, each effect estimate (value, CI, p,
outcome) and whether causal wording is allowed. Each row carries the PMID,
the PubMed link and the verbatim source sentence.

Two reviewer sheets (A and B) list the same rows in different random orders so
reviewers work independently. Decision columns are empty. This script never
fills a decision; the score is produced only from sheets filled by clinicians.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import random
import sys
from typing import Any, Dict, Iterable, List

HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATION = os.path.dirname(HERE)
ROOT = os.path.dirname(VALIDATION)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import evidence_model as em  # noqa: E402
from version import APP_VERSION  # noqa: E402

ITEM_COLUMNS = ["item_id", "pmid", "specialty", "design_reference", "field", "outcome", "engine_value",
                "source_sentence", "pubmed_url"]
DECISION_COLUMNS = ["karar", "dogru_deger", "not", "degerlendirici_kodu"]
DECISIONS = ("dogru", "yanlis", "eksik_veya_belirsiz", "kaynakta_yok")


def load_records() -> List[Dict[str, Any]]:
    """All validation records with the specialty and design from their reference table."""
    meta: Dict[str, Dict[str, str]] = {}
    for path in glob.glob(os.path.join(VALIDATION, "reference_dataset*.json")):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for ref in data.get("studies", data) if isinstance(data, dict) else data:
            meta[str(ref["pmid"])] = {"specialty": ref.get("specialty", ""),
                                      "design": (ref.get("design") or [""])[0]}
    external = os.path.join(VALIDATION, "reference_external_pr64.json")
    if os.path.exists(external):
        with open(external, encoding="utf-8") as fh:
            for case in json.load(fh)["cases"]:
                meta.setdefault(str(case["pmid"]), {"specialty": case["specialty"], "design": case["required_design"]})
    records: Dict[str, Dict[str, Any]] = {}
    for path in sorted(glob.glob(os.path.join(VALIDATION, "pubmed_records*.json"))):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        items = data.get("records", data) if isinstance(data, dict) else data
        items = list(items.values()) if isinstance(items, dict) else items
        for rec in items:
            if isinstance(rec, dict) and rec.get("pmid") and rec.get("abstract"):
                records.setdefault(str(rec["pmid"]), rec)
    out = []
    for pmid, rec in records.items():
        info = meta.get(pmid, {})
        out.append(dict(rec, _specialty=info.get("specialty", ""), _design_reference=info.get("design", "")))
    return out


def _fmt(value: Any) -> str:
    return "" if value is None else str(value)


def study_items(record: Dict[str, Any]) -> Iterable[Dict[str, str]]:
    em.clear_cache()
    study = em.build_study(record)
    pmid = study.pmid
    base = {"pmid": pmid, "specialty": record.get("_specialty", ""), "design_reference": record.get("_design_reference", ""),
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"}
    yield dict(base, field="tasarım", outcome="", engine_value=f"{study.design_label} ({study.design_key})",
               source_sentence=study.title)
    yield dict(base, field="nedensel dil izni", outcome="",
               engine_value="izin var (randomize)" if study.causal_inference_allowed else "izin yok",
               source_sentence=study.title)
    pop = study.population
    yield dict(base, field="toplam katılımcı (n)", outcome="",
               engine_value=_fmt(pop.n_total) or "bildirilmedi (değer atanmadı)",
               source_sentence=pop.source.sentence)
    for arm in study.arms:
        yield dict(base, field="kol büyüklüğü", outcome=arm.label, engine_value=_fmt(arm.n) or "bildirilmedi",
                   source_sentence=arm.source.sentence)
    for ev in study.event_counts:
        value = f"{ev.events}" + (f"/{ev.total}" if ev.total else "") + (f" ({ev.percent}%)" if ev.percent is not None else "")
        yield dict(base, field="olay sayısı", outcome="", engine_value=value, source_sentence=ev.source.sentence)
    for est in study.estimates:
        ci = f"GA {_fmt(est.ci_low)} – {_fmt(est.ci_high)}" if est.ci_low is not None and est.ci_high is not None else "GA bildirilmedi"
        value = f"{est.measure} {est.value_text}; {ci}" + (f"; {est.p_value}" if est.p_value else "")
        if not est.usable:
            value += f" [motor reddetti: {est.validation_note}]"
        yield dict(base, field="etki tahmini", outcome=est.outcome_name or "sonlanım adlandırılmadı",
                   engine_value=value, source_sentence=est.source.sentence)


def build_items(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for record in sorted(records, key=lambda r: str(r["pmid"])):
        for item in study_items(record):
            item["item_id"] = f"K{len(items) + 1:04d}"
            items.append({k: item.get(k, "") for k in ITEM_COLUMNS})
    return items


def write_sheet(path: str, items: List[Dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ITEM_COLUMNS + DECISION_COLUMNS)
        writer.writeheader()
        for item in items:
            writer.writerow({**item, **{c: "" for c in DECISION_COLUMNS}})


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=HERE)
    parser.add_argument("--seed", type=int, default=20261101)
    args = parser.parse_args(argv)
    items = build_items(load_records())
    os.makedirs(args.output, exist_ok=True)
    write_sheet(os.path.join(args.output, "items_master.csv"), items)
    rng = random.Random(args.seed)
    for reviewer in ("A", "B"):
        shuffled = list(items)
        rng.shuffle(shuffled)
        write_sheet(os.path.join(args.output, f"degerlendirici_{reviewer}.csv"), shuffled)
    summary = {
        "app_version": APP_VERSION, "items": len(items), "studies": len({i["pmid"] for i in items}),
        "specialties": sorted({i["specialty"] for i in items if i["specialty"]}),
        "status": "NOT_PERFORMED", "note": "Karar sütunları boştur; bu dosya bir doğrulama sonucu değildir.",
    }
    with open(os.path.join(args.output, "sheet_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

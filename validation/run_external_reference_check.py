"""Score the evidence model on an external reference table (PR #64's eight PubMed cases).

    python validation/run_external_reference_check.py             # summary + writes results JSON
    python validation/run_external_reference_check.py --no-write
Only numeric reference fields are scored; qualitative ones are listed.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import evidence_model as em  # noqa: E402

REFERENCE_PATH = os.path.join(HERE, "reference_external_pr64.json")
RECORDS_PATH = os.path.join(HERE, "pubmed_records_external_pr64.json")
RESULTS_PATH = os.path.join(HERE, "external_pr64_results.json")
FROZEN_PATH = os.path.join(HERE, "external_pr64_first_run_results.json")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--no-write", action="store_true")
args = parser.parse_args()
ref_path, rec_path, out_path = REFERENCE_PATH, RECORDS_PATH, RESULTS_PATH

ref = json.load(open(ref_path, encoding="utf-8"))["cases"]
records = {r["pmid"]: r for r in json.load(open(rec_path, encoding="utf-8"))["records"]}

MEASURE = {"hr": "HR", "or": "OR", "rr": "RR", "sensitivity": "sensitivity", "specificity": "specificity",
           "proportion": "proportion", "auc": "AUC"}
DESIGN_OK = {"rct": {"rct"}, "meta_analysis": {"meta_analysis", "systematic_review_and_meta_analysis"},
             "cohort": {"cohort"}, "case_control": {"case_control"},
             "systematic_review": {"systematic_review", "systematic_review_and_meta_analysis", "narrative_review"},
             "diagnostic_accuracy": {"diagnostic_accuracy"}, "case_series": {"case_series", "retrospective_case_series"}}

def num(text):
    if text is None: return None
    m = re.fullmatch(r"\s*([-−]?\d+(?:\.\d+)?)\s*%?\s*", str(text))
    return float(m.group(1).replace("−", "-")) if m else None

def close(a, b, tol=1e-6):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol

def p_norm(p):
    return re.sub(r"[\s=]", "", str(p or "")).lower().replace("p", "")

results, totals = [], {"scored": 0, "matched": 0, "wrong": 0, "missed": 0}
for case in ref:
    rec = records[case["pmid"]]
    em.clear_cache()
    study = em.build_studies([rec], "")[0][0]
    fields = []
    def score(name, expected, got, ok):
        status = "eşleşti" if ok else ("eksik" if got in (None, [], "") else "yanlış")
        fields.append({"field": name, "expected": expected, "got": got, "status": status})
        totals["scored"] += 1
        totals[{"eşleşti": "matched", "eksik": "missed", "yanlış": "wrong"}[status]] += 1

    score("design", case["required_design"], study.design_key, study.design_key in DESIGN_OK.get(case["required_design"], set()))
    if case.get("total_n"):
        score("total_n", case["total_n"], study.population.n_total, study.population.n_total == case["total_n"])
    arm_ns = [a.n for a in study.arms]
    for arm in case.get("arms") or []:
        expected = arm["participants_n"]
        if expected in arm_ns:
            score(f"arm_n:{arm['label']}", expected, arm_ns, True)
        else:
            # An arm found without a size is missing, not wrong; a different size is wrong.
            same = [a.n for a in study.arms if a.label and a.label.lower() in arm["label"].lower() or
                    arm["label"].lower() in (a.label or "").lower()]
            got = next((n for n in same if n is not None), None)
            fields.append({"field": f"arm_n:{arm['label']}", "expected": expected, "got": got,
                           "status": "yanlış" if got is not None else "eksik"})
            totals["scored"] += 1
            totals["wrong" if got is not None else "missed"] += 1

    ests = [e for e in getattr(study, "estimates", [])]
    events = [ev.events for ev in study.event_counts]
    qualitative = []
    for o in case.get("outcomes") or []:
        metric = MEASURE.get(str(o.get("metric")).lower())
        value = num(o.get("estimate"))
        if metric is None or value is None:
            qualitative.append({"outcome": o["outcome"], "metric": o.get("metric"), "estimate": o.get("estimate")})
            continue
        cand = [e for e in ests if close(e.value, value)]
        same_measure = [e for e in cand if (e.measure or "").lower() == metric.lower()]
        best = (same_measure or cand or [None])[0]
        label = f"{metric} {o['estimate']} ({o['outcome'][:40]})"
        # A descriptive proportion may be kept as an event count with its percent
        # (e.g. "47 (15.6%)") instead of an effect estimate; both are faithful.
        as_count = [ev for ev in study.event_counts if metric == "proportion" and close(ev.percent, value)]
        if not same_measure and as_count and not o.get("ci"):
            score(f"estimate:{label}", o["estimate"], f"olay sayısı {as_count[0].events} ({as_count[0].percent}%)", True)
            ec = o.get("event_count")
            for e in (ec if isinstance(ec, list) else ([ec] if ec else [])):
                ok = e in events
                fields.append({"field": f"events:{e} ({o['outcome'][:30]})", "expected": e, "got": events,
                               "status": "eşleşti" if ok else "eksik"})
                totals["scored"] += 1
                totals["matched" if ok else "missed"] += 1
            continue
        score(f"estimate:{label}", o["estimate"], (f"{best.measure} {best.value_text}" if best else None), bool(same_measure))
        if o.get("ci"):
            lo, hi = num(o["ci"][0]), num(o["ci"][1])
            got = (best.ci_low, best.ci_high) if best else None
            score(f"ci:{label}", o["ci"], got, bool(best) and close(best.ci_low, lo) and close(best.ci_high, hi))
        if o.get("p"):
            score(f"p:{label}", o["p"], best.p_value if best else None, bool(best) and p_norm(best.p_value) == p_norm(o["p"]))
        ec = o.get("event_count")
        for e in (ec if isinstance(ec, list) else ([ec] if ec else [])):
            ok = e in events
            fields.append({"field": f"events:{e} ({o['outcome'][:30]})", "expected": e, "got": events,
                           "status": "eşleşti" if ok else "eksik"})
            totals["scored"] += 1
            totals["matched" if ok else "missed"] += 1
    # Safety check: a participant count stored as an event count is a false extraction.
    people = {case.get("total_n")} | {a.get("participants_n") for a in case.get("arms") or []}
    people.discard(None)
    for ev in study.event_counts:
        if ev.events in people and ev.total is None:
            fields.append({"field": f"olay sayısı olarak hasta sayısı: {ev.events}", "expected": "olay değil",
                           "got": ev.events, "status": "yanlış"})
            totals["scored"] += 1
            totals["wrong"] += 1
    results.append({"pmid": case["pmid"], "specialty": case["specialty"], "design": case["required_design"],
                    "fields": fields, "qualitative_not_scored": qualitative,
                    "complete": all(f["status"] == "eşleşti" for f in fields)})

summary = dict(totals)
summary["complete_cases"] = sum(r["complete"] for r in results)
summary["cases"] = len(results)
if not args.no_write:
    json.dump({"summary": summary, "cases": results}, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
frozen = json.load(open(FROZEN_PATH, encoding="utf-8"))["summary"] if os.path.exists(FROZEN_PATH) else None
if frozen:
    print("ilk çalıştırma (dondurulmuş):", json.dumps(frozen, ensure_ascii=False))
print(json.dumps(summary, ensure_ascii=False))
for r in results:
    bad = [f for f in r["fields"] if f["status"] != "eşleşti"]
    print(f"{r['pmid']} {r['specialty']:<24} {r['design']:<20} {len(r['fields'])-len(bad)}/{len(r['fields'])}")
    for f in bad:
        print(f"    {f['status']:<8} {f['field']}: beklenen={f['expected']} bulunan={f['got']}")

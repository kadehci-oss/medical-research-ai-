"""Compare engine output with the pre-specified multi-specialty reference table.

Usage:
    python validation/run_multispecialty_validation.py            # writes JSON + Markdown report
    python validation/run_multispecialty_validation.py --no-write # print summary only

Inputs (all real PubMed records, no network needed):
    validation/pubmed_records_multispecialty.json  PubMed records (PMID, DOI, title, abstract, types)
    validation/reference_dataset.json             hand-curated reference values (written before engine output)

Outputs:
    validation/multispecialty_validation_results.json
    validation/MULTISPECIALTY_VALIDATION_REPORT.md
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import evidence_model as em  # noqa: E402
import question_framework as qf  # noqa: E402
import report_generator as rg  # noqa: E402
import report_verification as rv  # noqa: E402
from version import APP_VERSION  # noqa: E402

RECORDS_PATH = os.path.join(HERE, "pubmed_records_multispecialty.json")
REFERENCE_PATH = os.path.join(HERE, "reference_dataset.json")
HOLDOUT_RECORDS_PATH = os.path.join(HERE, "pubmed_records_holdout.json")
HOLDOUT_REFERENCE_PATH = os.path.join(HERE, "reference_dataset_holdout.json")
HOLDOUT_FROZEN_PATH = os.path.join(HERE, "holdout_first_run_results.json")
RESULTS_PATH = os.path.join(HERE, "multispecialty_validation_results.json")
REPORT_PATH = os.path.join(HERE, "MULTISPECIALTY_VALIDATION_REPORT.md")

DESIGN_CLASS = {
    "rct": "rct",
    "clinical_trial": "rct",
    "cohort": "cohort",
    "retrospective_comparative": "cohort",
    "case_control": "case_control",
    "cross_sectional": "cross_sectional",
    "diagnostic_accuracy": "diagnostic_accuracy",
    "case_series": "case_series",
    "retrospective_case_series": "case_series",
    "case_report": "case_report",
    "systematic_review": "systematic_review",
    "meta_analysis": "meta_analysis",
    "systematic_review_and_meta_analysis": "meta_analysis",
    "editorial": "letter",
}
DESIGN_TR = {
    "rct": "RCT", "cohort": "Kohort", "case_control": "Vaka-kontrol", "diagnostic_accuracy": "Tanısal doğruluk",
    "case_series": "Olgu serisi", "systematic_review": "Sistematik derleme", "meta_analysis": "Meta-analiz",
    "protocol": "Protokol (sonuç yok)", "letter": "Mektup (özet yok)",
}
LATER_REPORT = {"updated_analysis", "extended_follow_up"}


def load_inputs(records_path: Optional[str] = None, reference_path: Optional[str] = None):
    with open(records_path or RECORDS_PATH, encoding="utf-8") as handle:
        records = {r["pmid"]: r for r in json.load(handle)}
    with open(reference_path or REFERENCE_PATH, encoding="utf-8") as handle:
        reference = json.load(handle)
    return records, reference


def engine_design_class(study: em.Study) -> str:
    if "protokol" in study.design_label:
        return "protocol"
    return DESIGN_CLASS.get(study.design_key, study.design_key)


def _close(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= 0.0051 + abs(b) * 0.001


def _scaled(value: Optional[float], ref: Optional[float]) -> Optional[float]:
    """Compare 0.92 with 92% on the same scale."""
    if value is None or ref is None:
        return value
    if ref <= 1.0 < value <= 100:
        return value / 100.0
    if value <= 1.0 < ref <= 100:
        return value * 100.0
    return value


def _number_in_text(value: Optional[float], text: str) -> bool:
    if value is None:
        return True
    norm = em.normalize_text(text)
    unsigned = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", norm)}
    numbers = unsigned | {-n for n in unsigned}
    return any(abs(n - value) < 1e-9 for n in numbers)


def match_effect(ref_eff: Dict[str, Any], estimates: List[em.EffectEstimate]) -> Optional[em.EffectEstimate]:
    for est in estimates:
        if est.measure != ref_eff["measure"]:
            continue
        ref_value = ref_eff.get("value")
        if ref_value is None:
            if est.value is not None:
                continue
        elif not _close(_scaled(est.value, ref_value), ref_value):
            continue
        ref_ci = ref_eff.get("ci")
        if ref_ci:
            if est.ci_low is None or est.ci_high is None:
                continue
            ref_lo, ref_hi = ref_ci
            if not (_close(_scaled(est.ci_low, ref_lo), ref_lo) and _close(_scaled(est.ci_high, ref_hi), ref_hi)):
                continue
        elif est.ci_low is not None:
            continue
        if ref_eff.get("ci_level") and est.ci_level != ref_eff["ci_level"]:
            continue
        return est
    return None


def _kw_hit(text: str, keywords: List[str]) -> bool:
    low = (text or "").lower()
    return any(k.lower() in low for k in keywords)


class Tally:
    def __init__(self):
        self.reference_items = 0   # items the reference says are reported
        self.complete = 0          # reference items extracted correctly
        self.extracted = 0         # items the engine asserted (for false-extraction rate)
        self.false = 0             # engine assertions that contradict the reference
        self.details: List[str] = []

    def item(self, reported: bool, extracted: bool, correct: bool, label: str):
        if reported:
            self.reference_items += 1
            if extracted and correct:
                self.complete += 1
        if extracted:
            self.extracted += 1
            if not correct:
                self.false += 1
                self.details.append(f"YANLIŞ: {label}")
        elif reported:
            self.details.append(f"EKSİK: {label}")

    def as_dict(self):
        return {
            "reference_items": self.reference_items,
            "complete": self.complete,
            "complete_rate": round(self.complete / self.reference_items, 4) if self.reference_items else None,
            "extracted": self.extracted,
            "false": self.false,
            "false_rate": round(self.false / self.extracted, 4) if self.extracted else 0.0,
        }


def evaluate_study(ref: Dict[str, Any], study: em.Study) -> Dict[str, Any]:
    t = Tally()
    pmid = ref["pmid"]
    # Design
    design = engine_design_class(study)
    t.item(True, True, design in ref["design"], f"{pmid} tasarım {design} (beklenen {ref['design']})")
    # Sample size
    ref_n = ref.get("sample_size")
    accept = set(ref.get("sample_size_accept") or [])
    accept.add(ref_n)
    got_n = study.population.n_total
    n_confused = bool(got_n is not None and got_n in set(ref.get("forbidden_n") or []))
    if ref_n is None:
        t.item(False, got_n is not None, got_n in accept, f"{pmid} örneklem {got_n} (özette toplam yok; değer atanmamalı)")
    else:
        t.item(True, got_n is not None, got_n in accept, f"{pmid} örneklem {got_n} (beklenen {ref_n})")
    # Effects and outcome binding
    binding = {"bound": 0, "unbound": 0, "wrong": 0}
    for eff in ref.get("effects") or []:
        est = match_effect(eff, study.estimates)
        label = f"{pmid} {eff['measure']} {eff.get('value')} {eff.get('ci')}"
        t.item(True, est is not None, est is not None, label)
        if est is not None and eff.get("outcome_kw"):
            if not est.outcome_name:
                binding["unbound"] += 1
                t.details.append(f"BAĞLANMADI: {label} sonlanım adı yok")
            elif _kw_hit(est.outcome_name, eff["outcome_kw"]) or _kw_hit(est.outcome_basis, eff["outcome_kw"]):
                binding["bound"] += 1
            else:
                binding["wrong"] += 1
                t.false += 1
                t.extracted += 1
                t.details.append(f"YANLIŞ BAĞLAMA: {label} → '{est.outcome_name}'")
    if ref.get("results_reported") is False or (not ref.get("effects") and engine_design_class(study) in ("case_series",)):
        stray = [e for e in study.estimates if e.usable]
        for est in stray:
            t.item(False, True, False, f"{pmid} sonuç bildirmeyen/tanımlayıcı kayıtta etki tahmini {est.measure} {est.value}")
    # Intervention / comparator / background therapy
    interventions = " | ".join(i.name for i in study.interventions)
    comparators = " | ".join(c.name for c in study.comparators)
    co = " | ".join(c.name for c in study.co_treatments)
    if ref.get("intervention_kw"):
        ok = _kw_hit(interventions, ref["intervention_kw"])
        t.item(True, bool(interventions), ok, f"{pmid} müdahale '{interventions}' (beklenen {ref['intervention_kw']})")
    if ref.get("comparator_kw"):
        ok = _kw_hit(comparators, ref["comparator_kw"]) or _kw_hit(comparators.replace("Plasebo", "placebo"), ref["comparator_kw"])
        t.item(True, bool(comparators), ok, f"{pmid} karşılaştırıcı '{comparators}' (beklenen {ref['comparator_kw']})")
    background_as_intervention = 0
    if ref.get("background_kw"):
        t.item(True, bool(co), _kw_hit(co, ref["background_kw"]), f"{pmid} eşlik eden tedavi '{co}' (beklenen {ref['background_kw']})")
        for intervention in study.interventions:
            if _kw_hit(intervention.name, ref["background_kw"]) and not _kw_hit(intervention.name, ref.get("intervention_kw") or []):
                background_as_intervention += 1
                t.item(False, True, False, f"{pmid} eşlik eden tedavi müdahale sanıldı: '{intervention.name}'")
    # Relations
    ref_rel = ref.get("relation")
    role = study.report_role
    parents = {r.related_pmid for r in study.relations if r.relation_type != "includes_trial"}
    if ref_rel == "meta_analysis":
        correct = role == "evidence_synthesis"
        t.item(True, True, correct, f"{pmid} yayın rolü {role} (beklenen kanıt sentezi)")
        for included in ref.get("includes") or []:
            linked = any(r.relation_type == "includes_trial" and r.related_pmid == included for r in study.relations)
            t.item(True, linked, linked, f"{pmid} meta-analiz → PMID {included} katılımcı örtüşmesi")
    elif ref_rel == "primary":
        t.item(False, role != "primary", role == "primary", f"{pmid} birincil çalışma yanlışlıkla '{role}' sayıldı")
    else:
        role_ok = role == ref_rel or (role in LATER_REPORT and ref_rel in LATER_REPORT)
        t.item(True, role != "primary", role_ok, f"{pmid} yayın rolü {role} (beklenen {ref_rel})")
        t.item(True, bool(parents), ref.get("parent") in parents, f"{pmid} ana çalışma bağlantısı {sorted(parents)} (beklenen {ref.get('parent')})")
    expected_independent = ref_rel == "primary" and ref.get("results_reported", True)
    independence_error = study.counts_as_independent != expected_independent
    if independence_error:
        t.details.append(f"BAĞIMSIZLIK: {pmid} bağımsız={study.counts_as_independent} (beklenen {expected_independent})")
    # Causality
    causal_permission_error = study.causal_inference_allowed and not ref["causal_allowed"]
    return {
        "pmid": pmid,
        "specialty": ref["specialty"],
        "reference_design": ref["design"][0],
        "engine_design": design,
        "tally": t,
        "binding": binding,
        "n_confused_with_event_or_arm": n_confused,
        "background_as_intervention": background_as_intervention,
        "independence_error": independence_error,
        "causal_permission_error": causal_permission_error,
        "causal_allowed_reference": ref["causal_allowed"],
    }


def source_match_audit(studies: List[em.Study]) -> Dict[str, Any]:
    total = verified = value_ok = values_checked = 0
    failures: List[str] = []
    for study in studies:
        sources = [("örneklem", study.population.source)] if study.population.n_total else []
        sources += [("kol", a.source) for a in study.arms]
        sources += [("müdahale", i.source) for i in study.interventions]
        sources += [("karşılaştırıcı", c.source) for c in study.comparators]
        sources += [("eşlik eden tedavi", c.source) for c in study.co_treatments]
        sources += [("etki", e.source) for e in study.estimates]
        for kind, src in sources:
            total += 1
            pmid_ok = src.pmid == study.pmid
            if src.verification_status == em.SOURCE_DERIVED:
                _loc, status = em.verify_sentence_in_source(src.sentence, study.legacy.get("abstract", ""), study.title)
            else:
                status = src.verification_status
            if pmid_ok and status == em.SOURCE_VERIFIED:
                verified += 1
            else:
                failures.append(f"{study.pmid} {kind}: {src.verification_status} pmid_ok={pmid_ok}")
        for est in study.estimates:
            values_checked += 1
            if all(_number_in_text(v, est.source.sentence) for v in (est.value, est.ci_low, est.ci_high)):
                value_ok += 1
            else:
                failures.append(f"{study.pmid} {est.measure} değeri kaynak cümlede yok: {est.value} {est.ci_low} {est.ci_high}")
        if study.population.n_total and study.population.n_kind != "arm_sum":
            values_checked += 1
            sentence = em.normalize_text(study.population.source.sentence).replace(",", "").replace(" ", "")
            word_ok = any(w in study.population.source.sentence.lower() for w, n in em._WORD_NUMBERS.items()
                          if n == study.population.n_total)
            if str(study.population.n_total) in sentence or word_ok or study.population.n_kind == "cases":
                value_ok += 1
            else:
                failures.append(f"{study.pmid} örneklem {study.population.n_total} kaynak cümlede yok")
    return {
        "sources_total": total,
        "sources_verified": verified,
        "source_match_accuracy": round(verified / total, 4) if total else None,
        "values_checked": values_checked,
        "values_in_source": value_ok,
        "value_match_accuracy": round(value_ok / values_checked, 4) if values_checked else None,
        "failures": failures,
    }


def causal_language_audit(records: Dict[str, Dict[str, Any]], reference: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the full Turkish report per specialty and scan generated wording."""
    by_specialty: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ref in reference["studies"]:
        by_specialty[ref["specialty"]].append(records[ref["pmid"]])
    queries = {q["specialty"]: q["query"] for q in reference["queries"]}
    allowed = {r["pmid"]: r["causal_allowed"] for r in reference["studies"]}
    hits: List[Dict[str, str]] = []
    report_status: Dict[str, Any] = {}
    offline = {"status": "unverified", "verified": False, "reason": "offline validation run", "error": "offline"}
    with patch("report_generator.verify_citation", return_value=offline):
        for specialty, articles in by_specialty.items():
            query = queries.get(specialty, specialty)
            report = rg.generate_rule_based_turkish_report(query, articles, search_metadata={"search_date": "validation"})
            studies, _summary = em.build_studies(articles, query)
            check = rv.verify_report(report, studies)
            report_status[specialty] = {
                "status": check["status"],
                "unknown_pmids": check["unknown_pmids"],
                "quotes_checked": check["quotes_checked"],
                "quotes_failed": len(check["quotes_failed"]),
                "rob_rating_claims": len(check["rob_rating_claims"]),
                "grade_rating_claims": len(check["grade_rating_claims"]),
            }
            for line in report.split("## 13.")[0].splitlines():
                pmids = set(rv._PMID_RE.findall(line))
                if not pmids or any(allowed.get(p, True) for p in pmids):
                    continue
                words = em.find_causal_language(line)
                if words:
                    hits.append({"specialty": specialty, "pmids": ", ".join(sorted(pmids)), "words": ", ".join(words),
                                 "line": line[:220]})
    return {"false_causal_claims": len(hits), "hits": hits, "reports": report_status}


def run(records_path: Optional[str] = None, reference_path: Optional[str] = None) -> Dict[str, Any]:
    records, reference = load_inputs(records_path, reference_path)
    em.clear_cache()
    refs = reference["studies"]
    articles = [records[r["pmid"]] for r in refs]
    studies, summary = em.build_studies(articles)
    study_by_pmid = {s.pmid: s for s in studies}
    evaluations = [evaluate_study(ref, study_by_pmid[ref["pmid"]]) for ref in refs]

    def aggregate(items):
        agg = Tally()
        for ev in items:
            t = ev["tally"]
            agg.reference_items += t.reference_items
            agg.complete += t.complete
            agg.extracted += t.extracted
            agg.false += t.false
        return agg.as_dict()

    per_specialty = {}
    for specialty in sorted({r["specialty"] for r in refs}):
        items = [ev for ev in evaluations if ev["specialty"] == specialty]
        per_specialty[specialty] = {
            **aggregate(items),
            "studies": len(items),
            "designs": sorted({DESIGN_TR.get(ev["reference_design"], ev["reference_design"]) for ev in items}),
        }
    per_design = {}
    for design in sorted({ev["reference_design"] for ev in evaluations}):
        items = [ev for ev in evaluations if ev["reference_design"] == design]
        per_design[DESIGN_TR.get(design, design)] = {**aggregate(items), "studies": len(items)}

    sources = source_match_audit(studies)
    causal = causal_language_audit(records, reference)
    causal_permission_errors = [ev["pmid"] for ev in evaluations if ev["causal_permission_error"]]
    framework_rows = []
    for q in reference["queries"]:
        got = qf.classify_question_type(q["query"])
        framework_rows.append({**q, "engine": got, "correct": got == q["question_type"]})
    binding = defaultdict(int)
    for ev in evaluations:
        for k, v in ev["binding"].items():
            binding[k] += v

    results = {
        "generated": datetime.date.today().isoformat(),
        "app_version": APP_VERSION,
        "evidence_model_version": em.EVIDENCE_MODEL_VERSION,
        "n_studies": len(refs),
        "n_specialties": len(per_specialty),
        "overall": aggregate(evaluations),
        "per_specialty": per_specialty,
        "per_design": per_design,
        "outcome_binding": dict(binding),
        "sample_size_confused_with_event_or_arm_count": [ev["pmid"] for ev in evaluations if ev["n_confused_with_event_or_arm"]],
        "background_therapy_reported_as_intervention": sum(ev["background_as_intervention"] for ev in evaluations),
        "independence_errors": [ev["pmid"] for ev in evaluations if ev["independence_error"]],
        "relations_summary": {
            "independent_primary_units": summary["independent_primary_units"],
            "clusters_with_multiple_reports": {k: v for k, v in summary["clusters"].items() if len(v) > 1},
            "overlap_notes": summary["overlap_notes"],
        },
        "source_match": sources,
        "false_causal_claims": causal["false_causal_claims"] + len(causal_permission_errors),
        "false_causal_language_hits": causal["hits"],
        "causal_permission_errors": causal_permission_errors,
        "report_verification_by_specialty": causal["reports"],
        "question_framework": {
            "correct": sum(r["correct"] for r in framework_rows),
            "total": len(framework_rows),
            "rows": framework_rows,
        },
        "study_details": {ev["pmid"]: ev["tally"].details for ev in evaluations},
    }
    return results


def run_all() -> Dict[str, Any]:
    development = run(RECORDS_PATH, REFERENCE_PATH)
    holdout = run(HOLDOUT_RECORDS_PATH, HOLDOUT_REFERENCE_PATH)
    frozen = None
    if os.path.exists(HOLDOUT_FROZEN_PATH):
        with open(HOLDOUT_FROZEN_PATH, encoding="utf-8") as handle:
            frozen = json.load(handle)
    return {"development": development, "holdout_current": holdout, "holdout_first_run": frozen}


def _pct(value: Optional[float]) -> str:
    return "—" if value is None else f"%{value * 100:.1f}"


def _headline(res: Dict[str, Any]) -> List[Tuple[str, str]]:
    o = res["overall"]
    s = res["source_match"]
    return [
        ("Eksiksiz çıkarım oranı", f"{_pct(o['complete_rate'])} ({o['complete']}/{o['reference_items']})"),
        ("Yanlış çıkarım oranı", f"{_pct(o['false_rate'])} ({o['false']}/{o['extracted']})"),
        ("Kaynak eşleşme doğruluğu (cümle)", f"{_pct(s['source_match_accuracy'])} ({s['sources_verified']}/{s['sources_total']})"),
        ("Kaynak eşleşme doğruluğu (sayısal değer)", f"{_pct(s['value_match_accuracy'])} ({s['values_in_source']}/{s['values_checked']})"),
        ("Yanlış nedensellik iddiası", str(res["false_causal_claims"])),
        ("Soru çerçevesi seçimi", f"{res['question_framework']['correct']}/{res['question_framework']['total']}"),
    ]


def render_combined_markdown(all_res: Dict[str, Any]) -> str:
    dev = all_res["development"]
    hold = all_res["holdout_current"]
    frozen = all_res.get("holdout_first_run")
    lines = [
        "# Çok Branşlı Doğrulama Raporu",
        "",
        f"Oluşturulma: {dev['generated']} · Yazılım: `{dev['app_version']}` · Kanıt veri modeli: `{dev['evidence_model_version']}`",
        "",
        "Bu rapor `python validation/run_multispecialty_validation.py` ile üretilir; elle düzenlenmez.",
        "",
        "## Özet: üç ayrı sonuç kümesi",
        "",
        "Geliştirme kümesi motor ayarlanırken kullanıldı; sonuçları **iyimserdir** ve doğruluk tahmini olarak okunmamalıdır.",
        "Bağımsız tahmin için ayrılmış küme kuruldu: referans değerler motor bu kayıtlarda hiç çalıştırılmadan yazıldı ve",
        "ilk çalıştırma `validation/holdout_first_run_results.json` içinde donduruldu. İlk çalıştırmanın gösterdiği genel hatalar",
        "sonra düzeltildi; bu yüzden ayrılmış kümenin güncel sonucu artık bağımsız değildir.",
        "",
        "| Ölçüt | Geliştirme kümesi (ayarlı) | **Ayrılmış küme, ilk çalıştırma (bağımsız)** | Ayrılmış küme, düzeltme sonrası (bağımsız değil) |",
        "|---|---|---|---|",
    ]
    frozen_rows = _headline(frozen) if frozen else []
    for i, (name, dev_value) in enumerate(_headline(dev)):
        frozen_value = frozen_rows[i][1] if frozen_rows else "—"
        lines.append(f"| {name} | {dev_value} | **{frozen_value}** | {_headline(hold)[i][1]} |")
    lines += [
        "",
        f"- Geliştirme kümesi: {dev['n_studies']} yayın, {dev['n_specialties']} branş. Ayrılmış küme: {hold['n_studies']} yayın, "
        f"{hold['n_specialties']} branş. Toplam {dev['n_studies'] + hold['n_studies']} gerçek PubMed yayını.",
        "- **Sınırlılık:** Her iki referans tabloyu bir yapay zekâ asistanı hazırladı; bağımsız uzman hekim kontrolü yapılmadı. "
        "Yalnızca özetler kullanıldı. Küme küçük olduğu için oranların belirsizliği yüksektir.",
        "",
    ]
    if frozen:
        lines += ["### Ayrılmış kümenin ilk çalıştırmasında bulunan hatalar", ""]
        for pmid, details in (frozen.get("study_details") or {}).items():
            if details:
                lines.append(f"- **PMID {pmid}:** " + "; ".join(details))
        lines.append("")
    lines.append(render_markdown(dev, title="## Geliştirme kümesi ayrıntıları", heading_level=3))
    lines.append(render_markdown(hold, title="## Ayrılmış küme, güncel çalıştırma ayrıntıları", heading_level=3))
    return "\n".join(lines) + "\n"


def render_markdown(res: Dict[str, Any], title: str = "# Çok Branşlı Doğrulama Raporu", heading_level: int = 2) -> str:
    o = res["overall"]
    s = res["source_match"]
    lines = [
        title,
        "",
        f"{'#' * heading_level} Kapsam ve yöntem",
        "",
        f"- **{res['n_studies']} gerçek PubMed yayını**, **{res['n_specialties']} branş**: kardiyoloji, onkoloji, nöroloji, enfeksiyon, endokrinoloji, pediatri, cerrahi, radyoloji.",
        "- Kayıtlar PubMed'den alındı (PMID, DOI, başlık, özet, yayın türü) ve `validation/` altındaki JSON dosyalarında değiştirilmeden saklandı.",
        "- Referans tablo (`validation/reference_dataset.json`) özetler elle okunarak, motor çıktısına bakılmadan yazıldı.",
        "- **Sınırlılık:** Referans tabloyu bir yapay zekâ asistanı hazırladı. Bağımsız uzman hekim kontrolü henüz yapılmadı. Yalnızca özetler kullanıldı; tam metin okunmadı.",
        "",
        f"{'#' * heading_level} Ölçüt tanımları",
        "",
        "- **Eksiksiz çıkarım oranı:** Referansta bildirilen öğelerden (tasarım, örneklem, ana etki tahmini + GA, müdahale, karşılaştırıcı, eşlik eden tedavi, yayın ilişkisi) motorun doğru çıkardıklarının oranı.",
        "- **Yanlış çıkarım oranı:** Motorun ileri sürdüğü öğelerden referansla çelişenlerin oranı (yanlış sonlanım bağlama, olay/kol sayısının örneklem sanılması, eksik değere değer atama dahil).",
        "- **Kaynak eşleşme doğruluğu:** Her yapılandırılmış öğenin kaynak cümlesinin aynı PMID'nin özetinde birebir bulunma oranı; ayrıca her sayısal değerin o cümlede geçme oranı.",
        "- **Yanlış nedensellik iddiası:** Randomize olmayan çalışmalara bağlı rapor satırlarında (alıntılar hariç) nedensel/üstünlük ifadesi sayısı + nedensel çıkarıma yanlışlıkla izin verilen çalışma sayısı.",
        "",
        f"{'#' * heading_level} Genel sonuçlar",
        "",
        "| Ölçüt | Değer |",
        "|---|---|",
        f"| Eksiksiz çıkarım oranı | {_pct(o['complete_rate'])} ({o['complete']}/{o['reference_items']}) |",
        f"| Yanlış çıkarım oranı | {_pct(o['false_rate'])} ({o['false']}/{o['extracted']}) |",
        f"| Kaynak eşleşme doğruluğu (cümle) | {_pct(s['source_match_accuracy'])} ({s['sources_verified']}/{s['sources_total']}) |",
        f"| Kaynak eşleşme doğruluğu (sayısal değer) | {_pct(s['value_match_accuracy'])} ({s['values_in_source']}/{s['values_checked']}) |",
        f"| Yanlış nedensellik iddiası | {res['false_causal_claims']} |",
        f"| Örneklem yerine olay/kol sayısı | {len(res['sample_size_confused_with_event_or_arm_count'])} |",
        f"| Eşlik eden tedavinin müdahale sanılması | {res['background_therapy_reported_as_intervention']} |",
        f"| Bağımsız kanıt sayımı hatası | {len(res['independence_errors'])} |",
        f"| Soru çerçevesi seçimi | {res['question_framework']['correct']}/{res['question_framework']['total']} |",
        f"| Sonlanım bağlama (doğru / adsız / yanlış) | {res['outcome_binding'].get('bound', 0)} / {res['outcome_binding'].get('unbound', 0)} / {res['outcome_binding'].get('wrong', 0)} |",
        "",
        f"{'#' * heading_level} Branşlara göre",
        "",
        "| Branş | Yayın | Tasarımlar | Eksiksiz çıkarım | Yanlış çıkarım |",
        "|---|---|---|---|---|",
    ]
    for name, row in res["per_specialty"].items():
        lines.append(f"| {name} | {row['studies']} | {', '.join(row['designs'])} | {_pct(row['complete_rate'])} "
                     f"({row['complete']}/{row['reference_items']}) | {_pct(row['false_rate'])} ({row['false']}/{row['extracted']}) |")
    lines += ["", f"{'#' * heading_level} Araştırma türüne göre", "", "| Tasarım | Yayın | Eksiksiz çıkarım | Yanlış çıkarım |", "|---|---|---|---|"]
    for name, row in res["per_design"].items():
        lines.append(f"| {name} | {row['studies']} | {_pct(row['complete_rate'])} ({row['complete']}/{row['reference_items']}) | "
                     f"{_pct(row['false_rate'])} ({row['false']}/{row['extracted']}) |")
    lines += ["", f"{'#' * heading_level} Çalışma ilişkileri (mükerrer kanıt kontrolü)", ""]
    rel = res["relations_summary"]
    lines.append(f"- Bağımsız birincil kanıt birimi: {rel['independent_primary_units']}")
    for root, members in rel["clusters_with_multiple_reports"].items():
        lines.append(f"- Aynı çalışma kümesi: PMID {', '.join(members)}")
    for note in rel["overlap_notes"]:
        lines.append(f"- {note}")
    lines += ["", f"{'#' * heading_level} Rapor doğrulama durumu (branş başına tam Türkçe rapor)", "",
              "| Branş | Durum | Alıntı kontrolü | Kümede olmayan PMID | RoB/GRADE derece iddiası |", "|---|---|---|---|---|"]
    for name, row in res["report_verification_by_specialty"].items():
        lines.append(f"| {name} | {row['status']} | {row['quotes_checked'] - row['quotes_failed']}/{row['quotes_checked']} | "
                     f"{len(row['unknown_pmids'])} | {row['rob_rating_claims'] + row['grade_rating_claims']} |")
    if res["false_causal_language_hits"]:
        lines += ["", f"{'#' * heading_level} Yanlış nedensellik ifadeleri", ""]
        for hit in res["false_causal_language_hits"]:
            lines.append(f"- {hit['specialty']} / PMID {hit['pmids']}: `{hit['words']}` — {hit['line']}")
    lines += ["", f"{'#' * heading_level} Soru çerçevesi seçimi", "", "| Branş | Soru | Beklenen | Motor |", "|---|---|---|---|"]
    for row in res["question_framework"]["rows"]:
        mark = "✓" if row["correct"] else "✗"
        lines.append(f"| {row['specialty']} | {row['query']} | {row['question_type']} | {row['engine']} {mark} |")
    lines += ["", f"{'#' * heading_level} Eksik ve yanlış öğeler (çalışma bazında)", ""]
    for pmid, details in res["study_details"].items():
        if details:
            lines.append(f"- **PMID {pmid}:** " + "; ".join(details))
    if res["source_match"]["failures"]:
        lines += ["", f"{'#' * heading_level} Kaynak eşleşme hataları", ""]
        lines += [f"- {f}" for f in res["source_match"]["failures"]]
    lines += ["", f"{'#' * heading_level} Test kategorileri", "",
              "1. **Yazılım birim ve entegrasyon testleri:** `tests/test_evidence_model.py` (rapor doğrulama testleri dahil), `tests/test_question_framework.py` ve mevcut test paketi.",
              "2. **Gerçek PubMed kaynak doğrulaması:** `tests/test_pubmed_source_verification.py` (kayıtlı PubMed kayıtlarının bütünlüğü; `RUN_LIVE_PUBMED=1` ile canlı NCBI karşılaştırması).",
              "3. **Bağımsız klinik veri doğrulaması:** `tests/test_clinical_reference_validation.py` (bu raporun ölçütleri; eşik altına düşerse test başarısız olur).",
              ""]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    all_res = run_all()
    res = all_res["development"]
    if not args.no_write:
        with open(RESULTS_PATH, "w", encoding="utf-8") as handle:
            json.dump(all_res, handle, ensure_ascii=False, indent=1)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            handle.write(render_combined_markdown(all_res))
    o = res["overall"]
    print(f"complete={o['complete_rate']} false={o['false_rate']} source={res['source_match']['source_match_accuracy']} "
          f"values={res['source_match']['value_match_accuracy']} causal={res['false_causal_claims']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

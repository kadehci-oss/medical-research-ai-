"""Live PubMed validation and prespecified reference comparison.

Run from the repository root with:
    python validation/run_pubmed_benchmark.py

This evaluates abstract-level extraction against a curated reference table. It
is not independent clinician review, full-text adjudication, or a GRADE/RoB
assessment.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "validation" / "pubmed_reference_cases.json"
JSON_OUT = ROOT / "validation" / "pubmed_benchmark_report.json"
MD_OUT = ROOT / "validation" / "pubmed_benchmark_report.md"

sys.path.insert(0, str(ROOT))
from clinical_evidence import MODEL_VERSION, build_study_model, validate_study_model  # noqa: E402
from pubmed_client import verify_citation  # noqa: E402


def norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def number_tokens(value: Any) -> List[str]:
    return [x.replace(",", "") for x in re.findall(r"(?<![A-Za-z])[-−]?\d[\d,]*(?:\.\d+)?%?", str(value or ""))]


def numbers_equal(left: Any, right: Any) -> bool:
    a = number_tokens(left)
    b = number_tokens(right)
    if len(a) != 1 or len(b) != 1:
        return False
    return a[0].replace("−", "-").rstrip("%") == b[0].replace("−", "-").rstrip("%")


def source_present(sentence: str, article: Dict[str, Any]) -> bool:
    candidate = norm(sentence)
    if not candidate:
        return False
    full = norm(article.get("abstract"))
    title = norm(article.get("title"))
    return candidate in full or candidate in title


def iter_sourced_claims(node: Any, path: str = "study") -> Iterable[Tuple[str, Any, Dict[str, Any]]]:
    if isinstance(node, dict):
        if "value" in node and isinstance(node.get("source"), dict):
            if node.get("value") not in (None, ""):
                yield path, node.get("value"), node["source"]
            return
        for key, value in node.items():
            if key in {"source", "extraction_validation"}:
                continue
            yield from iter_sourced_claims(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_sourced_claims(value, f"{path}[{index}]")


def metric_aliases(metric: str) -> List[str]:
    return {
        "HR": ["HR", "hazard ratio"],
        "RR": ["RR", "risk ratio", "relative risk"],
        "OR": ["OR", "odds ratio"],
        "sensitivity": ["sensitivity"],
        "specificity": ["specificity"],
        "AUC": ["AUC", "AUROC"],
        "MD": ["MD", "mean difference"],
        "SMD": ["SMD", "standardized mean difference", "standardised mean difference"],
    }.get(metric, [metric.replace("_", " ")])


def expected_outcome_match(outcome: Dict[str, Any], model: Dict[str, Any]) -> Dict[str, Any]:
    expected_sentence = norm(outcome.get("source_sentence"))
    candidates = []
    for item in model.get("outcomes") or []:
        actual_sentence = norm((item.get("source") or {}).get("source_sentence"))
        if expected_sentence and actual_sentence and (expected_sentence in actual_sentence or actual_sentence in expected_sentence):
            candidates.append(item)
    effects = [effect for item in candidates for effect in item.get("effect_estimates") or []]
    metric = str(outcome.get("metric") or "")
    estimate = outcome.get("estimate")
    expected_numbers = number_tokens(estimate)
    estimate_ok = False
    metric_ok = False
    matched_effect = None
    for effect in effects:
        if len(expected_numbers) == 1 and numbers_equal(effect.get("value"), expected_numbers[0]):
            estimate_ok = True
            matched_effect = effect
            expected_metric = metric_aliases(metric)
            model_metric = str(effect.get("metric_type") or "")
            if model_metric in expected_metric or (model_metric == "not_named_in_source" and metric in {"proportion", "prevalence", "qualitative association", "likelihood ratio"}):
                metric_ok = True
            break
    ci = outcome.get("ci")
    ci_ok = None
    if ci is not None:
        ci_numbers = [number_tokens(x)[0] if number_tokens(x) else "" for x in ci]
        ci_ok = any(
            str(effect.get("ci_lower")) == ci_numbers[0].rstrip("%")
            and str(effect.get("ci_upper")) == ci_numbers[1].rstrip("%")
            for effect in effects if len(ci_numbers) == 2
        )
    p_ok = None
    if outcome.get("p") is not None:
        expected_p = re.sub(r"\s+", "", str(outcome["p"])).casefold()
        p_ok = any(re.sub(r"\s+", "", str(effect.get("p_value") or "")).casefold().removeprefix("p") == expected_p.casefold().removeprefix("p") for effect in effects)
    return {
        "source_sentence_matched": bool(candidates),
        "estimate_matched": estimate_ok,
        "metric_matched": metric_ok,
        "ci_matched": ci_ok,
        "p_matched": p_ok,
        "matched_effect": matched_effect,
    }


def compare_case(case: Dict[str, Any], article: Dict[str, Any], model: Dict[str, Any]) -> Dict[str, Any]:
    expected_checks: List[Tuple[str, bool]] = []
    expected_n = case.get("total_n")
    actual_n = ((model.get("population") or {}).get("total_participants") or {}).get("value")
    if expected_n is not None:
        expected_checks.append(("total_n", actual_n == expected_n))

    arm_results = []
    model_arms = model.get("arms") or []
    for arm in case.get("arms") or []:
        expected_arm_n = arm.get("participants_n")
        if expected_arm_n is None:
            continue
        label = norm(arm.get("label"))
        matches = [x for x in model_arms if label and (label in norm(x.get("label")) or norm(x.get("label")) in label)]
        n_match = any(x.get("participants_n", {}).get("value") == expected_arm_n for x in matches)
        expected_checks.append((f"arm_n:{arm.get('label')}", n_match))
        arm_results.append({"label": arm.get("label"), "expected_n": expected_arm_n, "matched": n_match})

    outcomes = []
    for index, expected in enumerate(case.get("outcomes") or [], 1):
        match = expected_outcome_match(expected, model)
        checks = []
        if expected.get("estimate") is not None:
            checks.extend([match["source_sentence_matched"], match["estimate_matched"], match["metric_matched"]])
        if expected.get("ci") is not None:
            checks.append(bool(match["ci_matched"]))
        if expected.get("p") is not None:
            checks.append(bool(match["p_matched"]))
        for event_count in expected.get("event_count") if isinstance(expected.get("event_count"), list) else ([expected["event_count"]] if expected.get("event_count") is not None else []):
            model_counts = []
            for item in model.get("outcomes") or []:
                model_counts.extend([x.get("event_count", {}).get("value") for x in item.get("arm_event_counts") or []])
                if item.get("event_count", {}).get("value") is not None:
                    model_counts.append(item["event_count"]["value"])
            event_ok = event_count in model_counts
            checks.append(event_ok)
        expected_checks.extend((f"outcome:{index}:field:{j + 1}", bool(value)) for j, value in enumerate(checks))
        outcomes.append({
            "outcome": expected.get("outcome"),
            "reference_metric": expected.get("metric"),
            "reference_estimate": expected.get("estimate"),
            "source_sentence_matched": match["source_sentence_matched"],
            "estimate_matched": match["estimate_matched"],
            "metric_matched": match["metric_matched"],
            "ci_matched": match["ci_matched"],
            "p_matched": match["p_matched"],
        })

    required_design = case.get("required_design")
    actual_design = model.get("design_key")
    design_alias = {
        "systematic_review": {"systematic_review", "systematic_review_and_meta_analysis", "meta_analysis"},
        "meta_analysis": {"meta_analysis", "systematic_review_and_meta_analysis"},
    }
    design_ok = actual_design == required_design or actual_design in design_alias.get(required_design, set())
    expected_checks.append(("study_design", design_ok))

    all_claims = list(iter_sourced_claims(model))
    sourced = [x for x in all_claims if x[2].get("source_sentence")]
    source_matches = [x for x in sourced if source_present(x[2].get("source_sentence", ""), article)]
    unsupported_values = []
    for path, value, source in all_claims:
        sentence = str(source.get("source_sentence") or "")
        if not sentence or not source_present(sentence, article):
            unsupported_values.append(path)
            continue
        # Numeric model values are auditable by literal value in their attached sentence.
        tokens = number_tokens(value)
        sentence_numbers = {x.replace("−", "-").rstrip("%") for x in number_tokens(sentence)}
        if any(token.replace("−", "-").rstrip("%") not in sentence_numbers for token in tokens):
            unsupported_values.append(path)

    # Named effect types must also occur in their attached source sentence.
    unsupported_metric_types = []
    for outcome in model.get("outcomes") or []:
        for effect in outcome.get("effect_estimates") or []:
            metric = effect.get("metric_type")
            if metric == "not_named_in_source":
                continue
            sentence = str((effect.get("source") or {}).get("source_sentence") or "").casefold()
            if not any(alias.casefold() in sentence for alias in metric_aliases(str(metric))):
                unsupported_metric_types.append(f"{outcome.get('id')}:{metric}")

    causal_status = model.get("causal_interpretation_status", "")
    observational = required_design in {"cohort", "case_control", "diagnostic_accuracy", "case_series", "systematic_review", "meta_analysis"}
    causal_overclaim = bool(observational and "association_only" not in causal_status and "descriptive_or_unclear" not in causal_status and "review_of_prior_studies" not in causal_status)
    return {
        "specialty": case["specialty"],
        "pmid": case["pmid"],
        "expected_design": required_design,
        "actual_design": actual_design,
        "design_match": design_ok,
        "expected_total_n": expected_n,
        "actual_total_n": actual_n,
        "total_n_match": None if expected_n is None else actual_n == expected_n,
        "arms": arm_results,
        "outcomes": outcomes,
        "reference_fields_matched": sum(1 for _, ok in expected_checks if ok),
        "reference_fields_expected": len(expected_checks),
        "complete_reference_extraction": bool(expected_checks) and all(ok for _, ok in expected_checks),
        "source_claim_count": len(all_claims),
        "metric_type_check_count": sum(
            1 for outcome in model.get("outcomes") or []
            for _effect in outcome.get("effect_estimates") or []
        ),
        "source_sentence_matches": len(source_matches),
        "source_sentence_exact_match_rate": (len(source_matches) / len(sourced)) if sourced else None,
        "unsupported_value_claims": unsupported_values,
        "unsupported_metric_type_claims": unsupported_metric_types,
        "false_causal_claim_flag": causal_overclaim,
        "model_validation": model.get("extraction_validation"),
        "record_verification_status": (model.get("source") or {}).get("verification_status"),
        "study_relationship": model.get("relationship"),
        "evidence_family_id": model.get("evidence_family_id"),
    }


def render_markdown(report: Dict[str, Any]) -> str:
    pubmed = report["test_categories"]["real_pubmed_source_validation"]
    software = report["test_categories"]["software_unit_integration_tests"]
    clinical = report["test_categories"]["independent_clinical_data_validation"]
    lines = [
        "# Çok Branşlı PubMed Klinik Kanıt Benchmark Raporu",
        "",
        "Bu rapor, sekiz önceden belirlenmiş PubMed kaydında abstract düzeyindeki çıkarımı kaynak cümleleriyle karşılaştırır. Bu bir hekim adjudikasyonu, tam metin incelemesi, GRADE değerlendirmesi veya yanlılık riski değerlendirmesi değildir.",
        "",
        "## Sonuç özeti",
        "",
        f"- PubMed kimliği doğrulanan kayıt: **{pubmed['verified_records']}/{pubmed['records_checked']}**.",
        f"- Önceden belirlenmiş referans alanı eşleşmesi: **{report['reference_comparison']['matched_fields']}/{report['reference_comparison']['expected_fields']}** ({report['reference_comparison']['field_match_rate']:.1%}).",
        f"- Eksiksiz makale çıkarımı: **{report['reference_comparison']['complete_articles']}/{report['reference_comparison']['articles']}** ({report['reference_comparison']['complete_article_rate']:.1%}).",
        f"- Kaynak cümlesi eşleşmesi: **{report['source_matching']['matched_claims']}/{report['source_matching']['claims_with_source_sentence']}** ({report['source_matching']['exact_match_rate']:.1%}); bu yalnızca cümlenin kaynak abstract'ta yer aldığını ölçer, anlamsal doğruluğu tek başına kanıtlamaz.",
        f"- Yanlış/unsupported çıkarım bayrakları: **{report['extraction_safety']['false_extraction_count']}/{report['extraction_safety']['claim_denominator']}** ({report['extraction_safety']['false_extraction_rate']:.1%}); kaynak cümlesi, sayısal değer ve metrik türü kontrollerinde başarısız alanlar sayılır.",
        f"- Yanlış nedensellik koruma bayrağı: **{report['extraction_safety']['false_causal_claims']}**.",
        "",
        "## Üç ayrı doğrulama kategorisi",
        "",
        f"1. **Yazılım birim/entegrasyon testleri:** `{software['command']}` — {software['status']}; {software.get('summary') or 'özet alınamadı'}.",
        f"2. **Gerçek PubMed kaynak doğrulaması:** {pubmed['verified_records']}/{pubmed['records_checked']} kayıt PMID ve sağlanan DOI/başlıkla yeniden alındı/eşleşti; **klinik iddialar bağımsız doğrulanmış sayılmaz**.",
        f"3. **Bağımsız klinik veri doğrulaması:** **{clinical['status']}** — {clinical['reason']}.",
        "",
        "## Branş ve tasarım bazında sonuçlar",
        "",
        "| Branş | PMID | Beklenen tasarım | Motor tasarımı | N (referans / motor) | Alan eşleşmesi | Kaynak cümlesi | Nedensellik bayrağı |",
        "|---|---:|---|---|---:|---:|---|---|",
    ]
    for item in report["cases"]:
        n = f"{item.get('expected_total_n')} / {item.get('actual_total_n')}" if item.get("expected_total_n") is not None else "— / belirtilmedi"
        fields = f"{item['reference_fields_matched']}/{item['reference_fields_expected']}"
        source_rate = item.get("source_sentence_exact_match_rate")
        source_text = f"{source_rate:.0%}" if source_rate is not None else "yok"
        causal = "BAYRAK" if item["false_causal_claim_flag"] else "yok"
        lines.append(f"| {item['specialty']} | {item['pmid']} | {item['expected_design']} | {item['actual_design']} | {n} | {fields} | {source_text} | {causal} |")
    lines.extend([
        "",
        "## Yorum ve sınırlar",
        "",
        "Eksiksiz çıkarım, yalnızca referans tablosunda açıkça verilmiş alanların tamamının eşleşmesi olarak tanımlanmıştır; desteklenmeyen alanlar tahminle doldurulmamıştır. Kaynak eşleşme oranı, çıkarılmış değerin doğru klinik yorumlandığını değil, bağlanan kaynak cümlenin PubMed abstract'ında bulunduğunu gösterir. Referans tablosu kısıtlı sayıda makale içerir ve bütün klinik çeşitliliği temsil etmez.",
        "",
        "Nedensellik bayrağı; gözlemsel, tanısal, olgu serisi ve derleme/meta-analiz kayıtlarının model durum alanındaki korumayı kontrol eder. Bu, oluşturulmuş her Türkçe cümlenin bağımsız hekim tarafından doğrulanmış olduğu anlamına gelmez.",
        "",
        f"Model sürümü: `{report['model_version']}`. PubMed referans kaynağı ve her makalenin bağlantısı [önceden belirlenmiş referans tablosunda](pubmed_reference_cases.json) yer alır.",
        "",
    ])
    return "\n".join(lines)


def run() -> Dict[str, Any]:
    references = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    cases = []
    verified = 0
    pubmed_checks = []
    for reference in references["cases"]:
        result = verify_citation({"pmid": reference["pmid"], "doi": reference.get("doi"), "title": reference.get("title")})
        fetched = result.get("fetched_article") or {}
        is_verified = result.get("status") == "verified"
        if is_verified:
            verified += 1
            model = build_study_model(fetched, query=reference["specialty"])
            case_result = compare_case(reference, fetched, model)
        else:
            case_result = {
                "specialty": reference["specialty"], "pmid": reference["pmid"],
                "expected_design": reference["required_design"], "actual_design": None,
                "design_match": False, "expected_total_n": reference.get("total_n"),
                "actual_total_n": None, "total_n_match": False, "arms": [], "outcomes": [],
                "reference_fields_matched": 0, "reference_fields_expected": 0,
                "complete_reference_extraction": False, "source_claim_count": 0,
                "metric_type_check_count": 0,
                "source_sentence_matches": 0, "source_sentence_exact_match_rate": None,
                "unsupported_value_claims": [], "unsupported_metric_type_claims": [],
                "false_causal_claim_flag": False, "model_validation": None,
                "record_verification_status": result.get("status"),
                "study_relationship": None, "evidence_family_id": None,
            }
        case_result["pubmed_verification"] = {
            "status": result.get("status"), "verified": bool(result.get("verified")),
            "pmid": result.get("pmid"), "reason": result.get("reason"),
            "doi_expected": reference.get("doi"),
            "doi_fetched": fetched.get("doi"),
            "title_fetched": fetched.get("title"),
            "pubmed_url": reference.get("pubmed_url"),
        }
        cases.append(case_result)
        pubmed_checks.append(case_result["pubmed_verification"])
        time.sleep(0.4)

    pytest = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True,
        text=True, timeout=900,
    )
    test_text = (pytest.stdout + "\n" + pytest.stderr).strip()
    summary_line = next((line.strip() for line in reversed(test_text.splitlines()) if " passed" in line or " failed" in line), "")

    expected_fields = sum(x["reference_fields_expected"] for x in cases)
    matched_fields = sum(x["reference_fields_matched"] for x in cases)
    source_claims = sum(x["source_claim_count"] for x in cases)
    source_matches = sum(x["source_sentence_matches"] for x in cases)
    source_with_sentence = sum(
        int(round((x.get("source_sentence_exact_match_rate") or 0) * x.get("source_claim_count", 0)))
        for x in cases
    )
    unsupported = sum(len(x.get("unsupported_value_claims") or []) + len(x.get("unsupported_metric_type_claims") or []) for x in cases)
    metric_claim_checks = sum(int(x.get("metric_type_check_count") or 0) for x in cases)
    false_causal = sum(1 for x in cases if x.get("false_causal_claim_flag"))
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION,
        "reference_dataset_version": references.get("dataset_version"),
        "test_categories": {
            "software_unit_integration_tests": {
                "command": "python -m pytest -q", "status": "PASS" if pytest.returncode == 0 else "FAIL",
                "exit_code": pytest.returncode, "summary": summary_line,
            },
            "real_pubmed_source_validation": {
                "records_checked": len(cases), "verified_records": verified,
                "status": "PASS" if verified == len(cases) else "PARTIAL_OR_FAIL",
                "records": pubmed_checks,
            },
            "independent_clinical_data_validation": {
                "status": "NOT_PERFORMED",
                "reason": "Bağımsız hekim değerlendirmeli veri kümesi veya tam metin çıkarımı sağlanmadı; PubMed kayıt kimliği ve özet cümlesi eşleşmesi klinik doğrulama değildir.",
            },
        },
        "reference_comparison": {
            "articles": len(cases),
            "complete_articles": sum(1 for x in cases if x.get("complete_reference_extraction")),
            "expected_fields": expected_fields,
            "matched_fields": matched_fields,
            "field_match_rate": matched_fields / expected_fields if expected_fields else 0.0,
            "complete_article_rate": sum(1 for x in cases if x.get("complete_reference_extraction")) / len(cases) if cases else 0.0,
        },
        "source_matching": {
            "claims_with_source_sentence": source_claims,
            "matched_claims": source_matches,
            "exact_match_rate": source_matches / source_claims if source_claims else 0.0,
        },
        "extraction_safety": {
            "unsupported_claims": unsupported,
            "false_extraction_count": unsupported,
            "claim_denominator": source_claims + metric_claim_checks,
            "unsupported_extraction_rate": unsupported / (source_claims + metric_claim_checks) if source_claims + metric_claim_checks else 0.0,
            "false_extraction_rate": unsupported / (source_claims + metric_claim_checks) if source_claims + metric_claim_checks else 0.0,
            "false_extraction_definition": "Count of claim-level flags where a source sentence is missing/not present in the fetched PubMed abstract, an extracted numeric value is absent from its attached sentence, or a named metric type is absent from that sentence; denominator is sourced value checks plus named metric-type checks.",
            "false_causal_claims": false_causal,
            "causality_rule": "Flag non-randomized designs whose model status does not declare association-only, descriptive/unclear, or review-of-prior-studies.",
        },
        "cases": cases,
    }
    report["report_markdown"] = render_markdown(report)
    JSON_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    MD_OUT.write_text(report["report_markdown"], encoding="utf-8")
    print(report["report_markdown"])
    print(f"\nFull JSON: {JSON_OUT}")
    if pytest.returncode != 0:
        print("\nPytest output (last 80 lines):\n" + "\n".join(test_text.splitlines()[-80:]))
    return report


if __name__ == "__main__":
    run()

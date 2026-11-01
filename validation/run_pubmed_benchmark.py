"""Live PubMed reference comparison using the canonical Study model.

Run from the repository root with:
    python validation/run_pubmed_benchmark.py

This is an abstract-level software/reference benchmark. It is not independent
clinical adjudication, full-text review, a GRADE assessment, or a risk-of-bias
assessment.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "validation" / "pubmed_reference_cases.json"
JSON_OUT = ROOT / "validation" / "pubmed_benchmark_report.json"
MD_OUT = ROOT / "validation" / "pubmed_benchmark_report.md"
sys.path.insert(0, str(ROOT))

import evidence_model as em  # noqa: E402
from pubmed_client import verify_citation  # noqa: E402


_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_METRIC_ALIASES = {
    "HR": ["hazard ratio", "HR"],
    "RR": ["risk ratio", "relative risk", "RR"],
    "OR": ["odds ratio", "OR"],
    "IRR": ["incidence rate ratio", "IRR"],
    "DOR": ["diagnostic odds ratio", "DOR"],
    "sensitivity": ["sensitivity", "sensitivities"],
    "specificity": ["specificity", "specificities"],
    "AUC": ["area under the curve", "AUC", "AUROC"],
    "MD": ["mean difference", "MD"],
    "SMD": ["standardized mean difference", "standardised mean difference", "SMD"],
    "WMD": ["weighted mean difference", "WMD"],
    "RD": ["risk difference", "absolute difference", "difference", "RD"],
    "PPV": ["positive predictive value", "PPV"],
    "NPV": ["negative predictive value", "NPV"],
    "accuracy": ["accuracy"],
    "LR+": ["positive likelihood ratio", "LR+"],
    "LR-": ["negative likelihood ratio", "LR-"],
    "mean_change": ["mean change", "percentage change"],
}
_DESIGN_ALIASES = {
    "systematic_review": {"systematic_review", "systematic_review_and_meta_analysis", "meta_analysis"},
    "meta_analysis": {"meta_analysis", "systematic_review_and_meta_analysis"},
}
_FIELD_GUIDANCE = {
    "outcome_source_sentence": "Bağlı cümleyi yalnızca doğrulanmış abstract metninden al.",
    "outcome_estimate": "Sadece açıkça raporlanan değerleri çıkar; değer uydurma.",
    "outcome_metric": "Etki ölçütlerini birbirinden ayır ve kaynakta adı geçmeyeni adlandırma.",
    "outcome_confidence_interval": "GA'yı yalnızca aynı tahmine bağla.",
    "outcome_p_value": "P değerini yalnızca aynı tahmine bağla.",
    "outcome_event_count": "Olay sayısını aynı sonlanım cümlesinde doğrula.",
    "arm_participant_n": "Tahsis edilmiş kol büyüklüğünü yalnızca açık kol cümlesinden al.",
    "study_total_n": "Çalışma toplamını alt grup/olay paydasından ayır.",
    "study_design": "Tasarımı kaynak metin ve yayın kaydına göre sınıflandır.",
}
_FIELD_PRIORITY = {
    "outcome_source_sentence": "P1 — kaynak bağlantısı",
    "outcome_estimate": "P1 — sonuç değeri",
    "outcome_metric": "P1 — ölçüt türü",
    "outcome_confidence_interval": "P1 — tahmin belirsizliği",
    "outcome_p_value": "P1 — istatistiksel bağlam",
    "outcome_event_count": "P2 — olay sayımı",
    "arm_participant_n": "P2 — kol büyüklüğü",
    "study_total_n": "P2 — çalışma toplamı",
    "study_design": "P2 — tasarım sınıflandırması",
}


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def number_tokens(value: Any) -> List[str]:
    text = str(value or "")
    tokens = re.findall(r"(?<![\d.])[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?", text)
    cleaned = [re.sub(r"[ ,]", "", token) for token in tokens]
    word_pattern = r"\b(?P<tens>twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[-\s]+(?P<unit>one|two|three|four|five|six|seven|eight|nine))?\b|\b(?P<word>" + "|".join(_NUMBER_WORDS) + r")\b"
    for match in re.finditer(word_pattern, text, re.IGNORECASE):
        if match.group("tens"):
            total = _NUMBER_WORDS[match.group("tens").casefold()] + _NUMBER_WORDS.get((match.group("unit") or "").casefold(), 0)
        else:
            total = _NUMBER_WORDS[match.group("word").casefold()]
        cleaned.append(str(total))
    return cleaned


def _number_key(value: Any) -> Optional[str]:
    raw = str(value or "").replace("−", "-").replace(",", "").replace("%", "").strip()
    try:
        return format(Decimal(raw).normalize(), "f")
    except (InvalidOperation, ValueError):
        return None


def numbers_equal(left: Any, right: Any) -> bool:
    left_numbers, right_numbers = number_tokens(left), number_tokens(right)
    return len(left_numbers) == 1 and len(right_numbers) == 1 and _number_key(left_numbers[0]) == _number_key(right_numbers[0])


def sentence_matches(expected: str, actual: str) -> bool:
    """Normalized text containment for alignment; this is not sentence equality."""
    left, right = norm(expected), norm(actual)
    return bool(left and right and (left in right or right in left))


def reference_quote_checks(case: Dict[str, Any], article: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check that each predeclared reference quote is present in the live record."""
    quotes = []
    if case.get("total_n_sentence"):
        quotes.append(("total_n_sentence", case["total_n_sentence"]))
    for index, outcome in enumerate(case.get("outcomes") or []):
        if outcome.get("source_sentence"):
            quotes.append((f"outcomes[{index}].source_sentence", outcome["source_sentence"]))

    checks = []
    for field, quote in quotes:
        location, status = em.verify_sentence_in_source(
            str(quote), article.get("abstract") or "", article.get("title") or ""
        )
        checks.append({
            "field": field,
            "present_in_live_record": status == em.SOURCE_VERIFIED,
            "location": location,
        })
    return checks


_UNSUPPORTED_CAUSAL_LANGUAGE_RE = re.compile(
    r"\b(?:neden\s+ol\w*|sebep\s+ol\w*|yol\s+aç\w*|art(?:ır|tır)\w*|"
    r"azalt\w*|azal\w*|önle\w*|sağla\w*|iyileştir\w*|düşür\w*|yükselt\w*|koru\w*)\b",
    re.IGNORECASE,
)


def has_unsupported_causal_language(claim_text: str, causal_allowed: bool) -> bool:
    """Phrase-scan a rendered claim; this is not clinical or semantic adjudication."""
    return bool(not causal_allowed and _UNSUPPORTED_CAUSAL_LANGUAGE_RE.search(claim_text or ""))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_run_provenance() -> Dict[str, Any]:
    try:
        git_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git_head = None
    return {
        "command": "python validation/run_pubmed_benchmark.py",
        "python_version": platform.python_version(),
        "git_head_at_run": git_head,
        "runner_sha256": _sha256_file(Path(__file__).resolve()),
        "reference_data_sha256": _sha256_file(REFERENCE_PATH),
        "live_source": "NCBI PubMed E-utilities through pubmed_client.verify_citation",
    }


def metric_aliases(metric: str) -> List[str]:
    return _METRIC_ALIASES.get(metric, [metric.replace("_", " ")])


def _metric_occurs(measure: str, sentence: str) -> bool:
    if measure in {"proportion", "unnamed", "not_named_in_source", "mean_change"}:
        if measure == "mean_change":
            aliases = metric_aliases(measure)
        else:
            return True
    else:
        aliases = metric_aliases(measure)
    for alias in aliases:
        if alias.isupper() or alias in {"LR+", "LR-"}:
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", sentence):
                return True
        elif re.search(rf"\b{re.escape(alias)}\b", sentence, re.IGNORECASE):
            return True
    return False


def _matching_estimates(outcome: Dict[str, Any], study: em.Study) -> List[em.EffectEstimate]:
    expected_sentence = str(outcome.get("source_sentence") or "")
    if not expected_sentence:
        return []
    return [estimate for estimate in study.estimates if sentence_matches(expected_sentence, estimate.source.sentence)]


def _matching_unstructured_findings(outcome: Dict[str, Any], study: em.Study) -> List[Dict[str, Any]]:
    expected_sentence = str(outcome.get("source_sentence") or "")
    if not expected_sentence:
        return []
    return [
        item for item in study.other_numeric_findings
        if isinstance(item.get("source"), em.EvidenceSource)
        and sentence_matches(expected_sentence, item["source"].sentence)
    ]


def _text_contains_expected_value(expected_value: Any, text: str) -> bool:
    expected = number_tokens(expected_value)
    if not expected:
        return bool(norm(expected_value) and norm(expected_value) in norm(text))
    actual = {_number_key(token) for token in number_tokens(text)}
    return all(_number_key(token) in actual for token in expected)


def _unstructured_metric_matches(metric: str, finding: Dict[str, Any]) -> bool:
    source = finding["source"].sentence
    metrics_text = " ".join(str(item) for item in finding.get("metrics") or [])
    combined = f"{finding.get('outcome', '')} {metrics_text} {source}"
    if metric == "prevalence":
        return "prevalence" in norm(combined)
    if metric == "proportion":
        return "%" in metrics_text or "%" in source
    if metric == "qualitative association":
        return "more likely" in norm(metrics_text) and "times" in norm(metrics_text)
    if metric == "likelihood ratio":
        return "likelihood ratio" in norm(source)
    return False


def expected_outcome_match(outcome: Dict[str, Any], study: em.Study) -> Dict[str, Any]:
    candidates = _matching_estimates(outcome, study)
    unstructured = _matching_unstructured_findings(outcome, study)
    metric = str(outcome.get("metric") or "")
    expected_value = outcome.get("estimate")
    expected_numbers = number_tokens(expected_value)
    estimate_match = False
    metric_match = False
    matched_estimate: Optional[em.EffectEstimate] = None

    if metric == "prevalence" and len(expected_numbers) > 1:
        # A stated prevalence range is not a confidence interval. Match only if
        # the canonical model actually extracted the range as its value text.
        matched_estimate = next(
            (item for item in candidates if norm(item.value_text) == norm(expected_value)), None
        )
        estimate_match = matched_estimate is not None
        metric_match = bool(matched_estimate and item_metric_matches(matched_estimate, metric))
    elif metric == "likelihood ratio" and len(expected_numbers) > 1:
        matched_values = [
            [item for item in candidates if item.measure in {"LR+", "LR-", "unnamed"} and numbers_equal(item.value, expected)]
            for expected in expected_numbers
        ]
        estimate_match = all(matched_values)
        metric_match = estimate_match and all(any(item_metric_matches(item, metric) for item in group) for group in matched_values)
    elif len(expected_numbers) == 1:
        matching_values = [item for item in candidates if numbers_equal(item.value, expected_value)]
        estimate_match = bool(matching_values)
        matched_estimate = next((item for item in matching_values if item_metric_matches(item, metric)), None)
        metric_match = matched_estimate is not None

    if not estimate_match and metric in {"proportion", "prevalence"} and len(expected_numbers) == 1:
        event_matches = [
            count for count in study.event_counts
            if count.percent is not None
            and sentence_matches(outcome.get("source_sentence", ""), count.source.sentence)
            and numbers_equal(count.percent, expected_value)
        ]
        if event_matches:
            estimate_match = True
            metric_match = True
    if not estimate_match:
        for finding in unstructured:
            metrics_text = " ".join(str(item) for item in finding.get("metrics") or [])
            if _text_contains_expected_value(expected_value, metrics_text) and _unstructured_metric_matches(metric, finding):
                estimate_match = True
                metric_match = True
                break

    ci_match: Optional[bool] = None
    ci = outcome.get("ci")
    if ci is not None:
        ci_match = bool(
            matched_estimate
            and len(ci) == 2
            and numbers_equal(matched_estimate.ci_low, ci[0])
            and numbers_equal(matched_estimate.ci_high, ci[1])
        )
    p_match: Optional[bool] = None
    if outcome.get("p") is not None:
        expected_p = re.sub(r"\s+", "", str(outcome["p"])).casefold().removeprefix("p")
        actual_p = re.sub(r"\s+", "", str((matched_estimate or em.EffectEstimate("", "", "", None, "")).p_value)).casefold().removeprefix("p")
        p_match = bool(matched_estimate and actual_p == expected_p)

    source_match = (
        any(sentence_matches(outcome.get("source_sentence", ""), item.source.sentence) for item in candidates)
        or any(sentence_matches(outcome.get("source_sentence", ""), item["source"].sentence) for item in unstructured)
        or any(sentence_matches(outcome.get("source_sentence", ""), item.source.sentence) for item in study.event_counts)
    )
    return {
        "source_sentence_matched": source_match,
        "estimate_matched": estimate_match,
        "metric_matched": metric_match,
        "ci_matched": ci_match,
        "p_matched": p_match,
        "matched_estimate": matched_estimate,
    }


def item_metric_matches(estimate: em.EffectEstimate, expected_metric: str) -> bool:
    if expected_metric in {"proportion", "prevalence"}:
        return estimate.family == "proportion" or estimate.measure == "proportion"
    if expected_metric == "qualitative association":
        return estimate.measure == "unnamed"
    if expected_metric == "likelihood ratio":
        return estimate.measure in {"LR+", "LR-", "unnamed"}
    aliases = metric_aliases(expected_metric)
    return estimate.measure in aliases


def _add_field(checks: List[Dict[str, Any]], category: str, field: str, matched: bool) -> None:
    checks.append({"category": category, "field": field, "matched": bool(matched)})


def _event_values_for_sentence(study: em.Study, expected_sentence: str) -> List[int]:
    return [
        count.events
        for count in study.event_counts
        if sentence_matches(expected_sentence, count.source.sentence)
    ]


def compare_case(case: Dict[str, Any], article: Dict[str, Any], study: em.Study) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    quote_checks = reference_quote_checks(case, article)
    expected_n = case.get("total_n")
    actual_n = study.population.n_total
    if expected_n is not None:
        _add_field(checks, "study_total_n", "total_n", actual_n == expected_n)

    arm_results = []
    for arm in case.get("arms") or []:
        expected_arm_n = arm.get("participants_n")
        if expected_arm_n is None:
            continue
        label = norm(arm.get("label")).replace("plasebo", "placebo")
        model_arms = [
            item for item in study.arms
            if label and (label in norm(item.label).replace("plasebo", "placebo")
                          or norm(item.label).replace("plasebo", "placebo") in label)
        ]
        matched = any(item.n == expected_arm_n for item in model_arms)
        _add_field(checks, "arm_participant_n", f"arm_n:{arm.get('label')}", matched)
        arm_results.append({"label": arm.get("label"), "expected_n": expected_arm_n, "matched": matched})

    outcome_results = []
    for index, expected in enumerate(case.get("outcomes") or [], 1):
        matched = expected_outcome_match(expected, study)
        outcome_checks = []
        if expected.get("estimate") is not None:
            outcome_checks.extend([
                ("outcome_source_sentence", matched["source_sentence_matched"]),
                ("outcome_estimate", matched["estimate_matched"]),
                ("outcome_metric", matched["metric_matched"]),
            ])
        if expected.get("ci") is not None:
            outcome_checks.append(("outcome_confidence_interval", bool(matched["ci_matched"])))
        if expected.get("p") is not None:
            outcome_checks.append(("outcome_p_value", bool(matched["p_matched"])))
        raw_counts = expected.get("event_count")
        expected_counts = raw_counts if isinstance(raw_counts, list) else ([raw_counts] if raw_counts is not None else [])
        actual_event_values = _event_values_for_sentence(study, expected.get("source_sentence", ""))
        event_matches = []
        for count in expected_counts:
            event_ok = count in actual_event_values
            outcome_checks.append(("outcome_event_count", event_ok))
            event_matches.append(event_ok)
        for category, value in outcome_checks:
            _add_field(checks, category, f"outcome:{index}:{category}", value)
        outcome_results.append({
            "outcome": expected.get("outcome"),
            "reference_metric": expected.get("metric"),
            "reference_estimate": expected.get("estimate"),
            "source_sentence_matched": matched["source_sentence_matched"],
            "estimate_matched": matched["estimate_matched"],
            "metric_matched": matched["metric_matched"],
            "ci_matched": matched["ci_matched"],
            "p_matched": matched["p_matched"],
            "event_counts_matched": event_matches,
        })

    expected_design = case.get("required_design")
    actual_design = study.design_key
    design_match = actual_design == expected_design or actual_design in _DESIGN_ALIASES.get(expected_design, set())
    _add_field(checks, "study_design", "study_design", design_match)

    sourced_claims = list(em.iter_sourced_claims(study))
    source_sentence_matches = 0
    unsupported_values: List[str] = []
    for path, value, source in sourced_claims:
        sentence = source.sentence or ""
        in_article = em.verify_sentence_in_source(sentence, article.get("abstract") or "", article.get("title") or "")[1] == em.SOURCE_VERIFIED
        if sentence and in_article:
            source_sentence_matches += 1
        else:
            unsupported_values.append(path)
            continue
        if source.verification_status != em.SOURCE_DERIVED:
            values = value if isinstance(value, (list, tuple)) else [value]
            source_numbers = {_number_key(token) for token in number_tokens(sentence)}
            for item in values:
                if isinstance(item, (int, float, str)):
                    value_numbers = number_tokens(item)
                    if value_numbers and any(_number_key(token) not in source_numbers for token in value_numbers):
                        unsupported_values.append(path)
                        break

    unsupported_metric_types = []
    for outcome_index, outcome in enumerate(study.outcomes):
        for estimate_index, estimate in enumerate(outcome.estimates):
            if estimate.measure in {"proportion", "unnamed"}:
                continue
            if not _metric_occurs(estimate.measure, estimate.source.sentence):
                unsupported_metric_types.append(f"outcomes[{outcome_index}].estimates[{estimate_index}]:{estimate.measure}")

    causal_allowed_by_design = (
        study.claim_type == "pooled_randomized"
        or (study.claim_type == "causal_effect" and study.design_key in {"rct", "clinical_trial"})
    )
    rendered_claims = [
        (f"outcomes[{outcome_index}].estimates[{estimate_index}]", em.claim_sentence_tr(study, estimate))
        for outcome_index, outcome in enumerate(study.outcomes)
        for estimate_index, estimate in enumerate(outcome.estimates)
        if estimate.usable or estimate.validation == "eksik"
    ]
    unsupported_causal_language = [
        path for path, text in rendered_claims
        if has_unsupported_causal_language(text, causal_allowed_by_design)
    ]
    causal_metadata_mismatch = bool(study.causal_inference_allowed) != causal_allowed_by_design
    model_validation = em.validate_study(study, article)
    return {
        "specialty": case["specialty"],
        "pmid": case["pmid"],
        "expected_design": expected_design,
        "actual_design": actual_design,
        "design_match": design_match,
        "expected_total_n": expected_n,
        "actual_total_n": actual_n,
        "total_n_match": None if expected_n is None else actual_n == expected_n,
        "arms": arm_results,
        "non_arm_groups_not_scored": list(case.get("non_arm_groups") or []),
        "outcomes": outcome_results,
        "reference_fields_matched": sum(1 for check in checks if check["matched"]),
        "reference_fields_expected": len(checks),
        "reference_field_checks": checks,
        "complete_reference_extraction": bool(checks) and all(check["matched"] for check in checks),
        "reference_quote_checks": quote_checks,
        "source_claim_count": len(sourced_claims),
        "metric_type_check_count": sum(
            1 for outcome in study.outcomes for estimate in outcome.estimates
            if estimate.measure not in {"proportion", "unnamed"}
        ),
        "source_sentence_matches": source_sentence_matches,
        "source_text_presence_rate": source_sentence_matches / len(sourced_claims) if sourced_claims else None,
        "unsupported_value_claims": sorted(set(unsupported_values)),
        "unsupported_metric_type_claims": unsupported_metric_types,
        "rendered_claims_checked": len(rendered_claims),
        "unsupported_causal_language_claims": unsupported_causal_language,
        "causal_metadata_mismatch": causal_metadata_mismatch,
        "model_validation": model_validation,
        "record_verification_status": study.citation_status,
        "study_relationship": study.report_role,
    }


def summarize_field_gaps(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, Dict[str, int]] = {}
    for case in cases:
        for check in case.get("reference_field_checks") or []:
            bucket = counts.setdefault(check["category"], {"expected": 0, "matched": 0})
            bucket["expected"] += 1
            bucket["matched"] += int(bool(check["matched"]))
    gaps = []
    for category, values in counts.items():
        unmatched = values["expected"] - values["matched"]
        if unmatched:
            gaps.append({
                "category": category,
                "expected": values["expected"],
                "matched": values["matched"],
                "unmatched": unmatched,
                "priority": _FIELD_PRIORITY.get(category, "P2 — diğer alan"),
                "next_step": _FIELD_GUIDANCE.get(category, "Alanı kaynak cümlesiyle ayrı ayrı incele."),
            })
    return sorted(gaps, key=lambda item: (0 if item["priority"].startswith("P1") else 1, -item["unmatched"], item["category"]))


def summarize_safety_checks(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    evaluated = [item for item in cases if item.get("record_verification_status") == "verified"]
    source_claims = sum(item.get("source_claim_count", 0) for item in evaluated)
    metric_checks = sum(item.get("metric_type_check_count", 0) for item in evaluated)
    unsupported_values = sum(len(item.get("unsupported_value_claims") or []) for item in evaluated)
    unsupported_metrics = sum(len(item.get("unsupported_metric_type_claims") or []) for item in evaluated)
    claim_denominator = source_claims + metric_checks
    causal_claims_checked = sum(item.get("rendered_claims_checked") or 0 for item in evaluated)
    causal_violations = sum(len(item.get("unsupported_causal_language_claims") or []) for item in evaluated)
    causal_metadata_mismatches = sum(bool(item.get("causal_metadata_mismatch")) for item in evaluated)
    status = "NOT_EVALUATED" if not evaluated or not claim_denominator else (
        "PASS" if unsupported_values + unsupported_metrics == 0 else "PARTIAL_OR_FAIL"
    )
    causal_status = "NOT_EVALUATED" if not causal_claims_checked else (
        "PASS" if causal_violations == 0 and causal_metadata_mismatches == 0 else "PARTIAL_OR_FAIL"
    )
    return {
        "status": status,
        "evaluated_records": len(evaluated),
        "not_evaluated_records": len(cases) - len(evaluated),
        "unsupported_claims": unsupported_values + unsupported_metrics,
        "unsupported_value_claims": unsupported_values,
        "unsupported_metric_type_claims": unsupported_metrics,
        "claim_denominator": claim_denominator,
        "unsupported_rate": (unsupported_values + unsupported_metrics) / claim_denominator if claim_denominator else None,
        "causal_language_status": causal_status,
        "rendered_causal_claims_checked": causal_claims_checked,
        "unsupported_causal_language_claims": causal_violations,
        "causal_metadata_mismatches": causal_metadata_mismatches,
        "causal_language_violation_rate": causal_violations / causal_claims_checked if causal_claims_checked else None,
        "interpretation": (
            "Software/source-string checks only. The causal phrase scan covers rendered canonical claim sentences; "
            "it is not semantic or independent clinical adjudication."
        ),
    }


def _empty_case_result(case: Dict[str, Any], status: str) -> Dict[str, Any]:
    return {
        "specialty": case["specialty"], "pmid": case["pmid"],
        "expected_design": case.get("required_design"), "actual_design": None,
        "design_match": False, "expected_total_n": case.get("total_n"),
        "actual_total_n": None, "total_n_match": False, "arms": [], "outcomes": [],
        "non_arm_groups_not_scored": list(case.get("non_arm_groups") or []),
        "reference_fields_matched": 0, "reference_fields_expected": 0,
        "reference_field_checks": [], "complete_reference_extraction": False,
        "reference_quote_checks": None,
        "source_claim_count": 0, "metric_type_check_count": 0,
        "source_sentence_matches": 0, "source_text_presence_rate": None,
        "unsupported_value_claims": [], "unsupported_metric_type_claims": [],
        "rendered_claims_checked": None, "unsupported_causal_language_claims": None,
        "causal_metadata_mismatch": None, "model_validation": None,
        "record_verification_status": status, "study_relationship": None,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    identity = report["pubmed_identity_validation"]
    reference = report["reference_comparison"]
    sources = report["source_sentence_checks"]
    safety = report["extraction_safety_checks"]
    quote_provenance = report["reference_quote_provenance"]
    source_summary = (
        f"{sources['matched_claims']}/{sources['claims_checked']} ({sources['text_presence_rate']:.1%})"
        if sources["text_presence_rate"] is not None else "değerlendirilemedi"
    )
    unsupported_summary = (
        f"{safety['unsupported_claims']}/{safety['claim_denominator']}"
        if safety["claim_denominator"] else "değerlendirilemedi"
    )
    causal_summary = (
        f"{safety['unsupported_causal_language_claims']}/{safety['rendered_causal_claims_checked']}"
        if safety["rendered_causal_claims_checked"] else "değerlendirilemedi"
    )
    field_summary = (
        f"{reference['matched_fields']}/{reference['expected_fields']} ({reference['field_match_rate']:.1%})"
        if reference["field_match_rate"] is not None else "değerlendirilemedi"
    )
    complete_summary = (
        f"{reference['complete_articles']}/{reference['records_evaluated']}"
        if reference["records_evaluated"] else "değerlendirilemedi"
    )
    quote_summary = (
        f"{quote_provenance['matched_quotes']}/{quote_provenance['expected_quotes']}"
        if quote_provenance["expected_quotes"] else "değerlendirilemedi"
    )
    lines = [
        "# Çok Branşlı PubMed Kaynaklı Alan Benchmark Raporu",
        "",
        "Bu rapor, sekiz önceden belirlenmiş PubMed kaydında abstract düzeyindeki yazılım çıkarımını kaynak cümleleri ve referans alanlarıyla karşılaştırır. Bu çalışma bağımsız klinik adjudikasyon, tam metin incelemesi, GRADE veya yanlılık riski değerlendirmesi değildir.",
        "",
        "## Sonuç özeti",
        "",
        f"- Yeniden alınarak PMID/başlık/DOI ile doğrulanan kayıt: **{identity['verified_records']}/{identity['records_checked']}**.",
        f"- Önceden belirlenmiş referans alanı eşleşmesi: **{field_summary}**.",
        f"- Eksiksiz referans alanı: **{complete_summary}**.",
        f"- Önceden belirlenmiş kaynak alıntısı metninin canlı PubMed kaydında bulunması: **{quote_summary}**.",
        f"- Model alanlarının kaynak metninin canlı abstract/başlık içinde bulunması: **{source_summary}**; bu tam cümle eşitliği veya klinik doğruluk değildir.",
        f"- Desteklenmeyen değer/metrik kaynak dizesi kontrolleri: **{unsupported_summary}**.",
        f"- Kanonik renderer’ın yapılandırılmış iddia cümlelerinde phrase-scan ile desteklenmeyen nedensel dil: **{causal_summary}**.",
        "",
        "## Referans alanı boşlukları",
        "",
        "Aşağıdaki öncelik, yalnızca sınırlı benchmark referansındaki eşleşmeyen alan sayısını gösterir; klinik risk veya klinik adjudikasyon sıralaması değildir.",
    ]
    gaps = reference.get("field_gap_priorities") or []
    if gaps:
        for index, gap in enumerate(gaps, 1):
            lines.append(f"{index}. **{gap['priority']} — {gap['category']}: {gap['matched']}/{gap['expected']} eşleşti, {gap['unmatched']} eksik.** {gap['next_step']}")
    else:
        lines.append("- Bu sınırlı referans kümesinde eşleşmeyen alan yok.")
    lines.extend([
        "",
        "## Kayıt bazında sonuçlar",
        "",
        "| Branş | PMID | Tasarım (beklenen / model) | N (beklenen / model) | Alan eşleşmesi | Kaynak metni | Model alan kontrolü |",
        "|---|---:|---|---:|---:|---:|---|",
    ])
    for case in report["cases"]:
        total = f"{case.get('expected_total_n')} / {case.get('actual_total_n')}" if case.get("expected_total_n") is not None else "— / belirtilmedi"
        model_status = (case.get("model_validation") or {}).get("status", "kayıt alınamadı")
        source_text = (
            f"{case.get('source_sentence_matches', 0)}/{case.get('source_claim_count', 0)}"
            if case.get("record_verification_status") == "verified" else "değerlendirilmedi"
        )
        lines.append(
            f"| {case['specialty']} | {case['pmid']} | {case.get('expected_design')} / {case.get('actual_design')} | {total} | "
            f"{case['reference_fields_matched']}/{case['reference_fields_expected']} | "
            f"{source_text} | {model_status} |"
        )
    lines.extend([
        "",
        "## Doğrulama sınırları",
        "",
        "PubMed kimlik kontrolü kaynak kaydının yeniden bulunması ve verilen kimlik alanlarının eşleşmesi içindir. Kaynak metni kontrolü normalize edilmiş alıntı metninin canlı abstract/başlık içinde yer almasını denetler; tam cümle eşitliği veya alanın klinik anlamda doğru yorumlandığını kanıtlamaz. Nedensel dil phrase-scan’i yalnızca kanonik renderer’ın yapılandırılmış iddia cümlelerini tarar; semantik veya hekim değerlendirmesi değildir. Benchmark referans kümesi sınırlıdır ve bütün klinik çeşitliliği temsil etmez.",
        "",
        "Bağımsız klinik doğrulama: **YAPILMADI**. GRADE ve yanlılık riski: **değerlendirilmedi**.",
        f"",
        f"Kanonik model sürümü: `{report['model_version']}`. Referans verisi: `pubmed_reference_cases.json` (sürüm {report['reference_dataset_version']}).",
        "",
        "## Çalıştırma izi",
        "",
        f"UTC zamanı: `{report['generated_at_utc']}`; Python: `{report['run_provenance']['python_version']}`; çalıştırıcı SHA-256: `{report['run_provenance']['runner_sha256']}`; referans verisi SHA-256: `{report['run_provenance']['reference_data_sha256']}`; çalıştırma anındaki Git HEAD: `{report['run_provenance']['git_head_at_run'] or 'bilinmiyor'}`.",
        f"Canlı abstract SHA-256 özeti her doğrulanan kayıt için JSON raporunda saklanır. Kimliği doğrulanamayan kayıtlar bu metriklerin paydasına dahil edilmez; değerlendirilmedikleri ayrıca sayılır.",
        "",
    ])
    return "\n".join(lines)


def run() -> Dict[str, Any]:
    references = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    results: List[Dict[str, Any]] = []
    pubmed_checks = []
    verified = 0

    for reference in references["cases"]:
        result = verify_citation({
            "pmid": reference["pmid"],
            "doi": reference.get("doi"),
            "title": reference.get("title"),
        })
        fetched = result.get("fetched_article") or {}
        is_verified = result.get("status") == "verified"
        if is_verified:
            verified += 1
            fetched["_citation_status"] = "verified"
            study = em.build_study(fetched, query=reference["specialty"])
            case_result = compare_case(reference, fetched, study)
        else:
            case_result = _empty_case_result(reference, str(result.get("status") or "unverified"))
        case_result["pubmed_verification"] = {
            "status": result.get("status"),
            "verified": bool(result.get("verified")),
            "pmid": result.get("pmid"),
            "reason": result.get("reason"),
            "doi_expected": reference.get("doi"),
            "doi_fetched": fetched.get("doi"),
            "title_fetched": fetched.get("title"),
            "abstract_sha256": hashlib.sha256(str(fetched.get("abstract") or "").encode("utf-8")).hexdigest()
            if fetched.get("abstract") else None,
            "pubmed_url": reference.get("pubmed_url"),
        }
        results.append(case_result)
        pubmed_checks.append(case_result["pubmed_verification"])
        time.sleep(0.4)

    verified_results = [item for item in results if item.get("record_verification_status") == "verified"]
    expected_fields = sum(item["reference_fields_expected"] for item in verified_results)
    matched_fields = sum(item["reference_fields_matched"] for item in verified_results)
    claims_checked = sum(item["source_claim_count"] for item in verified_results)
    claims_matched = sum(item["source_sentence_matches"] for item in verified_results)
    quote_checks = [check for item in verified_results for check in (item.get("reference_quote_checks") or [])]
    matched_quotes = sum(bool(check["present_in_live_record"]) for check in quote_checks)
    valid_models = sum(bool((item.get("model_validation") or {}).get("valid")) for item in verified_results)
    safety = summarize_safety_checks(results)
    complete_articles = sum(bool(item["complete_reference_extraction"]) for item in verified_results)
    field_match_rate = matched_fields / expected_fields if expected_fields else None
    complete_article_rate = complete_articles / len(verified_results) if verified_results else None
    quote_status = "NOT_EVALUATED" if not quote_checks else (
        "PASS" if matched_quotes == len(quote_checks) else "PARTIAL_OR_FAIL"
    )
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_provenance": build_run_provenance(),
        "model_version": em.EVIDENCE_MODEL_VERSION,
        "reference_dataset_version": references.get("dataset_version"),
        "pubmed_identity_validation": {
            "records_checked": len(results),
            "verified_records": verified,
            "status": "PASS" if verified == len(results) else "PARTIAL_OR_FAIL",
            "records": pubmed_checks,
        },
        "canonical_model_validation": {
            "records_checked": len(verified_results),
            "structurally_valid_records": valid_models,
            "status": "NOT_EVALUATED" if not verified_results else (
                "PASS" if valid_models == len(verified_results) else "PARTIAL_OR_FAIL"
            ),
            "independent_clinical_validation": "NOT_PERFORMED",
            "formal_grade_status": "NOT_ASSESSED",
        },
        "reference_comparison": {
            "articles": len(results),
            "records_evaluated": len(verified_results),
            "records_not_evaluated": len(results) - len(verified_results),
            "complete_articles": complete_articles,
            "expected_fields": expected_fields,
            "matched_fields": matched_fields,
            "field_match_rate": field_match_rate,
            "complete_article_rate": complete_article_rate,
            "field_gap_priorities": summarize_field_gaps(results),
        },
        "reference_quote_provenance": {
            "status": quote_status,
            "records_evaluated": len(verified_results),
            "records_not_evaluated": len(results) - len(verified_results),
            "expected_quotes": len(quote_checks),
            "matched_quotes": matched_quotes,
        },
        "source_sentence_checks": {
            "claims_checked": claims_checked,
            "matched_claims": claims_matched,
            "text_presence_rate": claims_matched / claims_checked if claims_checked else None,
            "records_evaluated": len(verified_results),
            "records_not_evaluated": len(results) - len(verified_results),
        },
        "extraction_safety_checks": safety,
        "independent_clinical_adjudication": {
            "status": "NOT_PERFORMED",
            "reason": "PMID/DOI/title and abstract source-sentence checks do not establish clinical correctness.",
        },
        "cases": results,
    }
    report["report_markdown"] = render_markdown(report)
    JSON_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    MD_OUT.write_text(report["report_markdown"], encoding="utf-8")
    print(report["report_markdown"])
    print(f"\nFull JSON: {JSON_OUT}")
    return report


if __name__ == "__main__":
    run()

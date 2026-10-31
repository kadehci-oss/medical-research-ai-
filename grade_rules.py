"""Safer rules for the preliminary GRADE estimate (fix for finding B3).

Rules used by the patched ``_risk_of_bias``, ``_imprecision`` and
``_apply_ceiling`` in grade_assessment.py. The patched functions keep the
module's own negation handling (``_first_unnegated_match``) and call into
this file only for the new rules. Return shapes match the originals
(``{"status", "reason"}`` for domains; ``preliminary_level``,
``applied_downgrades``, ``reason`` for the ceiling), so callers do not change.

What changed and why
--------------------
* If risk of bias or imprecision could not be assessed from the abstract, no
  certainty level is assigned. The result is "değerlendirilemedi" plus an
  ``upper_bound_level``. Before, unassessed domains lowered nothing, so an
  RCT abstract with no methods text came out as "Yüksek".
* Imprecision: for a ratio measure (HR/OR/RR), a confidence interval that
  crosses 1 is flagged. The old rule only looked at upper/lower >= 3, so
  0.62-1.15 passed. A ratio measure must be named in the text; the scale is
  never assumed.
* "double-blind" alone no longer means "no risk of bias concern".

The phrase lists are copied from the original module so wording-based
behaviour stays the same. This is still a rule-based, abstract-only estimate
and not a GRADE assessment. Keep the disclaimer in the report.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

import stat_direction as sd

NOT_ASSESSABLE = "değerlendirilemedi"
SERIOUS = "ciddi düşürme"
NO_DOWNGRADE = "düşürme yok"

LEVEL_BY_SCORE = {4: "Yüksek", 3: "Orta", 2: "Düşük", 1: "Çok düşük"}

CRITICAL_DOMAINS = ("risk_of_bias", "imprecision")
SPREAD_RATIO = 3.0

_ROB_DOWNGRADE_RE = re.compile(
    r"\b(high risk of bias|serious risk of bias|open-label|open label|unblinded|lack of blinding|"
    r"without blinding|allocation was not concealed|high attrition|substantial loss to follow-up|"
    r"yuksek yanlilik riski|acik etiket)\b",
    re.IGNORECASE,
)
ROB_LOW_RE = re.compile(r"\b(low risk of bias)\b", re.IGNORECASE)
BLINDING_RE = re.compile(r"\b(double-blind|double blind|triple-blind)\b", re.IGNORECASE)
_ROB_LOW_RE = ROB_LOW_RE
_BLINDING_RE = BLINDING_RE
_IMPRECISION_RE = re.compile(
    r"\b(underpowered|wide confidence interval|imprecise estimate|lack of precision|"
    r"guc yetersiz|genis guven araligi)\b",
    re.IGNORECASE,
)


def _domain(status: str, reason: str) -> Dict[str, str]:
    return {"status": status, "reason": reason}


def risk_of_bias(abstract: str) -> Dict[str, str]:
    match = _ROB_DOWNGRADE_RE.search(abstract or "")
    if match:
        return _domain(SERIOUS, f"Özette yanlılık ifadesi var: '{match.group(0)}'.")
    if _ROB_LOW_RE.search(abstract or ""):
        return _domain(
            NO_DOWNGRADE, "Özet düşük yanlılık riski belirtiyor. Tam metin RoB 2 uygulanmadı."
        )
    if _BLINDING_RE.search(abstract or ""):
        return _domain(
            NOT_ASSESSABLE,
            "Özet çift-kör tasarım belirtiyor; bu tek başına düşük yanlılık riski anlamına gelmez. "
            "RoB 2 uygulanmadı.",
        )
    return _domain(NOT_ASSESSABLE, "Özet, RoB 2 veya ROBINS-I için yeterli yöntem ayrıntısı vermiyor.")


def imprecision_from_ci(text: str, ci_strings: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """Imprecision judged from the confidence interval only.

    ``ci_strings`` are strings already known to be confidence intervals.
    A ratio measure (HR/OR/RR) must be named in the text; the scale is never
    assumed. A ratio CI that crosses 1 is serious imprecision.
    """
    text = text or ""
    ci_list = [s for s in (ci_strings or []) if isinstance(s, str)]
    blob = " ".join([text] + ci_list)
    ci = sd.parse_ci_strings(ci_list) or sd.parse_ci(blob)
    if not ci:
        return _domain(NOT_ASSESSABLE, "Özette güven aralığı veya açık imprecision ifadesi yok.")
    if not sd.parse_ratio(blob):
        return _domain(
            NOT_ASSESSABLE,
            "Oran ölçütü (HR/OR/RR) belirtilmedi; aralık bir oran gibi yorumlanmadı, ölçek varsayılmadı.",
        )
    low, high = ci
    if low <= 0:
        return _domain(NOT_ASSESSABLE, "Oran ölçütü için geçersiz güven aralığı; ölçek varsayılmadı.")
    if low <= 1.0 <= high:
        return _domain(SERIOUS, f"Özetteki aralık {low:g}-{high:g} etkisizlik değerini (1) kesiyor.")
    if high / low >= SPREAD_RATIO:
        return _domain(
            SERIOUS,
            f"Özetteki aralık {low:g}-{high:g}; üst/alt oranı {high / low:.2f} (≥3 kural eşiği).",
        )
    return _domain(
        NO_DOWNGRADE,
        f"Özetteki aralık {low:g}-{high:g}; 1'i kesmiyor, üst/alt oranı 3 eşiğinin altında.",
    )


def imprecision(text: str, ci_strings: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """Phrase check, then the CI rule (standalone use; no negation handling)."""
    match = _IMPRECISION_RE.search(text or "")
    if match:
        return _domain(SERIOUS, f"Özet imprecision belirtiyor: '{match.group(0)}'.")
    return imprecision_from_ci(text, ci_strings)


def apply_ceiling(start_score: Optional[int], domains: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """Combine the starting score and domains into the outcome level.

    If a critical domain is not assessable, ``preliminary_level`` is
    "değerlendirilemedi" and ``upper_bound_level`` carries the best case.
    """
    if start_score is None:
        return {
            "preliminary_level": NOT_ASSESSABLE,
            "upper_bound_level": NOT_ASSESSABLE,
            "applied_downgrades": 0,
            "reason": "Başlangıç düzeyi değerlendirilemediği için sayısal tavan üretilmedi.",
        }
    downgrades = sum(1 for d in domains.values() if d.get("status") == SERIOUS)
    upper = LEVEL_BY_SCORE[max(1, start_score - downgrades)]
    missing: List[str] = [
        name for name in CRITICAL_DOMAINS if domains.get(name, {}).get("status") == NOT_ASSESSABLE
    ]
    if missing:
        return {
            "preliminary_level": NOT_ASSESSABLE,
            "upper_bound_level": upper,
            "applied_downgrades": downgrades,
            "reason": (
                "Özetten değerlendirilemeyen kritik alan(lar): "
                + ", ".join(missing)
                + f". Kesinlik düzeyi atanmadı; en iyi durumda üst sınır: {upper}."
            ),
        }
    return {
        "preliminary_level": upper,
        "upper_bound_level": upper,
        "applied_downgrades": downgrades,
        "reason": "Yalnızca özette desteklenen ciddi düşürmeler başlangıçtan çıkarıldı.",
    }

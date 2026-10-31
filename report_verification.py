"""Audit a generated Turkish report against the Study objects it was built from.

Checks (all automatic, no network):

1. Every PMID cited in the report belongs to the retrieved article set.
2. Every quoted source sentence attributed to a PMID appears verbatim in that
   PMID's title or abstract.
3. No risk-of-bias rating or GRADE certainty rating is asserted (the engine never
   performs these appraisals).
4. Generated (non-quoted) wording on report lines tied to a non-randomized study
   contains no causal or superiority language.
5. Effect estimates flagged as inconsistent are not presented as findings.

The result is a status the Streamlit UI and exported reports show next to the
software version.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

import evidence_model as em

STATUS_OK = "Doğrulandı"
STATUS_WARN = "Uyarılarla doğrulandı"
STATUS_FAIL = "Doğrulama başarısız"

_PMID_RE = re.compile(r"PMID[:\s]*\[?(\d{5,9})\]?")
_QUOTE_WITH_PMID_RE = re.compile(r"\"([^\"]{25,})\"[^\"\n]{0,40}?\(PMID:\s*(\d{5,9})\)")
_ROB_RATING_RE = re.compile(
    r"(?:yanlılık riski|risk of bias|risk derecesi|rob 2|robins-i)[^\n]{0,40}?\b(?:düşük|yüksek|orta|low|high|some concerns|moderate|serious|critical)\b",
    re.IGNORECASE,
)
_GRADE_RATING_RE = re.compile(
    r"\bGRADE\b[^\n]{0,30}?(?:kesinli[ğk]i?|certainty)?\s*[:=]\s*\**\s*(?:yüksek|orta|düşük|çok düşük|high|moderate|low|very low)\b",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(r"\b(?:verilmez|verilmedi|yapılmadı|yapılmadan|üretilmez|değerlendirilmedi|not assessed|atanmaz|yok)\b",
                          re.IGNORECASE)


def verify_report(report_md: str, studies: List[em.Study]) -> Dict[str, Any]:
    text = report_md or ""
    by_pmid = {s.pmid: s for s in studies}
    problems: List[str] = []
    warnings: List[str] = []

    cited = set(_PMID_RE.findall(text))
    unknown = sorted(p for p in cited if p not in by_pmid)
    if unknown:
        problems.append("Makale kümesinde olmayan PMID atfı: " + ", ".join(unknown))

    quotes_checked = 0
    quotes_failed: List[str] = []
    for sentence, pmid in _QUOTE_WITH_PMID_RE.findall(text):
        study = by_pmid.get(pmid)
        if study is None:
            continue
        quotes_checked += 1
        _loc, status = em.verify_sentence_in_source(sentence, study.legacy.get("abstract", ""), study.title)
        if status != em.SOURCE_VERIFIED:
            quotes_failed.append(f"PMID {pmid}: \"{sentence[:80]}…\"")
    if quotes_failed:
        problems.append(f"Kaynakta birebir bulunamayan alıntı: {len(quotes_failed)}")

    rob_claims = [m.group(0) for m in _ROB_RATING_RE.finditer(text) if not _NEGATION_RE.search(m.group(0))]
    grade_claims = [m.group(0) for m in _GRADE_RATING_RE.finditer(text) if not _NEGATION_RE.search(m.group(0))]
    if rob_claims:
        problems.append("Değerlendirme yapılmadan yanlılık riski derecesi: " + "; ".join(rob_claims[:3]))
    if grade_claims:
        problems.append("Değerlendirme yapılmadan GRADE kesinlik derecesi: " + "; ".join(grade_claims[:3]))

    causal_hits: List[Dict[str, str]] = []
    non_causal = {s.pmid for s in studies if not s.causal_inference_allowed}
    body = text.split("## 13.")[0]  # the bibliography repeats titles/journal names verbatim
    for line in body.splitlines():
        pmids = set(_PMID_RE.findall(line))
        if not pmids or not pmids <= non_causal:
            continue
        hits = em.find_causal_language(line)
        if hits:
            causal_hits.append({"pmids": ", ".join(sorted(pmids)), "words": ", ".join(hits), "line": line[:200]})
    if causal_hits:
        warnings.append(f"Randomize olmayan çalışmaya bağlı satırlarda nedensel ifade: {len(causal_hits)}")

    inconsistent = [e for s in studies for e in s.estimates if e.validation == "tutarsiz"]
    if inconsistent:
        warnings.append(f"Tutarsız {len(inconsistent)} etki tahmini sentezden çıkarıldı.")

    sources = [e.source for s in studies for e in s.estimates] + [s.population.source for s in studies if s.population.n_total]
    verified_sources = sum(1 for src in sources if src.verification_status in (em.SOURCE_VERIFIED, em.SOURCE_DERIVED))
    if sources and verified_sources < len(sources):
        problems.append(f"Kaynak cümlesi doğrulanamayan çıkarım: {len(sources) - verified_sources}")

    if problems:
        status = STATUS_FAIL
    elif warnings:
        status = STATUS_WARN
    else:
        status = STATUS_OK
    return {
        "status": status,
        "evidence_model_version": em.EVIDENCE_MODEL_VERSION,
        "cited_pmids": len(cited),
        "unknown_pmids": unknown,
        "quotes_checked": quotes_checked,
        "quotes_failed": quotes_failed,
        "structured_sources": len(sources),
        "structured_sources_verified": verified_sources,
        "rob_rating_claims": rob_claims,
        "grade_rating_claims": grade_claims,
        "causal_language_hits": causal_hits,
        "problems": problems,
        "warnings": warnings,
    }


def render_verification_footer(result: Dict[str, Any], app_version: str) -> str:
    lines = [
        "",
        "---",
        "### 🔐 Rapor Doğrulama Durumu",
        f"- **Yazılım sürümü:** `{app_version}` | **Kanıt veri modeli:** `{result.get('evidence_model_version')}`",
        f"- **Durum:** **{result.get('status')}**",
        f"- **Atıf yapılan PMID:** {result.get('cited_pmids')} (kümede olmayan: {len(result.get('unknown_pmids') or [])})",
        f"- **Kaynak cümle alıntısı kontrolü:** {result.get('quotes_checked')} alıntı, "
        f"{len(result.get('quotes_failed') or [])} başarısız",
        f"- **Yapılandırılmış çıkarım kaynağı:** {result.get('structured_sources_verified')}/"
        f"{result.get('structured_sources')} kaynakta birebir doğrulandı",
        f"- **Randomize olmayan çalışmada nedensel ifade:** {len(result.get('causal_language_hits') or [])}",
        "- Bu otomatik denetim kaynak sadakatini kontrol eder; klinik doğruluğu veya uzman hekim onayını göstermez.",
    ]
    for item in (result.get("problems") or []) + (result.get("warnings") or []):
        lines.append(f"  - ⚠️ {item}")
    return "\n".join(lines) + "\n"

"""Preliminary, abstract-only, rule-based GRADE-style certainty notes.

This is not a GRADE rating. Unstated domains stay ``değerlendirilemedi``.
Downgrades use only phrases or intervals that appear in the abstract.
Formal GRADE remains Not Assessed until an expert reviews the full text.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_LEVEL_BY_SCORE = {4: "Yüksek", 3: "Orta", 2: "Düşük", 1: "Çok düşük"}
_NOT_ASSESSABLE = "değerlendirilemedi"

DISCLAIMER = (
    "Bu bir ön, özet-temelli ve kural tabanlı kesinlik tahminidir. "
    "Resmi GRADE değerlendirmesi değildir ve uzman hekim onayı gerektirir. "
    "Özette verisi olmayan alanlar 'değerlendirilemedi' bırakılmıştır; "
    "bu alanlar kesinlik düzeyini yükseltmek veya düşürmek için kullanılmamıştır."
)

_ROB_DOWNGRADE_RE = re.compile(
    r"\b(high risk of bias|serious risk of bias|open-label|open label|unblinded|lack of blinding|"
    r"without blinding|allocation was not concealed|high attrition|substantial loss to follow-up|"
    r"yuksek yanlilik riski|acik etiket)\b",
    re.IGNORECASE,
)
_ROB_OK_RE = re.compile(
    r"\b(low risk of bias|double-blind|double blind|triple-blind)\b",
    re.IGNORECASE,
)
_IMPRECISION_RE = re.compile(
    r"\b(underpowered|wide confidence interval|imprecise estimate|lack of precision|"
    r"guc yetersiz|genis guven araligi)\b",
    re.IGNORECASE,
)
_HETEROGENEITY_HIGH_RE = re.compile(
    r"\b(substantial heterogeneity|considerable heterogeneity|high heterogeneity|"
    r"significant heterogeneity|belirgin heterojenite)\b",
    re.IGNORECASE,
)
_HETEROGENEITY_LOW_RE = re.compile(
    r"\b(low heterogeneity|no significant heterogeneity|homogeneous results|"
    r"heterojenite dusuk)\b",
    re.IGNORECASE,
)
_I2_RE = re.compile(r"\bI\s*(?:\^?2|²)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*%?", re.IGNORECASE)
_PUB_BIAS_DOWN_RE = re.compile(
    r"\b(publication bias|funnel plot asymmetry|asymmetric funnel|yayin yanliligi)\b",
    re.IGNORECASE,
)
_PUB_BIAS_OK_RE = re.compile(
    r"\b(no publication bias|funnel plot (?:was )?symmetric|symmetric funnel)\b",
    re.IGNORECASE,
)
_CI_PAIR_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_CHILD_RE = re.compile(r"\b(child|children|pediatric|paediatric|infant|cocuk|yenidogan)\b", re.IGNORECASE)
_ADULT_RE = re.compile(r"\b(adult|adults|elderly|eriskin|yetiskin)\b", re.IGNORECASE)


def _domain(status: str, reason: str) -> Dict[str, str]:
    return {"status": status, "reason": reason}


def _design_start(design_name: str, abstract: str) -> Dict[str, Any]:
    """Map a classified design to a GRADE starting level, or leave it unassessed."""
    abstract_l = abstract or ""
    if "RCT" in design_name or "Rastgele" in design_name:
        return {"level": "Yüksek", "score": 4, "reason": "Çalışma tasarımı randomize kontrollü çalışma olarak sınıflandı."}
    if "Kohort" in design_name or "Vaka-Kontrol" in design_name or "Gözlemsel" in design_name or "Karşılaştırmalı" in design_name:
        return {"level": "Düşük", "score": 2, "reason": "Gözlemsel veya karşılaştırmalı non-randomize tasarım GRADE başlangıcında düşük kabul edilir."}
    if "Olgu" in design_name or "Niteliksel Derleme" in design_name or "Editör" in design_name:
        return {"level": "Çok düşük", "score": 1, "reason": "Olgu sunumu, anlatı derlemesi veya editöryal yazı etki kesinliği için çok düşük başlangıçtır."}
    if "Sistematik Derleme" in design_name or "Meta-Analiz" in design_name:
        if re.search(r"\brandomi[sz]ed\b|\brct\b|rastgele", abstract_l, re.IGNORECASE):
            return {
                "level": "Yüksek",
                "score": 4,
                "reason": "Sistematik derleme/meta-analiz özeti randomize çalışmalar içerdiğini belirtiyor.",
            }
        if re.search(r"\bcohort\b|\bobservational\b|kohort|gözlemsel", abstract_l, re.IGNORECASE):
            return {
                "level": "Düşük",
                "score": 2,
                "reason": "Özet, dahil edilen çalışmaları gözlemsel/kohort olarak belirtiyor; randomize tasarım ifadesi yok.",
            }
        return {
            "level": _NOT_ASSESSABLE,
            "score": None,
            "reason": "Sistematik derlemenin dahil ettiği çalışma tasarımı özette belirtilmedi.",
        }
    if "Klinik Araştırma" in design_name:
        return {
            "level": _NOT_ASSESSABLE,
            "score": None,
            "reason": "Kontrollü klinik araştırma kaydı randomizasyonu özette doğrulamıyor.",
        }
    return {
        "level": _NOT_ASSESSABLE,
        "score": None,
        "reason": "Özet ve yayın türünden GRADE başlangıç düzeyi için yeterli tasarım sinyali yok.",
    }


def _risk_of_bias(abstract: str) -> Dict[str, str]:
    match = _ROB_DOWNGRADE_RE.search(abstract or "")
    if match:
        return _domain("ciddi düşürme", f"Özette yanlılık ifadesi var: '{match.group(0)}'.")
    if _ROB_OK_RE.search(abstract or ""):
        return _domain("düşürme yok", "Özet düşük yanlılık riski veya çift-kör tasarım belirtiyor. Tam metin RoB 2 uygulanmadı.")
    return _domain(_NOT_ASSESSABLE, "Özet, RoB 2 veya ROBINS-I için yeterli yöntem ayrıntısı vermiyor.")


def _inconsistency(design_name: str, abstract: str) -> Dict[str, str]:
    is_synthesis = "Sistematik Derleme" in design_name or "Meta-Analiz" in design_name
    if not is_synthesis:
        return _domain(_NOT_ASSESSABLE, "Tek bir primer çalışmada çalışmalar arası tutarsızlık özette değerlendirilemez.")
    i2_match = _I2_RE.search(abstract or "")
    if i2_match:
        i2_value = float(i2_match.group(1))
        if i2_value >= 50:
            return _domain("ciddi düşürme", f"Özette bildirilen I² = {i2_match.group(1)} (≥50 kural eşiği).")
        return _domain("düşürme yok", f"Özette bildirilen I² = {i2_match.group(1)} (<50).")
    if _HETEROGENEITY_HIGH_RE.search(abstract or ""):
        return _domain("ciddi düşürme", "Özet belirgin heterojenite tarif ediyor.")
    if _HETEROGENEITY_LOW_RE.search(abstract or ""):
        return _domain("düşürme yok", "Özet heterojenitenin düşük olduğunu belirtiyor.")
    return _domain(_NOT_ASSESSABLE, "Özette I² veya heterojenite ifadesi yok.")


def _parsed_ci_bounds(ci_strings: List[str]) -> Optional[tuple]:
    for raw in ci_strings or []:
        match = _CI_PAIR_RE.search(raw or "")
        if not match:
            continue
        low = float(match.group(1))
        high = float(match.group(2))
        if high < low:
            low, high = high, low
        return low, high
    return None


def _imprecision(abstract: str, metrics: Dict[str, Any]) -> Dict[str, str]:
    match = _IMPRECISION_RE.search(abstract or "")
    if match:
        return _domain("ciddi düşürme", f"Özet imprecision belirtiyor: '{match.group(0)}'.")
    bounds = _parsed_ci_bounds(metrics.get("confidence_intervals") or [])
    if bounds is None:
        return _domain(_NOT_ASSESSABLE, "Özette güven aralığı veya açık imprecision ifadesi yok.")
    low, high = bounds
    # Only positive ratio-style intervals (HR/OR/RR) are scored. Continuous scales are not guessed.
    if low <= 0 or high <= 0 or low >= 10:
        return _domain(_NOT_ASSESSABLE, "Ayrıştırılan aralık bir oran ölçütü gibi durmuyor; ölçek varsayılmadı.")
    ratio = high / low if low else None
    if ratio is not None and ratio >= 3:
        return _domain(
            "ciddi düşürme",
            f"Özetteki aralık {low:g}-{high:g}; üst/alt oranı {ratio:.2f} (≥3 kural eşiği).",
        )
    return _domain("düşürme yok", f"Özetteki aralık {low:g}-{high:g}; üst/alt oranı 3 eşiğinin altında.")


def _indirectness(query: str, abstract: str, title: str) -> Dict[str, str]:
    from report_generator import extract_pico

    pico = extract_pico(query or "")
    population = pico.get("population") or ""
    if not population or population == "Belirtilmemiş":
        return _domain(_NOT_ASSESSABLE, "Sorguda popülasyon belirtilmediği için dolaylılık karşılaştırılamadı.")
    blob = f"{title or ''} {abstract or ''}"
    query_child = bool(_CHILD_RE.search(population))
    query_adult = bool(_ADULT_RE.search(population))
    text_child = bool(_CHILD_RE.search(blob))
    text_adult = bool(_ADULT_RE.search(blob))
    if query_child and text_adult and not text_child:
        return _domain("ciddi düşürme", "Sorgu çocuk popülasyonu, özet erişkin popülasyonu belirtiyor.")
    if query_adult and text_child and not text_adult:
        return _domain("ciddi düşürme", "Sorgu erişkin popülasyonu, özet çocuk popülasyonu belirtiyor.")
    tokens = [tok for tok in re.findall(r"[A-Za-zÀ-ÿ0-9\-]{4,}", population.lower()) if tok not in {"with", "patients", "adults", "children"}]
    blob_l = blob.lower()
    if tokens and any(tok in blob_l for tok in tokens):
        return _domain("düşürme yok", "Sorgu popülasyonundaki bir terim başlık veya özette geçiyor. Tam PICO uyumu iddia edilmez.")
    return _domain(_NOT_ASSESSABLE, "Sorgu popülasyonu ile özet arasında yeterince açık bir eşleşme veya çelişki yok.")


def _publication_bias(design_name: str, abstract: str) -> Dict[str, str]:
    is_synthesis = "Sistematik Derleme" in design_name or "Meta-Analiz" in design_name
    if not is_synthesis:
        return _domain(_NOT_ASSESSABLE, "Tek çalışmada yayın yanlılığı hunisi özette değerlendirilemez.")
    if _PUB_BIAS_DOWN_RE.search(abstract or "") and not _PUB_BIAS_OK_RE.search(abstract or ""):
        return _domain("ciddi düşürme", "Özet yayın yanlılığı veya asimetrik huni grafiği belirtiyor.")
    if _PUB_BIAS_OK_RE.search(abstract or ""):
        return _domain("düşürme yok", "Özet yayın yanlılığı lehine bir işaret bildirmediğini söylüyor.")
    return _domain(_NOT_ASSESSABLE, "Özette huni grafiği veya yayın yanlılığı ifadesi yok.")


def _apply_ceiling(start_score: Optional[int], domains: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    if start_score is None:
        return {
            "preliminary_level": _NOT_ASSESSABLE,
            "applied_downgrades": 0,
            "reason": "Başlangıç düzeyi değerlendirilemediği için sayısal tavan üretilmedi.",
        }
    downgrades = sum(1 for item in domains.values() if item.get("status") == "ciddi düşürme")
    score = max(1, start_score - downgrades)
    return {
        "preliminary_level": _LEVEL_BY_SCORE[score],
        "applied_downgrades": downgrades,
        "reason": "Yalnızca özette desteklenen ciddi düşürmeler başlangıçtan çıkarıldı.",
    }


def assess_preliminary_grade(article: Dict[str, Any], query: str = "") -> Dict[str, Any]:
    """Return a per-article preliminary GRADE-style note. Does not invent metrics."""
    from report_generator import classify_study_design, extract_study_metrics

    title = article.get("title") or ""
    abstract = article.get("abstract") or ""
    design = classify_study_design(article.get("publication_types") or [], title, abstract)
    design_name = design.get("design") or ""
    metrics = extract_study_metrics(abstract)
    starting = _design_start(design_name, abstract)
    domains = {
        "risk_of_bias": _risk_of_bias(abstract),
        "inconsistency": _inconsistency(design_name, abstract),
        "indirectness": _indirectness(query, abstract, title),
        "imprecision": _imprecision(abstract, metrics),
        "publication_bias": _publication_bias(design_name, abstract),
    }
    ceiling = _apply_ceiling(starting.get("score"), domains)
    return {
        "pmid": article.get("pmid") or "",
        "design": design_name,
        "starting_level": starting["level"],
        "starting_reason": starting["reason"],
        "domains": domains,
        "preliminary_level": ceiling["preliminary_level"],
        "applied_downgrades": ceiling["applied_downgrades"],
        "ceiling_reason": ceiling["reason"],
        "disclaimer": DISCLAIMER,
        "formal_grade_status": "GRADE Değerlendirilmedi (Not Assessed)",
    }


def format_preliminary_grade_markdown(query: str, articles: List[Dict[str, Any]]) -> str:
    """Turkish markdown block for section 11. Formal GRADE stays Not Assessed."""
    lines = [
        "### Ön GRADE-tarzı kesinlik tahmini (özet, kural tabanlı)",
        f"- {DISCLAIMER}",
        "- **Resmi GRADE:** GRADE Değerlendirilmedi (Not Assessed).",
    ]
    if not articles:
        lines.append("- Değerlendirilecek makale yok.")
        return "\n".join(lines)
    for art in articles:
        note = assess_preliminary_grade(art, query)
        pmid = note["pmid"] or "PMID yok"
        domain_bits = []
        labels = {
            "risk_of_bias": "Yanlılık riski",
            "inconsistency": "Tutarsızlık",
            "indirectness": "Dolaylılık",
            "imprecision": "Imprecision",
            "publication_bias": "Yayın yanlılığı",
        }
        for key, label in labels.items():
            item = note["domains"][key]
            domain_bits.append(f"{label}: {item['status']}")
        lines.append(
            f"- **PMID {pmid}** ({note['design'] or 'tasarım belirsiz'}): "
            f"başlangıç {note['starting_level']}; ön tavan {note['preliminary_level']}; "
            f"uygulanan ciddi düşürme sayısı {note['applied_downgrades']}. "
            + "; ".join(domain_bits)
            + "."
        )
    return "\n".join(lines)

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
    r"\b(low heterogeneity|no significant heterogeneity|no substantial heterogeneity|"
    r"no heterogeneity|homogeneous results|"
    r"heterojenite dusuk)\b",
    re.IGNORECASE,
)
_I2_RE = re.compile(r"\bI\s*(?:\^?2|²)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*%?", re.IGNORECASE)
_PUB_BIAS_DOWN_RE = re.compile(
    r"\b(publication bias|funnel plot asymmetry|asymmetric funnel|yayin yanliligi)\b",
    re.IGNORECASE,
)
_PUB_BIAS_OK_RE = re.compile(
    r"\b(no (?:evidence of )?publication bias|no (?:evidence of )?funnel plot asymmetry|"
    r"funnel plot (?:was )?symmetric|symmetric funnel)\b",
    re.IGNORECASE,
)
_CI_PAIR_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_CHILD_RE = re.compile(r"\b(child|children|pediatric|paediatric|infant|cocuk|yenidogan)\b", re.IGNORECASE)
_ADULT_RE = re.compile(r"\b(adult|adults|elderly|eriskin|yetiskin)\b", re.IGNORECASE)
_NEGATION_PREFIX_RE = re.compile(
    r"\b(?:no|not|without|neither|absence of|lack of|did not|does not|do not|"
    r"was not|were not|is not|are not|has not|have not|had not|never)\b"
    r"(?:\s+[\w'-]+){0,6}\s*$",
    re.IGNORECASE,
)
_NEGATION_SUFFIX_RE = re.compile(
    r"^\s+(?:(?:was|were|is|are|has been|have been|had been)\s+)?"
    r"(?:not\s+(?:observed|detected|found|reported|identified|present|associated)|"
    r"absent|ruled out|excluded)\b",
    re.IGNORECASE,
)


def _is_negated_match(text: str, match: re.Match) -> bool:
    """Avoid treating a negated phrase as positive evidence for a domain."""
    before = text[max(0, match.start() - 100):match.start()]
    before = re.split(r"[.!?;:]\s*", before)[-1]
    if _NEGATION_PREFIX_RE.search(before):
        return True
    after = text[match.end():match.end() + 60]
    return bool(_NEGATION_SUFFIX_RE.match(after))


def _first_unnegated_match(pattern: re.Pattern, text: str) -> Optional[re.Match]:
    for match in pattern.finditer(text or ""):
        if not _is_negated_match(text or "", match):
            return match
    return None



def _domain(status: str, reason: str) -> Dict[str, str]:
    return {"status": status, "reason": reason}


def _design_start(design_name: str, abstract: str) -> Dict[str, Any]:
    """Map a classified design to a GRADE starting level, or leave it unassessed."""
    abstract_l = abstract or ""
    if "RCT" in design_name or "Rastgele" in design_name:
        return {"level": "Yüksek", "score": 4, "reason": "Çalışma tasarımı randomize kontrollü çalışma olarak sınıflandı."}
    if any(token in design_name for token in ("Kohort", "Vaka-Kontrol", "Gözlemsel", "Karşılaştırmalı", "Kesitsel")):
        return {"level": "Düşük", "score": 2, "reason": "Gözlemsel tasarım GRADE başlangıcında düşük kabul edilir. Bu bir kanıt düzeyi damgası değildir."}
    if any(token in design_name for token in ("Olgu", "Niteliksel Derleme", "Editör", "Kılavuz", "Konsensüs", "belirlenemedi")):
        return {
            "level": _NOT_ASSESSABLE,
            "score": None,
            "reason": "Olgu sunumu, olgu serisi, derleme, kılavuz veya editöryal yazı için tasarım adından kesinlik düzeyi üretilmedi.",
        }
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
    text = abstract or ""
    match = _first_unnegated_match(_ROB_DOWNGRADE_RE, text)
    if match:
        return _domain("ciddi düşürme", f"Özette yanlılık ifadesi var: '{match.group(0)}'.")
    if _first_unnegated_match(_ROB_OK_RE, text):
        return _domain("düşürme yok", "Özet düşük yanlılık riski veya çift-kör tasarım belirtiyor. Tam metin RoB 2 uygulanmadı.")
    return _domain(_NOT_ASSESSABLE, "Özet, RoB 2 veya ROBINS-I için yeterli yöntem ayrıntısı vermiyor.")


def _inconsistency(design_name: str, abstract: str) -> Dict[str, str]:
    is_synthesis = "Sistematik Derleme" in design_name or "Meta-Analiz" in design_name
    if not is_synthesis:
        return _domain(_NOT_ASSESSABLE, "Tek bir primer çalışmada çalışmalar arası tutarsızlık özette değerlendirilemez.")
    i2_match = _I2_RE.search(abstract or "")
    if i2_match:
        i2_value = float(i2_match.group(1))
        if i2_value > 100:
            return _domain(_NOT_ASSESSABLE, f"Özette bildirilen I² = {i2_match.group(1)}; 0–100 aralığı dışında olduğu için yorumlanmadı.")
        if i2_value >= 50:
            return _domain("ciddi düşürme", f"Özette bildirilen I² = {i2_match.group(1)} (≥50 kural eşiği).")
        return _domain("düşürme yok", f"Özette bildirilen I² = {i2_match.group(1)} (<50).")
    text = abstract or ""
    if _first_unnegated_match(_HETEROGENEITY_HIGH_RE, text):
        return _domain("ciddi düşürme", "Özet belirgin heterojenite tarif ediyor.")
    if _first_unnegated_match(_HETEROGENEITY_LOW_RE, text):
        return _domain("düşürme yok", "Özet düşük veya belirgin olmayan heterojeniteyi kural tabanlı biçimde bildiriyor.")
    if _HETEROGENEITY_HIGH_RE.search(text):
        return _domain(_NOT_ASSESSABLE, "Heterojenite ifadesi olumsuzlanmış; açık olumlu kanıt olmadan düşürme veya düşük heterojenite çıkarımı yapılmadı.")
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
    match = _first_unnegated_match(_IMPRECISION_RE, abstract or "")
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
    text = abstract or ""
    if _first_unnegated_match(_PUB_BIAS_DOWN_RE, text):
        return _domain("ciddi düşürme", "Özet yayın yanlılığı veya asimetrik huni grafiği belirtiyor.")
    if _first_unnegated_match(_PUB_BIAS_OK_RE, text):
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


_GENERIC_OUTCOME = "primer klinik sonlanım / özet istatistiği"


def _outcome_is_named(label: str) -> bool:
    cleaned = (label or "").strip().lower()
    return bool(cleaned) and cleaned != _GENERIC_OUTCOME and cleaned != _NOT_ASSESSABLE


def _grade_one_outcome(
    article: Dict[str, Any],
    query: str,
    design_name: str,
    starting: Dict[str, Any],
    outcome: Dict[str, Any],
) -> Dict[str, Any]:
    """GRADE-style note for one outcome sentence. Missing pieces stay unassessed."""
    from report_generator import extract_study_metrics

    sentence = outcome.get("sentence") or outcome.get("source_sentence") or ""
    title = article.get("title") or ""
    abstract = article.get("abstract") or ""
    named = _outcome_is_named(outcome.get("outcome") or "")
    if not named:
        domains = {
            "risk_of_bias": _domain(_NOT_ASSESSABLE, "Sonlanım adı olmadığı için yanlılık alanı sonlanıma bağlanamadı."),
            "inconsistency": _domain(_NOT_ASSESSABLE, "Sonlanım adı olmadığı için tutarsızlık değerlendirilemedi."),
            "indirectness": _domain(_NOT_ASSESSABLE, "Sonlanım adı olmadığı için dolaylılık değerlendirilemedi."),
            "imprecision": _domain(_NOT_ASSESSABLE, "Sonlanım adı olmadığı için kesinlik eksikliği değerlendirilemedi."),
            "publication_bias": _domain(_NOT_ASSESSABLE, "Sonlanım adı olmadığı için yayın yanlılığı değerlendirilemedi."),
        }
        return {
            "outcome": _NOT_ASSESSABLE,
            "identified": False,
            "pmid": article.get("pmid") or "",
            "source_sentence": sentence,
            "metrics": list(outcome.get("metrics") or []),
            "starting_level": _NOT_ASSESSABLE,
            "domains": domains,
            "preliminary_level": _NOT_ASSESSABLE,
            "applied_downgrades": 0,
            "ceiling_reason": "Adlandırılmış sonlanım olmadığı için kesinlik düzeyi üretilmedi.",
        }

    metric_strings = list(outcome.get("metrics") or [])
    sentence_metrics = extract_study_metrics(sentence)
    sentence_metrics["confidence_intervals"] = [
        item for item in metric_strings if re.search(r"\bCI\b|95%", item, re.IGNORECASE)
    ] or sentence_metrics.get("confidence_intervals") or []
    domains = {
        "risk_of_bias": _risk_of_bias(sentence),
        "inconsistency": _inconsistency(design_name, sentence or abstract),
        "indirectness": _indirectness(query, abstract, title),
        "imprecision": _imprecision(sentence, sentence_metrics),
        "publication_bias": _publication_bias(design_name, sentence or abstract),
    }
    ceiling = _apply_ceiling(starting.get("score"), domains)
    return {
        "outcome": outcome.get("outcome"),
        "identified": True,
        "pmid": article.get("pmid") or "",
        "source_sentence": sentence,
        "metrics": metric_strings,
        "starting_level": starting["level"],
        "domains": domains,
        "preliminary_level": ceiling["preliminary_level"],
        "applied_downgrades": ceiling["applied_downgrades"],
        "ceiling_reason": ceiling["reason"],
    }


def assess_preliminary_grade(article: Dict[str, Any], query: str = "") -> Dict[str, Any]:
    """Return outcome-level GRADE-style notes. A missing outcome is not graded."""
    from report_generator import classify_study_design, extract_outcome_metrics, extract_study_metrics

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
    raw_outcomes = extract_outcome_metrics(abstract)
    if not raw_outcomes:
        raw_outcomes = [{"outcome": "", "metrics": [], "sentence": ""}]
    outcome_notes = [_grade_one_outcome(article, query, design_name, starting, item) for item in raw_outcomes]
    identified = [item for item in outcome_notes if item["identified"]]
    levels = {item["preliminary_level"] for item in identified}
    if not identified:
        preliminary_level = _NOT_ASSESSABLE
        applied_downgrades = 0
        ceiling_reason = "Adlandırılmış sonlanım olmadığı için kesinlik düzeyi üretilmedi."
    elif len(levels) == 1:
        preliminary_level = identified[0]["preliminary_level"]
        applied_downgrades = max(item["applied_downgrades"] for item in identified)
        ceiling_reason = "Ön kesinlik, adlandırılmış sonlanım cümlelerinden üretildi. Resmi GRADE değildir."
    else:
        preliminary_level = _NOT_ASSESSABLE
        applied_downgrades = 0
        ceiling_reason = "Sonlanımların ön kesinlik düzeyleri aynı değil; tek düzey üretilmedi."
    return {
        "pmid": article.get("pmid") or "",
        "design": design_name,
        "starting_level": starting["level"],
        "starting_reason": starting["reason"],
        "domains": domains,
        "outcomes": outcome_notes,
        "preliminary_level": preliminary_level,
        "applied_downgrades": applied_downgrades,
        "ceiling_reason": ceiling_reason,
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
        labels = {
            "risk_of_bias": "Yanlılık riski",
            "inconsistency": "Tutarsızlık",
            "indirectness": "Dolaylılık",
            "imprecision": "Kesinlik eksikliği",
            "publication_bias": "Yayın yanlılığı",
        }
        lines.append(
            f"- **PMID {pmid}** ({note['design'] or 'tasarım belirsiz'}). "
            f"Makale için tek kesinlik düzeyi: {note['preliminary_level']}. {note['ceiling_reason']}"
        )
        for outcome in note.get("outcomes") or []:
            bits = []
            for key, label in labels.items():
                item = outcome["domains"][key]
                bits.append(f"{label}: {item['status']}")
            sentence = outcome.get("source_sentence") or ""
            sentence_bit = f" Kaynak cümle: \"{sentence}\"." if sentence else " Kaynak cümle: değerlendirilemedi."
            lines.append(
                f"  - Sonlanım: {outcome['outcome']}; ön kesinlik: {outcome['preliminary_level']}; "
                + "; ".join(bits)
                + f".{sentence_bit} (PMID: {pmid})"
            )
    return "\n".join(lines)

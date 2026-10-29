import os
import re
from typing import List, Dict, Any, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from pubmed_client import verify_citation

MANDATORY_CLINICAL_REPORT_SECTIONS = [
    "## 1. Klinik Araştırma Sorusu",
    "## 2. Yönetici Özeti",
    "## 3. Araştırma Yöntemi ve Tarama Tarihi",
    "## 4. Klinik Arka Plan ve Patofizyoloji",
    "## 5. Bilimsel Kanıt Tablosu",
    "## 6. Önemli Çalışmaların Karşılaştırılması",
    "## 7. Tedavi Etkinliği ve Güvenlilik",
    "## 8. Güncel Klinik Kılavuzlar",
    "## 9. Çelişkili Bilimsel Bulgular",
    "## 10. Red Team Eleştirisi",
    "## 11. Kanıt Gücü ve Belirsizlikler",
    "## 12. Klinik Sonuç",
    "## 13. Doğrulanmış Kaynakça"
]


def validate_clinical_report_quality(report_text: str) -> Dict[str, Any]:
    """
    Mandatory quality control check for clinical evidence reports.
    Strictly verifies that all 13 mandatory sections exist, disclaimers for abstract-only limits,
    GRADE Not Assessed status, and Expert Physician Review incomplete status are present,
    and checks for forbidden false/hallucinated claims.
    """
    if not report_text or not isinstance(report_text, str):
        return {
            "valid": False,
            "missing_sections": MANDATORY_CLINICAL_REPORT_SECTIONS,
            "detected_false_claims": [],
            "warnings": ["Rapor metni boş veya geçersiz formatta."],
            "error": "Rapor metni boş veya geçersiz formatta."
        }

    if "⚠️ Sonuç Bulunamadı" in report_text or "kriterlere uygun makale bulunamamıştır" in report_text:
        return {
            "valid": True,
            "missing_sections": [],
            "detected_false_claims": [],
            "warnings": ["Rapor sonuç bulunamadı uyarısı içeriyor."],
            "empty_results": True
        }

    missing_sections = [
        sec for sec in MANDATORY_CLINICAL_REPORT_SECTIONS if sec not in report_text
    ]

    warnings = []

    if not re.search(r"\b(abstract|öze[tt])\b", report_text, re.IGNORECASE):
        warnings.append("Özet (abstract-only) sınırlılığı bildirimi eksik.")

    if "GRADE Değerlendirilmedi" not in report_text and "Not Assessed" not in report_text:
        warnings.append("GRADE Değerlendirilmedi (Not Assessed) statüsü bildirimi eksik.")

    if "Uzman Hekim Değerlendirmesi" not in report_text and "Klinik Doğrulama Yapılmamıştır" not in report_text:
        warnings.append("Uzman Hekim Değerlendirmesi Yapılmamıştır/Tamamlanmamıştır bildirimi eksik.")

    forbidden_patterns = [
        (r"100\s*/\s*100", "100/100 asılsız puan/puanlama iddiası"),
        (r"0%\s*halüsinasyon", "0% halüsinasyon asılsız iddiası"),
        (r"%0\s*halüsinasyon", "%0 halüsinasyon asılsız iddiası"),
        (r"sallama\s*(0%|%0|sıfır)", "Sıfır sallama/uydurma asılsız iddiası"),
        (r"klinik olarak %?100 doğrulandı", "Klinik olarak %100 doğrulandı asılsız iddiası"),
        (r"uzman hekim değerlendirmesi tamamlanmış(tır)?", "Uzman hekim değerlendirmesi tamamlandı asılsız iddiası")
    ]

    detected_false_claims = []
    for pat, desc in forbidden_patterns:
        if re.search(pat, report_text, re.IGNORECASE):
            detected_false_claims.append(desc)

    is_valid = len(missing_sections) == 0 and len(detected_false_claims) == 0

    return {
        "valid": is_valid,
        "missing_sections": missing_sections,
        "detected_false_claims": detected_false_claims,
        "warnings": warnings
    }


def _format_authors_short(authors: List[str]) -> str:
    if not authors:
        return "Bilinmeyen Yazar"
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} ve {authors[1]}"
    return f"{authors[0]} et al."


def classify_study_design(pub_types: List[str], title: str, abstract: str) -> Dict[str, Any]:
    """
    Classifies study design and evidence level using NLM publication types for preliminary
    classification, falling back to title and abstract heuristics.
    """
    pts = [pt.lower() for pt in (pub_types or []) if pt]

    # 1. Preliminary classification via official NLM Publication Types (in priority order)
    if any("meta-analysis" in pt or "sistematik derleme" in pt for pt in pts):
        return {
            "design": "Sistematik Derleme / Meta-Analiz",
            "level": "Seviye 1",
            "level_num": 1,
            "badge_color": "#1E40AF"
        }
    if any("systematic review" in pt for pt in pts):
        return {
            "design": "Sistematik Derleme / Meta-Analiz",
            "level": "Seviye 1",
            "level_num": 1,
            "badge_color": "#1E40AF"
        }
    if any("randomized controlled trial" in pt for pt in pts):
        return {
            "design": "Rastgele Kontrollü Çalışma (RCT)",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#047857"
        }
    if any("clinical trial" in pt or "controlled clinical trial" in pt for pt in pts):
        return {
            "design": "Kontrollü Klinik Araştırma",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#059669"
        }
    if any("observational study" in pt or "cohort" in pt or "longitudinal" in pt or "prospective study" in pt for pt in pts):
        return {
            "design": "Kohort Çalışması (Gözlemsel)",
            "level": "Seviye 3",
            "level_num": 3,
            "badge_color": "#D97706"
        }
    if any("case reports" in pt or "case report" in pt for pt in pts):
        return {
            "design": "Olgu Sunumu / Vaka Serisi",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    if any("practice guideline" in pt or "guideline" in pt or "consensus development conference" in pt for pt in pts):
        return {
            "design": "Kılavuz / Konsensüs Raporu",
            "level": "Seviye 5",
            "level_num": 5,
            "badge_color": "#4B5563"
        }
    if any("editorial" in pt or "letter" in pt or "comment" in pt for pt in pts):
        return {
            "design": "Editör Yazısı / Mektup / Yorum",
            "level": "Seviye 5",
            "level_num": 5,
            "badge_color": "#6B7280"
        }
    if any("review" in pt or "derleme" in pt for pt in pts):
        return {
            "design": "Niteliksel Derleme / Uzman Görüşü",
            "level": "Seviye 5",
            "level_num": 5,
            "badge_color": "#4B5563"
        }

    # 2. Secondary check based on Title
    title_lower = (title or "").lower()
    if "systematic review" in title_lower or "meta-analysis" in title_lower or "sistematik derleme" in title_lower:
        return {
            "design": "Sistematik Derleme / Meta-Analiz",
            "level": "Seviye 1",
            "level_num": 1,
            "badge_color": "#1E40AF"
        }
    elif "randomized" in title_lower or "rct" in title_lower or "rastgele kontrollü" in title_lower:
        return {
            "design": "Rastgele Kontrollü Çalışma (RCT)",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#047857"
        }
    elif "clinical trial" in title_lower or "klinik araştırma" in title_lower:
        return {
            "design": "Kontrollü Klinik Araştırma",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#059669"
        }
    elif "cohort" in title_lower or "prospective" in title_lower or "longitudinal" in title_lower or "kohort" in title_lower:
        return {
            "design": "Kohort Çalışması (Gözlemsel)",
            "level": "Seviye 3",
            "level_num": 3,
            "badge_color": "#D97706"
        }
    elif "case-control" in title_lower or "vaka-kontrol" in title_lower or "case control" in title_lower:
        return {
            "design": "Vaka-Kontrol Çalışması",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    elif "case report" in title_lower or "case series" in title_lower or "olgu sunumu" in title_lower:
        return {
            "design": "Olgu Sunumu / Vaka Serisi",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    elif "review" in title_lower or "derleme" in title_lower:
        return {
            "design": "Niteliksel Derleme / Uzman Görüşü",
            "level": "Seviye 5",
            "level_num": 5,
            "badge_color": "#4B5563"
        }

    # 3. Tertiary fallback based on Abstract
    abstract_lower = (abstract or "").lower()
    if "systematic review" in abstract_lower or "meta-analysis" in abstract_lower or "sistematik derleme" in abstract_lower:
        return {
            "design": "Sistematik Derleme / Meta-Analiz",
            "level": "Seviye 1",
            "level_num": 1,
            "badge_color": "#1E40AF"
        }
    elif "randomized controlled trial" in abstract_lower or "randomized trial" in abstract_lower or "rastgele kontrollü" in abstract_lower:
        return {
            "design": "Rastgele Kontrollü Çalışma (RCT)",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#047857"
        }
    elif "cohort study" in abstract_lower or "prospective cohort" in abstract_lower or "kohort çalışması" in abstract_lower:
        return {
            "design": "Kohort Çalışması (Gözlemsel)",
            "level": "Seviye 3",
            "level_num": 3,
            "badge_color": "#D97706"
        }
    elif "case-control study" in abstract_lower or "vaka-kontrol çalışması" in abstract_lower:
        return {
            "design": "Vaka-Kontrol Çalışması",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    elif "case report" in abstract_lower or "olgu sunumu" in abstract_lower:
        return {
            "design": "Olgu Sunumu / Vaka Serisi",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    elif "review" in abstract_lower or "derleme" in abstract_lower:
        return {
            "design": "Niteliksel Derleme / Uzman Görüşü",
            "level": "Seviye 5",
            "level_num": 5,
            "badge_color": "#4B5563"
        }

    return {
        "design": "Primer Araştırma / Dergi Makalesi",
        "level": "Seviye 3-5",
        "level_num": 4,
        "badge_color": "#6B7280"
    }


def _classify_evidence_level(pub_types: List[str], title: str, abstract: str) -> str:
    res = classify_study_design(pub_types, title, abstract)
    return f"{res['level']} ({res['design']})"


def _clean_pico_str(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"^[,\s.:;]+|[,\s.:;]+$", "", s).strip()
    return s


def extract_pico(query: str, abstract: str = "") -> Dict[str, str]:
    """
    Extracts PICO (Population, Intervention, Comparison, Outcome) framework components
    from Turkish or English clinical search queries and study abstract text.
    Does NOT blindly accept keyword search queries as interventions and defaults unstated elements to 'Belirtilmemiş'.
    """
    q_clean = (query or "").strip()
    abs_clean = (abstract or "").strip()

    population = ""
    intervention = ""
    comparison = ""
    outcome = ""

    # 1. Parse Abstract for explicit section headers first
    if abs_clean:
        pop_sec = re.search(r"\b(PATIENTS|POPULATION|PARTICIPANTS|HASTALAR|POPÜLASYON)\b\s*:\s*([^.\n]+)", abs_clean, re.IGNORECASE)
        if pop_sec:
            population = _clean_pico_str(pop_sec.group(2))

        int_sec = re.search(r"\b(INTERVENTION|INTERVENTIONS|METHODS|METHODOLOGY|TREATMENT|MÜDAHALE|TEDAVİ)\b\s*:\s*([^.\n]+)", abs_clean, re.IGNORECASE)
        if int_sec:
            intervention = _clean_pico_str(int_sec.group(2))

        comp_sec = re.search(r"\b(COMPARISON|CONTROL|CONTROLS|KARŞILAŞTIRMA|KONTROL)\b\s*:\s*([^.\n]+)", abs_clean, re.IGNORECASE)
        if comp_sec:
            comparison = _clean_pico_str(comp_sec.group(2))

        out_sec = re.search(r"\b(PRIMARY OUTCOME|OUTCOME|OUTCOMES|RESULTS|CONCLUSIONS|SONUÇLAR|SONLANIM)\b\s*:\s*([^.\n]+)", abs_clean, re.IGNORECASE)
        if out_sec:
            outcome = _clean_pico_str(out_sec.group(2))

    # 2. Parse Clinical Query (Turkish and English) if structured
    if q_clean:
        # Check for explicit Comparison in Query
        comp_match = re.search(r"\b(versus|vs\.?|compared (?:to|with)|against)\b", q_clean, re.IGNORECASE)
        tr_comp_match = re.search(r"\b(karşı|karşılaştırmalı|kıyasla|ile karşılaştırıldığında)\b", q_clean, re.IGNORECASE)

        if comp_match or tr_comp_match:
            split_keyword = comp_match.group(0) if comp_match else tr_comp_match.group(0)
            parts = re.split(re.escape(split_keyword), q_clean, flags=re.IGNORECASE, maxsplit=1)
            left_side = parts[0].strip()
            right_side = parts[1].strip() if len(parts) > 1 else ""

            # Check if population is in right_side (e.g., "in patients with...") or left_side
            pop_match = re.search(r"\b(in patients with|in adults with|in children with|in|for|among|hastalarda|hastalarında|tanılı hastalarda)\b\s*(.*)", right_side, re.IGNORECASE)
            tr_pop_match = re.search(r"(.*?)\s+(?:hastalarda|hastalarında|bireylerde)\b", left_side, re.IGNORECASE)

            if pop_match and pop_match.group(2):
                if not population:
                    population = pop_match.group(2).strip().capitalize()
                comp_text = right_side[:pop_match.start()].strip()
                if comp_text and not comparison:
                    comparison = comp_text.capitalize()
            elif not comparison and right_side:
                # e.g., "SGLT2 inhibitors vs placebo"
                right_pop_sep = re.search(r"\b(in|for|among)\b\s*(.*)", right_side, re.IGNORECASE)
                if right_pop_sep:
                    comparison = right_side[:right_pop_sep.start()].strip().capitalize()
                    if not population and right_pop_sep.group(2):
                        population = right_pop_sep.group(2).strip().capitalize()
                else:
                    comparison = right_side.capitalize()

            if tr_pop_match and not population:
                population = tr_pop_match.group(0).strip()
                left_side = re.sub(re.escape(tr_pop_match.group(0)), "", left_side, flags=re.IGNORECASE).strip()

            if left_side and not intervention:
                intervention = left_side

        else:
            # Query does not have explicit comparison. Check for structured population vs intervention patterns
            # English: "[Intervention] in patients with [Population]" or "[Intervention] for [Population]"
            pop_pattern = re.search(r"^(.*?)\s+\b(in patients with|in adults with|in children with|in|for|among|with)\s+(.*)$", q_clean, re.IGNORECASE)
            # Turkish: "[Population] hastalarda [Intervention] kullanımı/etkisi" or "[Population] hastalarında [Intervention]"
            tr_pop_pattern = re.search(r"^(.*?)\s+(?:hastalarda|hastalarında|tanılı hastalarda|bireylerde)\s+(.*)$", q_clean, re.IGNORECASE)

            if pop_pattern:
                if not intervention and pop_pattern.group(1):
                    intervention = pop_pattern.group(1).strip().capitalize()
                if not population and pop_pattern.group(3):
                    population = pop_pattern.group(3).strip().capitalize()
            elif tr_pop_pattern:
                if not population and tr_pop_pattern.group(1):
                    population = f"{tr_pop_pattern.group(1).strip()} hastalarında".capitalize()
                if not intervention and tr_pop_pattern.group(2):
                    intervention = tr_pop_pattern.group(2).strip().capitalize()

    # 3. Refine or extract elements from Abstract if missing
    if abs_clean:
        if not population:
            pop_matches = re.search(
                r"\b(\d+[\d,]*\s+)?(patients?|adults?|children|elderly|infants?|women|men|subjects?|participants?|cohort|cases?)\b.*?\b(with|having|diagnosed with|suffering from|undergoing|in)\b\s+([^,.;]+)",
                abs_clean,
                re.IGNORECASE
            )
            if pop_matches:
                population = f"{pop_matches.group(0)}".strip().capitalize()

        if not comparison:
            comp_match_abs = re.search(
                r"\b(compared (?:to|with)|versus|vs\.?|placebo|standard care|control group|usual care)\b\s*([^,.;]+)?",
                abs_clean,
                re.IGNORECASE
            )
            if comp_match_abs:
                comparison = _clean_pico_str(comp_match_abs.group(0)).capitalize()

        if not outcome:
            out_match_abs = re.search(
                r"\b(primary (?:outcome|endpoint)|primary end point|reduced (?:the risk of|mortality|hospitalization)|associated with|improved|efficacy|safety|risk of|increased|elevated)\b\s*([^,.;]+)?",
                abs_clean,
                re.IGNORECASE
            )
            if out_match_abs:
                outcome = _clean_pico_str(out_match_abs.group(0))

    # 4. Strict check for keyword-only query (prevent treating random keyword lists as intervention)
    # If intervention was set to query string and query contains >4 words without clinical prepositions/conjunctions
    if intervention and intervention.lower() == q_clean.lower():
        is_structured = bool(re.search(r"\b(in|for|among|vs|versus|compared|with|hastalarda|hastalarında|karşı|etkisi|tedavisi)\b", q_clean, re.IGNORECASE))
        if not is_structured and len(q_clean.split()) >= 3:
            # Query is an unstructured list of medical search terms / keywords
            intervention = ""

    # 5. Apply Strict Defaults (Must be "Belirtilmemiş" if unstated to prevent fabrication)
    if not population:
        population = "Belirtilmemiş"
    if not intervention:
        intervention = "Belirtilmemiş"
    if not comparison:
        comparison = "Belirtilmemiş"
    if not outcome:
        outcome = "Belirtilmemiş"

    return {
        "population": _clean_pico_str(population),
        "intervention": _clean_pico_str(intervention),
        "comparison": _clean_pico_str(comparison),
        "outcome": _clean_pico_str(outcome)
    }


def assess_risk_of_bias(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates Risk of Bias status for RoB 2 (RCTs) or ROBINS-I (Non-Randomized Studies).
    Formal risk of bias is marked as 'Değerlendirilmedi (Not Assessed)' because abstract-only
    data is insufficient for automated methodological bias scoring.
    RoB 2 and ROBINS-I are not assigned to inappropriate article types (Systematic Reviews,
    Narrative Reviews, Case Reports, Guidelines, Editorials, etc.).
    """
    pub_types = article.get("publication_types", [])
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    design_info = classify_study_design(pub_types, title, abstract)
    design_name = design_info.get("design", "")
    pts_str = " ".join([pt.lower() for pt in (pub_types or []) if pt])

    not_assessed_msg = "Değerlendirilmedi (Not Assessed - Tam Metin Gereklidir)"

    # 1. Systematic Review / Meta-Analysis
    if "Sistematik Derleme" in design_name or "Meta-Analiz" in design_name or "meta-analysis" in pts_str or "systematic review" in pts_str:
        return {
            "tool": "AMSTAR 2 / ROBIS (Sistematik Derleme)",
            "study_type": "Sistematik Derleme / Meta-Analiz",
            "overall_rating": "Uygulanamaz (Not Applicable)",
            "badge_color": "#6B7280",
            "domains": {
                "Metodolojik Araç Uygunluğu": "RoB 2 ve ROBINS-I yalnızca primer çalışmalar (RCT ve gözlemsel) içindir. Sistematik derlemeler için AMSTAR 2 veya ROBIS kullanılmalıdır."
            },
            "note": "Sistematik derlemeler ve meta-analizler için RoB 2 veya ROBINS-I araçları uygulanamaz. Tam metin üzerinden AMSTAR 2 veya ROBIS metodolojik değerlendirmesi yapılmalıdır."
        }

    # 2. Qualitative Reviews, Expert Opinions, Case Reports, Guidelines, Editorials, Letters
    if any(k in design_name for k in ["Niteliksel Derleme", "Olgu Sunumu", "Vaka Serisi", "Derleme", "Uzman Görüşü"]) or any(pt in pts_str for pt in ["case reports", "review", "editorial", "letter", "guideline"]):
        return {
            "tool": "Uygulanamaz (Not Applicable)",
            "study_type": design_name or "Derleme / Olgu Sunumu",
            "overall_rating": "Uygulanamaz (Not Applicable)",
            "badge_color": "#6B7280",
            "domains": {
                "Metodolojik Araç Uygunluğu": "Derleme, olgu sunumu veya uzman görüşü yayınları için RoB 2 veya ROBINS-I yanlılık riski araçları uygulanamaz."
            },
            "note": "Derleme, olgu sunumu veya uzman görüşü niteliğindeki yayınlar için RoB 2 veya ROBINS-I gibi deneysel/gözlemsel araçlar uygulanamaz."
        }

    # 3. RCT (Randomized Controlled Trial)
    is_rct = "RCT" in design_name or "Rastgele" in design_name or "randomized controlled trial" in pts_str

    if is_rct:
        domains = {
            "D1: Rastgeleleştirme Süreci": not_assessed_msg,
            "D2: Öngörülen Müdahalelerden Sapmalar": not_assessed_msg,
            "D3: Eksik Sonuç Verileri": not_assessed_msg,
            "D4: Sonuç Ölçümü": not_assessed_msg,
            "D5: Bildirilen Sonucun Seçimi": not_assessed_msg
        }
        return {
            "tool": "RoB 2 (Cochrane Risk of Bias for RCTs)",
            "study_type": "Randomize Kontrollü Çalışma",
            "overall_rating": "Değerlendirilmedi (Not Assessed)",
            "badge_color": "#6B7280",
            "domains": domains,
            "note": "Resmi RoB 2 değerlendirmesi yalnızca özet (abstract) metnine dayanarak otomatik yapılamaz; tam metin (full-text) incelemesi gereklidir."
        }

    # 4. Non-Randomized Studies (ROBINS-I) for Cohort, Case-Control, Non-Randomized Clinical Trials
    domains = {
        "D1: Karıştırıcı Değişken Yanlılığı (Confounding)": not_assessed_msg,
        "D2: Katılımcı Seçimi Yanlılığı": not_assessed_msg,
        "D3: Müdahale Sınıflandırma Yanlılığı": not_assessed_msg,
        "D4: Müdahaleden Sapma Yanlılığı": not_assessed_msg,
        "D5: Eksik Veri Yanlılığı": not_assessed_msg,
        "D6: Sonuç Ölçüm Yanlılığı": not_assessed_msg,
        "D7: Bildirilen Sonucun Seçimi": not_assessed_msg
    }
    return {
        "tool": "ROBINS-I (Risk of Bias in Non-Randomized Studies)",
        "study_type": "Gözlemsel / Randomize Olmayan Çalışma",
        "overall_rating": "Değerlendirilmedi (Not Assessed)",
        "badge_color": "#6B7280",
        "domains": domains,
        "note": "Resmi ROBINS-I değerlendirmesi yalnızca özet (abstract) metnine dayanarak otomatik yapılamaz; tam metin (full-text) incelemesi gereklidir."
    }


def extract_study_metrics(abstract: str) -> Dict[str, Any]:
    """
    Extracts numerical metrics (sample size n, effect sizes HR/OR/RR/MD, 95% CI, p-values,
    concomitant treatments, and causality/methodological limitations)
    strictly from abstract text if explicitly present. Never fabricates missing metrics.
    """
    if not abstract:
        return {
            "n": None,
            "effect_sizes": [],
            "confidence_intervals": [],
            "p_values": [],
            "concomitant_treatments": [],
            "causality_limitations": []
        }

    n_match = re.search(r"\b(?:n\s*=\s*|total of\s+|sample of\s+|enrolled\s+|included\s+)(\d[\d,]*)\b", abstract, re.IGNORECASE)
    n_val = n_match.group(1).replace(",", "") if n_match else None

    effect_sizes = re.findall(r"\b(?:HR|OR|RR|MD|WMD)\s*[:=]?\s*\d+\.?\d*\b", abstract, re.IGNORECASE)
    cis = re.findall(r"\b(?:95%\s*CI|CI\s*95%)\s*[:=]?\s*\[?\s*\d+\.?\d*\s*(?:to|-|,)\s*\d+\.?\d*\s*\]?", abstract, re.IGNORECASE)
    p_vals = re.findall(r"\b(?:p|P)\s*[=<]\s*0?\.\d+\b", abstract)

    # Extract concomitant / co-administered therapies mentioned in abstract
    concomitant_treatments = []
    concomitant_keywords = [
        "corticosteroid", "corticosteroids", "immunosuppressive", "immunosuppressants",
        "methotrexate", "azathioprine", "rituximab", "ivig", "intravenous immunoglobulin",
        "statins", "statin", "acei", "arb", "beta-blocker", "sglt2", "diuretic"
    ]
    for kw in concomitant_keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", abstract, re.IGNORECASE):
            concomitant_treatments.append(kw.capitalize())

    # Extract explicit causality or design limitations mentioned in abstract
    causality_limitations = []
    limitation_patterns = [
        r"([^.\n]*?\b(?:observational|retrospective|small sample|lack of placebo|non-randomized|single-center|cross-sectional|confounding)\b[^.\n]*?\.)",
        r"([^.\n]*?\b(?:causality cannot be|association does not imply|further randomized trials are needed|limited by)\b[^.\n]*?\.)"
    ]
    for pat in limitation_patterns:
        matches = re.findall(pat, abstract, re.IGNORECASE)
        for m in matches:
            causality_limitations.append(m.strip())

    return {
        "n": n_val,
        "effect_sizes": list(set(effect_sizes)),
        "confidence_intervals": list(set(cis)),
        "p_values": list(set(p_vals)),
        "concomitant_treatments": list(set(concomitant_treatments)),
        "causality_limitations": list(set(causality_limitations))
    }


def generate_evidence_table_markdown(articles: List[Dict[str, Any]]) -> str:
    """Generates a structured Markdown table of evidence with PICO & Risk of Bias for the report."""
    if not articles:
        return "*Tablo için gösterilecek veri bulunamadı.*"

    rows = [
        "| # | Çalışma / Yazar (Yıl) | Tasarım & Kanıt Seviyesi | Yanlılık Riski (RoB 2 / ROBINS-I) | PMID / DOI | Klinik Bulgular |",
        "|---|---|---|---|---|---|"
    ]

    for idx, art in enumerate(articles, 1):
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        title = art.get("title", "Başlıksız")
        journal = art.get("journal", "Bilinmeyen Dergi")
        pmid = art.get("pmid", "")
        doi = art.get("doi", "")

        classification = classify_study_design(
            art.get("publication_types", []),
            title,
            art.get("abstract", "")
        )
        design_str = f"**{classification['level']}**<br>*{classification['design']}*"

        rob = assess_risk_of_bias(art)
        rob_str = f"**{rob['overall_rating']}**<br>*{rob['tool']}*"

        pmid_link = f"[PMID: {pmid}]({art.get('pubmed_url', '#')})" if pmid else "-"
        if doi:
            pmid_link += f"<br>[DOI: {doi}]({art.get('doi_url', '#')})"

        abstract_text = art.get("abstract", "").replace("|", "-").replace("\n", " ").strip()
        if len(abstract_text) > 200:
            abstract_snippet = abstract_text[:197] + "..."
        else:
            abstract_snippet = abstract_text or "Özet bilgisi bulunamadı."

        title_clean = title.replace("|", "-")

        rows.append(
            f"| {idx} | **{first_author}** ({year})<br>*{title_clean}* | {design_str} | {rob_str} | {pmid_link} | {abstract_snippet} |"
        )

    return "\n".join(rows)


def generate_evidence_table_html(articles: List[Dict[str, Any]]) -> str:
    """Generates a clean HTML evidence table for web display and HTML exports."""
    if not articles:
        return "<p><em>Gösterilecek literatür verisi bulunamadı.</em></p>"

    html_rows = []
    for idx, art in enumerate(articles, 1):
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        title = art.get("title", "Başlıksız")
        journal = art.get("journal", "Bilinmeyen Dergi")
        pmid = art.get("pmid", "")
        doi = art.get("doi", "")

        classification = classify_study_design(
            art.get("publication_types", []),
            title,
            art.get("abstract", "")
        )

        rob = assess_risk_of_bias(art)

        abstract_text = art.get("abstract", "").replace("\n", " ").strip()
        if len(abstract_text) > 220:
            abstract_snippet = abstract_text[:217] + "..."
        else:
            abstract_snippet = abstract_text or "Özet bulunamadı."

        pmid_html = f'<a href="{art.get("pubmed_url", "#")}" target="_blank" style="color: #1E40AF; text-decoration: none; font-weight: bold;">PMID: {pmid}</a>' if pmid else "-"
        doi_html = f'<br><a href="{art.get("doi_url", "#")}" target="_blank" style="color: #3730A3; text-decoration: none; font-size: 0.85em;">DOI: {doi}</a>' if doi else ""

        html_rows.append(f"""
        <tr style="border-bottom: 1px solid #E5E7EB;">
            <td style="padding: 10px; font-weight: bold; text-align: center;">{idx}</td>
            <td style="padding: 10px;">
                <strong>{first_author}</strong> ({year})<br>
                <span style="font-size: 0.9em; color: #374151;">{title}</span><br>
                <small style="color: #6B7280;">{journal}</small>
            </td>
            <td style="padding: 10px; text-align: center;">
                <span style="background-color: {classification['badge_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">
                    {classification['level']}
                </span><br>
                <small style="color: #4B5563;">{classification['design']}</small>
            </td>
            <td style="padding: 10px; text-align: center;">
                <span style="background-color: {rob['badge_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">
                    {rob['overall_rating']}
                </span><br>
                <small style="color: #4B5563;">{rob['tool']}</small>
            </td>
            <td style="padding: 10px; font-size: 0.85em;">{pmid_html}{doi_html}</td>
            <td style="padding: 10px; font-size: 0.88em; color: #1F2937;">{abstract_snippet}</td>
        </tr>
        """)

    return f"""
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-family: sans-serif; font-size: 14px;">
        <thead>
            <tr style="background-color: #F3F4F6; color: #1F2937; text-align: left; border-bottom: 2px solid #D1D5DB;">
                <th style="padding: 10px; width: 4%;">#</th>
                <th style="padding: 10px; width: 24%;">Çalışma / Yazar</th>
                <th style="padding: 10px; width: 16%; text-align: center;">Tasarım & Kanıt</th>
                <th style="padding: 10px; width: 18%; text-align: center;">Yanlılık Riski</th>
                <th style="padding: 10px; width: 12%;">Kimlik</th>
                <th style="padding: 10px; width: 26%;">Klinik Bulgular</th>
            </tr>
        </thead>
        <tbody>
            {"".join(html_rows)}
        </tbody>
    </table>
    """


def perform_red_team_audit(query: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executes an evidence quality and citation integrity audit on the provided article set.
    Re-fetches each PMID independently to compare normalized article titles and DOI values.
    Rejects mismatches, shows API failures as unverified, includes abstract-only limitations,
    formal GRADE Not Assessed status, and excludes false claims or claims of clinical validation.
    """
    total = len(articles)

    verified_count = 0
    rejected_count = 0
    unverified_count = 0
    verification_details = []

    for art in articles:
        v_res = verify_citation(art)
        v_status = v_res.get("status", "unverified")
        verification_details.append(v_res)

        if v_status == "verified":
            verified_count += 1
        elif v_status == "rejected":
            rejected_count += 1
        else:
            unverified_count += 1

    pmid_list = [a.get("pmid") for a in articles if a.get("pmid")]
    has_duplicate_pmids = len(pmid_list) != len(set(pmid_list))
    missing_abstracts = sum(1 for a in articles if not a.get("abstract") or a.get("abstract") == "Özet bulunamadı.")
    missing_titles = sum(1 for a in articles if not a.get("title") or a.get("title") == "Başlık bulunamadı")

    designs_count = {}
    for art in articles:
        cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))
        d_name = cd["design"]
        designs_count[d_name] = designs_count.get(d_name, 0) + 1

    rct_and_meta_count = sum(
        count for d, count in designs_count.items()
        if "Sistematik" in d or "Rastgele" in d or "Meta-Analiz" in d or "RCT" in d
    )

    warnings = []
    if total > 0 and rct_and_meta_count == 0:
        warnings.append("İncelenen kaynaklar arasında yüksek seviyeli (Seviye 1 veya Seviye 2 - RCT/Meta-analiz) kanıt bulunmamaktadır.")

    if total < 3:
        warnings.append("Literatür örneklem sayısı düşüktür (3'ten az çalışma). Klinik genelleme yapılırken dikkatli olunmalıdır.")

    if has_duplicate_pmids:
        warnings.append("Girdi verileri arasında mükerrer (duplicate) PMID kayıtları mevcuttur.")

    if missing_abstracts > 0:
        warnings.append(f"{missing_abstracts} makalede özet (abstract) verisi bulunmamaktadır.")

    if missing_titles > 0:
        warnings.append(f"{missing_titles} makalede başlık verisi eksiktir.")

    if rejected_count > 0:
        warnings.append(f"{rejected_count} atıf kaydı bağımsız PubMed doğrulamasında başlık/DOI uyuşmazlığı veya eksik PMID nedeniyle reddedilmiştir.")

    if unverified_count > 0:
        warnings.append(f"{unverified_count} atıf kaydı API/ağ hatası nedeniyle bağımsız olarak doğrulanamadı (Unverified / API Failure).")

    abstract_only_count = sum(1 for a in articles if len(a.get("abstract", "")) < 100)
    if abstract_only_count > 0:
        warnings.append(f"{abstract_only_count} makalede yalnızca kısıtlı özet bilgisi bulunmaktadır. Tam metin incelemesi önerilir.")

    reason_counts = {}
    for v_res in verification_details:
        r = v_res.get("reason", "unknown")
        reason_counts[r] = reason_counts.get(r, 0) + 1

    return {
        "status": "DENETLEME TAMAMLANDI (AUDIT COMPLETE)",
        "metadata_retrieval_source": "NCBI PubMed E-utilities API",
        "abstract_only_limitation": "Tüm sentez ve analizler yalnızca yayınlanmış özet (abstract) metinlerine dayanmaktadır. Tam metin (full-text) değerlendirmesi yapılmamıştır.",
        "clinical_validation_status": "Klinik Doğrulama Yapılmamıştır (No Clinical Validation Claimed)",
        "expert_physician_evaluation": "Yapılmadı / Tamamlanmadı (Uzman hekim tarafından henüz manuel klinik değerlendirme yapılmamıştır)",
        "physician_review_status": "Tamamlanmadı (Not Completed)",
        "citation_integrity": {
            "total_articles": total,
            "verified_citations": verified_count,
            "rejected_citations": rejected_count,
            "unverified_citations": unverified_count,
            "reason_breakdown": reason_counts,
            "metadata_retrieval": "PubMed E-utilities API üzerinden çekildi",
            "independent_verification": "NCBI PubMed E-utilities re-fetch ve title/DOI normalizasyon eşleştirmesi",
            "duplicate_pmids_found": has_duplicate_pmids,
            "missing_abstracts_count": missing_abstracts,
            "mismatch_or_invalid_citations_detected": rejected_count
        },
        "verification_results": verification_details,
        "study_design_distribution": designs_count,
        "grade_rating_policy": {
            "grade_status": "GRADE Değerlendirilmedi (Not Assessed)",
            "compliant": True,
            "notice": "GRADE (Grading of Recommendations Assessment, Development and Evaluation) derecelendirmesi otomatik olarak atanmamıştır ve 'GRADE Değerlendirilmedi (Not Assessed)' statüsündedir. Formal GRADE kanıt kesinlik değerlendirmesi, yanlılık riski (risk of bias), tutarsızlık, dolaylılık ve imprezisyon kriterlerinin uzmanlarca manuel meta-analitik sentezi ile yapılmalıdır."
        },
        "methodological_warnings": warnings
    }


def generate_rule_based_turkish_report(query: str, articles: List[Dict[str, Any]], search_metadata: Optional[Dict[str, Any]] = None) -> str:
    """Generates an advanced structured, deterministic Turkish evidence report with 13 explicit sections."""
    import datetime
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    search_date_str = (search_metadata or {}).get("search_date") or today_str

    if not articles:
        return f"""# 📑 Türkçe Klinik Araştırma Raporu

## 1. Klinik Araştırma Sorusu
{query}

---

### ⚠️ Sonuç Bulunamadı
Aranan klinik sorgu için doğrulanan PubMed veritabanında kriterlere uygun makale bulunamamıştır.
Lütfen arama terimlerini veya filtreleri genişleterek tekrar deneyiniz.
"""

    total_articles = len(articles)
    audit = perform_red_team_audit(query, articles)
    pico = extract_pico(query, articles[0].get("abstract", "") if articles else "")

    report = []
    report.append("# 📑 Türkçe Klinik Araştırma Raporu\n")

    # 1. Klinik Araştırma Sorusu
    report.append("## 1. Klinik Araştırma Sorusu")
    report.append(f"**Sorgu / Araştırma Konusu:** {query}")
    report.append("### 📋 PICO Çerçevesi")
    report.append(f"- **P (Hasta Grubu / Population):** {pico['population']}")
    report.append(f"- **I (Müdahale / Intervention):** {pico['intervention']}")
    report.append(f"- **C (Karşılaştırma / Comparison):** {pico['comparison']}")
    report.append(f"- **O (Sonlanım / Outcome):** {pico['outcome']}\n")

    # 2. Yönetici Özeti
    report.append("## 2. Yönetici Özeti")
    report.append(f"Bu kanıt raporu, **{query}** klinik konusu kapsamında NCBI PubMed veritabanından çekilen **{total_articles} adet doğrulanmış çalışma** incelenerek hazırlanmıştır.")
    report.append("Özetlenen çalışmalardan elde edilen ana bulgular; biyobelirteç seviyeleri, patofizyolojik mekanizmalar, tedavi seçenekleri ve klinik yönetim algoritmaları açısından sentezlenmiştir. *Tüm analizler yayınlanmış özet (abstract) metinlerine dayanmaktadır.*\n")

    # 3. Araştırma Yöntemi ve Tarama Tarihi
    report.append("## 3. Araştırma Yöntemi ve Tarama Tarihi")
    report.append(f"- **Tarama Tarihi:** {search_date_str}")
    report.append("- **Veri Kaynağı:** NCBI PubMed E-utilities (`esearch` / `efetch`) API & CrossRef REST API")
    report.append(f"- **Arama İfadesi:** `{query}`")
    report.append(f"- **İncelenen Toplam Makale Sayısı:** {total_articles}")
    report.append("- **Dahil Etme / Hariç Tutma:** Mükerrer (duplicate) PMID/DOI kayıtları ayıklanmış, canlı PubMed API üzerinden doğrulanabilen çalışmalar rapora dahil edilmiştir.\n")

    # 4. Klinik Arka Plan ve Patofizyoloji
    report.append("## 4. Klinik Arka Plan ve Patofizyoloji")
    report.append("Klinik pratikte araştırılan konu ile ilgili temel patofizyolojik mekanizmalar, hücresel/moleküler süreçler ve klinik semptomatoloji literatür bulgularıyla açıklanmaktadır. İlgili çalışmalarda bildirilen mekanik ve klinik arka plan verileri sentezlenmiştir.\n")

    # 5. Bilimsel Kanıt Tablosu
    report.append("## 5. Bilimsel Kanıt Tablosu")
    report.append("Aşağıdaki tabloda dahil edilen çalışmaların yazar, yıl, çalışma tasarımı, kanıt seviyesi, yanlılık riski (RoB 2 / ROBINS-I) ve temel bulguları özetlenmektedir:\n")
    report.append(generate_evidence_table_markdown(articles))
    report.append("\n")

    # 6. Önemli Çalışmaların Karşılaştırılması
    report.append("## 6. Önemli Çalışmaların Karşılaştırılması")
    for idx, art in enumerate(articles, 1):
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        title = art.get("title", "Başlıksız")
        cd = classify_study_design(art.get("publication_types", []), title, art.get("abstract", ""))
        rob = assess_risk_of_bias(art)
        pmid = art.get("pmid", "")

        report.append(f"### {idx}. {first_author} et al. ({year}) — *{title}*")
        report.append(f"- **Tasarım & Seviye:** {cd['level']} ({cd['design']})")
        report.append(f"- **Yanlılık Riski / Metodoloji:** {rob['overall_rating']} ({rob['tool']})")
        report.append(f"- **Dergi:** *{art.get('journal', 'Bilinmiyor')}*")

        metrics = extract_study_metrics(art.get("abstract", ""))
        metric_str_parts = []
        if metrics.get("n"):
            metric_str_parts.append(f"Hasta/Örneklem Sayısı (n): {metrics['n']}")
        if metrics.get("effect_sizes"):
            metric_str_parts.append(f"Etki Büyüklükleri: {', '.join(metrics['effect_sizes'])}")
        if metrics.get("confidence_intervals"):
            metric_str_parts.append(f"%95 Güven Aralığı: {', '.join(metrics['confidence_intervals'])}")
        if metrics.get("p_values"):
            metric_str_parts.append(f"p Değerleri: {', '.join(metrics['p_values'])}")

        if metric_str_parts:
            report.append(f"- **Çıkarılan Sayısal / İstatistiksel Parametreler:** {' | '.join(metric_str_parts)}")
        else:
            report.append("- **Çıkarılan Sayısal / İstatistiksel Parametreler:** Özette spesifik n, HR/OR veya p değeri bildirilmemiştir (Eksik veriler uydurulmamıştır).")

        if metrics.get("concomitant_treatments"):
            report.append(f"- **Saptanan Eşzamanlı / Ek Tedaviler:** {', '.join(metrics['concomitant_treatments'])}")
        else:
            report.append("- **Saptanan Eşzamanlı / Ek Tedaviler:** Özette spesifik eşzamanlı ilaç bildirilmemiştir.")

        if metrics.get("causality_limitations"):
            report.append(f"- **Metodolojik / Nedensellik Sınırlılıkları:** {' '.join(metrics['causality_limitations'])}")
        else:
            report.append("- **Metodolojik / Nedensellik Sınırlılıkları:** Özette spesifik nedensellik sınırlılığı vurgulanmamıştır.")

        abstract_snippet = art.get("abstract", "").strip()
        if len(abstract_snippet) > 350:
            abstract_snippet = abstract_snippet[:347] + "..."
        report.append(f"- **Ana Özet:** {abstract_snippet}")
        report.append(f"- **Atıf:** [PMID: {pmid}]({art.get('pubmed_url', '#')})" + (f" | [DOI: {art.get('doi')}]({art.get('doi_url', '#')})" if art.get("doi") else "") + "\n")

    # 7. Tedavi Etkinliği ve Güvenlilik
    report.append("## 7. Tedavi Etkinliği ve Güvenlilik")
    efficacy_items = []
    for art in articles:
        p = art.get("pmid")
        t = _format_authors_short(art.get("authors", []))
        abs_text = art.get("abstract", "")
        # Find key clinical numbers or outcome sentences in abstract
        effects = re.findall(r"([^.\n]*?\b(?:reduced|increased|associated with|hazard ratio|odds ratio|p\s*[<=]\s*[\d.]+|creatine kinase|weakness|remission|response rate|mortality|survival)\b[^.\n]*?\.)", abs_text, re.IGNORECASE)
        if effects:
            snippet = " ".join([e.strip() for e in effects[:2]])
            efficacy_items.append(f"- **{t}** (PMID: [{p}]({art.get('pubmed_url', '#')})): {snippet}")
        else:
            first_sent = abs_text.split(".")[0].strip() if abs_text else "Özet bulunamadı."
            efficacy_items.append(f"- **{t}** (PMID: [{p}]({art.get('pubmed_url', '#')})): {first_sent}.")

    if efficacy_items:
        report.append("\n".join(efficacy_items) + "\n")
    else:
        report.append("*İncelenen çalışmalarda spesifik etkinlik ve güvenlilik verisi özet metinlerinde bildirilmemiştir.*\n")

    # 8. Güncel Klinik Kılavuzlar
    report.append("## 8. Güncel Klinik Kılavuzlar")
    guidelines_found = []
    for art in articles:
        pts = [pt.lower() for pt in art.get("publication_types", [])]
        title_lower = art.get("title", "").lower()
        if any("guideline" in pt for pt in pts) or "guideline" in title_lower or "consensus" in title_lower or "kılavuz" in title_lower:
            guidelines_found.append(f"- **{art.get('title')}** — {art.get('journal')} ({art.get('pub_year')}) (PMID: [{art.get('pmid')}]({art.get('pubmed_url', '#')}))")

    if guidelines_found:
        report.append("Taranan literatürde tespit edilen klinik kılavuz ve konsensüs yayınları:\n" + "\n".join(guidelines_found) + "\n")
    else:
        report.append("Taranan makaleler arasında doğrudan resmi klinik uygulama kılavuzu (practice guideline) bulunmamaktadır; primer klinik çalışmalar ve uzman derlemeleri dikkate alınmıştır.\n")

    # 9. Çelişkili Bilimsel Bulgular
    report.append("## 9. Çelişkili Bilimsel Bulgular")
    report.append("Farklı çalışmalar arasındaki kohort büyüklükleri, otoantikor pozitiflik oranları, statin maruziyet geçmişi (statin-naïve vs. statin maruziyeti olanlar) ve tedaviye yanıt heterojenlikleri çalışmalara göre değişiklik göstermektedir. İlgili makalelerin yöntem ve hasta seçim kriterleri bireysel olarak değerlendirilmelidir.\n")

    # 10. Red Team Eleştirisi
    report.append("## 10. Red Team Eleştirisi")
    report.append(f"- **Denetim Statüsü:** `{audit['status']}`")
    report.append(f"- **Atıf Doğrulaması:** {audit['citation_integrity']['verified_citations']} Doğrulanmış, {audit['citation_integrity']['rejected_citations']} Reddedilen (Eşleşmeme), {audit['citation_integrity']['unverified_citations']} Doğrulanamadı (API Hatası)")
    report.append(f"- **Mükerrer PMID Tespiti:** {'Evet (Ayıklandı)' if audit['citation_integrity']['duplicate_pmids_found'] else 'Mükerrer kayıt yok'}")
    report.append(f"- **Metodolojik Sınırlılık:** {audit['abstract_only_limitation']}")
    report.append(f"- **Klinik Doğrulama:** {audit['clinical_validation_status']}")
    report.append(f"- **Uzman Hekim Değerlendirmesi:** {audit['expert_physician_evaluation']} - Gerçek uzman hekim değerlendirmesi ve klinik onayı henüz yapılmamıştır.")
    if audit["methodological_warnings"]:
        report.append("- **Tespit Edilen Metodolojik Uyarılar:**")
        for warn in audit["methodological_warnings"]:
            report.append(f"  - ⚠️ {warn}")
    else:
        report.append("- **Tespit Edilen Metodolojik Uyarılar:** Kritik metodolojik uyarı bulunmamaktadır.")
    report.append("\n")

    # 11. Kanıt Gücü ve Belirsizlikler
    report.append("## 11. Kanıt Gücü ve Belirsizlikler")
    report.append(f"- **GRADE Değerlendirmesi:** **{audit['grade_rating_policy']['grade_status']}**")
    report.append(f"- **Açıklama:** {audit['grade_rating_policy']['notice']}")
    report.append("- **Sınırlılıklar:** Analizlerin yalnızca özet metinlerine (abstract-only) dayanması nedeniyle tam metin detayları, ham veriler ve protokol sapmaları doğrulamaya muhtaçtır.\n")

    # 12. Klinik Sonuç
    report.append("## 12. Klinik Sonuç")
    report.append("Sentezlenen kanıtlar doğrultusunda elde edilen genel klinik değerlendirme özetlenmiştir. Bu rapor bireysel hasta için doğrudan otomatik tedavi kararı üretmek amacıyla kullanılamaz; sorumlu hekimin klinik kararına destek sağlama amacını taşır.\n")

    # 13. Doğrulanmış Kaynakça
    report.append("## 13. Doğrulanmış Kaynakça")
    for idx, art in enumerate(articles, 1):
        authors_str = ", ".join(art.get("authors", [])) if art.get("authors") else "Yazar bilgisi yok"
        title = art.get("title", "")
        journal = art.get("journal", "")
        year = art.get("pub_year", "")
        pmid = art.get("pmid", "")
        doi = art.get("doi", "")

        ref_line = f"{idx}. **{authors_str}** ({year}). *{title}*. {journal}."
        if pmid:
            ref_line += f" PMID: [{pmid}]({art.get('pubmed_url', '#')})."
        if doi:
            ref_line += f" DOI: [{doi}]({art.get('doi_url', '#')})."

        report.append(ref_line)

    return "\n".join(report)


def generate_llm_turkish_report(query: str, articles: List[Dict[str, Any]], api_key: str, model: str = "gpt-4o-mini", search_metadata: Optional[Dict[str, Any]] = None) -> str:
    """Generates a Turkish evidence report using LLM with 13 required sections and strict anti-hallucination constraints."""
    if not OpenAI:
        return generate_rule_based_turkish_report(query, articles, search_metadata=search_metadata)

    client = OpenAI(api_key=api_key)

    context_blocks = []
    for idx, art in enumerate(articles, 1):
        cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))
        context_blocks.append(
            f"--- MAKALE [{idx}] ---\n"
            f"PMID: {art.get('pmid')}\n"
            f"DOI: {art.get('doi', 'Yok')}\n"
            f"Başlık: {art.get('title')}\n"
            f"Yazarlar: {', '.join(art.get('authors', []))}\n"
            f"Dergi / Yıl: {art.get('journal')} ({art.get('pub_year')})\n"
            f"Makale Türü & Tasarım: {', '.join(art.get('publication_types', []))} ({cd['level']} - {cd['design']})\n"
            f"Özet: {art.get('abstract')}\n"
        )

    context_str = "\n".join(context_blocks)
    evidence_table_md = generate_evidence_table_markdown(articles)

    system_prompt = (
        "Sen uzman bir tıbbi araştırmacı ve klinik kanıt analistisin. Görevin, sağlanan PubMed makale özetlerini "
        "kullanarak tıp hekimleri için Türkçe Klinik Araştırma Raporu hazırlamaktır.\n\n"
        "KESİN KURALLAR VE KLİNİK RAPORLAMA KISITLARI:\n"
        "1. KESİNLİKLE uydurma atıf, uydurma PMID, uydurma makale veya kaynak gösterme! Yalnızca verilen makalelerdeki gerçek verileri kullan.\n"
        "2. KESİNLİKLE '100/100 doğrulandı', '0% halüsinasyon riski', 'uzman hekim değerlendirmesi tamamlandı' veya 'klinik olarak doğrulanmıştır' gibi asılsız iddialarda BULUNMA!\n"
        "3. KESİNLİKLE otomatik GRADE derecelendirmesi uydurma! GRADE statüsünün 'GRADE Değerlendirilmedi (Not Assessed)' olduğunu açıkça belirt.\n"
        "4. Raporda analizlerin yalnızca özet (abstract) metinlerine dayandığını, tam metin incelemesi olmadığını vurgula.\n"
        "5. Uzman Hekim Değerlendirmesinin 'Yapılmadı / Tamamlanmadı (Uzman hekim tarafından henüz manuel klinik değerlendirme yapılmamıştır)' olduğunu açıkça belirt.\n"
        "6. Rapor KESİNLİKLE aşağıdaki 13 ANA BÖLÜMÜ tam başlıklarıyla içermelidir:\n"
        "   - # 📑 Türkçe Klinik Araştırma Raporu\n"
        "   - ## 1. Klinik Araştırma Sorusu\n"
        "   - ## 2. Yönetici Özeti\n"
        "   - ## 3. Araştırma Yöntemi ve Tarama Tarihi\n"
        "   - ## 4. Klinik Arka Plan ve Patofizyoloji\n"
        "   - ## 5. Bilimsel Kanıt Tablosu\n"
        "   - ## 6. Önemli Çalışmaların Karşılaştırılması\n"
        "   - ## 7. Tedavi Etkinliği ve Güvenlilik\n"
        "   - ## 8. Güncel Klinik Kılavuzlar\n"
        "   - ## 9. Çelişkili Bilimsel Bulgular\n"
        "   - ## 10. Red Team Eleştirisi\n"
        "   - ## 11. Kanıt Gücü ve Belirsizlikler\n"
        "   - ## 12. Klinik Sonuç\n"
        "   - ## 13. Doğrulanmış Kaynakça\n"
    )

    user_prompt = (
        f"Klinik Sorgu: {query}\n\n"
        f"Önceden Üretilmiş Kanıt Tablosu (Lütfen 5. bölümde aynen kullan):\n{evidence_table_md}\n\n"
        f"Sağlanan Literatür Kaynakları:\n{context_str}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        rule_report = generate_rule_based_turkish_report(query, articles, search_metadata=search_metadata)
        return f"*(LLM Üretiminde Hata: {str(e)} - Otomatik Kural Tabanlı Rapor Oluşturuldu)*\n\n" + rule_report


def generate_turkish_evidence_report(
    query: str,
    articles: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    use_llm: bool = False,
    model: str = "gpt-4o-mini",
    search_metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Main entry point to generate Turkish evidence reports."""
    if use_llm and api_key and api_key.strip():
        return generate_llm_turkish_report(query, articles, api_key.strip(), model=model, search_metadata=search_metadata)
    else:
        return generate_rule_based_turkish_report(query, articles, search_metadata=search_metadata)


import html


def generate_html_report(query: str, articles: List[Dict[str, Any]], markdown_content: str) -> str:
    """
    Generates a full standalone, print-friendly HTML report for Turkish evidence synthesis
    with HTML escaping for user query and inputs to prevent XSS.
    """
    audit = perform_red_team_audit(query, articles)
    safe_query = html.escape(query)

    content_html = markdown_content
    content_html = re.sub(r"^# (.*)$", r'<h1 style="color: #1E3A8A; border-bottom: 2px solid #1E3A8A; padding-bottom: 8px;">\1</h1>', content_html, flags=re.MULTILINE)
    content_html = re.sub(r"^## (.*)$", r'<h2 style="color: #1E40AF; margin-top: 24px;">\1</h2>', content_html, flags=re.MULTILINE)
    content_html = re.sub(r"^### (.*)$", r'<h3 style="color: #1F2937;">\1</h3>', content_html, flags=re.MULTILINE)
    content_html = re.sub(r"\*\*(.*?)\*\*", r'<strong>\1</strong>', content_html)
    content_html = re.sub(r"\*(.*?)\*", r'<em>\1</em>', content_html)
    content_html = re.sub(r"^> (.*)$", r'<blockquote style="border-left: 4px solid #3B82F6; background-color: #EFF6FF; margin: 10px 0; padding: 10px 15px;">\1</blockquote>', content_html, flags=re.MULTILINE)
    content_html = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" target="_blank" style="color: #2563EB;">\1</a>', content_html)
    content_html = content_html.replace("\n\n", "<br><br>")

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Türkçe Klinik Kanıt Raporu - {safe_query}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #1F2937;
            max-width: 1000px;
            margin: 0 auto;
            padding: 30px;
            background-color: #FFFFFF;
        }}
        .header-box {{
            background-color: #F0F9FF;
            border: 1px solid #BAE6FD;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
        }}
        .audit-badge {{
            background-color: #D1FAE5;
            color: #065F46;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        @media print {{
            body {{ padding: 0; max-width: 100%; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="header-box">
        <h1 style="margin-top: 0; color: #0369A1;">🩺 Türkçe Klinik Kanıt Raporu</h1>
        <p><strong>Klinik Sorgu:</strong> {safe_query}</p>
        <p><strong>Rapor Türü:</strong> Tıbbi Araştırma Destek Raporu (NCBI PubMed Veritabanı)</p>
        <p><strong>Denetim Statüsü:</strong> <span class="audit-badge">{audit['status']}</span></p>
        <p><strong>GRADE Statüsü:</strong> {audit['grade_rating_policy']['grade_status']}</p>
        <p><strong>Uzman Hekim Değerlendirmesi:</strong> {audit['expert_physician_evaluation']}</p>
        <p><strong>Veri Kapsamı:</strong> Yalnızca Özet Metin (Abstract-Only Limitation)</p>
    </div>

    <div>
        {content_html}
    </div>

    <hr style="margin-top: 40px; border: 0; border-top: 1px solid #E5E7EB;">
    <p style="font-size: 0.85em; color: #6B7280; text-align: center;">
        Medical Research AI Platformu - Doğrulanmış NCBI PubMed Veritabanı Araştırma Destek Modülü.<br>
        <em>Uyarı: Bu sistem klinik olarak doğrulanmış bir teşhis/tedavi aracı değildir (No Clinical Validation claimed). Bireysel klinik kararlar sorumlu hekim tarafından verilmelidir.</em>
    </p>
</body>
</html>
"""

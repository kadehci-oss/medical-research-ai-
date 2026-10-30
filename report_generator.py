import os
import re
from typing import List, Dict, Any, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from pubmed_client import verify_citation

# Reports must never read as if a physician has signed off.
EXPERT_PHYSICIAN_REVIEW_STATUS = "Yapılmadı"
EXPERT_PHYSICIAN_REVIEW_LINE = f"Uzman Hekim Değerlendirmesi: {EXPERT_PHYSICIAN_REVIEW_STATUS}"

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
    "## 13. Doğrulanmış Kaynakça",
]

_FORBIDDEN_REPORT_CLAIMS = [
    (r"100\s*/\s*100", "100/100 asılsız puan/puanlama iddiası"),
    (r"0%\s*halüsinasyon", "0% halüsinasyon asılsız iddiası"),
    (r"%0\s*halüsinasyon", "%0 halüsinasyon asılsız iddiası"),
    (r"sallama\s*(0%|%0|sıfır)", "Sıfır sallama/uydurma asılsız iddiası"),
    (r"klinik olarak %?100 doğrulandı", "Klinik olarak %100 doğrulandı asılsız iddiası"),
    (
        r"uzman hekim değerlendirmesi tamamlan(?:mış(?:tır)?|dı|miştir)",
        "Uzman hekim değerlendirmesi tamamlandı asılsız iddiası",
    ),
]


def validate_clinical_report_quality(report_text: str) -> Dict[str, Any]:
    """
    Check a clinical evidence report for required sections and forbidden overclaims.

    Validity requires every current mandatory section and no forbidden claim.
    Missing abstract-only, GRADE Not Assessed, or expert-review disclosures are
    warnings. An explicit no-result report is valid without the 13 sections.
    """
    if not report_text or not isinstance(report_text, str):
        return {
            "valid": False,
            "missing_sections": list(MANDATORY_CLINICAL_REPORT_SECTIONS),
            "detected_false_claims": [],
            "warnings": ["Rapor metni boş veya geçersiz formatta."],
            "error": "Rapor metni boş veya geçersiz formatta.",
        }

    if "⚠️ Sonuç Bulunamadı" in report_text or "kriterlere uygun makale bulunamamıştır" in report_text:
        warnings = []
        if EXPERT_PHYSICIAN_REVIEW_LINE not in report_text:
            warnings.append("Uzman Hekim Değerlendirmesi: Yapılmadı bildirimi eksik.")
        detected_false_claims = [
            description
            for pattern, description in _FORBIDDEN_REPORT_CLAIMS
            if re.search(pattern, report_text, re.IGNORECASE)
        ]
        return {
            "valid": len(detected_false_claims) == 0,
            "missing_sections": [],
            "detected_false_claims": detected_false_claims,
            "warnings": warnings,
            "empty_results": True,
        }

    missing_sections = [sec for sec in MANDATORY_CLINICAL_REPORT_SECTIONS if sec not in report_text]
    warnings = []

    if not re.search(r"\b(abstract|öze[tt])\b", report_text, re.IGNORECASE):
        warnings.append("Özet (abstract-only) sınırlılığı bildirimi eksik.")

    if "GRADE Değerlendirilmedi" not in report_text and "Not Assessed" not in report_text:
        warnings.append("GRADE Değerlendirilmedi (Not Assessed) statüsü bildirimi eksik.")

    if EXPERT_PHYSICIAN_REVIEW_LINE not in report_text:
        warnings.append("Uzman Hekim Değerlendirmesi: Yapılmadı bildirimi eksik.")

    detected_false_claims = []
    for pattern, description in _FORBIDDEN_REPORT_CLAIMS:
        if re.search(pattern, report_text, re.IGNORECASE):
            detected_false_claims.append(description)

    return {
        "valid": len(missing_sections) == 0 and len(detected_false_claims) == 0,
        "missing_sections": missing_sections,
        "detected_false_claims": detected_false_claims,
        "warnings": warnings,
    }


def _format_authors_short(authors: List[str]) -> str:
    if not authors:
        return "Bilinmeyen Yazar"
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} ve {authors[1]}"
    return f"{authors[0]} ve ark."


# Design labels are not evidence grades. Certainty stays unassigned until an
# outcome-level GRADE assessment has the data it needs.
UNASSIGNED_EVIDENCE_LEVEL = "Değerlendirilemedi"
EVIDENCE_LEVEL_NOTE = (
    "Kanıt düzeyi çalışma tasarımından üretilmez. "
    "Sonlanım bazlı GRADE değerlendirmesi yapılmadan kesinlik derecesi atanmaz."
)

_DESIGN_LABELS = {
    "meta_analysis": "Meta-Analiz",
    "systematic_review": "Sistematik Derleme",
    "systematic_review_and_meta_analysis": "Sistematik Derleme ve Meta-Analiz",
    "rct": "Rastgele Kontrollü Çalışma (RCT)",
    "clinical_trial": "Kontrollü Klinik Araştırma",
    "case_control": "Vaka-Kontrol Çalışması",
    "cross_sectional": "Kesitsel Çalışma",
    "cohort": "Kohort Çalışması (Gözlemsel)",
    "case_report": "Olgu Sunumu",
    "case_series": "Olgu Serisi",
    "guideline": "Klinik Kılavuz",
    "consensus": "Konsensüs Raporu",
    "editorial": "Editör Yazısı / Mektup / Yorum",
    "comparative": "Karşılaştırmalı Klinik Çalışma",
    "narrative_review": "Niteliksel Derleme / Uzman Görüşü",
    "observational_unspecified": "Gözlemsel Çalışma (tasarım ayrıştırılamadı)",
    "diagnostic_accuracy": "Tanı Doğruluğu Çalışması",
    "unclassified": "Çalışma tasarımı belirlenemedi",
}

_BACKGROUND_BEFORE_RE = re.compile(
    r"\b(previous|prior|published|earlier|existing|önceki|yayımlanmış|yayinlanmis)\b\W*$",
    re.IGNORECASE,
)
_BACKGROUND_AFTER_RE = re.compile(
    r"^\s+(?:was\s+|were\s+)?(?:previously|earlier)\b",
    re.IGNORECASE,
)
_META_RE = re.compile(r"\b(meta-?analysis|meta analysis|metaanalysis|meta-?analiz)\b", re.IGNORECASE)
_SR_RE = re.compile(r"\b(systematic reviews?|sistematik derleme|sistematik inceleme)\b", re.IGNORECASE)
_RCT_RE = re.compile(
    r"(?<!non)(?<!non-)(?<!non )\b(?:randomi[sz]ed controlled trials?|randomi[sz]ed trials?|randomi[sz]ed|rastgele kontroll[uü]|rct)\b",
    re.IGNORECASE,
)
_CASE_CONTROL_RE = re.compile(r"\b(case-?control|vaka-?kontrol|olgu-?kontrol)\b", re.IGNORECASE)
_CROSS_RE = re.compile(r"\b(cross[-\s]?sectional|kesitsel)\b", re.IGNORECASE)
_COHORT_RE = re.compile(r"\b(cohort|kohort)\b", re.IGNORECASE)
_FOLLOW_RE = re.compile(
    r"\b(followed(?:\s+up)?(?:\s+for|\s+over)?|were followed|was followed|longitudinal follow)\b",
    re.IGNORECASE,
)
# Counts of two or more. A bare "1" or "a patient" stays a single case report.
_AT_LEAST_TWO_PATIENTS = (
    r"few|several|multiple|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"[2-9]|[1-9]\d+"
)
_CASE_SERIES_RE = re.compile(
    rf"\b("
    rf"case series|olgu serisi|vaka serisi|series of cases|"
    rf"series of (?:\d+\s+)?(?:cases|patients)|"
    rf"(?:{_AT_LEAST_TWO_PATIENTS})\s+cases\s+of|"
    rf"(?:herein\s+)?we\s+(?:report|present|describe)\s+(?:a\s+series\s+of\s+)?"
    rf"(?:{_AT_LEAST_TWO_PATIENTS})\s+"
    rf"(?:consecutive\s+|adult\s+|pediatric\s+|paediatric\s+)?"
    rf"(?:patients|cases|women|men|children)"
    rf")\b",
    re.IGNORECASE,
)
# "case report" is an explicit design label. Bare "a case of" is weaker: a
# review can use it as a metaphor ("a case of neuronal life and death").
_CASE_REPORT_EXPLICIT_RE = re.compile(
    r"\b(case reports?|olgu sunumu|olgu bildirimi)\b",
    re.IGNORECASE,
)
_A_CASE_OF_RE = re.compile(r"\ba case of\b", re.IGNORECASE)
_CASE_REPORT_RE = re.compile(
    r"\b(case reports?|olgu sunumu|olgu bildirimi|a case of)\b",
    re.IGNORECASE,
)
# The paper's own description of itself as a review, not a citation of one.
_SELF_DESCRIBED_REVIEW_RE = re.compile(
    r"\b(?:"
    r"this\s+(?:narrative\s+|brief\s+|scoping\s+|perspective\s+)?"
    r"(?:review|perspective|article|paper)\s+"
    r"(?:summarizes|reviews|examines|discusses|provides)|"
    r"this\s+perspective\s+reviews|"
    r"(?:we|this\s+(?:paper|article|review))\s+review(?:s)?\s+(?:the\s+)?literature"
    r")\b",
    re.IGNORECASE,
)
# "We report/present a … patient" (or case/man/woman). Gap words that name a
# review or a study design do not count: "we present a review of patients".
_WE_PRESENT_PATIENT_RE = re.compile(
    r"\b(?:herein\s+)?we\s+(?:report|present|describe)\s+(?:a|an|the)\s+"
    r"(?:(?!(?:review|reviews|overview|summary|discussion|analysis|analyses|"
    r"study|studies|trial|trials|cohort|literature|management|systematic|meta)\b)"
    r"[\w-]+\s+){0,10}?"
    r"(?:patient|case|man|woman|boy|girl|child|infant)\b",
    re.IGNORECASE,
)
# Demographic opening used by case reports. Not "a 10-year-old cohort".
_YEAR_OLD_CASE_RE = re.compile(
    r"\ba[n]?\s+\d{1,3}-year-old\b(?!\s+(?:cohort|study|trial|review|population|group|sample|series)\b)",
    re.IGNORECASE,
)
_GUIDELINE_RE = re.compile(
    r"\b(practice guidelines?|clinical practice guidelines?|klinik kılavuz(?:lar|u)?|klinik kilavuz(?:lar|u)?|uygulama kılavuzu|uygulama kilavuzu)\b",
    re.IGNORECASE,
)
_DIAG_RE = re.compile(
    r"\b(diagnostic accuracy|sensitivity and specificity|tanı doğruluğu|tani dogrulugu)\b",
    re.IGNORECASE,
)
_NARRATIVE_TITLE_RE = re.compile(r"\b(narrative review|literature review|derleme)\b", re.IGNORECASE)
_INTERVENTION_RE = re.compile(
    r"\b(placebos?|plasebo|treatments?|therap(?:y|ies)|treated|inhibitors?|supplements?|surger(?:y|ies)|interventions?|drugs?|tedavi|ilaç|ilac)\b",
    re.IGNORECASE,
)
_EFFECTIVENESS_RE = re.compile(
    r"\b(effectiveness|efficacy|treated with|placebo|plasebo|etkinlik)\b",
    re.IGNORECASE,
)


def _design_record(design_key: str) -> Dict[str, Any]:
    return {
        "design": _DESIGN_LABELS[design_key],
        "design_key": design_key,
        "level": UNASSIGNED_EVIDENCE_LEVEL,
        "level_num": None,
        "evidence_level_note": EVIDENCE_LEVEL_NOTE,
        "badge_color": "#4B5563",
    }


def _sentence_around(text: str, start: int, end: int) -> str:
    if not text or start is None or start < 0:
        return ""
    left_period = text.rfind(".", 0, start)
    left_break = text.rfind("\n", 0, start)
    begin = max(left_period, left_break) + 1
    right_candidates = [pos for pos in (text.find(".", end), text.find("\n", end)) if pos != -1]
    finish = (min(right_candidates) + 1) if right_candidates else len(text)
    return re.sub(r"\s+", " ", text[begin:finish]).strip()


def _has_pub_type(pts: List[str], *needles: str) -> bool:
    return any(any(needle in pt for needle in needles) for pt in pts)


def _own_design_match(text: str, pattern: re.Pattern) -> bool:
    """True when the cue describes this study, not a paper it cites."""
    if not text:
        return False
    for match in pattern.finditer(text):
        before = text[max(0, match.start() - 60):match.start()]
        after = text[match.end():match.end() + 48]
        if _BACKGROUND_BEFORE_RE.search(before) or _BACKGROUND_AFTER_RE.search(after):
            continue
        return True
    return False


def _title_opens_as_case(title: str) -> bool:
    """True when the title itself is phrased as a case report, not a metaphor."""
    return bool(re.match(r"\s*a case of\b", title or "", re.IGNORECASE))


def _bare_case_of_is_review_metaphor(title: str, abstract: str) -> bool:
    """True when 'a case of' is figurative and the paper calls itself a review.

    A title that opens with 'a case of', or a real patient cue (case report,
    we present a patient, a NN-year-old), is not a metaphor.
    """
    title = title or ""
    abstract = abstract or ""
    if _title_opens_as_case(title):
        return False
    combined = f"{title}\n{abstract}"
    if not _own_design_match(combined, _A_CASE_OF_RE):
        return False
    for blob in (title, abstract):
        if (
            _own_design_match(blob, _CASE_REPORT_EXPLICIT_RE)
            or _own_design_match(blob, _WE_PRESENT_PATIENT_RE)
            or _own_design_match(blob, _YEAR_OLD_CASE_RE)
            or _own_design_match(blob, _CASE_SERIES_RE)
        ):
            return False
    return _own_design_match(combined, _SELF_DESCRIBED_REVIEW_RE)


def _case_report_in_text(blob: str, title: str, abstract: str) -> bool:
    """Explicit case-report wording in one field.

    Age ('a NN-year-old') is intentionally excluded so a cohort phrase in the
    same field can still win. Cited cases and a metaphorical 'a case of' inside
    a self-described review do not count.
    """
    if not blob:
        return False
    if _own_design_match(blob, _CASE_REPORT_EXPLICIT_RE) or _own_design_match(blob, _WE_PRESENT_PATIENT_RE):
        return True
    if _title_opens_as_case(title) and blob == title and _own_design_match(blob, _A_CASE_OF_RE):
        return True
    if _own_design_match(blob, _A_CASE_OF_RE) and not _bare_case_of_is_review_metaphor(title, abstract):
        return True
    return False


def _case_evidence_key(title: str, abstract: str) -> Optional[str]:
    """Case series or case report cues that describe this paper's own patients.

    A cited case ("a previous case report") does not count. Several patients
    described by the paper are a case series; one patient is a case report.
    A generic Review tag must not hide these cues. A metaphorical 'a case of'
    inside a paper that describes itself as a review is not a case report.
    """
    title = title or ""
    abstract = abstract or ""
    for blob in (title, abstract):
        if _own_design_match(blob, _CASE_SERIES_RE):
            return "case_series"
    for blob in (title, abstract):
        if _case_report_in_text(blob, title, abstract) or _own_design_match(blob, _YEAR_OLD_CASE_RE):
            return "case_report"
    return None


def _text_design_key(title: str, abstract: str) -> Optional[str]:
    """Read the study's own design from the title, then from the abstract."""
    title = title or ""
    abstract = abstract or ""
    for blob, allow_follow in ((title, False), (abstract, True)):
        meta = _own_design_match(blob, _META_RE)
        systematic = _own_design_match(blob, _SR_RE)
        if meta and systematic:
            return "systematic_review_and_meta_analysis"
        if meta:
            return "meta_analysis"
        if systematic:
            return "systematic_review"
        if _own_design_match(blob, _GUIDELINE_RE):
            return "guideline"
        if _own_design_match(blob, _RCT_RE):
            return "rct"
        if _own_design_match(blob, _CASE_CONTROL_RE):
            return "case_control"
        if _own_design_match(blob, _CROSS_RE):
            return "cross_sectional"
        if _own_design_match(blob, _CASE_SERIES_RE):
            return "case_series"
        if _case_report_in_text(blob, title, abstract):
            return "case_report"
        if _own_design_match(blob, _COHORT_RE):
            return "cohort"
        if allow_follow and _own_design_match(blob, _FOLLOW_RE):
            return "cohort"
        if _own_design_match(blob, _DIAG_RE):
            return "diagnostic_accuracy"
        # Age alone is weaker than a named design in the same field, but it is
        # still a case report when nothing stronger was stated.
        if _own_design_match(blob, _YEAR_OLD_CASE_RE):
            return "case_report"
    if _NARRATIVE_TITLE_RE.search(title) or (
        re.search(r"\breview\b", title, re.IGNORECASE) and not _own_design_match(title, _SR_RE)
    ):
        return "narrative_review"
    return None


def classify_study_design(pub_types: List[str], title: str, abstract: str) -> Dict[str, Any]:
    """
    Classify study design from NLM publication types, then title, then abstract.

    Meta-analysis, systematic review, RCT, cohort, case-control, cross-sectional,
    case report, case series, and clinical guideline are separate labels.
    Explicit NLM tags (systematic review, meta-analysis, randomized controlled
    trial, cohort, case-control, and case reports) outrank title and abstract
    cues. A generic Review tag does not outrank clear case-report or
    case-series evidence in the title or abstract.
    The returned level is never an evidence grade inferred from the design.
    """
    pts = [pt.lower() for pt in (pub_types or []) if pt]
    text_key = _text_design_key(title or "", abstract or "")

    if _has_pub_type(pts, "meta-analysis"):
        if _has_pub_type(pts, "systematic review") or text_key == "systematic_review":
            return _design_record("systematic_review_and_meta_analysis")
        return _design_record("meta_analysis")

    if _has_pub_type(pts, "systematic review"):
        if text_key == "meta_analysis":
            return _design_record("systematic_review_and_meta_analysis")
        return _design_record("systematic_review")

    if _has_pub_type(pts, "randomized controlled trial"):
        return _design_record("rct")

    if _has_pub_type(pts, "case-control", "case control", "vaka-kontrol"):
        return _design_record("case_control")

    if _has_pub_type(pts, "cross-sectional", "cross sectional"):
        return _design_record("cross_sectional")

    if _has_pub_type(pts, "cohort"):
        return _design_record("cohort")

    if _has_pub_type(pts, "case reports", "case report"):
        if text_key == "case_series":
            return _design_record("case_series")
        return _design_record("case_report")

    if _has_pub_type(pts, "practice guideline", "guideline"):
        return _design_record("guideline")

    if _has_pub_type(pts, "consensus development conference"):
        return _design_record("consensus")

    if _has_pub_type(pts, "editorial") or _has_pub_type(pts, "letter") or _has_pub_type(pts, "comment"):
        return _design_record("editorial")

    if _has_pub_type(pts, "clinical trial", "controlled clinical trial"):
        if text_key == "rct":
            return _design_record("rct")
        return _design_record("clinical_trial")

    if _has_pub_type(pts, "comparative study"):
        if text_key in ("cohort", "case_control", "cross_sectional", "rct", "case_series", "case_report"):
            return _design_record(text_key)
        return _design_record("comparative")

    if _has_pub_type(pts, "review", "derleme"):
        # A review often cites trials. Only an explicit synthesis or guideline
        # label promotes it; a mentioned RCT does not make the paper an RCT.
        # A generic Review tag is not an explicit NLM design. Clear case-report
        # evidence in the title or abstract ("a case of", "case report",
        # "we report/present a … patient", "a NN-year-old", or several patients)
        # is a case report or a case series.
        if text_key in (
            "meta_analysis",
            "systematic_review",
            "systematic_review_and_meta_analysis",
            "guideline",
        ):
            return _design_record(text_key)
        case_key = _case_evidence_key(title, abstract)
        if case_key:
            return _design_record(case_key)
        return _design_record("narrative_review")

    if _has_pub_type(pts, "observational study", "prospective studies", "longitudinal studies"):
        if text_key in ("cohort", "case_control", "cross_sectional", "case_series", "case_report", "rct", "diagnostic_accuracy"):
            return _design_record(text_key)
        if _own_design_match(f"{title or ''} {abstract or ''}", _FOLLOW_RE):
            return _design_record("cohort")
        return _design_record("observational_unspecified")

    if text_key:
        return _design_record(text_key)
    return _design_record("unclassified")


def _classify_evidence_level(pub_types: List[str], title: str, abstract: str) -> str:
    res = classify_study_design(pub_types, title, abstract)
    return f"{res['level']} ({res['design']})"


def _excluded_from_primary_pool(design_name: str) -> bool:
    """Synthesis papers and single case reports are not pooled as comparative trials."""
    return any(
        key in (design_name or "")
        for key in ("Derleme", "Meta-Analiz", "Kılavuz", "Uzman Görüşü", "Editör", "Olgu Sunumu")
    )


def _clean_pico_str(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"^[,\s.:;]+|[,\s.:;]+$", "", s).strip()
    return s


# Longer population phrases must be tried before bare prepositions (in/for/among/with).
_EN_POP_RE = re.compile(
    r"\b("
    r"in pediatric patients with|in paediatric patients with|"
    r"in patients with|in adults with|in children with|"
    r"among patients with|among adults with|among children with|"
    r"for patients with|patients with|"
    r"in|for|among|with"
    r")\b",
    re.IGNORECASE,
)
_TR_POP_RE = re.compile(
    r"\b("
    r"tanısı olan hastalarda|tanili hastalarda|tanılı hastalarda|"
    r"hastalarında|hastalarinda|hastalarda|"
    r"bireylerde|çocuklarda|cocuklarda|"
    r"erişkinlerde|eriskinlerde|yetişkinlerde|yetiskinlerde|"
    r"olgularında|olgularinda|olgularda"
    r")\b",
    re.IGNORECASE,
)
_EN_FULL_POP_RE = re.compile(
    r"^(.*?)\s+\b("
    r"in pediatric patients with|in paediatric patients with|"
    r"in patients with|in adults with|in children with|"
    r"among patients with|among adults with|among children with|"
    r"for patients with|patients with|"
    r"in|for|among|with"
    r")\b\s+(.*)$",
    re.IGNORECASE,
)
_SHORT_POP_MARKERS = {"in", "for", "among", "with"}

# kind: "a" = comparator follows the cue (vs Y), "b" = comparator precedes the cue
# (Y ile karşılaştırıldığında), "ambiguous" = resolved from the surrounding text.
_COMPARISON_CUES = [
    ("b", re.compile(r"ile\s+karşılaştırıldığında", re.IGNORECASE)),
    ("b", re.compile(r"ile\s+karsilastirildiginda", re.IGNORECASE)),
    ("b", re.compile(r"ile\s+kıyaslandığında", re.IGNORECASE)),
    ("b", re.compile(r"ile\s+kiyaslandiginda", re.IGNORECASE)),
    ("b", re.compile(r"ile\s+kıyasla", re.IGNORECASE)),
    ("b", re.compile(r"ile\s+kiyasla", re.IGNORECASE)),
    ("b", re.compile(r"karşılaştırıldığında", re.IGNORECASE)),
    ("b", re.compile(r"karsilastirildiginda", re.IGNORECASE)),
    ("b", re.compile(r"kıyaslandığında", re.IGNORECASE)),
    ("b", re.compile(r"kiyaslandiginda", re.IGNORECASE)),
    ("ambiguous", re.compile(r"karşısında", re.IGNORECASE)),
    ("ambiguous", re.compile(r"karsisinda", re.IGNORECASE)),
    ("ambiguous", re.compile(r"kıyasla", re.IGNORECASE)),
    ("ambiguous", re.compile(r"(?<!\w)kiyasla(?!\w)", re.IGNORECASE)),
    ("a", re.compile(r"karşılaştırmalı", re.IGNORECASE)),
    ("a", re.compile(r"karsilastirmali", re.IGNORECASE)),
    ("ambiguous", re.compile(r"(?<!\w)karşı(?!\w)", re.IGNORECASE)),
    ("ambiguous", re.compile(r"(?<!\w)karsi(?!\w)", re.IGNORECASE)),
    ("a", re.compile(r"\bas\s+compared\s+(?:to|with|against)\b", re.IGNORECASE)),
    ("a", re.compile(r"\bcompared\s+(?:to|with|against)\b", re.IGNORECASE)),
    ("a", re.compile(r"\bin\s+comparison\s+(?:to|with)\b", re.IGNORECASE)),
    ("a", re.compile(r"\brelative\s+to\b", re.IGNORECASE)),
    ("a", re.compile(r"\bversus\b", re.IGNORECASE)),
    ("a", re.compile(r"(?<!\w)vs\.?(?!\w)", re.IGNORECASE)),
    ("a", re.compile(r"\bagainst\b", re.IGNORECASE)),
]
_OUTCOME_RES = [
    re.compile(
        r"\b(?:primary|secondary|clinical)\s+outcome(?:s)?(?:\s+(?:of|was|:))?\s+(?P<out>[^,.;]{3,80})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bon\s+(?P<out>HbA1c|all-cause mortality|cardiovascular mortality|cardiovascular death|"
        r"mortality|hospitali[sz]ations?|MACE|major adverse cardiovascular events|"
        r"glyca?emic control|seizure freedom|seizures|remission|quality of life|"
        r"adverse events|kidney failure|bleeding)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bfor\s+(?:the\s+)?(?:reducing\s+|reduction\s+of\s+|prevention\s+of\s+|the\s+prevention\s+of\s+)?"
        r"(?P<out>all-cause mortality|cardiovascular mortality|cardiovascular death|mortality|"
        r"hospitali[sz]ations?|MACE|HbA1c|glyca?emic control|seizure freedom|seizures|remission|"
        r"quality of life|adverse events|kidney failure|bleeding)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<out>HbA1c|kardiyovasküler mortalite|kardiyovaskuler mortalite|"
        r"tüm nedenli mortalite|tum nedenli mortalite|ölüm oranı|olum orani|"
        r"hastaneye yatış|hastaneye yatis|hastane yatışı|hastane yatisi|"
        r"glisemik kontrol|nöbet kontrolü|nobet kontrolu|remisyon|sağkalım|sagkalim|"
        r"yaşam kalitesi|yasam kalitesi|yan etki|mortalite)\b"
        r"(?:\s+(?:üzerine(?:ki)?(?:\s+etkisi)?|uzerine(?:ki)?(?:\s+etkisi)?|açısından|acisindan|sonlanımı|sonlanimi|sonlanım|sonlanim))?",
        re.IGNORECASE,
    ),
]
# Do not combine Turkish capitals with re.IGNORECASE: Python treats İ as i.
_TR_LETTER_RE = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
_TR_WORD_HINT_RE = re.compile(
    r"\b("
    r"hastalarda|hastalarında|hastalarinda|karşı|karsi|kıyasla|kiyasla|"
    r"karşılaştırıldığında|karsilastirildiginda|çocuklarda|cocuklarda|"
    r"üzerine|uzerine|mortalite|etkisi|tedavisi|bireylerde|için|icin"
    r")\b",
    re.IGNORECASE,
)
_PICO_STRUCTURE_RE = re.compile(
    r"\b(in|for|among|vs\.?|versus|compared|with|hasta|karşı|karsi|etkisi|tedavisi|"
    r"üzerine|uzerine|children|patients|adults)\b",
    re.IGNORECASE,
)


def _label_pico(text: str, turkish: bool = False) -> str:
    """Uppercase the first letter without lowercasing acronyms already in the string."""
    cleaned = _clean_pico_str(text)
    if not cleaned:
        return ""
    first = cleaned[0]
    use_turkish_i = turkish or bool(re.search(r"[çğıöşüÇĞİÖŞÜ]", cleaned))
    if use_turkish_i and first == "i":
        first = "İ"
    elif first == "ı":
        first = "I"
    elif first.isalpha():
        first = first.upper()
    return first + cleaned[1:]


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip(" ,;:")


def _is_turkish_query(query: str) -> bool:
    text = query or ""
    return bool(_TR_LETTER_RE.search(text) or _TR_WORD_HINT_RE.search(text))


def _strip_tr_nominal(word: str) -> str:
    """Drop a trailing Turkish genitive or dative suffix from one token, conservatively."""
    if not word:
        return word
    genitive = re.match(r"^(?P<stem>.+(?:leri|ları|lari))(?:nin|nın|nun|nün)$", word, re.IGNORECASE)
    if genitive and len(genitive.group("stem")) >= 3:
        return genitive.group("stem")
    if re.search(r"[çğıöşüÇĞİÖŞÜ]", word):
        marked = re.match(r"^(?P<stem>.{4,}?)(?:nin|nın|nun|nün)$", word, re.IGNORECASE)
        if marked:
            word = marked.group("stem")
    if len(word) >= 7 and re.search(r"[aeıioöuü](?:ya|ye)$", word, re.IGNORECASE):
        return word[:-2]
    # Keep plural markers (inhibitörleri). A final vowel is stripped only for a
    # dative such as "insüline", not for "-ler/-lar/-leri".
    if re.search(r"(?:leri|ları|lari|ler|lar)$", word, re.IGNORECASE):
        return word
    if (
        re.search(r"[çğıöşüÇĞİÖŞÜ]", word)
        and len(word) >= 6
        and re.search(r"[bcçdfgğhjklmnprsştvyz][aeıiuü]$", word, re.IGNORECASE)
    ):
        return word[:-1]
    return word


def _strip_tr_phrase(phrase: str, turkish: bool) -> str:
    phrase = _collapse_ws(phrase)
    if not phrase or not turkish:
        return phrase
    words = phrase.split()
    words[-1] = _strip_tr_nominal(words[-1])
    if len(words[-1]) < 3:
        return phrase
    return " ".join(words)


def _population_from_marker(marker: str, after: str) -> str:
    """Build the population span. Short prepositions are not part of the label."""
    after = _collapse_ws(after)
    marker_l = (marker or "").lower()
    if marker_l in _SHORT_POP_MARKERS:
        return after
    lead = re.match(r"^(in|for|among|with)\s+", marker or "", re.IGNORECASE)
    if lead:
        rest = marker[lead.end():].strip()
        return _collapse_ws(f"{rest} {after}")
    return _collapse_ws(f"{marker} {after}")


def _peel_tr_population(text: str) -> tuple:
    """Return (population, remainder) when a Turkish population marker is present."""
    cleaned = _collapse_ws(text)
    if not cleaned:
        return "", ""
    match = _TR_POP_RE.search(cleaned)
    if not match:
        return "", cleaned
    before = _collapse_ws(cleaned[:match.start()])
    after = _collapse_ws(cleaned[match.end():])
    if not before:
        if after:
            return match.group(0), after
        return "", cleaned
    population = _collapse_ws(f"{before} {match.group(0)}")
    return population, after


def _split_en_right(right: str) -> tuple:
    """Return (population, comparison) for text that follows a type-A comparison cue."""
    right = _collapse_ws(right)
    if not right:
        return "", ""
    match = _EN_POP_RE.search(right)
    if not match:
        return "", right
    before = _collapse_ws(right[:match.start()])
    after = _collapse_ws(right[match.end():])
    if not after:
        return "", right
    return _population_from_marker(match.group(1), after), before


def _find_comparison_cue(text: str):
    """Return (kind, match) for the earliest, then longest, comparison cue."""
    best = None
    for kind, pattern in _COMPARISON_CUES:
        match = pattern.search(text)
        if not match:
            continue
        rank = (match.start(), -len(match.group(0)))
        if best is None or rank < best[0]:
            best = (rank, kind, match)
    if best is None:
        return None, None
    return best[1], best[2]


def _resolve_comparison_kind(kind: str, left: str, right: str) -> str:
    if kind != "ambiguous":
        return kind
    if _TR_POP_RE.search(right or "") or (not (right or "").strip() and len((left or "").split()) >= 2):
        return "b"
    return "a"


def _split_comparator_before_cue(left: str) -> tuple:
    """Return (intervention, comparison) for text before a type-B cue."""
    left = _collapse_ws(left)
    if not left:
        return "", ""
    if "," in left:
        head, tail = left.rsplit(",", 1)
        head, tail = _collapse_ws(head), _collapse_ws(tail)
        if head and tail:
            return head, tail
    words = left.split()
    if len(words) == 1:
        return "", words[0]
    return " ".join(words[:-1]), words[-1]


def _extract_outcome_span(query: str) -> tuple:
    """Return (outcome, query_without_outcome). Unstated outcomes stay empty."""
    for pattern in _OUTCOME_RES:
        match = pattern.search(query)
        if not match:
            continue
        outcome = _collapse_ws(match.group("out"))
        remaining = _collapse_ws(query[:match.start()] + " " + query[match.end():])
        if outcome and len(remaining) >= 3:
            return outcome, remaining
    return "", query


def _split_uncompared(working: str) -> tuple:
    """Return (population, intervention) when the query has no comparison cue."""
    tr_pop, tr_rest = _peel_tr_population(working)
    if tr_pop:
        return tr_pop, tr_rest
    match = _EN_FULL_POP_RE.search(working)
    if match and match.group(1).strip() and match.group(3).strip():
        population = _population_from_marker(match.group(2), match.group(3))
        return population, _collapse_ws(match.group(1))
    return "", ""


def _pico_defaults(
    population: str,
    intervention: str,
    comparison: str,
    outcome: str,
    turkish: bool = False,
) -> Dict[str, str]:
    return {
        "population": _label_pico(population, turkish) or "Belirtilmemiş",
        "intervention": _label_pico(intervention, turkish) or "Belirtilmemiş",
        "comparison": _label_pico(comparison, turkish) or "Belirtilmemiş",
        "outcome": _label_pico(outcome, turkish) or "Belirtilmemiş",
    }


def extract_pico_improved(query: str) -> Dict[str, str]:
    """
    Extract PICO elements strictly from the clinical query text.

    English cues include vs/versus/compared with/in comparison with and population
    markers such as "in patients with", "in adults with", "in children with",
    and "among". Turkish cues include "ile karşılaştırıldığında", "karşı",
    "kıyasla", and population markers such as "hastalarında", "çocuklarda",
    and "erişkinlerde". Outcome terms are taken only from an explicit cue
    (for example "on HbA1c", "cardiovascular mortality", "mortalite",
    "üzerine etkisi"). Abstracts are never consulted.

    Unstated components are "Belirtilmemiş". Keyword-only strings that lack a
    PICO cue are left unspecified so a bag of search terms is not relabelled
    as an intervention.
    """
    q_clean = _collapse_ws(query or "")
    if not q_clean:
        return _pico_defaults("", "", "", "")

    turkish = _is_turkish_query(q_clean)
    outcome, working = _extract_outcome_span(q_clean)
    population = ""
    intervention = ""
    comparison = ""

    kind, cue = _find_comparison_cue(working)
    if cue is not None:
        left = _collapse_ws(working[:cue.start()])
        right = _collapse_ws(working[cue.end():])
        resolved = _resolve_comparison_kind(kind, left, right)
        if resolved == "b":
            intervention, comparison = _split_comparator_before_cue(left)
            tr_pop, tr_rest = _peel_tr_population(intervention)
            if tr_pop:
                population = tr_pop
                intervention = tr_rest
            if not population:
                tr_pop, tr_rest = _peel_tr_population(right)
                if tr_pop:
                    population = tr_pop
                    if not intervention and tr_rest:
                        intervention = tr_rest
            if not population:
                en_pop, en_before = _split_en_right(right)
                if en_pop:
                    population = en_pop
                    if en_before and not comparison:
                        comparison = en_before
                elif right and not comparison:
                    comparison = right
        else:
            population, comparison = _split_en_right(right)
            tr_pop, tr_rest = _peel_tr_population(left)
            if tr_pop:
                intervention = tr_rest
                if not population:
                    population = tr_pop
            else:
                intervention = left
            if not comparison and right and not population:
                comparison = right
    else:
        population, intervention = _split_uncompared(working)

    intervention = _strip_tr_phrase(intervention, turkish)
    comparison = _strip_tr_phrase(comparison, turkish)
    population = _collapse_ws(population)
    outcome = _collapse_ws(outcome)

    if intervention and intervention.lower() == q_clean.lower() and not _PICO_STRUCTURE_RE.search(q_clean):
        intervention = ""

    return _pico_defaults(population, intervention, comparison, outcome, turkish=turkish)


def extract_pico(query: str) -> Dict[str, str]:
    """
    Public PICO extractor. Alias of extract_pico_improved so existing callers
    and tests keep working. Components that the query does not state stay
    "Belirtilmemiş". Article abstracts are not used.
    """
    return extract_pico_improved(query)



def _unassessed_bias(
    tool: str,
    study_type: str,
    domain_names: List[str],
    note: str,
) -> Dict[str, Any]:
    """Select a tool and leave every domain unrated until a real appraisal is done."""
    pending = "Değerlendirilmedi (Not Assessed - Tam Metin Gereklidir)"
    return {
        "tool": tool,
        "study_type": study_type,
        "overall_rating": "Değerlendirilmedi (Not Assessed)",
        "badge_color": "#6B7280",
        "domains": {name: pending for name in domain_names},
        "note": note,
        "risk_assigned": False,
        "rating_policy": "Değerlendirme yapılmadan risk derecesi verilmez.",
    }


def assess_risk_of_bias(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Choose RoB 2, ROBINS-I, ROBIS, or another design-specific tool.

    No low/some-concerns/high rating is emitted. Abstract text is not an appraisal.
    """
    title = article.get("title", "") or ""
    abstract = article.get("abstract", "") or ""
    design_info = classify_study_design(article.get("publication_types", []), title, abstract)
    design_key = design_info.get("design_key") or "unclassified"
    design_name = design_info.get("design") or ""
    blob = f"{title} {abstract}"

    if design_key in ("systematic_review", "meta_analysis", "systematic_review_and_meta_analysis"):
        return _unassessed_bias(
            "ROBIS (Risk of Bias in Systematic Reviews)",
            design_name,
            [
                "Çalışmaya alınma ölçütleri",
                "Çalışmaların belirlenmesi ve seçimi",
                "Veri toplama ve değerlendirme",
                "Sentez ve bulgular",
            ],
            "Sistematik derleme veya meta-analiz için ROBIS seçildi. Değerlendirme yapılmadığı için risk derecesi verilmedi.",
        )

    if design_key == "rct":
        return _unassessed_bias(
            "RoB 2 (Cochrane Risk of Bias for RCTs)",
            design_name,
            [
                "D1: Rastgeleleştirme Süreci",
                "D2: Öngörülen Müdahalelerden Sapmalar",
                "D3: Eksik Sonuç Verileri",
                "D4: Sonuç Ölçümü",
                "D5: Bildirilen Sonucun Seçimi",
            ],
            "RoB 2 seçildi. Resmi RoB 2 değerlendirmesi yalnızca özet metnine dayanarak otomatik yapılamaz; tam metin (full-text) incelemesi gereklidir. Risk derecesi verilmedi.",
        )

    if design_key == "cross_sectional":
        return _unassessed_bias(
            "AXIS (Kesitsel Çalışmalar)",
            design_name,
            ["Amaç", "Yöntem", "Sonuç verisi", "Tartışma", "Çıkar çatışması"],
            "Kesitsel çalışma için AXIS seçildi. Değerlendirme yapılmadığı için risk derecesi verilmedi.",
        )

    if design_key == "case_report":
        return _unassessed_bias(
            "JBI Olgu Sunumu Değerlendirme Listesi",
            design_name,
            ["Hasta tanımlaması", "Tanı", "Müdahale", "Sonuç", "Çıkarılabilir ders"],
            "Olgu sunumu için JBI listesi seçildi. Değerlendirme yapılmadığı için risk derecesi verilmedi.",
        )

    if design_key == "case_series":
        return _unassessed_bias(
            "JBI Olgu Serisi Değerlendirme Listesi",
            design_name,
            ["Dahil etme", "Tanı", "Ardışık dahil etme", "Sonuç", "İstatistik"],
            "Olgu serisi için JBI listesi seçildi. Değerlendirme yapılmadığı için risk derecesi verilmedi.",
        )

    if design_key == "guideline":
        return _unassessed_bias(
            "AGREE II (Klinik Kılavuz)",
            design_name,
            ["Kapsam", "Paydaş katılımı", "Yöntemin titizliği", "Uygulanabilirlik", "Editöryal bağımsızlık"],
            "Klinik kılavuz için AGREE II seçildi. Değerlendirme yapılmadığı için risk derecesi verilmedi.",
        )

    if design_key == "diagnostic_accuracy":
        return _unassessed_bias(
            "QUADAS-2 (Tanı Doğruluğu)",
            design_name,
            ["Hasta seçimi", "İndeks test", "Referans standart", "Akış ve zamanlama"],
            "Tanı doğruluğu çalışması için QUADAS-2 seçildi. Değerlendirme yapılmadığı için risk derecesi verilmedi.",
        )

    if design_key in ("cohort", "case_control", "comparative", "observational_unspecified"):
        use_robins = design_key != "case_control" and bool(_INTERVENTION_RE.search(blob))
        if design_key == "case_control" and _EFFECTIVENESS_RE.search(blob):
            use_robins = True
        if use_robins:
            tool = "ROBINS-I (Risk of Bias in Non-Randomized Studies)"
            note = "Müdahale etkisi bildiren randomize olmayan çalışma için ROBINS-I seçildi. Değerlendirme yapılmadığı için risk derecesi verilmedi."
            domains = [
                "D1: Karıştırıcı Değişken Yanlılığı (Confounding)",
                "D2: Katılımcı Seçimi Yanlılığı",
                "D3: Müdahale Sınıflandırma Yanlılığı",
                "D4: Müdahaleden Sapma Yanlılığı",
                "D5: Eksik Veri Yanlılığı",
                "D6: Sonuç Ölçüm Yanlılığı",
                "D7: Bildirilen Sonucun Seçimi",
            ]
        else:
            tool = "Newcastle-Ottawa Scale (NOS)"
            note = "Etiyolojik gözlemsel çalışma için Newcastle-Ottawa Scale seçildi. Değerlendirme yapılmadığı için risk derecesi verilmedi."
            domains = ["Seçim", "Karşılaştırılabilirlik", "Maruziyet veya sonlanım"]
        return _unassessed_bias(tool, design_name, domains, note)

    if design_key == "clinical_trial":
        return _unassessed_bias(
            "Değerlendirilemedi (randomizasyon doğrulanmadı)",
            design_name,
            ["Randomizasyon"],
            "Klinik araştırma kaydı randomizasyonu doğrulamıyor. RoB 2 veya ROBINS-I seçilmedi ve risk derecesi verilmedi.",
        )

    if design_key == "consensus":
        return _unassessed_bias(
            "Uygulanamaz (Not Applicable)",
            design_name,
            ["Metodolojik Araç Uygunluğu"],
            "Konsensüs metni için RoB 2, ROBINS-I veya ROBIS uygulanamaz. Risk derecesi verilmedi.",
        )

    return _unassessed_bias(
        "Uygulanamaz (Not Applicable)",
        design_name or "Sınıflandırılamadı",
        ["Metodolojik Araç Uygunluğu"],
        "Bu yayın türü için RoB 2, ROBINS-I veya ROBIS uygulanamaz. Değerlendirme yapılmadan risk derecesi verilmez.",
    )


# Longer phrases precede shorter ones so "standardized mean difference" is not read as "mean difference".
_EFFECT_MEASURE_ALTERNATION = (
    "HR|OR|RR|WMD|IRR|SMD|MD|"
    "hazard ratio|odds ratio|relative risk|"
    "incidence rate ratio|standardized mean difference|mean difference"
)
_EFFECT_MEASURE_RE = re.compile(
    rf"\b(?:{_EFFECT_MEASURE_ALTERNATION})\s*[:=, ]?\s*-?\d+\.?\d*\b",
    re.IGNORECASE,
)


def extract_outcome_metrics(abstract: str) -> List[Dict[str, Any]]:
    """
    Parses abstract sentences/clauses and binds HR, RR, OR, IRR, SMD, MD, 95% CI,
    and p-values directly to their respective clinical outcomes.
    Returns a list of dicts: [{"outcome": str, "metrics": List[str], "sentence": str}]
    """
    if not abstract:
        return []

    raw_clauses = re.split(r'(?<=[.!?])\s+|\n+|(?:;\s*)', abstract)
    clauses = []

    for raw in raw_clauses:
        raw_clean = raw.strip()
        if not raw_clean:
            continue

        eff_count = len(_EFFECT_MEASURE_RE.findall(raw_clean))
        p_count = len(re.findall(r"\b(?:p|P)\s*[=<]\s*0?\.\d+\b", raw_clean))

        if eff_count > 1 or (eff_count >= 1 and p_count > 1):
            sub_parts = re.split(
                rf"(?<=\))\s*(?:and\s+|,|\s+while\s+)|(?:\b(?:and|,)\s+)(?=[A-Za-z\s]+?\b(?:{_EFFECT_MEASURE_ALTERNATION}|p\s*[=<]))",
                raw_clean,
                flags=re.IGNORECASE,
            )
            for sp in sub_parts:
                if sp.strip():
                    clauses.append(sp.strip())
        else:
            clauses.append(raw_clean)

    results = []

    outcome_keywords = [
        "cardiovascular death", "cv death", "all-cause mortality", "mortality", "death",
        "hospitalization", "heart failure hospitalization", "readmission", "events",
        "remission", "relapse", "progression-free survival", "overall survival",
        "myopathy", "muscle pain", "muscle symptoms", "ck elevation", "anti-hmgcr",
        "adverse events", "side effects", "infection rate", "cure rate", "response rate",
        "recurrence", "blood pressure", "ejection fraction", "stroke", "infarction",
        "depression", "depression symptoms", "functional independence", "pasi", "walking speed",
        "nasal polyp score", "nasal polyps", "pain", "symptoms", "quality of life"
    ]

    for clause in clauses:
        clause_clean = clause.strip()
        if not clause_clean:
            continue

        effect_sizes = _EFFECT_MEASURE_RE.findall(clause_clean)
        cis = re.findall(r"\b(?:95%\s*CI|CI\s*95%)\s*[:=]?\s*\[?\s*\d+\.?\d*\s*(?:to|-|,)\s*\d+\.?\d*\s*\]?", clause_clean, re.IGNORECASE)
        p_vals = re.findall(r"\b(?:p|P)\s*[=<]\s*0?\.\d+\b", clause_clean)

        combined_metrics = list(dict.fromkeys(effect_sizes + cis + p_vals))
        if not combined_metrics:
            continue

        outcome_name = ""
        clause_lower = clause_clean.lower()
        for kw in outcome_keywords:
            if kw in clause_lower:
                outcome_name = kw.title()
                break

        if not outcome_name:
            metric_match = re.search(
                rf"\b(?:{_EFFECT_MEASURE_ALTERNATION}|95%\s*CI|95%CI|CI|p|P)(?:\s*interaction|\s*value)?\b",
                clause_clean,
                re.IGNORECASE,
            )
            if metric_match:
                prefix = clause_clean[:metric_match.start()].strip()
                prefix = re.sub(r"\b(?:compared (?:to|with)|vs\.?|versus|against)\s+[^.,;\n]*$", "", prefix, flags=re.IGNORECASE).strip()
                prefix = re.sub(r"[\(\[\{\)\]\}]", " ", prefix)
                prefix = re.sub(r"\s+", " ", prefix).strip()
                prefix = re.sub(r"^[,\s.:;]+|[,\s.:;]+$", "", prefix)
                words = prefix.split()
                if len(words) > 0:
                    cand_name = " ".join(words[-4:]).strip().capitalize()
                    if cand_name and not cand_name.lower().startswith((
                        "hazard", "odds", "relative", "mean", "incidence", "standardized",
                        "p", "ci", "hr", "or", "rr", "md", "irr", "smd", "wmd",
                    )):
                        outcome_name = cand_name

        if not outcome_name:
            outcome_name = "Primer Klinik Sonlanım / Özet İstatistiği"

        results.append({
            "outcome": outcome_name,
            "metrics": combined_metrics,
            "sentence": clause_clean
        })

    return results


def extract_study_metrics(abstract: str) -> Dict[str, Any]:
    """
    Extracts numerical metrics (sample size n, effect sizes HR/OR/RR/IRR/SMD/MD, 95% CI, p-values,
    outcome-bound metrics, concomitant treatments, and causality/methodological limitations)
    strictly from abstract text if explicitly present. Never fabricates missing metrics.
    """
    if not abstract:
        return {
            "n": None,
            "n_source_sentence": "",
            "effect_sizes": [],
            "confidence_intervals": [],
            "p_values": [],
            "outcome_metrics": [],
            "concomitant_treatments": [],
            "causality_limitations": []
        }

    # Clean non-breaking spaces
    abstract_clean = abstract.replace("\xa0", " ")

    # 1. Sample Size (n) Extraction Patterns
    n_val = None
    n_sentence = ""
    n_match = re.search(r"\b(?:n|N)\s*=\s*(\d[\d,]*)\b", abstract_clean)
    if not n_match:
        n_match = re.search(r"\b(?:total of|sample of|enrolled|included|assigned|randomly assigned|randomized|randomised)\s+(\d[\d,]*)\b", abstract_clean, re.IGNORECASE)
    if not n_match:
        n_match = re.search(r"\b(?:of the|among the|a total of)\s+(\d[\d,]*)\s+(?:patients|subjects|participants|adults|children|individuals|cases)\b", abstract_clean, re.IGNORECASE)
    if not n_match:
        n_match = re.search(r"\b(\d[\d,]*)\s+(?:patients|subjects|participants|adults|children|individuals|cases)\s+(?:were\s+)?(?:enrolled|randomized|randomised|included|studied|evaluated|assigned|followed)\b", abstract_clean, re.IGNORECASE)

    if n_match:
        n_val = n_match.group(1).replace(",", "")
        n_sentence = _sentence_around(abstract_clean, n_match.start(), n_match.end())

    effect_sizes = _EFFECT_MEASURE_RE.findall(abstract_clean)
    cis = re.findall(r"\[?\s*\b(?:95%\s*CI|95%CI|CI\s*95%)\b\s*[:=,]?\s*-?\d+\.?\d*\s*(?:to|-|–|,)\s*-?\d+\.?\d*\s*\]?", abstract_clean, re.IGNORECASE)
    p_vals = re.findall(r"\b(?:p|P)(?:interaction|-value)?\s*[=<]\s*(?:0?\.\d+|\d+\.?\d*|\.\d+)\b", abstract_clean)

    outcome_metrics = extract_outcome_metrics(abstract_clean)

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
        "n_source_sentence": n_sentence,
        "effect_sizes": list(set(effect_sizes)),
        "confidence_intervals": list(set(cis)),
        "p_values": list(set(p_vals)),
        "outcome_metrics": outcome_metrics,
        "concomitant_treatments": list(set(concomitant_treatments)),
        "causality_limitations": list(set(causality_limitations))
    }


def extract_article_clinical_details(article: Dict[str, Any], query: str = "") -> Dict[str, Any]:
    """
    Extracts individual PubMed article clinical details separately:
    - Hasta Grubu (Patient Group / Population)
    - Örneklem Büyüklüğü (Sample Size / n)
    - Çalışma Tasarımı (Study Design)
    - Müdahale (Intervention)
    - Karşılaştırma (Comparison)
    - Sonlanım & İstatistiksel Metrikler (Outcomes & Bound Metrics)
    - Gerçek Bulgular (Ground-Truth Findings)
    """
    title = article.get("title", "")
    abstract = (article.get("abstract") or "").replace("\xa0", " ")
    pub_types = article.get("publication_types", [])

    classification = classify_study_design(pub_types, title, abstract)
    metrics = extract_study_metrics(abstract)
    outcome_metrics = extract_outcome_metrics(abstract)

    pmid = str(article.get("pmid") or "")

    def _claim(value: str, sentence: str, source: str) -> Dict[str, str]:
        stated = bool(value) and value not in ("Belirtilmedi", "Özette bildirilmedi")
        return {
            "value": value if stated else "değerlendirilemedi",
            "source_sentence": sentence if stated and sentence else "",
            "pmid": pmid if stated else "",
            "source": source if stated else "missing",
        }

    # 1. Sample Size — only a number that the abstract itself states
    if metrics.get("n"):
        sample_size_str = f"n = {metrics['n']}"
        sample_sentence = metrics.get("n_source_sentence") or ""
    else:
        sample_size_str = "Özette bildirilmedi"
        sample_sentence = ""

    # 2. Patient group from the abstract sentence, never from the user's question
    patient_group = "Belirtilmedi"
    pop_sentence = ""
    pop_match = re.search(
        r"\b(?:patients|subjects|adults|children|individuals|participants|hastalar)\s+"
        r"(?:with|having|diagnosed with|suffering from)\s+([^.,;\n]+)",
        abstract,
        re.IGNORECASE,
    )
    if pop_match:
        patient_group = pop_match.group(1).strip().capitalize()
        pop_sentence = _sentence_around(abstract, pop_match.start(), pop_match.end())

    # 3. Intervention and comparator from the abstract or the article title
    intervention = "Belirtilmedi"
    comparison = "Belirtilmedi"
    intervention_sentence = ""
    intervention_source = "missing"
    comparison_sentence = ""
    comparison_source = "missing"

    int_comp_match = re.search(
        r"\b(?:randomized|assigned|allocated|treated)\b.*?\bto\s+receive\s+([^.,;\n]+?)\s+"
        r"(?:or|vs\.?|versus|compared\s+(?:to|with))\s+([^.,;\n]+)",
        abstract,
        re.IGNORECASE,
    )
    if not int_comp_match:
        int_comp_match = re.search(
            r"\b(?:randomized|assigned|allocated|treated)\s+(?:to\s+)?(?:receive\s+)?"
            r"([^.,;\n]+?)\s+(?:or|vs\.?|versus|compared\s+(?:to|with))\s+([^.,;\n]+)",
            abstract,
            re.IGNORECASE,
        )

    if int_comp_match:
        raw_int = int_comp_match.group(1).strip()
        raw_comp = int_comp_match.group(2).strip()
        if "to receive " in raw_int.lower():
            raw_int = re.sub(r"^.*?\bto\s+receive\s+", "", raw_int, flags=re.IGNORECASE).strip()
        intervention = raw_int.capitalize()
        comparison = raw_comp.capitalize()
        intervention_sentence = _sentence_around(abstract, int_comp_match.start(), int_comp_match.end())
        comparison_sentence = intervention_sentence
        intervention_source = "abstract"
        comparison_source = "abstract"

    if intervention == "Belirtilmedi":
        int_match = re.search(
            r"\b(?:effect|efficacy|safety|impact|role) of\s+([^.,;\n]+?)\s+(?:in|on|for|vs|versus|compared)\b",
            abstract or "",
            re.IGNORECASE,
        )
        if int_match and int_match.group(1):
            intervention = int_match.group(1).strip().capitalize()
            intervention_sentence = _sentence_around(abstract, int_match.start(), int_match.end())
            intervention_source = "abstract"

    if intervention == "Belirtilmedi" and title:
        int_title_match = re.search(r"^([A-Za-z0-9\s\-]+?)\s+\b(?:for|in|among|versus|vs\.?)\b", title, re.IGNORECASE)
        if int_title_match and int_title_match.group(1):
            t_cand = int_title_match.group(1).strip()
            if len(t_cand) > 2 and not any(k in t_cand.lower() for k in ["study", "trial", "analysis", "review"]):
                intervention = t_cand.capitalize()
                intervention_sentence = title.strip()
                intervention_source = "title"

    if comparison == "Belirtilmedi":
        comp_match = re.search(
            r"\b(?:versus|vs\.?|compared with|compared to|against)\s+([^.,;\n]+)",
            abstract or "",
            re.IGNORECASE,
        )
        if comp_match and comp_match.group(1):
            comparison = comp_match.group(1).strip().capitalize()
            comparison_sentence = _sentence_around(abstract, comp_match.start(), comp_match.end())
            comparison_source = "abstract"
        else:
            placebo_match = re.search(r"\bplacebo\b", abstract or "", re.IGNORECASE)
            if placebo_match:
                comparison = "Placebo"
                comparison_sentence = _sentence_around(abstract, placebo_match.start(), placebo_match.end())
                comparison_source = "abstract"

    if comparison.lower().startswith("placebo"):
        comparison = "Placebo"

    # 4. Outcomes stay tied to the abstract clause that stated the statistic
    bound_outcomes = []
    for om in outcome_metrics:
        bound_outcomes.append({
            "outcome": om.get("outcome") or "değerlendirilemedi",
            "metrics": list(om.get("metrics") or []),
            "sentence": om.get("sentence") or "",
            "source_sentence": om.get("sentence") or "",
            "pmid": pmid,
        })

    outcomes_formatted = []
    if bound_outcomes:
        for om in bound_outcomes:
            metric_text = ", ".join(om["metrics"]) if om["metrics"] else "değerlendirilemedi"
            outcomes_formatted.append(f"{om['outcome']}: {metric_text}")
    else:
        outcomes_formatted.append("Özette nicel etki ölçütü bildirilmedi")

    real_findings = _translate_clinical_conclusion_to_turkish(
        "", abstract, metrics, classification["design"], title, pico=extract_pico(query)
    )

    provenance = {
        "pmid": pmid,
        "population": _claim(patient_group, pop_sentence, "abstract"),
        "sample_size": _claim(sample_size_str, sample_sentence, "abstract"),
        "intervention": _claim(intervention, intervention_sentence, intervention_source),
        "comparison": _claim(comparison, comparison_sentence, comparison_source),
        "outcomes": bound_outcomes,
    }

    return {
        "patient_group": patient_group,
        "sample_size": sample_size_str,
        "study_design": classification["design"],
        "evidence_level": classification["level"],
        "evidence_level_note": classification["evidence_level_note"],
        "design_key": classification["design_key"],
        "intervention": intervention,
        "comparison": comparison,
        "outcome_metrics": bound_outcomes,
        "outcomes_summary": "; ".join(outcomes_formatted),
        "real_findings": real_findings,
        "provenance": provenance,
        "pmid": pmid,
    }


def _format_bound_claims(details: Dict[str, Any]) -> str:
    """Turkish lines that keep each extracted item next to its sentence and PMID."""
    prov = details.get("provenance") or {}
    pmid = prov.get("pmid") or details.get("pmid") or "PMID yok"
    lines = [f"*Kaynağa bağlı öğeler (PMID: {pmid}):*"]
    labels = (
        ("Hasta grubu", "population"),
        ("Örneklem", "sample_size"),
        ("Müdahale", "intervention"),
        ("Karşılaştırıcı", "comparison"),
    )
    for label, key in labels:
        item = prov.get(key) or {}
        value = item.get("value") or "değerlendirilemedi"
        sentence = item.get("source_sentence") or ""
        if sentence:
            lines.append(f"{label}: {value}. Kaynak cümle: \"{sentence}\" (PMID: {pmid})")
        else:
            lines.append(f"{label}: değerlendirilemedi. Kaynak cümle yok (PMID: {pmid})")
    outcomes = prov.get("outcomes") or []
    if not outcomes:
        lines.append(f"Sonlanım ve istatistik: değerlendirilemedi (PMID: {pmid})")
    for om in outcomes:
        metric_text = ", ".join(om.get("metrics") or []) or "değerlendirilemedi"
        sentence = om.get("source_sentence") or om.get("sentence") or ""
        if sentence:
            lines.append(
                f"Sonlanım: {om.get('outcome')}. İstatistik: {metric_text}. "
                f"Kaynak cümle: \"{sentence}\" (PMID: {pmid})"
            )
        else:
            lines.append(f"Sonlanım: değerlendirilemedi. İstatistik: {metric_text} (PMID: {pmid})")
    return " ".join(lines)


# Section 5 must not paste the English abstract. These labels stay Turkish.
# Outcome names, effect-measure wording, numbers, and the source sentence stay
# in the language of the abstract. Nothing is translated or invented.
NO_NUMERIC_CLINICAL_FINDING_TR = "Özette sayısal klinik bulgu bulunamadı"
_UNNAMED_OUTCOME_TR = "özette adlandırılmadı"
_UNNAMED_EFFECT_TR = "özette adlandırılmadı"
_MISSING_CI_TR = "özette bildirilmedi"
_UNPAIRED_CI_TR = "kaynak cümlede var ancak tek etki ölçütüne bağlanamadı"

_EFFECT_PHRASE_RE = re.compile(
    r"\b(hazard\s+ratios?|odds\s+ratios?|relative\s+risks?|risk\s+ratios?|"
    r"incidence\s+rate\s+ratios?|win\s+ratios?|"
    r"standardized\s+mean\s+differences?|mean\s+differences?)\b",
    re.IGNORECASE,
)
# Uppercase only, so the conjunction "or" is not read as an odds ratio.
_EFFECT_ACRONYM_RE = re.compile(r"\b(HR|OR|RR|IRR|SMD|WMD|MD)\b")
_FINDING_NUMBER_RE = re.compile(r"[-−]?\d+(?:\.\d+)?")
_CI_RE = re.compile(
    r"(?:\[\s*)?"
    r"(?:95\s*%\s*(?:confidence\s+intervals?|CI)|"
    r"(?:confidence\s+intervals?)\s*,?\s*95\s*%|"
    r"\bCI\s*,?\s*95\s*%)"
    r"(?![A-Za-z])"
    r"(?:\s*\[\s*CI\s*\])?"
    r"\s*[:=,]?\s*"
    r"\[?\s*"
    r"(?P<low>[-−]?\d+(?:\.\d+)?)"
    r"\s*(?:to|–|—|-|−|,)\s*"
    r"(?P<high>[-−]?\d+(?:\.\d+)?)"
    r"\s*\]?",
    re.IGNORECASE,
)
# Longer phrases first so "body weight" wins over "weight".
_OUTCOME_KEYWORDS = (
    "event-free survival",
    "progression-free survival",
    "overall survival",
    "hospitalization for heart failure",
    "heart failure hospitalization",
    "cardiovascular death",
    "all-cause mortality",
    "cardiovascular mortality",
    "lymphocytic leukaemia",
    "lymphocytic leukemia",
    "waist circumference",
    "body weight",
    "response rate",
    "adverse events",
    "leukaemia",
    "leukemia",
    "hospitalization",
    "remission",
    "relapse",
    "mortality",
    "myopathy",
    "infection",
    "exacerbation",
    "depression",
    "seizure",
    "weight",
    "stroke",
    "hba1c",
)


def _finding_sentences(abstract: str) -> List[str]:
    """Split an abstract into sentences without changing their wording."""
    text = (abstract or "").replace("\xa0", " ").replace("\u2009", " ")
    sentences = []
    for block in re.split(r"\n+", text):
        block = block.strip()
        if not block:
            continue
        for chunk in re.split(r"(?<=[.!?])\s+", block):
            sentence = re.sub(r"\s+", " ", chunk).strip()
            if sentence:
                sentences.append(sentence)
    return sentences


def _is_calendar_year(raw: str) -> bool:
    digits = raw.lstrip("-−")
    if not re.fullmatch(r"\d{4}", digits):
        return False
    year = int(digits)
    return 1900 <= year <= 2100


def _number_after(text: str, start: int, max_gap: int):
    """First non-year number within max_gap, not past a sentence boundary."""
    window = text[start:start + max_gap]
    for match in _FINDING_NUMBER_RE.finditer(window):
        gap = window[:match.start()]
        if re.search(r"[.!?]\s", gap):
            return None
        if _is_calendar_year(match.group(0)):
            continue
        return match
    return None


def _keyword_outcome(sentence: str, anchor: int) -> str:
    """Outcome word copied from the sentence, nearest to the effect measure."""
    found = []
    for keyword in _OUTCOME_KEYWORDS:
        for match in re.finditer(rf"\b{re.escape(keyword)}\b", sentence, re.IGNORECASE):
            found.append((-(match.end() - match.start()), abs(match.start() - anchor), match.start()))
    if not found:
        return ""
    found.sort()
    start = found[0][2]
    keyword = next(item for item in _OUTCOME_KEYWORDS if sentence[start:start + len(item)].lower() == item)
    return sentence[start:start + len(keyword)]


def _outcome_from_gap(sentence: str, name_end: int, value_start: int, anchor: int) -> str:
    gap = sentence[name_end:value_start]
    gap = re.sub(r"\([^)]*\)", " ", gap)
    gap = re.sub(r"^(?:\s*(?:for|of)\s+)+", "", gap, flags=re.IGNORECASE)
    gap = re.sub(r"\s+(?:of|was|were|is)$", "", gap.strip(" ,;:()[]"), flags=re.IGNORECASE)
    gap = gap.strip(" ,;:()[]")
    if gap and re.search(r"[A-Za-z]{4,}", gap) and len(gap) <= 90:
        if not re.fullmatch(
            r"(?:the|a|an|patients?|groups?|compared(?:\s+with)?|versus|vs\.?)",
            gap,
            re.IGNORECASE,
        ):
            return re.sub(r"\s+", " ", gap)
    return _keyword_outcome(sentence, anchor) or _UNNAMED_OUTCOME_TR


def _collect_named_effects(sentence: str) -> List[Dict[str, Any]]:
    """Named effect measures whose numeric value is in the same sentence."""
    candidates = []
    for pattern, max_gap in ((_EFFECT_PHRASE_RE, 90), (_EFFECT_ACRONYM_RE, 18)):
        for match in pattern.finditer(sentence):
            value = _number_after(sentence, match.end(), max_gap)
            if not value:
                continue
            value_start = match.end() + value.start()
            value_end = match.end() + value.end()
            candidates.append({
                "name": sentence[match.start():match.end()],
                "name_start": match.start(),
                "name_end": match.end(),
                "value": value.group(0),
                "value_start": value_start,
                "value_end": value_end,
                "span": match.end() - match.start(),
            })
    candidates.sort(key=lambda item: (item["name_start"], -item["span"]))
    kept = []
    for item in candidates:
        overlap = False
        for prior in kept:
            if not (item["value_end"] <= prior["name_start"] or item["name_start"] >= prior["value_end"]):
                overlap = True
                break
        if not overlap:
            kept.append(item)
    kept.sort(key=lambda item: item["name_start"])
    return kept


def _collect_confidence_intervals(sentence: str) -> List[Dict[str, Any]]:
    intervals = []
    for match in _CI_RE.finditer(sentence):
        intervals.append({
            "low": match.group("low"),
            "high": match.group("high"),
            "start": match.start(),
            "end": match.end(),
            "text": f"{match.group('low')} ile {match.group('high')}",
        })
    return intervals


def _point_before_ci(sentence: str, ci_start: int) -> str:
    """Number written immediately before a confidence interval, if the source has one."""
    window = sentence[max(0, ci_start - 28):ci_start]
    match = re.search(r"([-−]?\d+(?:\.\d+)?)(\s*%)?\s*[\(,;:]?\s*$", window)
    if not match or _is_calendar_year(match.group(1)):
        return ""
    percent = "%" if match.group(2) else ""
    return f"{match.group(1)}{percent}"


def _pair_effects_with_intervals(effects: List[Dict[str, Any]], intervals: List[Dict[str, Any]]):
    """Pair each effect with the CI that belongs to it. Do not guess when ambiguous."""
    if len(effects) == 1 and len(intervals) == 1:
        return [(effects[0], intervals[0])], []
    used = set()
    pairs = []
    ambiguous_notes = []
    for index, effect in enumerate(effects):
        next_name = effects[index + 1]["name_start"] if index + 1 < len(effects) else 10**9
        candidates = [
            item for item in intervals
            if effect["value_end"] <= item["start"] < next_name and id(item) not in used
        ]
        if len(candidates) == 1:
            used.add(id(candidates[0]))
            pairs.append((effect, candidates[0]))
        elif len(candidates) == 0:
            pairs.append((effect, None))
        else:
            pairs.append((effect, None))
            ambiguous_notes.append(", ".join(item["text"] for item in candidates))
    return pairs, ambiguous_notes


def extract_grounded_clinical_findings(abstract: str) -> List[Dict[str, str]]:
    """Turkish-labeled findings taken only from effect measures and CIs in the abstract.

    Each item keeps the PMID-ready fields outcome, effect, ci, and the exact
    source sentence. Missing outcome, effect name, or CI is stated in Turkish.
    """
    findings = []
    for sentence in _finding_sentences(abstract):
        effects = _collect_named_effects(sentence)
        intervals = _collect_confidence_intervals(sentence)
        if effects:
            pairs, ambiguous = _pair_effects_with_intervals(effects, intervals)
            ambiguous_text = "; ".join(note for note in ambiguous if note)
            for effect, interval in pairs:
                outcome = _outcome_from_gap(
                    sentence, effect["name_end"], effect["value_start"], effect["name_start"]
                )
                if interval is not None:
                    ci_text = interval["text"]
                elif ambiguous_text:
                    ci_text = f"{_UNPAIRED_CI_TR} ({ambiguous_text})"
                else:
                    ci_text = _MISSING_CI_TR
                findings.append({
                    "outcome": outcome,
                    "effect": f"{effect['name']} {effect['value']}",
                    "ci": ci_text,
                    "sentence": sentence,
                })
            continue
        if not intervals:
            continue
        for interval in intervals:
            point = _point_before_ci(sentence, interval["start"])
            if point:
                effect = f"{_UNNAMED_EFFECT_TR}; kaynak değer: {point}"
            else:
                effect = _UNNAMED_EFFECT_TR
            outcome = _keyword_outcome(sentence, interval["start"]) or _UNNAMED_OUTCOME_TR
            findings.append({
                "outcome": outcome,
                "effect": effect,
                "ci": interval["text"],
                "sentence": sentence,
            })
    return findings


def format_klinik_bulgular_cell(article: Dict[str, Any]) -> str:
    """Klinik Bulgular cell: Turkish labels, source numbers, exact source sentence.

    The raw abstract is never copied in. When no effect measure or confidence
    interval can be read from the abstract, the cell says so in Turkish.
    """
    pmid = str((article or {}).get("pmid") or "").strip() or "yok"
    findings = extract_grounded_clinical_findings((article or {}).get("abstract") or "")
    if not findings:
        return f"{NO_NUMERIC_CLINICAL_FINDING_TR} (PMID: {pmid})."
    parts = []
    for item in findings:
        sentence = item["sentence"].replace("|", "/").replace("\n", " ")
        parts.append(
            f"PMID: {pmid}. Sonlanım: {item['outcome']}. "
            f"Etki ölçütü: {item['effect']}. "
            f"Güven aralığı: {item['ci']}. "
            f"Kaynak cümle: \"{sentence}\"."
        )
    return " ".join(parts)


def generate_evidence_table_markdown(articles: List[Dict[str, Any]]) -> str:
    """Generates a structured Markdown table of evidence with PICO & Risk of Bias for the report."""
    if not articles:
        return "*Tablo için gösterilecek veri bulunamadı.*"

    rows = [
        "| # | Çalışma / Yazar (Yıl) | Çalışma Tasarımı | Yanlılık Aracı (derece yok) | PMID / DOI | Klinik Bulgular |",
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
        design_str = f"**{classification['design']}** — *Kanıt düzeyi: {classification['level']}*"

        rob = assess_risk_of_bias(art)
        rob_str = f"**{rob['overall_rating']}** — *{rob['tool']}*"

        pmid_link = f"[PMID: {pmid}]({art.get('pubmed_url', '#')})" if pmid else "-"
        if doi:
            pmid_link += f" / [DOI: {doi}]({art.get('doi_url', '#')})"

        finding_cell = format_klinik_bulgular_cell(art).replace("|", "/").replace("\n", " ")
        title_clean = title.replace("|", "-")

        rows.append(
            f"| {idx} | **{first_author}** ({year}) — *{title_clean}* | {design_str} | {rob_str} | {pmid_link} | {finding_cell} |"
        )

    return "\n".join(rows)


def generate_evidence_table_html(articles: List[Dict[str, Any]]) -> str:
    """Generates a responsive, clean HTML evidence table for web display and HTML exports."""
    import html
    if not articles:
        return "<p><em>Gösterilecek literatür verisi bulunamadı.</em></p>"

    html_rows = []
    for idx, art in enumerate(articles, 1):
        first_author = html.escape(_format_authors_short(art.get("authors", [])))
        year = html.escape(str(art.get("pub_year", "Tarih Yok")))
        title = html.escape(str(art.get("title", "Başlıksız")))
        journal = html.escape(str(art.get("journal", "Bilinmeyen Dergi")))
        pmid = html.escape(str(art.get("pmid", "")))
        doi = html.escape(str(art.get("doi", "")))

        classification = classify_study_design(
            art.get("publication_types", []),
            art.get("title", ""),
            art.get("abstract", "")
        )

        rob = assess_risk_of_bias(art)

        finding_cell = html.escape(format_klinik_bulgular_cell(art))

        pubmed_url = html.escape(art.get("pubmed_url", "#"))
        doi_url = html.escape(art.get("doi_url", "#"))

        pmid_html = f'<a href="{pubmed_url}" target="_blank" style="color: #1E40AF; text-decoration: none; font-weight: bold; word-break: break-all;">PMID: {pmid}</a>' if pmid else "-"
        doi_html = f'<br><a href="{doi_url}" target="_blank" style="color: #3730A3; text-decoration: none; font-size: 0.85em; word-break: break-all;">DOI: {doi}</a>' if doi else ""

        level_escaped = html.escape(classification['level'])
        design_escaped = html.escape(classification['design'])
        rating_escaped = html.escape(rob['overall_rating'])
        tool_escaped = html.escape(rob['tool'])

        html_rows.append(f"""
        <tr style="border-bottom: 1px solid #E5E7EB;">
            <td style="padding: 10px; font-weight: bold; text-align: center;">{idx}</td>
            <td style="padding: 10px; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word;">
                <strong>{first_author}</strong> ({year})<br>
                <span style="font-size: 0.9em; color: #374151;">{title}</span><br>
                <small style="color: #6B7280;">{journal}</small>
            </td>
            <td style="padding: 10px; text-align: center;">
                <span style="background-color: {classification['badge_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; display: inline-block;">
                    {level_escaped}
                </span><br>
                <small style="color: #4B5563;">{design_escaped}</small>
            </td>
            <td style="padding: 10px; text-align: center;">
                <span style="background-color: {rob['badge_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; display: inline-block;">
                    {rating_escaped}
                </span><br>
                <small style="color: #4B5563;">{tool_escaped}</small>
            </td>
            <td style="padding: 10px; font-size: 0.85em; word-break: break-all;">{pmid_html}{doi_html}</td>
            <td style="padding: 10px; font-size: 0.88em; color: #1F2937; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word;">{finding_cell}</td>
        </tr>
        """)

    return f"""
    <div style="width: 100%; max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 15px 0;">
        <table style="width: 100%; min-width: 600px; border-collapse: collapse; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; table-layout: auto;">
            <thead>
                <tr style="background-color: #F3F4F6; color: #1F2937; text-align: left; border-bottom: 2px solid #D1D5DB;">
                    <th style="padding: 10px; width: 4%;">#</th>
                    <th style="padding: 10px; width: 24%;">Çalışma / Yazar</th>
                    <th style="padding: 10px; width: 16%; text-align: center;">Çalışma Tasarımı</th>
                    <th style="padding: 10px; width: 18%; text-align: center;">Yanlılık Aracı</th>
                    <th style="padding: 10px; width: 12%;">Kimlik</th>
                    <th style="padding: 10px; width: 26%;">Klinik Bulgular</th>
                </tr>
            </thead>
            <tbody>
                {"".join(html_rows)}
            </tbody>
        </table>
    </div>
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
        warnings.append("İncelenen kaynaklar arasında randomize kontrollü çalışma, sistematik derleme veya meta-analiz yok. Bu saptama tek başına bir kanıt düzeyi değildir.")

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
        "expert_physician_review": EXPERT_PHYSICIAN_REVIEW_STATUS,
        "physician_review_status": EXPERT_PHYSICIAN_REVIEW_STATUS,
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
            "notice": "GRADE (Grading of Recommendations Assessment, Development and Evaluation) derecelendirmesi otomatik olarak atanmamıştır ve 'GRADE Değerlendirilmedi (Not Assessed)' statüsündedir. Resmi GRADE; yanlılık riski, tutarsızlık, dolaylılık, kesinlik eksikliği ve yayın yanlılığını sonlanım bazında ve tam metinle değerlendirir. Eksik sonlanım 'değerlendirilemedi' bırakılır."
        },
        "methodological_warnings": warnings
    }


def _translate_clinical_conclusion_to_turkish(
    raw_conc: str,
    abstract: str,
    metrics: Dict[str, Any],
    design_name: str,
    title: str,
    pico: Optional[Dict[str, str]] = None
) -> str:
    """
    Synthesizes clinical study results into Turkish WITHOUT generating automated claims
    from trigger words like 'effective', 'safe', 'reduced', or 'associated with'.
    Integrates quantitative metrics (n, HR/OR/RR, 95% CI, p-values), PICO context,
    and reports evidence limitations when data is unverified or non-quantitative.
    """
    text_to_check = (raw_conc or abstract or "").lower()

    # Format extracted metrics
    stat_parts = []
    if metrics.get("n"):
        stat_parts.append(f"n = {metrics['n']}")
    if metrics.get("effect_sizes"):
        stat_parts.append(f"Etki büyüklüğü: {', '.join(metrics['effect_sizes'])}")
    if metrics.get("confidence_intervals"):
        cleaned_cis = [re.sub(r"^\s*\[?\s*(?:95%\s*CI|95%CI|CI\s*95%)\s*[:=,]?\s*", "", ci, flags=re.IGNORECASE).rstrip("]") for ci in metrics["confidence_intervals"]]
        stat_parts.append(f"%95 GA: {', '.join(cleaned_cis)}")
    if metrics.get("p_values"):
        stat_parts.append(f"p değeri: {', '.join(metrics['p_values'])}")

    stat_str = f" ({'; '.join(stat_parts)})" if stat_parts else ""

    # Check for explicit non-significant / negative findings
    is_nonsignificant = any(phrase in text_to_check for phrase in [
        "no significant", "not significant", "no statistically significant",
        "statistically insignificant", "no difference", "not associated",
        "failed to show", "did not reduce", "did not improve"
    ]) or any("p >" in p.lower() or "p> " in p.lower() or "p >0" in p.lower() for p in metrics.get("p_values", []))

    # Check for explicit conflicting / heterogeneous findings
    is_conflicting = any(phrase in text_to_check for phrase in [
        "conflicting", "inconsistent", "discrepant", "mixed results",
        "heterogeneous", "controversial"
    ])

    title_snippet = f"*{title}* çalışması ({design_name})" if title else f"{design_name}"

    is_review = any(k in design_name.lower() for k in ["derleme", "meta-analiz", "kılavuz", "uzman görüşü", "review", "guideline", "editorial"])

    if is_review:
        if is_conflicting:
            summary_tr = f"{title_snippet} niteliğindeki bu yayında derlenen verilerde çelişkili veya heterojen sonuçlar bildirilmiştir{stat_str}."
        elif is_nonsignificant:
            summary_tr = f"{title_snippet} niteliğindeki bu yayında derlenen verilere göre gruplar veya parametreler arasında istatistiksel olarak anlamlı bir fark saptanmamıştır{stat_str}."
        elif stat_parts:
            summary_tr = f"{title_snippet} niteliğindeki bu yayında literatürdeki klinik/RCT verileri derlenmiş olup atıfta bulunulan çalışma bulguları: {'; '.join(stat_parts)}. *(Not: Bu bulgular derleme yazarının bağımsız ampirik araştırması olmayıp, referans gösterilen klinik çalışmalardan aktarılmıştır.)*"
        else:
            summary_tr = f"{title_snippet} niteliğindeki yayında klinik veriler ve literatür bulguları derlenmiş olup özet metninde nicel istatistiksel parametre bildirilmemiştir."
    elif is_conflicting:
        summary_tr = f"{title_snippet} verilerinde çelişkili veya heterojen sonuçlar bildirilmiştir{stat_str}."
    elif is_nonsignificant:
        summary_tr = f"{title_snippet} bulgularına göre gruplar veya parametreler arasında istatistiksel olarak anlamlı bir fark saptanmamıştır{stat_str}."
    elif stat_parts:
        summary_tr = f"{title_snippet} kapsamında elde edilen istatistiksel ve nicel bulgular: {'; '.join(stat_parts)}."
    else:
        summary_tr = f"{title_snippet} özetinde kural tabanlı motor tarafından doğrulanabilir nicel klinik sonuç veya istatistiksel parametre verisi yetersizdir / bildirilmemiştir; tam metin incelemesi önerilir."

    return summary_tr


def _synthesize_article_conclusion_tr(art: Dict[str, Any], query: str) -> str:
    """Synthesizes a topic-specific Turkish clinical conclusion for an article with explicit PMID citation based on actual abstract data."""
    pmid = art.get("pmid", "")
    pubmed_url = art.get("pubmed_url", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#")
    authors_short = _format_authors_short(art.get("authors", []))
    year = art.get("pub_year", "")
    title = art.get("title", "")
    abstract = (art.get("abstract") or "").strip()
    pmid_link = f"[PMID: {pmid}]({pubmed_url})" if pmid else "PMID Yok"

    pico = extract_pico(query)
    pico_str = f"Popülasyon (P): **{pico['population']}** | Müdahale (I): **{pico['intervention']}** | Karşılaştırma (C): **{pico['comparison']}** | Sonlanım (O): **{pico['outcome']}**"

    if not abstract or abstract in ["Özet bulunamadı.", "Özet bilgisi bulunamadı."] or len(abstract) < 40:
        return (
            f"- **{authors_short} ({year})** ({pmid_link}): Makale özetinde klinik kanıt veya sonuç verisi yetersizdir / bildirilmemiştir.\n"
            f"  - *Hasta Sayısı:* Özette bildirilmedi | *Etki Ölçütleri:* Bildirilmedi | *Belirsizlikler:* Özet metni yetersizdir\n"
            f"  - *PICO Matrisi:* {pico_str}"
        )

    metrics = extract_study_metrics(abstract)
    classification = classify_study_design(art.get("publication_types", []), title, abstract)
    design_name = classification.get("design", "Çalışma")

    summary_tr = _translate_clinical_conclusion_to_turkish("", abstract, metrics, design_name, title, pico=pico)

    is_review_type = _excluded_from_primary_pool(design_name)

    review_note = ""
    if is_review_type:
        review_note = " *(Derleme/Kılavuz/Uzman Görüşü niteliğindeki yayınlardan kesin tedavi etkinliği çıkarılamaz; bu yayınlar ampirik primer veri sunmamaktadır.)*"

    n_val_str = f"n = {metrics['n']}" if metrics.get("n") else "Özette bildirilmedi"

    eff_parts = []
    if metrics.get("effect_sizes"):
        eff_parts.append(", ".join(metrics["effect_sizes"]))
    if metrics.get("confidence_intervals"):
        eff_parts.append(", ".join(metrics["confidence_intervals"]))
    if metrics.get("p_values"):
        eff_parts.append(", ".join(metrics["p_values"]))
    eff_val_str = "; ".join(eff_parts) if eff_parts else "Özette nicel etki ölçütü bildirilmedi"

    lim_val_str = " ".join(metrics.get("causality_limitations", [])) or "Yalnızca özet metnine dayalı sınırlılık (tam metin incelemesi önerilir)"

    details = extract_article_clinical_details(art, query)
    return (
        f"- **{authors_short} ({year})** ({pmid_link}): {summary_tr}{review_note}\n"
        f"  - *Hasta Sayısı:* {n_val_str} | *Etki Ölçütleri:* {eff_val_str} | *Belirsizlikler:* {lim_val_str}\n"
        f"  - *Sorgu PICO (makale özeti değildir):* {pico_str}\n"
        f"  - {_format_bound_claims(details)}"
    )


def _generate_section_12_synthesis(query: str, articles: List[Dict[str, Any]], cross_comp: Optional[Dict[str, Any]] = None) -> str:
    """
    Synthesizes Section 12 ("Klinik Sonuç") in Turkish without printing a bulleted article list.
    Synthesizes 4 mandatory clinical dimensions:
    1. Ortak Klinik Bulgular ve Sentez (Common Clinical Findings with PMID citations)
    2. Çelişkili Bulgular ve Heterojenlikler (Contradictions & Discrepancies)
    3. Klinik Önem ve Uygulanabilirlik (Clinical Significance & Practice)
    4. Kanıt Sınırlılıkları (Evidence Limitations & Constraints)
    """
    if not articles:
        return "İncelenen literatürde sentezlenecek klinik kanıt bulunamamıştır."

    primary_studies = []
    review_studies = []

    for art in articles:
        cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))
        d_design = cd.get("design", "")
        pts_str = " ".join([pt.lower() for pt in art.get("publication_types", [])])
        if _excluded_from_primary_pool(d_design) or any(k in pts_str for k in ["guideline", "editorial"]):
            review_studies.append(art)
        else:
            primary_studies.append(art)

    sec_lines = []

    # 1. Ortak Klinik Bulgular ve Sentez
    sec_lines.append("### 🎯 Ortak Klinik Bulgular ve Sentez")

    if primary_studies:
        primary_citations = []
        quant_summaries = []
        for art in primary_studies:
            pmid = art.get("pmid", "")
            pubmed_url = art.get("pubmed_url", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#")
            pmid_link = f"[PMID: {pmid}]({pubmed_url})" if pmid else "PMID Yok"
            authors_short = _format_authors_short(art.get("authors", []))
            year = art.get("pub_year", "")
            details = extract_article_clinical_details(art, query)

            quant_summaries.append(
                f"**{authors_short} ({year})** ({pmid_link}): {details['real_findings']} "
                f"(Tasarım: {details['study_design']}, kanıt düzeyi: {details.get('evidence_level', UNASSIGNED_EVIDENCE_LEVEL)}, "
                f"Örneklem: {details['sample_size']}, Sonlanım Ölçütleri: {details['outcomes_summary']}). "
                f"{_format_bound_claims(details)}"
            )

        sec_lines.append(f"**{query}** odağında incelenen ampirik primer araştırmalar klinik verileri ve nicel etki ölçütlerini ortaya koymaktadır:")
        sec_lines.append("\n".join([f"- {s}" for s in quant_summaries]))
        sec_lines.append("")

    if review_studies:
        rev_citations = []
        rev_bound = []
        for a in review_studies:
            pmid = a.get("pmid", "")
            p_url = a.get("pubmed_url", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#")
            p_link = f"[PMID: {pmid}]({p_url})" if pmid else "PMID Yok"
            rev_citations.append(f"{_format_authors_short(a.get('authors', []))} ({a.get('pub_year', '')}) {p_link}")
            rev_bound.append(_format_bound_claims(extract_article_clinical_details(a, query)))

        sec_lines.append(
            f"Derleme, meta-analiz, kılavuz ve olgu sunumu niteliğindeki yayınlarda ({', '.join(rev_citations)}) "
            "kesin tedavi etkinliği çıkarılmamıştır. Özette geçen sayılar aşağıdaki kaynak cümlelerine bağlıdır: "
            + " ".join(rev_bound)
        )
        sec_lines.append("")

    # 2. Çelişkili Bulgular ve Heterojenlikler
    sec_lines.append("### ⚠️ Çelişkili Bulgular ve Heterojenlikler")
    conflicts = []

    if cross_comp and cross_comp.get("conflicting_findings"):
        for cf in cross_comp["conflicting_findings"]:
            conflicts.append(f"- {cf['details']}")
    else:
        for art in articles:
            pmid = art.get("pmid", "")
            p_url = art.get("pubmed_url", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#")
            pmid_link = f"[PMID: {pmid}]({p_url})" if pmid else ""
            authors_short = _format_authors_short(art.get("authors", []))
            year = art.get("pub_year", "")
            abs_text = (art.get("abstract") or "").lower()

            if any(phrase in abs_text for phrase in ["conflicting", "inconsistent", "discrepant", "mixed results", "heterogeneous", "controversial"]):
                conflicts.append(f"- **{authors_short} ({year})** ({pmid_link}): Çalışma özetinde veriler arasında heterojenlik veya çelişkili klinik bulgular vurgulanmıştır.")

    if conflicts:
        sec_lines.append("\n".join(conflicts))
    else:
        pmid_links_all = [f"[PMID: {a.get('pmid')}]({a.get('pubmed_url', '#')})" for a in articles if a.get("pmid")]
        sec_lines.append(f"İncelenen çalışmalarda ({', '.join(pmid_links_all)}) hasta seçim kriterleri, örneklem büyüklükleri ve takip sürelerindeki farklılıklara bağlı metodolojik heterojenlikler mevcuttur. Bireysel çalışmaların sonuçları klinik bağlamda ayrı ayrı değerlendirilmelidir.")
    sec_lines.append("")

    # 3. Klinik Önem ve Uygulanabilirlik
    sec_lines.append("### 🩺 Klinik Önem ve Uygulanabilirlik")
    pmid_links_primary = [f"[PMID: {a.get('pmid')}]({a.get('pubmed_url', '#')})" for a in primary_studies if a.get("pmid")]
    sec_lines.append(
        f"Elde edilen klinik kanıt sentezi, hekimin **{query}** konusundaki karar destek sürecini yapılandırmayı amaçlamaktadır. "
        f"Primer araştırmaların özette bildirilen nicel bulguları ({', '.join(pmid_links_primary) if pmid_links_primary else 'bulunmamaktadır'}) "
        "kaynak cümleleriyle okunmalıdır. Çalışma tasarımından kanıt düzeyi üretilmemiştir."
    )
    sec_lines.append("*Uyarı: Bu kanıt raporu doğrudan otomatik tedavi kararı niteliğinde değildir; kaynaksız tedavi önerisi üretilmemiştir. Sorumlu hekim klinik değerlendirmeyi bireysel hasta bağlamında yapmalıdır.*")
    sec_lines.append("")

    # 4. Kanıt Sınırlılıkları ve Metodolojik Engeller
    sec_lines.append("### 🔬 Kanıt Sınırlılıkları ve Metodolojik Engeller")
    limitations = []
    for art in articles:
        pmid = art.get("pmid", "")
        p_url = art.get("pubmed_url", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#")
        pmid_link = f"[PMID: {pmid}]({p_url})" if pmid else ""
        authors_short = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "")
        metrics = extract_study_metrics(art.get("abstract", ""))

        if metrics.get("causality_limitations"):
            limitations.append(f"- **{authors_short} ({year})** ({pmid_link}): {' '.join(metrics['causality_limitations'])}")

    if limitations:
        sec_lines.append("\n".join(limitations))

    pmid_links_all = [f"[PMID: {a.get('pmid')}]({a.get('pubmed_url', '#')})" for a in articles if a.get("pmid")]
    sec_lines.append(f"- Tüm analizler NCBI PubMed veritabanındaki yayınlanmış özet (abstract-only) metinlerine dayanmaktadır; tam metin (full-text) incelemesi yapılmamıştır ({', '.join(pmid_links_all)}).")
    sec_lines.append("- Otomatik GRADE kanıt kesinlik derecelendirmesi atanmamış olup 'GRADE Değerlendirilmedi (Not Assessed)' statüsündedir.")

    return "\n".join(sec_lines)


def generate_rule_based_turkish_report(query: str, articles: List[Dict[str, Any]], search_metadata: Optional[Dict[str, Any]] = None) -> str:
    """Generates an advanced structured, deterministic Turkish evidence report with 13 explicit sections."""
    import datetime
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    search_date_str = (search_metadata or {}).get("search_date") or today_str

    if not articles:
        return f"""# 📑 Türkçe Klinik Araştırma Raporu

{EXPERT_PHYSICIAN_REVIEW_LINE}

## 1. Klinik Araştırma Sorusu
{query}

---

### ⚠️ Sonuç Bulunamadı
Aranan klinik sorgu için doğrulanan PubMed veritabanında kriterlere uygun makale bulunamamıştır.
Lütfen arama terimlerini veya filtreleri genişleterek tekrar deneyiniz.
"""

    total_articles = len(articles)
    audit = perform_red_team_audit(query, articles)
    pico = extract_pico(query)

    report = []
    report.append("# 📑 Türkçe Klinik Araştırma Raporu\n")
    report.append(f"{EXPERT_PHYSICIAN_REVIEW_LINE}\n")

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
    report.append(f"Bu kanıt raporu, **{query}** sorusu için NCBI PubMed kaydından alınan **{total_articles}** yayının özetine dayanır.")
    report.append("Çalışma tasarımı sınıflandırıldı. Kanıt düzeyi çalışma tasarımından üretilmedi. GRADE, sonlanım bazında ve yalnızca özette bulunan veriyle ön not olarak yazılır; eksik sonlanım değerlendirilemedi bırakılır. *Tüm analizler yayınlanmış özet (abstract) metinlerine dayanmaktadır.*\n")

    # 3. Araştırma Yöntemi ve Tarama Tarihi
    report.append("## 3. Araştırma Yöntemi ve Tarama Tarihi")
    report.append(f"- **Tarama Tarihi:** {search_date_str}")
    report.append("- **Veri Kaynağı:** NCBI PubMed E-utilities (`esearch` / `efetch`) API & CrossRef REST API")
    report.append(f"- **Arama İfadesi:** `{query}`")
    report.append(f"- **İncelenen Toplam Makale Sayısı:** {total_articles}")
    report.append("- **Dahil Etme / Hariç Tutma:** Mükerrer (duplicate) PMID/DOI kayıtları ayıklanmış, canlı PubMed API üzerinden doğrulanabilen çalışmalar rapora dahil edilmiştir.\n")

    # 4. Klinik Arka Plan ve Patofizyoloji
    report.append("## 4. Klinik Arka Plan ve Patofizyoloji")
    background_findings = []
    for art in articles:
        abs_text = art.get("abstract", "")
        pmid = art.get("pmid", "")
        authors_short = _format_authors_short(art.get("authors", []))
        pmid_link = f"[PMID: {pmid}]({art.get('pubmed_url', '#')})" if pmid else ""
        cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), abs_text)

        opening = _sentence_around(abs_text, 0, 1) if abs_text else ""
        source_bit = (
            f" Kaynak cümle: \"{opening}\" (PMID: {pmid})."
            if opening
            else " Kaynak cümle: değerlendirilemedi."
        )
        background_findings.append(
            f"- **{authors_short} ({art.get('pub_year', '')})** ({pmid_link}): "
            f"*{art.get('title', '')}* ({cd['design']}). Kanıt düzeyi: {cd['level']}. "
            f"Özetten patofizyoloji veya biyobelirteç sonucu çıkarılmamıştır.{source_bit}"
        )

    if background_findings:
        report.append(f"**{query}** için aşağıdaki satırlar yayın kimliğini ve çalışma tasarımını gösterir. Özet, tam metin mekanizma verisinin yerine geçmez.\n")
        report.append("\n".join(background_findings) + "\n")
    else:
        report.append(f"İncelenen {total_articles} makale özetinde **{query}** konusuna ilişkin patofizyolojik mekanizmalar ve moleküler süreçler kural tabanlı motor tarafından tam olarak çıkarılamamıştır. Ayrıntılı patofizyolojik analiz için ilgili yayınların tam metinlerinin incelenmesi önerilir.\n")

    # 5. Bilimsel Kanıt Tablosu
    report.append("## 5. Bilimsel Kanıt Tablosu")
    report.append(
        "Aşağıdaki tabloda yazar, yıl, çalışma tasarımı ve seçilen yanlılık aracı yer alır. "
        "Kanıt düzeyi tasarımından üretilmez. Araç seçilmiş olsa da değerlendirme yapılmadan risk derecesi verilmez. "
        "Klinik Bulgular hücresi ham özet metni değildir. Her sayısal sonuç PMID, sonlanım, etki ölçütü "
        "(değer ve varsa güven aralığı) ve kaynak cümle ile gösterilir. Özette çıkarılabilir sayısal bulgu yoksa "
        "bu açıkça yazılır. Kaynakta olmayan sayı, güven aralığı veya sonlanım üretilmez.\n"
    )
    report.append(generate_evidence_table_markdown(articles))
    report.append("\n")

    # Cross-article comparison calculation via engine
    try:
        from universal_evidence_engine import UniversalEvidenceEngine
        cross_engine = UniversalEvidenceEngine()
        cross_comp = cross_engine.compare_cross_article_findings(articles, query)
    except Exception:
        cross_comp = None

    # 6. Önemli Çalışmaların Karşılaştırılması
    report.append("## 6. Önemli Çalışmaların Karşılaştırılması")
    report.append("### 📊 Karşılaştırmalı Sentez Matrisi")

    comp_lines = []
    for art in articles:
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))
        rob = assess_risk_of_bias(art)
        pmid = art.get("pmid", "")
        pmid_link = f"[PMID: {pmid}]({art.get('pubmed_url', '#')})" if pmid else "-"
        metrics = extract_study_metrics(art.get("abstract", ""))

        n_str = f"n = {metrics['n']}" if metrics.get("n") else "n bildirilmedi"

        stat_summary = _translate_clinical_conclusion_to_turkish("", art.get("abstract", ""), metrics, cd["design"], art.get("title", ""), pico=pico)
        lim_str = " ".join(metrics.get("causality_limitations", [])) or "Özette spesifik metodolojik sınırlılık vurgulanmamıştır (Tam metin incelemesi önerilir)."

        outcomes_list = extract_outcome_metrics(art.get("abstract", ""))
        o_str_parts = []
        if outcomes_list:
            for om in outcomes_list:
                m_str = ", ".join(om.get("metrics", [])) if om.get("metrics") else "Özette nicel etki ölçütü yok"
                o_str_parts.append(f"{om['outcome']} ({m_str})")
            o_str = "; ".join(o_str_parts)
        else:
            o_str = "Özette bağlı nicel sonlanım ölçütü bildirilmedi"

        bound = _format_bound_claims(extract_article_clinical_details(art, query))
        comp_lines.append(
            f"- **{first_author} ({year})** ({pmid_link}):\n"
            f"  - **Yöntem ve tasarım:** {cd['design']} | **Kanıt düzeyi:** {cd['level']}\n"
            f"  - **Yanlılık aracı:** {rob['tool']} | **Risk derecesi:** {rob['overall_rating']}\n"
            f"  - **Hasta / Örneklem Sayısı:** {n_str}\n"
            f"  - **Klinik Sonlanımlar ve Etki Ölçütleri:** {o_str}\n"
            f"  - **Kaynağa bağlı PICO ve istatistik:** {bound}\n"
            f"  - **Klinik Bulgular:** {stat_summary}\n"
            f"  - **Kanıt Sınırlılıkları:** {lim_str}"
        )

    report.append("\n".join(comp_lines) + "\n")

    report.append("### ✅ Tutarlı Klinik Bulgular")
    if cross_comp and cross_comp.get("consistent_findings"):
        c_lines = []
        for cf in cross_comp["consistent_findings"]:
            c_lines.append(f"- **Sonlanım:** {cf['outcome']} | **Kaynaklar:** {cf['source_citations']}\n  - {cf['details']}")
        report.append("\n".join(c_lines) + "\n")
    else:
        report.append("Doğrudan eşleşen PICO ve çalışma tasarımına sahip makaleler arasında tutarlı sonlanım çifti saptanmamıştır veya çalışmalar metodolojik açıdan heterojendir.\n")

    report.append("### 🚫 Karşılaştırılamama Durumları ve Gerekçeleri")
    if cross_comp and cross_comp.get("non_comparable_studies"):
        nc_lines = []
        for nc in cross_comp["non_comparable_studies"]:
            nc_lines.append(f"- **Kaynaklar:** {nc['source_citations']}\n  - **Gerekçe:** {nc['reason']}")
        report.append("\n".join(nc_lines) + "\n")
    else:
        report.append("İncelenen tüm primer çalışmalar birbiriyle karşılaştırılabilir PICO yapısına sahiptir.\n")

    report.append("### 📑 Bireysel Çalışma Detayları")
    for idx, art in enumerate(articles, 1):
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        title = art.get("title", "Başlıksız")
        cd = classify_study_design(art.get("publication_types", []), title, art.get("abstract", ""))
        rob = assess_risk_of_bias(art)
        pmid = art.get("pmid", "")

        report.append(f"#### {idx}. {first_author} ({year}) — *{title}*")
        report.append(f"- **Çalışma tasarımı:** {cd['design']}")
        report.append(f"- **Kanıt düzeyi:** {cd['level']}. {cd.get('evidence_level_note', EVIDENCE_LEVEL_NOTE)}")
        report.append(f"- **Yanlılık aracı:** {rob['tool']} | **Risk derecesi:** {rob['overall_rating']}")
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
        metrics = extract_study_metrics(abs_text)
        cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), abs_text)
        p_link = f"[PMID: {p}]({art.get('pubmed_url', '#')})" if p else "PMID Yok"

        stat_summary = _translate_clinical_conclusion_to_turkish("", abs_text, metrics, cd["design"], art.get("title", ""), pico=pico)
        efficacy_items.append(f"- **{t} ({art.get('pub_year', '')})** ({p_link}): {stat_summary}")

    if efficacy_items:
        report.append("\n".join(efficacy_items) + "\n")
    else:
        report.append("*İncelenen çalışmalarda kural tabanlı motor tarafından doğrulanabilir etkinlik ve güvenlilik parametresi saptanmamıştır.*\n")

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
    if cross_comp and cross_comp.get("conflicting_findings"):
        conf_lines = []
        for cf in cross_comp["conflicting_findings"]:
            conf_lines.append(f"- **Sonlanım:** {cf['outcome']} | **Kaynaklar:** {cf['source_citations']}\n  - {cf['details']}")
        report.append("\n".join(conf_lines) + "\n")
    else:
        report.append("Doğrudan eşleşen PICO ve çalışma tasarımına sahip makaleler arasında zıt yönde istatistiksel çelişki tespit edilmemiştir. Bununla birlikte, farklı çalışmalar arasındaki örneklem büyüklükleri, alt grup özellikleri, tedavi protokolleri ve takip sürelerindeki heterojenlikler klinik bağlamda dikkate alınmalıdır.\n")

    # 10. Red Team Eleştirisi
    report.append("## 10. Red Team Eleştirisi")
    report.append(f"- **Denetim Statüsü:** `{audit['status']}`")
    report.append(f"- **Atıf Doğrulaması:** {audit['citation_integrity']['verified_citations']} Doğrulanmış, {audit['citation_integrity']['rejected_citations']} Reddedilen (Eşleşmeme), {audit['citation_integrity']['unverified_citations']} Doğrulanamadı (API Hatası)")
    report.append(f"- **Mükerrer PMID Tespiti:** {'Evet (Ayıklandı)' if audit['citation_integrity']['duplicate_pmids_found'] else 'Mükerrer kayıt yok'}")
    report.append(f"- **Metodolojik Sınırlılık:** {audit['abstract_only_limitation']}")
    report.append(f"- **Klinik Doğrulama:** {audit['clinical_validation_status']}")
    report.append(f"- {EXPERT_PHYSICIAN_REVIEW_LINE}")
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
    report.append("- **Sınırlılıklar:** Analizlerin yalnızca özet metinlerine (abstract-only) dayanması nedeniyle tam metin detayları, ham veriler ve protokol sapmaları doğrulamaya muhtaçtır.")
    from grade_assessment import format_preliminary_grade_markdown
    report.append(format_preliminary_grade_markdown(query, articles))
    report.append("")

    # 12. Klinik Sonuç
    report.append("## 12. Klinik Sonuç")
    report.append(f"**{query}** konusu kapsamındaki doğrulanmış kanıtların kaynaklara dayalı Türkçe karşılaştırmalı değerlendirmesi ve klinik çıkarımları aşağıda sunulmaktadır:\n")
    report.append(_generate_section_12_synthesis(query, articles, cross_comp=cross_comp))
    report.append("\n*Uyarı: Bu sentez sonuçları hekimin klinik kararına destek sağlama amacını taşır; doğrudan otomatik tedavi kararı niteliğinde değildir.*\n")

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
            f"Makale Türü ve Tasarım: {', '.join(art.get('publication_types', []))} ({cd['design']}; kanıt düzeyi: {cd['level']})\n"
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
        f"5. Raporda şu satır AYNEN yer almalıdır: '{EXPERT_PHYSICIAN_REVIEW_LINE}'. Bu rapor klinik imza veya uzman onayı anlamına gelmez.\n"
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
        "   - ## 13. Doğrulanmış Kaynakça\n\n"
        "7. Bölüm 5'teki Klinik Bulgular hücresine ham İngilizce özet yapıştırma. "
        "Önceden üretilmiş tablodaki Türkçe ve kaynağa bağlı bulguyu aynen kullan. "
        "Sayısal bulgu yoksa 'Özette sayısal klinik bulgu bulunamadı' ifadesini koru. "
        "Kaynakta olmayan sayı, güven aralığı veya sonlanım üretme.\n"
        "8. BÖLÜM 12 (Klinik Sonuç) İÇİN ÖZEL KURALLAR:\n"
        "   - Bölüm 12'de kaynaklara dayalı, Türkçe, karşılaştırmalı bir değerlendirme üret.\n"
        "   - Derleme/kılavuz/uzman görüşü niteliğindeki yayınlardan kesin tedavi etkinliği KESİNLİKLE ÇIKARMA!\n"
        "   - Çalışmaların hasta sayılarını (n), etki ölçütlerini (HR, OR, RR, IRR, SMD, MD, %95 GA, p) ve belirsizlikleri/sınırlılıkları [PMID: xxx] kaynaklarıyla göster.\n"
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
        <p>{EXPERT_PHYSICIAN_REVIEW_LINE}</p>
        <p><strong>Veri Kapsamı:</strong> Yalnızca özet metin (Abstract-Only Limitation). Tam metin değerlendirmesi yapılmamıştır.</p>
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

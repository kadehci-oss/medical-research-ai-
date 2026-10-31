"""Structured evidence model shared by search cards, report sections 5/6 and exports.

One ``Study`` object is built per PubMed record. Every extracted value carries an
``EvidenceSource`` (PMID, DOI, verbatim source sentence, verification status).
Renderers read these objects; they never re-parse the abstract on their own.

Scientific safety rules enforced here:

* Participant counts, event counts and arm sizes are separate fields. A number that
  is an event numerator or an arm size is never reported as the total sample.
* Effect estimates (HR, RR, OR, IRR, RD, MD, SMD, WMD, sensitivity, specificity,
  AUC, PPV, NPV, DOR, accuracy) are parsed with their own confidence interval and
  bound to the outcome named in the same sentence. A missing point estimate or CI
  stays missing; nothing is imputed. Inconsistent estimates (CI does not contain
  the point estimate, impossible ranges) are flagged and excluded from synthesis.
* Causal treatment language is only allowed for randomized comparisons (or pooled
  randomized evidence). Observational, diagnostic and uncontrolled designs are
  rendered as association, accuracy or descriptive findings.
* Risk-of-bias and GRADE objects stay ``not_assessed`` unless a real, documented
  assessment is attached. Nothing is derived from the design label.
* Secondary/post hoc analyses, updated analyses, extended follow-up reports and
  meta-analyses are linked to their parent trial (shared registry number or trial
  acronym) so the same participants are not counted twice.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import report_generator as rg

EVIDENCE_MODEL_VERSION = "1.0.0"

NOT_REPORTED_TR = "özette bildirilmedi"
NOT_ASSESSED_TR = "Değerlendirilmedi"

# Verification statuses for a source sentence.
SOURCE_VERIFIED = "kaynakta_dogrulandi"
SOURCE_NOT_FOUND = "kaynakta_bulunamadi"
SOURCE_MISSING = "kaynak_cumlesi_yok"
SOURCE_DERIVED = "kaynaktan_hesaplandi"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EvidenceSource:
    pmid: str = ""
    doi: str = ""
    sentence: str = ""
    location: str = "none"  # abstract | title | derived | none
    verification_status: str = SOURCE_MISSING
    citation_status: str = "not_checked"  # verified | rejected | unverified | not_checked
    note: str = ""


@dataclass
class Population:
    description: str = ""
    n_total: Optional[int] = None
    n_kind: str = ""  # enrolled | randomized | analyzed | cohort | pooled | cases | arm_sum | planned
    n_cases: Optional[int] = None
    n_planned: Optional[int] = None
    source: EvidenceSource = field(default_factory=EvidenceSource)


@dataclass
class StudyArm:
    label: str
    n: Optional[int]
    role: str = "unknown"  # intervention | comparator | unknown
    source: EvidenceSource = field(default_factory=EvidenceSource)


@dataclass
class Intervention:
    name: str
    role_label: str = "Müdahale"  # Müdahale | Maruziyet | İndeks test | Prognostik faktör
    source: EvidenceSource = field(default_factory=EvidenceSource)


@dataclass
class Comparator:
    name: str
    source: EvidenceSource = field(default_factory=EvidenceSource)


@dataclass
class CoTreatment:
    """Background or concomitant therapy given alongside the studied intervention."""
    name: str
    source: EvidenceSource = field(default_factory=EvidenceSource)


@dataclass
class EventCount:
    events: int
    total: Optional[int]
    percent: Optional[float]
    source: EvidenceSource = field(default_factory=EvidenceSource)


@dataclass
class EffectEstimate:
    measure: str  # HR, OR, RR, IRR, RD, MD, SMD, WMD, DOR, sensitivity, ...
    measure_text: str
    family: str  # ratio | difference | diagnostic | change
    value: Optional[float]
    value_text: str
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    ci_level: Optional[int] = None
    p_value: str = ""
    contrast_value: Optional[float] = None  # "95.6% vs. 92.3%"
    outcome_name: str = ""
    outcome_basis: str = ""
    subgroup: bool = False
    validation: str = "gecerli"
    validation_note: str = ""
    source: EvidenceSource = field(default_factory=EvidenceSource)

    @property
    def usable(self) -> bool:
        return self.validation == "gecerli"


@dataclass
class Outcome:
    name: str
    kind: str = "unspecified"  # efficacy | safety | diagnostic | association | descriptive
    estimates: List[EffectEstimate] = field(default_factory=list)
    source: EvidenceSource = field(default_factory=EvidenceSource)


@dataclass
class RiskOfBiasAssessment:
    tool: str
    status: str = "not_assessed"
    overall_rating: Optional[str] = None
    domains: Dict[str, str] = field(default_factory=dict)
    assessor: Optional[str] = None
    note: str = ""


@dataclass
class CertaintyAssessment:
    """GRADE placeholder. Never filled from the design label."""
    status: str = "not_assessed"
    rating: Optional[str] = None
    note: str = "GRADE kesinlik değerlendirmesi yapılmadı; tasarımdan kesinlik derecesi üretilmez."


@dataclass
class StudyRelation:
    relation_type: str  # secondary_analysis | updated_analysis | extended_follow_up | pooled_analysis | includes_trial
    related_pmid: str
    basis: str  # shared registry id / acronym / title similarity
    confidence: str  # kesin | olasi


@dataclass
class Study:
    pmid: str
    doi: str
    title: str
    journal: str
    year: str
    design_key: str
    design_label: str
    evidence_level: str
    evidence_level_note: str
    claim_type: str
    claim_type_tr: str
    causal_inference_allowed: bool
    results_reported: bool
    population: Population
    arms: List[StudyArm] = field(default_factory=list)
    interventions: List[Intervention] = field(default_factory=list)
    comparators: List[Comparator] = field(default_factory=list)
    co_treatments: List[CoTreatment] = field(default_factory=list)
    outcomes: List[Outcome] = field(default_factory=list)
    event_counts: List[EventCount] = field(default_factory=list)
    risk_of_bias: RiskOfBiasAssessment = field(default_factory=lambda: RiskOfBiasAssessment(tool=""))
    certainty: CertaintyAssessment = field(default_factory=CertaintyAssessment)
    registry_ids: List[str] = field(default_factory=list)
    trial_acronyms: List[str] = field(default_factory=list)
    report_role: str = "primary"  # primary | secondary_analysis | updated_analysis | extended_follow_up | pooled_analysis | evidence_synthesis
    relations: List[StudyRelation] = field(default_factory=list)
    evidence_cluster: str = ""
    counts_as_independent: bool = True
    citation_status: str = "not_checked"
    other_numeric_findings: List[Dict[str, Any]] = field(default_factory=list)
    legacy: Dict[str, Any] = field(default_factory=dict)

    # -- convenience ------------------------------------------------------
    @property
    def estimates(self) -> List[EffectEstimate]:
        return [est for outcome in self.outcomes for est in outcome.estimates]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("legacy", None)
        return data


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_ONE_TO_ONE = str.maketrans({
    "·": ".",  # Lancet decimal point
    "−": "-",
    "–": "-",
    "—": "-",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
})


def normalize_text(text: str) -> str:
    """Character-for-character normalization (decimal dots, dashes, spaces)."""
    return (text or "").translate(_ONE_TO_ONE)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).strip()


_ABBREV_END_RE = re.compile(r"(?:\bvs|\be\.g|\bi\.e|\bal|\bFig|\bapprox|\bNo|\bDr|\bSt|\bcf)\.$", re.IGNORECASE)


def sentences_of(text: str) -> List[str]:
    out: List[str] = []
    for sentence in rg._finding_sentences(normalize_text(text)):
        if len(sentence) < 260:
            out.append(sentence)
            continue
        start = 0
        for match in re.finditer(r"(?<=[.])\s+(?=[A-Z][a-z]|[A-Z]{2,}\s)", sentence):
            head = sentence[start:match.start()]
            if _ABBREV_END_RE.search(head) or len(head) < 40:
                continue
            out.append(head.strip())
            start = match.end()
        out.append(sentence[start:].strip())
    return [s for s in out if s]


def verify_sentence_in_source(sentence: str, abstract: str, title: str = "") -> Tuple[str, str]:
    """Return (location, status) after checking the sentence verbatim in the record."""
    if not sentence:
        return "none", SOURCE_MISSING
    needle = _collapse(sentence)
    if needle and needle in _collapse(abstract):
        return "abstract", SOURCE_VERIFIED
    if needle and needle in _collapse(title):
        return "title", SOURCE_VERIFIED
    return "none", SOURCE_NOT_FOUND


def _source(article: Dict[str, Any], sentence: str, note: str = "") -> EvidenceSource:
    location, status = verify_sentence_in_source(
        sentence, article.get("abstract") or "", article.get("title") or ""
    )
    return EvidenceSource(
        pmid=str(article.get("pmid") or ""),
        doi=str(article.get("doi") or ""),
        sentence=_collapse(sentence) if sentence else "",
        location=location,
        verification_status=status,
        citation_status=str(article.get("_citation_status") or "not_checked"),
        note=note,
    )


_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_WORD_NUM_RE = (
    r"(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:-(?:one|two|three|four|five|six|seven|eight|nine))?"
    r"|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
    r"|one|two|three|four|five|six|seven|eight|nine|ten)"
)
_DIGIT_NUM_RE = r"\d{1,3}(?:[ ,]\d{3})+(?![\d.])|\d+(?![\d.,]\d)"
NUM_RE = rf"(?:{_DIGIT_NUM_RE}|{_WORD_NUM_RE})"


def parse_count(token: str) -> Optional[int]:
    raw = (token or "").strip().lower()
    if not raw:
        return None
    digits = re.sub(r"[ ,]", "", raw)
    if digits.isdigit():
        return int(digits)
    if raw in _WORD_NUMBERS:
        return _WORD_NUMBERS[raw]
    if "-" in raw:
        left, right = raw.split("-", 1)
        if left in _WORD_NUMBERS and right in _WORD_NUMBERS:
            return _WORD_NUMBERS[left] + _WORD_NUMBERS[right]
    return None


def _to_float(token: str) -> Optional[float]:
    try:
        return float(normalize_text(token).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Participant counts, arms and event counts
# ---------------------------------------------------------------------------

_PEOPLE = (
    r"(?:patients|participants|adults|children|infants|neonates|newborns|adolescents|women|men|"
    r"subjects|individuals|persons|people|cases|volunteers|pregnancies|samples|mothers|students|"
    r"residents|veterans|survivors|recipients)"
)
_FILLER = r"(?:[A-Za-z][\w'+/-]*\s+){0,6}?"
_FILLER_SHORT = r"(?:[A-Za-z][\w'+/-]*\s+){0,4}?"

_ARM_PATTERNS = [
    re.compile(
        rf"(?P<n1>{NUM_RE})\s+(?:{_PEOPLE}\s+)?(?:were\s+)?(?:randomly\s+)?(?:assigned|randomi[sz]ed|allocated)\s+"
        rf"to\s+(?:receive\s+|undergo\s+)?(?:the\s+)?(?P<a1>[^,;()]+?)(?:\s*\([^)]*\))?\s*,?\s+and\s+"
        rf"(?P<n2>{NUM_RE})\s+(?:were\s+)?(?:assigned\s+)?to\s+(?:receive\s+|undergo\s+)?(?:the\s+)?(?P<a2>[^,;.()]+)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:to|the|either|by)\s+(?P<a1>[\w\s+/-]{{2,60}}?)\s*(?:group\s*)?\(\s*n\s*=\s*(?P<n1>{_DIGIT_NUM_RE})\s*\)\s*,?\s*"
        rf"(?:or|and)\s+(?:to\s+)?(?:the\s+)?(?P<a2>[\w\s+/-]{{2,60}}?)\s*(?:group\s*)?\(\s*n\s*=\s*(?P<n2>{_DIGIT_NUM_RE})\s*\)",
        re.IGNORECASE,
    ),
]

_TOTAL_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("enrolled", re.compile(
        rf"\bOf\s+(?:the\s+)?{NUM_RE}\s+{_FILLER_SHORT}{_PEOPLE},\s+(?P<n>{NUM_RE})\s+were\s+"
        r"(?:enrolled|included|randomi[sz]ed|analy[sz]ed)",
        re.IGNORECASE)),
    ("enrolled", re.compile(
        rf"\b(?:randomly\s+assigned|randomi[sz]ed|randomised|assigned|enrolled|recruited|included|analy[sz]ed|include|enrol{{1,2}}|recruit|"
        rf"evaluated|examined|studied|conducted\s+(?:on|in|among)|involving|comprising)\s+(?:a\s+total\s+of\s+)?"
        rf"(?P<n>{NUM_RE})\s+{_FILLER}{_PEOPLE}\b",
        re.IGNORECASE)),
    ("enrolled", re.compile(
        rf"\b(?:a\s+total\s+of|total\s+of|in\s+total,?)\s+(?P<n>{NUM_RE})\s+{_FILLER_SHORT}{_PEOPLE}\b",
        re.IGNORECASE)),
    ("enrolled", re.compile(
        rf"\b(?P<n>{NUM_RE})\s+{_FILLER_SHORT}{_PEOPLE}\s+(?:with\s+[^,.;()]{{1,60}}?\s+)?(?:\([^)]*\)\s+)?(?:were|was)\s+(?:randomly\s+)?"
        r"(?:enrolled|randomi[sz]ed|included|recruited|studied|evaluated|analy[sz]ed|assigned|identified|followed|admitted|treated|"
        r"characteri[sz]ed|described|reviewed)",
        re.IGNORECASE)),
    ("enrolled", re.compile(
        rf"\b(?:were|was)\s+(?:enrolled|included|recruited|studied)\b[^.]{{0,60}}?\(\s*N\s*=\s*(?P<n>{_DIGIT_NUM_RE})\s*\)")),
    ("cohort", re.compile(
        rf"\b(?:cohort|sample|population|registry)\s+of\s+(?P<n>{NUM_RE})\s+{_FILLER_SHORT}{_PEOPLE}\b",
        re.IGNORECASE)),
    ("cases", re.compile(
        rf"\b(?:series\s+of|report(?:ing|ed)?|present(?:ing|ed)?|describe[ds]?|records\s+of)\s+(?P<n>{NUM_RE})\s+{_FILLER_SHORT}"
        r"(?:cases|patients)\b",
        re.IGNORECASE)),
    ("analyzed", re.compile(
        rf"\b(?:among|of\s+the|in\s+the)\s+(?P<n>{NUM_RE})\s+{_FILLER_SHORT}{_PEOPLE}\b",
        re.IGNORECASE)),
    ("analyzed", re.compile(
        rf"\b(?:data\s+from|the)\s+(?P<n>{NUM_RE})\s+{_FILLER_SHORT}{_PEOPLE}\b",
        re.IGNORECASE)),
]

_CASE_CONTROL_TOTAL_RE = re.compile(
    rf"\b(?P<c>{NUM_RE})\s+(?:[^.;\d]|(?:19|20)\d{{2}}){{0,90}}?\b(?:were\s+)?(?:matched\b(?:\s*\([^)]*\))?[^.;\d]{{0,40}}?\b(?:to|with)|and)\s+"
    rf"(?P<k>{NUM_RE})\s+(?:[^.;\d]{{0,50}}?)?\bcontrols\b",
    re.IGNORECASE,
)
_POOLED_PATTERN = re.compile(
    rf"\b(?:studies|trials|RCTs|cohorts|articles)\b[^.]{{0,90}}?\b(?:including|involving|comprising|encompassing|"
    rf"yielding|of|with|enrolling|totaling|totalling)\s+(?P<n>{NUM_RE})\s+{_FILLER_SHORT}{_PEOPLE}\b",
    re.IGNORECASE,
)

_EVENT_PATTERNS = [
    re.compile(rf"\b(?P<e>{_DIGIT_NUM_RE})\s+(?:\((?P<p>\d+(?:\.\d+)?)%\)\s+)?of\s+(?:the\s+)?(?P<t>{_DIGIT_NUM_RE})\b"),
    re.compile(rf"\b(?P<e>{_DIGIT_NUM_RE})\s+{_FILLER_SHORT}{_PEOPLE}\s+\((?P<p>\d+(?:\.\d+)?)%\)"),
    re.compile(rf"\b(?P<e>{_DIGIT_NUM_RE})\s+\((?P<p>\d+(?:\.\d+)?)%\)"),
]

_FUTURE_RE = re.compile(r"\b(?:will|shall)\s+(?:be\s+)?(?:include|enrol|enroll|recruit|randomi[sz]e|included|enrolled|recruited)", re.IGNORECASE)


_ARM_NO_COUNT_RE = re.compile(
    r"\b(?:randomi[sz]ation|randomi[sz]ed|randomly\s+assigned|assigned|allocated)\b[^.]{0,300}?\bto\s+(?:receive\s+|undergo\s+)?"
    r"(?:either\s+)?(?P<a1>[^;()]{2,90}?)(?:\s*\([^)]*\))?\s+or\s+(?:to\s+)?(?:receive\s+|undergo\s+)?(?P<a2>[^,;.()]{2,60}?)"
    r"(?=\s*(?:,|\.|;|\(|$|\s+for\s+\d|\s+once\b|\s+in\s+addition\b|\s+every\b|\s+after\b|\s+before\b|\s+during\b))",
    re.IGNORECASE,
)


_THREE_ARM_RE = re.compile(
    rf"(?P<n1>{NUM_RE})\s+(?:{_PEOPLE}\s+)?(?:were\s+)?(?:randomly\s+)?(?:assigned|randomi[sz]ed|allocated)\s+to\s+(?:receive\s+)?(?:the\s+)?"
    rf"(?P<a1>[^,;()]+?),\s+(?P<n2>{NUM_RE})\s+(?:were\s+)?(?:assigned\s+)?to\s+(?:receive\s+)?(?:the\s+)?(?P<a2>[^,;()]+?),?\s+and\s+"
    rf"(?P<n3>{NUM_RE})\s+(?:were\s+)?(?:assigned\s+)?(?:to\s+)?(?:receive\s+)?(?:the\s+)?(?P<a3>[^,;.()]+)",
    re.IGNORECASE,
)
_CONTROL_ARM_RE = re.compile(r"\b(?:placebo|standard\s+(?:of\s+)?care|usual\s+care|control|no\s+treatment|sham)\b", re.IGNORECASE)


def extract_arms(article: Dict[str, Any], randomized: bool = True) -> List[StudyArm]:
    arms: List[StudyArm] = []
    for sentence in sentences_of(article.get("abstract") or ""):
        three = _THREE_ARM_RE.search(sentence)
        if three and all(parse_count(three.group(k)) for k in ("n1", "n2", "n3")):
            src = _source(article, sentence)
            for idx in (1, 2, 3):
                label = _clean_arm_label(three.group(f"a{idx}"))
                role = "comparator" if _CONTROL_ARM_RE.search(label) else "intervention"
                arms.append(StudyArm(label=label, n=parse_count(three.group(f"n{idx}")), role=role, source=src))
            return arms
    for sentence in sentences_of(article.get("abstract") or ""):
        for pattern in _ARM_PATTERNS:
            match = pattern.search(sentence)
            if not match:
                continue
            n1, n2 = parse_count(match.group("n1")), parse_count(match.group("n2"))
            if not n1 or not n2:
                continue
            src = _source(article, sentence)
            arms.append(StudyArm(label=_clean_arm_label(match.group("a1")), n=n1, role="intervention", source=src))
            arms.append(StudyArm(label=_clean_arm_label(match.group("a2")), n=n2, role="comparator", source=src))
            return arms
    if not randomized:
        return arms
    for sentence in sentences_of(article.get("abstract") or ""):
        match = _ARM_NO_COUNT_RE.search(sentence)
        if not match:
            continue
        a1 = _clean_arm_label(re.sub(r"^(?:once-weekly|once-daily|oral|intravenous|subcutaneous)[,\s]+", "", match.group("a1").strip(),
                                     flags=re.IGNORECASE))
        a1 = re.sub(r"^(?:(?:once-weekly|once-daily|weekly|daily|oral|intravenous|subcutaneous),?\s+)+", "", a1, flags=re.IGNORECASE)
        a2 = _clean_arm_label(match.group("a2"))
        if not a1 or not a2 or re.search(r"\d+\s*:\s*\d+", a1) or len(a1.split()) > 8:
            continue
        src = _source(article, sentence)
        arms.append(StudyArm(label=a1, n=None, role="intervention", source=src))
        arms.append(StudyArm(label=a2, n=None, role="comparator", source=src))
        return arms
    return arms


def extract_event_counts(article: Dict[str, Any]) -> List[EventCount]:
    counts: List[EventCount] = []
    seen = set()
    for sentence in sentences_of(article.get("abstract") or ""):
        for pattern in _EVENT_PATTERNS:
            for match in pattern.finditer(sentence):
                events = parse_count(match.group("e"))
                if events is None or rg._is_calendar_year(str(events)):
                    continue
                total = parse_count(match.groupdict().get("t") or "")
                pct = _to_float(match.groupdict().get("p") or "")
                key = (events, total, pct, sentence)
                if key in seen:
                    continue
                seen.add(key)
                counts.append(EventCount(events=events, total=total, percent=pct, source=_source(article, sentence)))
    return counts


def extract_population(article: Dict[str, Any], design_key: str, arms: List[StudyArm],
                       events: List[EventCount]) -> Population:
    """Total participants, kept apart from arm sizes and event numerators."""
    abstract = article.get("abstract") or ""
    sentences = sentences_of(abstract)
    arm_sizes = {arm.n for arm in arms if arm.n}
    event_numerators = {ev.events for ev in events if ev.total is not None or ev.percent is not None}
    population = Population()

    def _accept(n: Optional[int]) -> bool:
        if not n or n < 1:
            return False
        if rg._is_calendar_year(str(n)):
            return False
        if n in arm_sizes or n in event_numerators:
            return False
        return True

    synthesis = design_key in ("meta_analysis", "systematic_review", "systematic_review_and_meta_analysis")
    if synthesis:
        for sentence in sentences:
            match = _POOLED_PATTERN.search(sentence)
            if match and _accept(parse_count(match.group("n"))):
                population.n_total = parse_count(match.group("n"))
                population.n_kind = "pooled"
                population.source = _source(article, sentence, "Dahil edilen çalışmalardaki toplam katılımcı")
                return population

    if design_key == "case_control":
        for sentence in sentences:
            cc = _CASE_CONTROL_TOTAL_RE.search(sentence)
            if cc and parse_count(cc.group("c")) and parse_count(cc.group("k")) \
                    and not rg._is_calendar_year(str(parse_count(cc.group("c")))):
                cases, controls = parse_count(cc.group("c")), parse_count(cc.group("k"))
                population.n_cases = cases
                population.n_total = cases + controls
                population.n_kind = "arm_sum"
                population.source = EvidenceSource(
                    pmid=str(article.get("pmid") or ""), doi=str(article.get("doi") or ""), sentence=_collapse(sentence),
                    location="abstract", verification_status=SOURCE_DERIVED,
                    note=f"{cases} olgu + {controls} kontrol; toplam hesaplandı.",
                )
                return population
    patterns = list(_TOTAL_PATTERNS)
    if design_key in _DESCRIPTIVE_KEYS:
        patterns.sort(key=lambda item: 0 if item[0] == "cases" else 1)
    for kind, pattern in patterns:
        for sentence in sentences:
            for match in pattern.finditer(sentence):
                n = parse_count(match.group("n"))
                if _FUTURE_RE.search(sentence):
                    if n and population.n_planned is None:
                        population.n_planned = n
                        population.source = _source(article, sentence, "Planlanan örneklem; sonuç bildirilmedi")
                    continue
                if not _accept(n):
                    continue
                if design_key == "case_control" and re.search(r"\bcases\b", match.group(0), re.IGNORECASE) \
                        and not re.search(r"\bcontrols?\b", match.group(0), re.IGNORECASE):
                    if population.n_cases is None:
                        population.n_cases = n
                    continue
                if kind == "cases":
                    tail = sentence[match.end():]
                    extra = re.match(rf"[^.;]{{0,80}}?\band\s+(?P<m>{NUM_RE})\s+(?:other\s+)?(?:cases?|patients?)\b", tail, re.IGNORECASE)
                    if extra and parse_count(extra.group("m")):
                        n = n + parse_count(extra.group("m"))
                population.n_total = n
                population.n_kind = kind
                population.source = _source(article, sentence)
                return population

    for sentence in sentences:
        each = re.search(rf"\b(?P<n>{_DIGIT_NUM_RE})\s+{_FILLER_SHORT}{_PEOPLE}\s+in\s+each\s+(?:group|arm|cohort)\b", sentence,
                         re.IGNORECASE)
        if each and re.search(r"\b1\s*:\s*1\b", sentence):
            per_group = parse_count(each.group("n"))
            if per_group:
                population.n_total = 2 * per_group
                population.n_kind = "arm_sum"
                population.source = EvidenceSource(
                    pmid=str(article.get("pmid") or ""), doi=str(article.get("doi") or ""),
                    sentence=_collapse(sentence), location="abstract", verification_status=SOURCE_DERIVED,
                    note=f"1:1 eşleştirmede her grupta {per_group}; toplam iki grubun toplamıdır.",
                )
                return population
    if len(arms) >= 2 and all(arm.n for arm in arms):
        population.n_total = sum(arm.n for arm in arms)
        population.n_kind = "arm_sum"
        population.source = EvidenceSource(
            pmid=str(article.get("pmid") or ""),
            doi=str(article.get("doi") or ""),
            sentence=arms[0].source.sentence,
            location=arms[0].source.location,
            verification_status=SOURCE_DERIVED,
            note="Toplam, özette bildirilen kol sayılarının toplamıdır.",
        )
    return population


# ---------------------------------------------------------------------------
# Effect estimates
# ---------------------------------------------------------------------------

_MEASURES: List[Tuple[str, str, str]] = [
    # (regex, code, family) — longest phrases first
    (r"diagnostic\s+odds\s+ratios?|\bDORs?\b", "DOR", "ratio"),
    (r"(?:age-adjusted\s+|adjusted\s+|unadjusted\s+)?(?:common\s+)?odds\s+ratios?|\baORs?\b|\bORs?\b", "OR", "ratio"),
    (r"(?:age-adjusted\s+|adjusted\s+|unadjusted\s+)?(?:subdistribution\s+)?hazard\s+ratios?|\baHRs?\b|\bsHRs?\b|\bHRs?\b", "HR", "ratio"),
    (r"incidence\s+rate\s+ratios?|\bIRRs?\b", "IRR", "ratio"),
    (r"(?:age-adjusted\s+|adjusted\s+|unadjusted\s+)?rate\s+ratios?", "RR", "ratio"),
    (r"(?:adjusted\s+)?relative\s+risks?|(?:adjusted\s+)?risk\s+ratios?|\bRRs?\b", "RR", "ratio"),
    (r"positive\s+likelihood\s+ratios?|\bLR\+", "LR+", "ratio"),
    (r"negative\s+likelihood\s+ratios?|\bLR-", "LR-", "ratio"),
    (r"standardi[sz]ed\s+mean\s+differences?|\bSMDs?\b", "SMD", "difference"),
    (r"weighted\s+mean\s+differences?|\bWMDs?\b", "WMD", "difference"),
    (r"(?:adjusted\s+|unadjusted\s+)?(?:absolute\s+)?risk\s+differences?|absolute\s+differences?", "RD", "difference"),
    (r"mean\s+differences?|\bMDs?\b", "MD", "difference"),
    (r"mean\s+percentage\s+change|percentage\s+change|mean\s+change", "mean_change", "change"),
    (r"(?:pooled\s+)?sensitivit(?:y|ies)|true\s+positive\s+rate|\bTPR\b", "sensitivity", "diagnostic"),
    (r"(?:pooled\s+)?specificit(?:y|ies)|true\s+negative\s+rate|\bTNR\b", "specificity", "diagnostic"),
    (r"area\s+under\s+the\s+(?:receiver\s+operating\s+characteristic\s+)?(?:\(ROC\)\s+)?curve|\bAUC\b|\bAUROC\b|\bC-statistic\b", "AUC", "diagnostic"),
    (r"positive\s+predictive\s+values?|\bPPV\b", "PPV", "diagnostic"),
    (r"negative\s+predictive\s+values?|\bNPV\b", "NPV", "diagnostic"),
    (r"(?:overall\s+|diagnostic\s+)accuracy", "accuracy", "diagnostic"),
    (r"(?<![\w-])difference(?![\w-])", "RD", "difference"),
]
_CASE_SENSITIVE_ACRONYM = re.compile(r"^(?:\\b)?[A-Z]")

_MEASURE_RE = re.compile(
    "|".join(f"(?P<m{i}>{pattern})" for i, (pattern, _c, _f) in enumerate(_MEASURES)),
    re.IGNORECASE,
)
_ACRONYM_ONLY = re.compile(r"^(?:a|s)?(?:OR|HR|RR|IRR|SMD|WMD|MD|DOR|AUC|AUROC|PPV|NPV|LR[+-])s?$")

_NUMBER = r"-?\d+(?:\.\d+)?"
_VALUE_RE = re.compile(
    rf"^(?P<lead>[\s,:;=(\[]*(?:(?:was|were|is|of|at|=|:|reached|showed|yielded|corresponding\s+to)\s*)?[\s,:;=(\[]*)"
    rf"(?P<val>{_NUMBER})\s*(?P<pct>%)?"
)
_CI_AFTER_RE = re.compile(
    rf"^\s*(?:%|percentage\s+points?|points?|mg/dl|kg|months?|days?)?\s*[;,]?\s*[(\[]?\s*"
    rf"(?:(?P<lvl>\d{{2}})\s*%\s*(?:CI|confidence\s+intervals?)(?:\s*\[CI\])?|CI)?\s*[,:=]?\s*[(\[]?\s*"
    rf"(?P<lo>{_NUMBER})\s*%?\s*(?:to|-|,)\s*(?P<hi>{_NUMBER})\s*%?\s*[)\]]?",
    re.IGNORECASE,
)
_CI_ONLY_RE = re.compile(
    rf"^\s*and\s+(?P<lvl>\d{{2}})\s*%\s*confidence\s+intervals?\s*[(\[]\s*(?P<lo>{_NUMBER})\s*(?:to|-|,)\s*(?P<hi>{_NUMBER})\s*[)\]]",
    re.IGNORECASE,
)
_VS_RE = re.compile(rf"^\s*(?:%)?\s*(?:vs\.?|versus)\s*(?P<val>{_NUMBER})\s*%?", re.IGNORECASE)
_P_AFTER_RE = re.compile(r"^[\s;,)\]]*(?:(?:one|two)-sided\s+)?(?:interaction\s+)?p\s*(?P<op>[=<>≤≥])\s*(?P<p>0?\.\d+|\d+(?:\.\d+)?)", re.IGNORECASE)
_LIST_SEP_RE = re.compile(r"^\s*(?:,\s*and|,|and)\s+(?:the\s+)?(?:pooled\s+)?$", re.IGNORECASE)


def _measure_code(match: re.Match) -> Tuple[str, str]:
    for i, (_pattern, code, family) in enumerate(_MEASURES):
        if match.group(f"m{i}"):
            return code, family
    return "", ""


def _measure_mentions(sentence: str) -> List[Dict[str, Any]]:
    mentions = []
    for match in _MEASURE_RE.finditer(sentence):
        text = match.group(0)
        bare = text.strip()
        # Acronyms only count in upper case, so "or" is never an odds ratio.
        if _ACRONYM_ONLY.match(bare.replace(" ", "")) is None and re.fullmatch(r"(?i)(?:a|s)?(?:or|hr|rr|irr|smd|wmd|md|dor|auc|auroc|ppv|npv)s?", bare):
            continue
        code, family = _measure_code(match)
        if mentions and mentions[-1]["code"] == code and re.fullmatch(r"\s*[\[(]\s*", sentence[mentions[-1]["end"]:match.start()]):
            continue
        if code == "RD" and bare.lower() == "difference":
            # A bare "difference" is an estimate only when a number follows closely.
            if not re.match(rf"^[\s,:;(]*(?:of\s+)?{_NUMBER}", sentence[match.end():]):
                continue
        mentions.append({"start": match.start(), "end": match.end(), "text": text, "code": code, "family": family})
    return mentions


def _parse_value_group(text: str) -> Optional[Dict[str, Any]]:
    """Parse "<value>[%] [vs. <value>] [(95% CI lo-hi)] [p]" at the start of text."""
    match = _VALUE_RE.match(text)
    if not match:
        return None
    if re.search(r"[A-Za-z]{3,}", match.group("lead") or "") and not re.search(
        r"(?:was|were|is|of|at|reached|showed|yielded|corresponding\s+to)", match.group("lead"), re.IGNORECASE
    ):
        return None
    group: Dict[str, Any] = {
        "value": float(match.group("val")),
        "value_text": match.group("val") + (match.group("pct") or ""),
        "percent": bool(match.group("pct")),
        "end": match.end(),
        "ci": None,
        "ci_level": None,
        "contrast": None,
        "p": "",
    }
    rest = text[match.end():]
    vs = _VS_RE.match(rest)
    if vs:
        group["contrast"] = float(vs.group("val"))
        group["end"] += vs.end()
        rest = text[group["end"]:]
    ci = _CI_AFTER_RE.match(rest)
    if ci:
        lo, hi = float(ci.group("lo")), float(ci.group("hi"))
        if lo <= hi:
            group["ci"] = (lo, hi)
            group["ci_level"] = int(ci.group("lvl")) if ci.group("lvl") else None
            group["end"] += ci.end()
            rest = text[group["end"]:]
    p_match = _P_AFTER_RE.match(rest)
    if p_match:
        group["p"] = f"p {p_match.group('op')} {p_match.group('p')}"
        group["end"] += p_match.end()
    return group


def _validate_estimate(est: EffectEstimate) -> None:
    v, lo, hi = est.value, est.ci_low, est.ci_high
    if v is None:
        est.validation = "eksik"
        est.validation_note = "Nokta tahmini özette bildirilmedi; değer üretilmedi."
        return
    tol = 0.0051 + abs(v) * 0.002
    if est.family == "ratio":
        if v <= 0 or (lo is not None and lo < 0):
            est.validation = "tutarsiz"
            est.validation_note = "Oran ölçütü sıfır veya negatif olamaz."
            return
    if est.family == "diagnostic":
        scale = 100.0 if v > 1.0 else 1.0
        if est.measure in ("AUC",) and v > 1.0 and v <= 100:
            scale = 100.0
        if v < 0 or v > scale or (hi is not None and hi > scale + tol):
            est.validation = "tutarsiz"
            est.validation_note = "Tanısal ölçüt 0-1 (veya %0-100) aralığı dışında."
            return
    if lo is not None and hi is not None and not (lo - tol <= v <= hi + tol):
        est.validation = "tutarsiz"
        est.validation_note = "Güven aralığı nokta tahminini içermiyor; eşleştirme reddedildi."
        return
    est.validation = "gecerli"


_TARGET_RE = re.compile(
    r"\b(?:for|in)\s+(?:the\s+)?(?:detection|diagnosis|detecting|diagnosing|identification)\s+(?:of\s+)?(?P<t>[^,;.()]{3,80})",
    re.IGNORECASE,
)
_LEADING_FOR_RE = re.compile(r"^\s*(?:For|In)\s+(?P<t>[^,]{3,80}),", re.IGNORECASE)
_TRAILING_FOR_RE = re.compile(r"\bfor\s+(?P<t>[A-Z][\w-]{1,15}(?:\s+[\w-]+){0,3})\s+(?:were|was)\b")

_STAT_ONLY_OUTCOME_RE = re.compile(
    r"^(?:the\s+)?(?:adjusted\s+)?(?:hazard|odds|risk|rate|relative|mean|confidence|ci|p|value|ratio|difference|"
    r"estimate|effect|analysis|model|regression|interval)\b",
    re.IGNORECASE,
)


def _diagnostic_target(sentence: str, article: Dict[str, Any]) -> str:
    for pattern in (_LEADING_FOR_RE, _TARGET_RE, _TRAILING_FOR_RE):
        match = pattern.search(sentence)
        if match:
            return match.group("t").strip()
    return ""


DIAGNOSTIC_MEASURES = {"DOR", "LR+", "LR-", "sensitivity", "specificity", "AUC", "PPV", "NPV", "accuracy"}

_BAD_OUTCOME_START_RE = re.compile(
    r"^(?:in\s|the\s+\w+\s+group|those|not\s+to|to\s+those|in\s+those|among|after|treatment\s+with|use\s+of|"
    r"patients?\b|participants?\b|children\b|we\b|this\b|there\b|pooled\b|overall\b|both\b|group\b|placebo\b)",
    re.IGNORECASE,
)
_NOT_OUTCOME_RE = re.compile(
    r"\b(?:correlation|association|yielded|showed|pooled|trend\s+toward|significant|significantly|no\s+significant)\b",
    re.IGNORECASE,
)
_CUT_RE = re.compile(
    r"\s+(?:than|in\s+the\s+\w+(?:\s+\w+)?\s+group|among|compared\s+(?:with|to)|versus|vs\.?|was|were|primarily|due\s+to|"
    r"with\s+(?:or|OR|HR|RR)\b|respectively|also|did\s+not|does\s+not|differ\w*|in\s+(?:patients|participants|children|adults|those))\b.*$",
    re.IGNORECASE,
)
_LEAD_QUAL_RE = re.compile(
    r"^(?:and\s+)?(?:an?\s+|the\s+)?(?:significantly\s+)?(?:reduced|lower|higher|increased|decreased|greater|smaller|"
    r"substantial|significant|reduction\s+in|increase\s+in|decrease\s+in)?\s*(?:risk\s+of\s+|incidence\s+of\s+|rate\s+of\s+)?",
    re.IGNORECASE,
)


def _clean_outcome(text: str) -> str:
    outcome = re.sub(r"\s+", " ", text or "").strip(" ,;:.(")
    outcome = _CUT_RE.sub("", outcome).strip(" ,;:")
    outcome = re.sub(r"(?:[,\s]+(?:and|with|or))+$", "", outcome).strip(" ,;:")
    outcome = re.sub(r"\s+estimates?$", "", outcome).strip()
    if " , " in outcome:
        outcome = outcome.split(" , ")[-1].strip()
    outcome = _LEAD_QUAL_RE.sub("", outcome).strip(" ,;:")
    if _NOT_OUTCOME_RE.search(outcome):
        return ""
    if re.fullmatch(r"(?:the\s+)?(?:primary|secondary|co-?primary)\s+(?:outcome|end\s*point|endpoint)(?:\s+events?)?s?", outcome,
                    re.IGNORECASE):
        return ""  # resolved from the primary-outcome definition instead
    if not outcome or len(outcome) > 110 or (len(outcome) < 3 and not re.fullmatch(r"[A-Z]{2}", outcome)):
        return ""
    if _BAD_OUTCOME_START_RE.match(outcome) or _STAT_ONLY_OUTCOME_RE.match(outcome):
        return ""
    if re.fullmatch(r"[\d\s.,%-]+", outcome) or _MEASURE_RE.fullmatch(outcome):
        return ""
    return outcome


_BEFORE_PATTERNS = [
    re.compile(r"\brisk\s+factors?\s+for\s+(?P<o>[^,;()]+?)\s+(?:was|were)\b", re.IGNORECASE),
    re.compile(r"\bbetween\s+.+?\s+and\s+(?P<o>[^,;()]*?\b(?:risk|incidence|mortality|death|cancer|disease|events?)\b[^,;()]*?)(?:\s+with)?\s*$", re.IGNORECASE),
    re.compile(r"\b(?:on\s+the\s+basis\s+of|in\s+terms\s+of|with\s+respect\s+to)\s+(?P<o>[^;()]+?)\s*$", re.IGNORECASE),
    re.compile(r"\b(?:risks?|incidence|rates?|odds|hazard|likelihood|occurrence|number|frequency|proportion|reductions?|"
               r"increases?|decreases?)\s+(?:in\s+(?:the\s+)?rate\s+)?of\s+(?P<o>[^;(),]+?)\s*(?:,?\s*with)?\s*$", re.IGNORECASE),
    re.compile(r"\b(?:reductions?|increases?|decreases?|differences?|changes?)\s+in\s+(?P<o>[^;(),]+?)\s*$", re.IGNORECASE),
    re.compile(r"^(?:and\s+)?(?:an?\s+|the\s+)?(?P<o>[A-Za-z][^,;()]{2,70}?)\s+(?:were|was)\s+(?:lower|higher|more\s+common|"
               r"less\s+common|reduced|increased)\b", re.IGNORECASE),
    re.compile(r"^(?:the\s+)?(?P<o>[\w-]+(?:\s+[\w-]+){0,5}?)\s+(?:estimates?\s+)?(?:was|were)\s+-?\d", re.IGNORECASE),
    re.compile(r"\b(?:associated\s+with|reduced|decreased|increased|improved|lowered|lower|higher)\s+(?P<o>[^;()]+?)\s*$", re.IGNORECASE),
    re.compile(r"\b(?P<o>died\s+within\s+[^;()]+?|died|deaths?)\s*$", re.IGNORECASE),
    re.compile(r"\b(?:HRs?|hazard\s+ratios?|ORs?|RRs?)\s+for\s+(?P<o>[A-Za-z][\w-]*(?:\s+[\w-]+){0,3}?)\s+(?:favou?red|was|were|in|among)\b"),
    re.compile(r"\b(?:mean|median)\s+(?P<o>[A-Z]{2,5}|[\w-]+\s+survival)\b"),
    re.compile(r"\b(?:had\s+)?(?P<o>died|all-cause\s+mortality|mortality)\b", re.IGNORECASE),
    re.compile(r"^(?:and\s+)?(?:an?\s+|the\s+)?(?P<o>[A-Za-z][^,;()]{2,70}?)\s+(?:occurred|was\s+observed|was\s+reported|"
               r"developed|was\s+achieved|were\s+more\s+common|was\s+more\s+common|was\s+lower|was\s+higher|were\s+lower|"
               r"were\s+higher)\b", re.IGNORECASE),
]


def _strip_parens(text: str) -> str:
    out, depth = [], 0
    for ch in text:
        if ch in "([":
            depth += 1
            continue
        if ch in ")]":
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out))


def _enclosing_close(sentence: str, index: int) -> int:
    depth = 0
    for i in range(index, len(sentence)):
        ch = sentence[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            if depth == 0:
                return i
            depth -= 1
    return -1


def _clause_before(sentence: str, start: int) -> str:
    prefix = sentence[:start]
    depth = 0
    for i in range(len(prefix) - 1, -1, -1):
        ch = prefix[i]
        if ch in ")]":
            depth += 1
        elif ch in "([":
            if depth == 0:
                prefix = prefix[:i]
                break
            depth -= 1
    stripped = re.sub(r"\s*,\s+(?:corresponding|equivalent)\s+to\b.*$", "", _strip_parens(prefix))
    clause = re.split(r"\s*;|\s*,\s+and\s+|\s*,\s+but\s+|\s*,\s+whereas\s+", stripped)[-1]
    return clause.strip()


_AFTER_PAREN_RE = re.compile(
    r"^\s*(?:and\s+[^.;()]{0,40}?\([^)]*\)\s*)?(?:both\s+)?(?:were|was|significantly|both|have|has|\s)*"
    r"(?:\w+\s+)?(?:associated\s+with|reduced|increased|lowered|decreased)\s+(?:an?\s+|the\s+)?(?:increased\s+|decreased\s+|"
    r"higher\s+|lower\s+|reduced\s+)?(?:risk|odds|incidence|hazard)\s+of\s+(?P<o>[^,.;()]{3,80})",
    re.IGNORECASE,
)


def _inside_parens(sentence: str, index: int) -> bool:
    return rg._depth_at(sentence, index) > 0


def _resolve_outcome(sentence: str, mention: Dict[str, Any], value_end: int) -> str:
    if _inside_parens(sentence, mention["start"]):
        close = _enclosing_close(sentence, mention["start"])
        after = _AFTER_PAREN_RE.match(sentence[close + 1:]) if close >= 0 else None
        if after:
            outcome = _clean_outcome(after.group("o"))
            if outcome:
                return outcome
    direct = re.match(r"^\s*for\s+(?P<o>[^,;().]{3,60})", sentence[value_end:])
    if direct:
        outcome = _clean_outcome(direct.group("o"))
        if outcome:
            return outcome
    clause = _clause_before(sentence, mention["start"])
    for pattern in _BEFORE_PATTERNS:
        match = pattern.search(clause)
        if match:
            outcome = _clean_outcome(match.group("o"))
            if outcome:
                return outcome
    legacy = rg._resolve_finding_outcome(sentence, mention["start"], mention["end"], value_end)
    if legacy and legacy != rg._UNNAMED_OUTCOME_TR:
        outcome = _clean_outcome(legacy)
        if outcome:
            return outcome
    tail = re.match(r"^[^(]*?\)?\s*(?:in|for)\s+(?:the\s+)?(?:rate|risk|incidence|proportion)?\s*(?:of\s+)?(?P<o>[^,;(.]{3,60})",
                    sentence[value_end:])
    if tail:
        outcome = _clean_outcome(tail.group("o"))
        if outcome:
            return outcome
    anywhere = re.search(r"\b(?:incidence|risk|rate)\s+of\s+(?P<o>\w+(?:\s+\w+)?)\b", sentence[: mention["start"]], re.IGNORECASE)
    if anywhere:
        return _clean_outcome(anywhere.group("o"))
    return ""


def extract_effect_estimates(article: Dict[str, Any]) -> List[EffectEstimate]:
    """Effect estimates with their own CI, p-value, outcome and verbatim source sentence."""
    estimates: List[EffectEstimate] = []
    for sentence in sentences_of(article.get("abstract") or ""):
        mentions = _measure_mentions(sentence)
        consumed_until = -1
        index = 0
        while index < len(mentions):
            mention = mentions[index]
            if mention["start"] < consumed_until:
                index += 1
                continue
            # Coordinated list: "sensitivity and specificity were A (CI) and B (CI)".
            run = [mention]
            j = index + 1
            while j < len(mentions):
                gap = sentence[run[-1]["end"]:mentions[j]["start"]]
                if _LIST_SEP_RE.match(gap) or re.fullmatch(r"\s*,\s*", gap):
                    run.append(mentions[j])
                    j += 1
                else:
                    break
            groups: List[Dict[str, Any]] = []
            if len(run) >= 2:
                tail_start = run[-1]["end"]
                lead = re.match(r"^[^0-9\-]{0,70}?(?=-?\d)", sentence[tail_start:])
                cursor = tail_start + (lead.end() if lead else 0)
                if lead and not re.search(r"[;]", lead.group(0)):
                    for _k in range(len(run)):
                        group = _parse_value_group(sentence[cursor:])
                        if not group:
                            break
                        group["abs_start"] = cursor
                        groups.append(group)
                        cursor += group["end"]
                        sep = re.match(r"^\s*(?:,\s*and|,|and)\s+(?:a\s+|an\s+)?", sentence[cursor:])
                        if sep:
                            cursor += sep.end()
                if len(groups) == len(run):
                    for m, g in zip(run, groups):
                        estimates.append(_build_estimate(article, sentence, m, g, mentions))
                    consumed_until = cursor
                    index = j
                    continue
            # Single measure followed by its value.
            after = sentence[mention["end"]:]
            ci_only = _CI_ONLY_RE.match(after)
            if ci_only:
                est = EffectEstimate(
                    measure=mention["code"], measure_text=mention["text"], family=mention["family"],
                    value=None, value_text="", ci_low=float(ci_only.group("lo")), ci_high=float(ci_only.group("hi")),
                    ci_level=int(ci_only.group("lvl")),
                    outcome_name=_resolve_outcome(sentence, mention, mention["end"]),
                    source=_source(article, sentence),
                )
                _validate_estimate(est)
                estimates.append(est)
                consumed_until = mention["end"] + ci_only.end()
                index += 1
                continue
            found = _find_value_after(sentence, mention, mentions)
            if found is None:
                index += 1
                continue
            lead_text, group = found
            if rg._is_calendar_year(group["value_text"].rstrip("%")):
                index += 1
                continue
            lead_outcome = ""
            lead_for = re.match(r"^\s*(?:for|of)\s+(?:having\s+)?(?:an?\s+)?(?P<o>[^;]{3,90}?)(?:\s+(?:in\s+the|among|compared|was|were)\b.*)?,?\s*$",
                                lead_text, re.IGNORECASE)
            if lead_for and not re.search(r"\d", lead_for.group("o")):
                lead_outcome = lead_for.group("o").strip(" ,")
            estimates.append(_build_estimate(article, sentence, mention, group, mentions, lead_outcome))
            consumed_until = group["abs_start"] + group["end"]
            index += 1
        _reverse_order_estimates(article, sentence, estimates)
        _legend_estimates(article, sentence, estimates)
    estimates = _dedupe_estimates(estimates)
    _inherit_subgroup_outcomes(estimates)
    _bind_primary_outcome(article, estimates)
    return estimates


_CONNECTOR_END_RE = re.compile(
    r"(?:\b(?:was|were|is|are|of|reached|showed|yielded|ratio|ratios|difference|at|totaled|equalled|equaled)|[=:,(\[])\s*$",
    re.IGNORECASE,
)
_CI_LABEL_LEAD_RE = re.compile(
    r"^\s*(?:[\[(]\s*(?:\d{2}\s*%\s*CI|[A-Za-z]{1,5})\s*[\])]\s*:?|,\s*\d{2}\s*%\s*(?:CI|confidence\s+intervals?)\s*:)",
    re.IGNORECASE,
)


def _find_value_after(sentence: str, mention: Dict[str, Any], mentions: List[Dict[str, Any]]):
    """First number after the measure whose preceding text ends with a connector."""
    after = sentence[mention["end"]:]
    label = _CI_LABEL_LEAD_RE.match(after)  # "HR [95% CI]: 0.75 [0.68, 0.82]"
    offset = label.end() if label else 0
    next_measure = next((m for m in mentions if m["start"] > mention["start"]), None)
    limit = 140
    if next_measure is not None:
        limit = min(limit, next_measure["start"] - mention["end"])
    window = after[offset:limit] if limit > offset else ""
    for num in re.finditer(r"-?\d+(?:\.\d+)?", window):
        lead = window[: num.start()]
        lead_wo_time = re.sub(r"\b(?:at\s+)?(?:week|month|day|year)s?\s+\d+\b|\b\d+[-\s](?:day|week|month|year)s?\b", " ", lead,
                              flags=re.IGNORECASE)
        if re.search(r"\d", lead_wo_time) or ";" in lead or re.search(r"\b(?:vs\.?|versus)\b", lead, re.IGNORECASE):
            return None
        if lead.strip() and re.search(r"[A-Za-z]{2,}", lead) and not _CONNECTOR_END_RE.search(lead):
            continue
        if len(re.findall(r"[A-Za-z]+", lead)) > 4 and not re.search(r"(?:\b(?:was|were|is|are)|[=:])\s*$", lead) \
                and not re.match(r"^\s*for\s", lead):
            return None
        group = _parse_value_group(window[num.start():])
        if group is None:
            return None
        group["abs_start"] = mention["end"] + offset + num.start()
        return lead, group
    return None


_REVERSE_RE = re.compile(
    r"(?P<val>\d+(?:\.\d+)?)\s*%\s+(?P<m>(?:diagnostic\s+|overall\s+)?(?:accuracy|sensitivity|specificity))\b",
    re.IGNORECASE,
)


def _reverse_order_estimates(article, sentence: str, estimates: List[EffectEstimate]) -> None:
    """"84% diagnostic accuracy" writes the value before the measure."""
    for match in _REVERSE_RE.finditer(sentence):
        word = match.group("m").lower()
        code = "accuracy" if "accuracy" in word else ("sensitivity" if "sensitivity" in word else "specificity")
        est = EffectEstimate(
            measure=code, measure_text=match.group("m"), family="diagnostic",
            value=float(match.group("val")), value_text=match.group("val") + "%",
            outcome_name=_diagnostic_target(sentence, article),
            source=_source(article, sentence),
        )
        tail = re.match(r"\s+(?:against|versus|vs\.?|compared\s+with)\s+(?P<ref>[^,;.]{2,40})", sentence[match.end():], re.IGNORECASE)
        if tail:
            est.outcome_basis = f"referans: {tail.group('ref').strip()}"
        _validate_estimate(est)
        estimates.append(est)


_LEGEND_RE = re.compile(r"\((?P<m>a?OR|a?HR|RR|IRR)\s*[;,/]\s*(?:95\s*%\s*)?CI\)", re.IGNORECASE)
_LEGEND_GROUP_RE = re.compile(
    r"(?P<label>[A-Za-z][^,;()]{2,70}?)\s*\((?P<v>\d+(?:\.\d+)?)\s*;\s*(?P<lo>\d+(?:\.\d+)?)\s*-\s*(?P<hi>\d+(?:\.\d+)?)\)"
)


def _legend_estimates(article, sentence: str, estimates: List[EffectEstimate]) -> None:
    """"Risk factors for BC (OR;CI) were X (3.9;3.2-4.7)": the legend names the measure once."""
    legend = _LEGEND_RE.search(sentence)
    if not legend:
        return
    code = legend.group("m").upper().lstrip("A") or "OR"
    target = re.search(r"\bfor\s+(?P<t>[\w-]+(?:\s+[\w-]+){0,3})\s*$", sentence[: legend.start()])
    outcome = target.group("t") if target else ""
    for match in _LEGEND_GROUP_RE.finditer(sentence, legend.end()):
        exposure = re.sub(r"^(?:and\s+|were\s+|was\s+|the\s+|non-modifiable\s+risk-factors\s+were\s+)", "",
                          match.group("label").strip(), flags=re.IGNORECASE)
        est = EffectEstimate(
            measure=code, measure_text=legend.group(0), family="ratio",
            value=float(match.group("v")), value_text=match.group("v"),
            ci_low=float(match.group("lo")), ci_high=float(match.group("hi")),
            ci_level=95 if "95" in legend.group(0) else None,
            outcome_name=outcome, outcome_basis=f"maruziyet: {exposure}",
            source=_source(article, sentence),
        )
        _validate_estimate(est)
        estimates.append(est)


def _inherit_subgroup_outcomes(estimates: List[EffectEstimate]) -> None:
    """An unnamed estimate in a subgroup clause takes the endpoint named earlier in the same sentence."""
    for i, est in enumerate(estimates):
        if est.outcome_name or est.family == "diagnostic":
            continue
        for prior in reversed(estimates[:i]):
            if prior.source.sentence == est.source.sentence and prior.outcome_name:
                est.outcome_name = prior.outcome_name
                est.outcome_basis = "aynı cümlede önce adlandırılan sonlanım (alt grup)"
                est.subgroup = True
                break


_PRIMARY_DEF_RE = re.compile(
    r"\b(?:the\s+)?(?:co-?primary|dual\s+primary|primary)\s+(?:efficacy\s+)?(?:outcome|end\s*points?|endpoint)s?"
    r"(?:\s+for\s+this\s+meta-analysis)?\s+(?:was|were)\s+(?:the\s+)?(?P<o>[^.;]{3,160})",
    re.IGNORECASE,
)


def _bind_primary_outcome(article: Dict[str, Any], estimates: List[EffectEstimate]) -> None:
    """Bind an unnamed estimate to the defined primary outcome only when the text links them."""
    sentences = sentences_of(article.get("abstract") or "")
    definition, def_index = None, -1
    for idx, sentence in enumerate(sentences):
        match = _PRIMARY_DEF_RE.search(sentence)
        if match:
            definition, def_index = match, idx
            break
    if definition is None:
        return
    primary = re.sub(r"\s+", " ", definition.group("o")).strip(" ,")
    primary = re.split(r"[;]|\s+\((?:the|time)", primary)[0].strip()
    methods_window = " ".join(sentences[def_index: def_index + 4]).lower()
    for est in estimates:
        if est.outcome_name or est.family == "diagnostic":
            continue
        sentence = est.source.sentence
        names_primary = re.search(r"\bprimary\s+(?:outcome|end\s*point|endpoint)", sentence, re.IGNORECASE)
        phrase = re.sub(r"^(?:adjusted|unadjusted|age-adjusted)\s+", "", est.measure_text.lower()).strip()
        methods_link = len(phrase) > 4 and phrase in methods_window and phrase not in ("hazard ratio", "odds ratio")
        if names_primary or methods_link:
            est.outcome_name = primary
            est.outcome_basis = (
                "birincil sonlanım tanımı (ayrı cümle): \"" + _collapse(sentences[def_index]) + "\""
            )


def _build_estimate(article, sentence, mention, group, mentions, lead_outcome: str = "") -> EffectEstimate:
    ci = group.get("ci")
    if mention["family"] == "diagnostic" or mention["code"] in DIAGNOSTIC_MEASURES:
        outcome = _diagnostic_target(sentence, article)
    else:
        outcome = _clean_outcome(lead_outcome) or _resolve_outcome(
            sentence, mention, group.get("abs_start", mention["end"]) + group.get("end", 0)
        )
    est = EffectEstimate(
        measure=mention["code"],
        measure_text=mention["text"].strip(),
        family=mention["family"],
        value=group["value"],
        value_text=group["value_text"],
        ci_low=ci[0] if ci else None,
        ci_high=ci[1] if ci else None,
        ci_level=group.get("ci_level") or (95 if ci and re.search(r"95\s*%|\bCI\b", sentence) else None),
        p_value=group.get("p") or "",
        contrast_value=group.get("contrast"),
        outcome_name=outcome,
        subgroup=bool(re.search(r"\b(?:among|subgroup|in patients (?:receiving|with)|for those)\b",
                                sentence[: mention["start"]], re.IGNORECASE)),
        source=_source(article, sentence),
    )
    if ci and group.get("ci_level") is None:
        level = re.search(r"(\d{2})\s*%\s*(?:CI|confidence)", sentence[mention["start"]:])
        if level:
            est.ci_level = int(level.group(1))
    _validate_estimate(est)
    return est


def _dedupe_estimates(estimates: List[EffectEstimate]) -> List[EffectEstimate]:
    seen = set()
    unique = []
    for est in estimates:
        key = (est.measure, est.value, est.ci_low, est.ci_high, est.source.sentence)
        if key in seen:
            continue
        seen.add(key)
        unique.append(est)
    return unique


# ---------------------------------------------------------------------------
# Design-dependent claim types and causal-language guard
# ---------------------------------------------------------------------------

_RANDOMIZED_KEYS = {"rct"}
_SYNTHESIS_KEYS = {"meta_analysis", "systematic_review", "systematic_review_and_meta_analysis"}
_ASSOCIATION_KEYS = {"cohort", "case_control", "cross_sectional", "retrospective_comparative", "observational_unspecified", "comparative"}
_DESCRIPTIVE_KEYS = {"case_report", "case_series", "retrospective_case_series"}

CLAIM_TYPE_TR = {
    "causal_effect": "Randomize karşılaştırma: tedavi etkisi tahmini",
    "pooled_randomized": "Randomize çalışmaların havuzlanmış tahmini",
    "pooled_observational": "Gözlemsel çalışmaların havuzlanmış ilişki tahmini",
    "pooled_diagnostic": "Tanısal doğruluk çalışmalarının havuzlanmış tahmini",
    "pooled_unspecified": "Havuzlanmış tahmin (dahil edilen tasarım özette belirsiz)",
    "association": "Gözlemsel ilişki: nedensellik çıkarılamaz",
    "diagnostic_accuracy": "Tanısal doğruluk: tedavi etkisi değildir",
    "descriptive": "Tanımlayıcı gözlem: kontrol grubu yok, nedensellik çıkarılamaz",
    "uncontrolled": "Kontrolsüz araştırma: nedensel tedavi üstünlüğü çıkarılamaz",
    "no_results": "Sonuç bildirilmedi (protokol veya özetsiz kayıt)",
    "not_applicable": "Birincil veri yok: nedensel çıkarım yapılmaz",
}

_DIAG_CUE_RE = re.compile(r"\b(?:diagnostic\s+accuracy|sensitivity(?!\s+(?:and\s+subgroup\s+)?analys)|specificity|area\s+under\s+the|AUC|reference\s+standard|index\s+test)\b", re.IGNORECASE)
_RCT_POOL_RE = re.compile(r"\b(?:randomi[sz]ed\s+(?:controlled\s+)?trials?|RCTs?|randomised\s+controlled)\b", re.IGNORECASE)
_OBS_POOL_RE = re.compile(r"\b(?:observational|cohort|case-control|cross-sectional)\b", re.IGNORECASE)
_PROTOCOL_RE = re.compile(r"\b(?:study\s+protocol|a\s+protocol\s+for|trial\s+protocol|protocol\s+of)\b", re.IGNORECASE)


def classify_claim_type(design_key: str, title: str, abstract: str, results_reported: bool) -> str:
    text = f"{title} {abstract}"
    if not results_reported:
        return "no_results"
    if design_key in _RANDOMIZED_KEYS:
        return "causal_effect"
    if design_key in _SYNTHESIS_KEYS:
        if _DIAG_CUE_RE.search(text):
            return "pooled_diagnostic"
        rct = _RCT_POOL_RE.search(text)
        obs = _OBS_POOL_RE.search(text)
        if rct and not obs:
            return "pooled_randomized"
        if obs and not rct:
            return "pooled_observational"
        return "pooled_unspecified"
    if design_key == "diagnostic_accuracy" or (_DIAG_CUE_RE.search(text) and design_key in _ASSOCIATION_KEYS | {"unclassified"}):
        return "diagnostic_accuracy"
    if design_key in _ASSOCIATION_KEYS:
        return "association"
    if design_key in _DESCRIPTIVE_KEYS:
        return "descriptive"
    if design_key == "clinical_trial":
        return "uncontrolled"
    return "not_applicable"


CAUSAL_CLAIM_TYPES = {"causal_effect", "pooled_randomized"}

# Turkish and English causal / superiority wording.
CAUSAL_LANGUAGE_RE = re.compile(
    r"\b(?:azaltt[ıi]|azalt[ıi]r|azaltmaktad[ıi]r|art[ıi]rd[ıi]|art[ıi]r[ıi]r|önledi|önler|üstün(?:dür|lük)?|"
    r"etkilidir|etkili\s+bulundu|iyileştirdi|iyileştirir|neden\s+ol(?:du|ur|maktadır)|yol\s+açt[ıi]|"
    r"koruyucu(?:dur)?|fayda\s+sağlad[ıi]|"
    r"reduced|reduces|prevent(?:s|ed)?|caused|causes|superior|improved|improves|effective|"
    r"led\s+to|leads\s+to|protective|outperform(?:s|ed)?)\b",
    re.IGNORECASE,
)


def strip_quotations(text: str) -> str:
    """Remove verbatim quoted source sentences before checking generated wording."""
    return re.sub(r"\"[^\"]*\"|“[^”]*”|«[^»]*»", " ", text or "")


def find_causal_language(text: str) -> List[str]:
    return [m.group(0) for m in CAUSAL_LANGUAGE_RE.finditer(strip_quotations(text))]


# ---------------------------------------------------------------------------
# Interventions, comparators and co-treatments
# ---------------------------------------------------------------------------

_COTREATMENT_RES = [
    re.compile(r"\bin\s+addition\s+to\s+(?P<c>(?:usual|standard|background|guideline-directed|optimal|recommended|conventional)\s+[\w\s-]{2,40}?)(?=[.,;)]|$)", re.IGNORECASE),
    re.compile(r"\bon\s+top\s+of\s+(?P<c>[\w\s-]{3,40}?)(?=[.,;)]|$)", re.IGNORECASE),
    re.compile(r"\beach\s+of\s+which\s+was\s+given\s+with\s+(?P<c>[\w\s-]{3,50}?)(?=\s+for\b|[.,;)]|$)", re.IGNORECASE),
    re.compile(r"\b(?:plus|and)\s+(?P<c>usual\s+care|standard\s+care|standard\s+of\s+care|best\s+supportive\s+care)\b", re.IGNORECASE),
    re.compile(r"\b(?P<c>[\w-]+(?:-based)?\s+chemotherapy)\b(?=[^.]*\b(?:placebo|alone)\b[^.]*\bplus\s+(?:[\w-]+-based\s+)?chemotherapy)", re.IGNORECASE),
    re.compile(r"\btreated\s+with\s+(?P<c>intravenous\s+[\w-]+)\s+before\s+randomi[sz]ation", re.IGNORECASE),
    re.compile(r"\b(?:background|concomitant|concurrent)\s+(?:therapy|therapies|treatment|treatments|medications?)\s+"
               r"(?:with|of|including)\s+(?P<c>[\w-]+(?:\s+[\w-]+)?)", re.IGNORECASE),
    re.compile(r"\bconcomitant\s+(?P<c>[\w-]+)\s+(?:use|therapy|treatment)\b", re.IGNORECASE),
]


def extract_co_treatments(article: Dict[str, Any]) -> List[CoTreatment]:
    found: List[CoTreatment] = []
    seen = set()
    for sentence in sentences_of(article.get("abstract") or ""):
        for pattern in _COTREATMENT_RES:
            for match in pattern.finditer(sentence):
                name = re.sub(r"\s+", " ", match.group("c")).strip(" ,;")
                if not name or name.lower() in seen or len(name) < 3:
                    continue
                if re.match(r"(?i)(?:of|the|a|an|to|and|in)\b", name):
                    continue
                seen.add(name.lower())
                found.append(CoTreatment(name=name, source=_source(article, sentence)))
    return found


_NAME_FUNCTION_WORDS = {
    "ve", "veya", "ile", "için", "sonra", "önce", "grup", "grubu", "alone", "group", "the", "and", "or", "of",
    "hastalar", "tedavi", "almak", "gün", "hafta", "değerlendirilemedi", "belirtilmedi",
}


def _plausible_name(value: Optional[str]) -> str:
    """Reject clipped fragments ("ve", "(1:1)", "hastalar tedavi") from the legacy extractor."""
    text = re.sub(r"\s+", " ", (value or "")).strip(" ,;")
    if not text or text in ("Belirtilmedi", "değerlendirilemedi"):
        return ""
    tokens = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9+/-]+", text)
    while tokens and tokens[-1].lower() in _NAME_FUNCTION_WORDS:
        tokens.pop()
    content = [t for t in tokens if t.lower() not in _NAME_FUNCTION_WORDS and len(t) >= 4 and not t.isdigit()]
    if not content or text.startswith("(") or re.search(r"\d+%", text):
        return ""
    if len(content) < len([t for t in tokens if not t.isdigit()]) / 2:
        return ""
    cleaned = re.sub(r"(?:\s+(?:" + "|".join(sorted(_NAME_FUNCTION_WORDS, key=len, reverse=True)) + r"))+\s*$", "", text,
                     flags=re.IGNORECASE)
    return cleaned.strip(" ,;")


def _clean_arm_label(label: str) -> str:
    text = re.sub(r"^(?:the|a|an)\s+", "", (label or "").strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s+group$", "", text, flags=re.IGNORECASE)
    return text.strip()


def _core_intervention(name: str, co_treatments: List[CoTreatment]) -> str:
    """Drop a co-treatment that sits inside the intervention phrase."""
    core = name or ""
    for co in co_treatments:
        core = re.sub(rf"\s*(?:\+|plus|and|with|ile|artı)\s+{re.escape(co.name)}\b", "", core, flags=re.IGNORECASE)
        core = re.sub(rf"\b{re.escape(co.name)}\s*(?:\+|plus|and|ile|artı)\s+", "", core, flags=re.IGNORECASE)
    return core.strip(" ,;") or name


_ROLE_LABEL = {
    "causal_effect": "Müdahale",
    "pooled_randomized": "Müdahale",
    "association": "Maruziyet",
    "pooled_observational": "Maruziyet",
    "diagnostic_accuracy": "İndeks test",
    "pooled_diagnostic": "İndeks test",
}


# ---------------------------------------------------------------------------
# Trial identity and report relations
# ---------------------------------------------------------------------------

REGISTRY_RE = re.compile(
    r"\b(NCT\d{8}|ISRCTN\d{6,}|NTR\d{3,}|DRKS\d{8}|jRCT\d{6,}|ChiCTR[\w-]{6,}|ACTRN\d{10,}|"
    r"EudraCT\s*\d{4}-\d{6}-\d{2}|CTRI/\d{4}/\d{2,3}/\d{5,6}|UMIN\d{6,})\b",
    re.IGNORECASE,
)
PROSPERO_RE = re.compile(r"\bCRD\d{8,}\b")
_ACRONYM_TOKEN = r"[A-Z][A-Z0-9]{1,}(?:-[A-Za-z0-9]+)*"
_ACRONYM_CONTEXT_RES = [
    re.compile(rf"\b(?P<a>{_ACRONYM_TOKEN}(?:\s+[A-Z]{{3,}})?)\s+(?:ClinicalTrials\.gov|Netherlands\s+Trial\s+Register|Current\s+Controlled|ISRCTN|number)"),
    re.compile(rf"\((?P<a>{_ACRONYM_TOKEN})\)\s*:"),
    re.compile(rf"\b(?:the|of|from)\s+(?P<a>{_ACRONYM_TOKEN})\s+(?:trial|study|analysis|cohort)\b"),
    re.compile(rf"\b(?P<a>{_ACRONYM_TOKEN})\s+(?:and|or)\s+(?P<b>{_ACRONYM_TOKEN})\s+trials\b"),
    re.compile(rf"\bthe\s+(?P<a>{_ACRONYM_TOKEN})\s+(?:and|or)\s+(?P<b>{_ACRONYM_TOKEN})\s+trials\b"),
    re.compile(rf"\bof\s+(?P<a>{_ACRONYM_TOKEN}(?:-[A-Z][a-z]+)?)\s*[.:]?\s*$"),
]
_NOT_TRIAL_ACRONYMS = {
    "HR", "OR", "RR", "CI", "HF", "NSCLC", "CT", "MRI", "COVID", "SARS", "UK", "USA", "US", "BMI", "ICU", "DNA", "RNA",
    "PCR", "ECG", "AF", "TB", "NHS", "WHO", "FDA", "EMA", "IQR", "SD", "ITT", "LVO", "MSU", "OMOP", "CDM", "OHDSI",
    "UKB", "PRP", "PH", "CRC", "BC", "TC", "MRCP", "USG", "CBD", "ICH", "IPH", "SAH", "IVH", "DOR", "CBCT",
    "ONSD", "IICP", "ASM", "PSE", "GLD", "GLDS", "T2DM", "DPP4", "SGLT2", "SGLT-2", "GLP-1", "ICIM", "ICI", "ICIS",
    "TOSV-AM", "TOSV", "AIS", "POCT", "LFA", "CDS", "UACR", "EQ-5D", "MTBC", "RR", "DST", "CRS", "AE", "SAE",
}

_RELATION_CUES = [
    ("secondary_analysis", re.compile(
        r"\b(?:this|a|our|we\s+(?:performed|conducted|did|report)\s+an?)\s+(?:secondary|post\s*hoc|post-hoc|exploratory|"
        r"ancillary|prespecified|pre-specified)\s+(?:subgroup\s+)?analys[ie]s\b"
        r"|\b(?:secondary|post\s*hoc|post-hoc|ancillary|subgroup)\s+analys[ie]s\s+of\b|\bsub-?analys[ie]s\s+of\b",
        re.IGNORECASE)),
    ("pooled_analysis", re.compile(r"\bpooled\s+analys[ie]s\b|\bindividual\s+(?:patient|participant)\s+data\s+from\b|-Pooled\b", re.IGNORECASE)),
    ("extended_follow_up", re.compile(
        r"\b(?:we\s+report|report\s+the|present\s+the|here\s+we\s+report)\s+(?:the\s+)?"
        r"[^.]{0,40}?\b(?:long(?:er)?-term\s+(?:follow-up|outcomes|results)|extended\s+follow-up|extension\s+study|"
        r"open-label\s+extension|\d+-year\s+(?:follow-up|outcomes|results))\b", re.IGNORECASE)),
    ("updated_analysis", re.compile(r"\b(?:second|third|final)\s+interim\s+analysis\b|\bupdated\s+(?:analysis|results)\b|\bat\s+the\s+first\s+interim\s+analysis\b[^.]*\bwe\s+report\b", re.IGNORECASE)),
]
_TITLE_STOP = {
    "a", "an", "the", "of", "in", "for", "with", "and", "or", "to", "on", "versus", "vs", "trial", "study",
    "randomized", "randomised", "comparing", "patients", "analysis", "effect", "effects", "outcomes", "longer", "term",
    "long", "results", "clinical", "from", "by", "at",
}


def extract_registry_ids(article: Dict[str, Any]) -> List[str]:
    text = normalize_text(f"{article.get('title') or ''} {article.get('abstract') or ''}")
    ids = []
    for match in REGISTRY_RE.finditer(text):
        value = re.sub(r"\s+", "", match.group(1)).upper()
        if value not in ids:
            ids.append(value)
    return ids


def extract_trial_acronyms(article: Dict[str, Any]) -> List[str]:
    text = normalize_text(f"{article.get('title') or ''}. {article.get('abstract') or ''}")
    found: List[str] = []
    title = normalize_text(article.get("title") or "")
    for match in re.finditer(rf"\((?P<a>{_ACRONYM_TOKEN})\)", title):
        found.append(match.group("a"))
    for pattern in _ACRONYM_CONTEXT_RES:
        for match in pattern.finditer(text):
            for key in ("a", "b"):
                value = match.groupdict().get(key)
                if value:
                    found.append(value.strip())
    cleaned = []
    for item in found:
        token = item.strip()
        if token.upper() in _NOT_TRIAL_ACRONYMS or len(token) < 4:
            continue
        if re.fullmatch(r"[A-Z]{1,3}\d*", token):
            continue
        if token not in cleaned:
            cleaned.append(token)
    return cleaned


_TITLE_ROLE_CUES = [
    ("secondary_analysis", re.compile(r"\b(?:secondary|post\s*hoc|post-hoc|exploratory|ancillary|prespecified|pre-specified|"
                                      r"subgroup)\s+analys[ie]s\b|\bsub-?analys[ie]s\b", re.IGNORECASE)),
    ("pooled_analysis", re.compile(r"\bpooled\s+analys[ie]s\b", re.IGNORECASE)),
    ("extended_follow_up", re.compile(r"\b(?:long(?:er)?-term\s+(?:follow-up|outcomes|results)|extended\s+follow-up|"
                                      r"extension\s+study|open-label\s+extension|\d+-year\s+(?:follow-up|outcomes|results))\b",
                                      re.IGNORECASE)),
    ("updated_analysis", re.compile(r"\b(?:final|updated|overall\s+survival)\s+(?:analysis|results)\b", re.IGNORECASE)),
]


def detect_report_role(article: Dict[str, Any], design_key: str) -> str:
    """Primary report, or a report derived from an earlier trial publication."""
    if design_key in _SYNTHESIS_KEYS:
        return "evidence_synthesis"
    title = normalize_text(article.get("title") or "")
    abstract = normalize_text(article.get("abstract") or "")
    for role, pattern in _TITLE_ROLE_CUES:
        if pattern.search(title):
            return role
    for role, pattern in _RELATION_CUES:
        if pattern.search(abstract):
            return role
    return "primary"


def _title_tokens(title: str) -> set:
    words = re.findall(r"[a-z]+", (title or "").lower())
    tokens = set()
    for word in words:
        if word in _TITLE_STOP or len(word) < 4:
            continue
        tokens.add(word[:8])  # crude stem: appendectomy / appendicectomy differ, antibiotics/antibiotic agree
    return tokens


def link_studies(studies: List[Study]) -> Dict[str, Any]:
    """Link derived reports to their parent trial and mark independent evidence units.

    Returns a summary with clusters, independent participant totals and overlap notes.
    """
    by_pmid = {s.pmid: s for s in studies}
    parent: Dict[str, str] = {s.pmid: s.pmid for s in studies}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    primaries = [s for s in studies if s.report_role != "evidence_synthesis"]
    # 1) Shared registry numbers or trial acronyms -> same trial.
    for i, a in enumerate(primaries):
        for b in primaries[i + 1:]:
            shared_ids = set(a.registry_ids) & set(b.registry_ids)
            shared_acr = {x.lower() for x in a.trial_acronyms} & {x.lower() for x in b.trial_acronyms}
            if shared_ids or shared_acr:
                union(a.pmid, b.pmid)
                basis = "ortak kayıt numarası: " + ", ".join(sorted(shared_ids)) if shared_ids else \
                    "ortak çalışma kısaltması: " + ", ".join(sorted(shared_acr))
                derived, base = (a, b) if a.report_role != "primary" and b.report_role == "primary" else (b, a)
                if derived.report_role == "primary" and base.report_role == "primary":
                    # Two "primary" reports of one trial: the later one is a further report.
                    derived, base = sorted((a, b), key=lambda s: (s.year or "", s.pmid))[::-1]
                    derived.report_role = "updated_analysis"
                derived.relations.append(StudyRelation(derived.report_role, base.pmid, basis, "kesin"))
    # 2) Derived reports without an identifier: conservative title similarity.
    for study in primaries:
        if study.report_role == "primary" or study.relations:
            continue
        mine = _title_tokens(study.title)
        best, best_score = None, 0.0
        for other in primaries:
            if other.pmid == study.pmid or other.report_role != "primary":
                continue
            theirs = _title_tokens(other.title)
            if not mine or not theirs:
                continue
            score = len(mine & theirs) / len(mine | theirs)
            if score > best_score:
                best, best_score = other, score
        if best is not None and best_score >= 0.3 and best.journal and best.journal == study.journal:
            study.relations.append(StudyRelation(
                study.report_role, best.pmid,
                f"başlık benzerliği {best_score:.2f} ve aynı dergi; kayıt numarası yok", "olasi",
            ))
            union(best.pmid, study.pmid)
    # 3) Evidence syntheses that name a trial present in the set.
    overlap_notes = []
    for synth in studies:
        noted_roots = set()
        if synth.report_role != "evidence_synthesis":
            continue
        text = normalize_text(synth.legacy.get("abstract", "")).lower()
        for other in primaries:
            names = [x for x in other.trial_acronyms if len(x) >= 4]
            ids = other.registry_ids
            if any(re.search(rf"\b{re.escape(n.lower())}\b", text) for n in names) or any(i.lower() in text for i in ids):
                synth.relations.append(StudyRelation("includes_trial", other.pmid,
                                                     "meta-analiz özeti çalışmanın adını veriyor", "kesin"))
                root = find(other.pmid)
                if root in noted_roots:
                    continue
                noted_roots.add(root)
                members = sorted(p for p in parent if find(p) == root)
                overlap_notes.append(
                    f"PMID {synth.pmid} (kanıt sentezi), PMID {', '.join(members)} ile aynı katılımcıları içeriyor; "
                    "bu katılımcılar bağımsız kanıt toplamına iki kez eklenmedi."
                )
    clusters: Dict[str, List[str]] = {}
    for study in studies:
        root = find(study.pmid)
        clusters.setdefault(root, []).append(study.pmid)
    independent_n = 0
    independent_units = 0
    for root, members in clusters.items():
        members_studies = [by_pmid[m] for m in members]
        for s in members_studies:
            s.evidence_cluster = root
        primary_members = [s for s in members_studies if s.report_role == "primary"]
        if members_studies[0].report_role == "evidence_synthesis" and len(members_studies) == 1:
            members_studies[0].counts_as_independent = False
            continue
        anchor = primary_members[0] if primary_members else sorted(members_studies, key=lambda s: (s.year or "", s.pmid))[0]
        for s in members_studies:
            s.counts_as_independent = s is anchor and s.results_reported
        if anchor.results_reported:
            independent_units += 1
            if anchor.population.n_total:
                independent_n += anchor.population.n_total
    return {
        "clusters": clusters,
        "independent_primary_units": independent_units,
        "independent_participants": independent_n,
        "overlap_notes": overlap_notes,
    }


# ---------------------------------------------------------------------------
# Building Study objects (cached so every renderer uses the same object)
# ---------------------------------------------------------------------------

_CACHE: Dict[str, Study] = {}
_CACHE_LIMIT = 512


def _article_key(article: Dict[str, Any]) -> str:
    payload = json.dumps(
        [article.get("pmid"), article.get("doi"), article.get("title"), article.get("abstract"),
         list(article.get("publication_types") or []), article.get("_citation_status")],
        ensure_ascii=False, default=str,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def build_study(article: Dict[str, Any], query: str = "") -> Study:
    """Return the single structured ``Study`` object for one PubMed record."""
    key = _article_key(article) + "|" + (query or "")
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    study = _build_study_uncached(article, query)
    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.clear()
    _CACHE[key] = study
    return study


def clear_cache() -> None:
    _CACHE.clear()


def _build_study_uncached(article: Dict[str, Any], query: str) -> Study:
    title = article.get("title") or ""
    abstract = (article.get("abstract") or "").replace("\xa0", " ")
    if abstract.strip().lower() in ("[abstract not available]", "abstract not available"):
        abstract = ""
    art = dict(article)
    art["abstract"] = abstract
    pmid = str(article.get("pmid") or "")
    classification = rg.classify_study_design(article.get("publication_types") or [], title, abstract)
    design_key = classification["design_key"]
    design_label = classification["design"]
    protocol = bool(_PROTOCOL_RE.search(title)) or bool(_FUTURE_RE.search(abstract) and not re.search(r"\b(?:were|was)\s+(?:enrolled|randomi[sz]ed|included)\b", abstract))
    if protocol:
        design_label = f"{design_label} — çalışma protokolü (sonuç yok)"
    results_reported = bool(abstract.strip()) and not protocol

    details = rg.extract_article_clinical_details(art, query)
    rob_legacy = rg.assess_risk_of_bias(art)

    arms = extract_arms(art, randomized=design_key in ("rct", "clinical_trial"))
    events = extract_event_counts(art)
    population = extract_population(art, design_key, arms, events)
    pop_prov = (details.get("provenance") or {}).get("population") or {}
    population.description = details.get("patient_group") if details.get("patient_group") not in ("Belirtilmedi", "") else ""
    if population.description and pop_prov.get("source_sentence") and population.source.location == "none":
        population.source = _source(art, pop_prov.get("source_sentence"))

    claim_type = classify_claim_type(design_key, title, abstract, results_reported)
    if claim_type == "diagnostic_accuracy" and design_key in (
        "comparative", "observational_unspecified", "unclassified", "cross_sectional", "cohort",
    ) and re.search(r"diagnostic\s+(?:accuracy|performance)|sensitivity\s+and\s+specificity", f"{title} {abstract}", re.IGNORECASE):
        design_key = "diagnostic_accuracy"
        design_label = rg._DESIGN_LABELS["diagnostic_accuracy"] + (" — çalışma protokolü (sonuç yok)" if protocol else "")
    co_treatments = extract_co_treatments(art)
    role_label = _ROLE_LABEL.get(claim_type, "Müdahale")

    interventions: List[Intervention] = []
    comparators: List[Comparator] = []
    if arms and claim_type in ("causal_effect", "association", "uncontrolled"):
        # Arm labels are copied verbatim from the allocation sentence.
        if len(arms) > 2 and any(a.role == "comparator" for a in arms):
            active = [a for a in arms if a.role != "comparator"]
            control = [a for a in arms if a.role == "comparator"]
        else:
            active, control = arms[:1], arms[1:2]
        for arm in active:
            interventions.append(Intervention(name=_core_intervention(arm.label, co_treatments),
                                              role_label=role_label, source=arm.source))
        for arm in control:
            comparators.append(Comparator(name=_core_intervention(arm.label, co_treatments), source=arm.source))
    elif claim_type in ("pooled_randomized", "pooled_observational", "pooled_unspecified"):
        title_int = re.match(r"^(?P<i>[A-Za-z0-9][\w\s+/-]{2,60}?)\s+(?:in|for|among)\s+(?:patients|adults|children|people|"
                             r"women|men|individuals|participants)\b", normalize_text(title))
        if title_int and not re.search(r"\b(?:meta-analysis|review|effect|effects|association|risk)\b", title_int.group("i"),
                                       re.IGNORECASE):
            interventions.append(Intervention(name=title_int.group("i").strip(), role_label=role_label,
                                              source=_source(art, title)))
    elif claim_type not in ("pooled_diagnostic", "no_results", "descriptive"):
        prov = details.get("provenance") or {}
        int_claim = prov.get("intervention") or {}
        comp_claim = prov.get("comparison") or {}
        int_value = _plausible_name(int_claim.get("value"))
        comp_value = _plausible_name(comp_claim.get("value"))
        if int_value:
            interventions.append(Intervention(name=_core_intervention(int_value, co_treatments), role_label=role_label,
                                              source=_source(art, int_claim.get("source_sentence") or "")))
        if comp_value:
            comparators.append(Comparator(name=_core_intervention(comp_value, co_treatments),
                                          source=_source(art, comp_claim.get("source_sentence") or "")))
        # A name whose source sentence cannot be found verbatim is not shown.
        interventions = [i for i in interventions if i.source.verification_status == SOURCE_VERIFIED]
        comparators = [c for c in comparators if c.source.verification_status == SOURCE_VERIFIED]

    estimates = extract_effect_estimates(art) if results_reported else []
    outcomes: Dict[str, Outcome] = {}
    for est in estimates:
        name = est.outcome_name or ""
        kind = {
            "diagnostic": "diagnostic",
        }.get(est.family, "efficacy" if claim_type in CAUSAL_CLAIM_TYPES else "association")
        if re.search(r"adverse|toxicit|complication|side effect|safety|infection", name, re.IGNORECASE):
            kind = "safety"
        outcome = outcomes.setdefault(name, Outcome(name=name, kind=kind, source=est.source))
        outcome.estimates.append(est)

    rob = RiskOfBiasAssessment(
        tool=rob_legacy.get("tool") or "",
        status="not_assessed",
        overall_rating=None,
        domains={k: NOT_ASSESSED_TR for k in (rob_legacy.get("domains") or {})},
        note="Araç seçildi; tam metin üzerinde gerçek değerlendirme yapılmadan risk derecesi verilmez.",
    )

    # Numeric contrasts the abstract states without a named effect measure
    # ("61.6 years vs 39.8", "9.1% vs 55.6%") stay visible as unstructured findings.
    covered = {est.source.sentence for est in estimates}
    other_numeric = []
    for om in details.get("outcome_metrics") or []:
        sentence = _collapse(om.get("source_sentence") or om.get("sentence") or "")
        if not sentence or sentence in covered or not om.get("metrics"):
            continue
        other_numeric.append({
            "outcome": om.get("outcome") or "",
            "metrics": list(om.get("metrics") or []),
            "source": _source(art, sentence),
        })

    study = Study(
        pmid=pmid,
        doi=str(article.get("doi") or ""),
        title=title,
        journal=article.get("journal") or "",
        year=str(article.get("pub_year") or ""),
        design_key=design_key,
        design_label=design_label,
        evidence_level=classification["level"],
        evidence_level_note=classification.get("evidence_level_note") or rg.EVIDENCE_LEVEL_NOTE,
        claim_type=claim_type,
        claim_type_tr=CLAIM_TYPE_TR[claim_type],
        causal_inference_allowed=claim_type in CAUSAL_CLAIM_TYPES,
        results_reported=results_reported,
        population=population,
        arms=arms,
        interventions=interventions,
        comparators=comparators,
        co_treatments=co_treatments,
        outcomes=list(outcomes.values()),
        event_counts=events,
        risk_of_bias=rob,
        registry_ids=extract_registry_ids(art),
        trial_acronyms=extract_trial_acronyms(art),
        report_role=detect_report_role(art, design_key),
        citation_status=str(article.get("_citation_status") or "not_checked"),
        other_numeric_findings=other_numeric,
        legacy={
            "abstract": abstract,
            "classification": classification,
            "rob": rob_legacy,
            "details": details,
        },
    )
    return study


def build_studies(articles: Iterable[Dict[str, Any]], query: str = "") -> Tuple[List[Study], Dict[str, Any]]:
    """Build (or fetch cached) Study objects and link them across the set."""
    studies = [build_study(a, query) for a in articles or []]
    for s in studies:
        s.relations = []
        s.counts_as_independent = True
        s.report_role = detect_report_role({"title": s.title, "abstract": s.legacy.get("abstract", "")}, s.design_key)
    summary = link_studies(studies)
    return studies, summary


# ---------------------------------------------------------------------------
# Turkish renderers (single source for cards, sections 5/6 and exports)
# ---------------------------------------------------------------------------

_MEASURE_TR = {
    "HR": "HR (risk oranı)", "OR": "OR (olasılık oranı)", "RR": "RR (göreli risk/oran oranı)",
    "IRR": "IRR (insidans hızı oranı)", "RD": "Fark", "MD": "Ortalama fark", "SMD": "Standardize ortalama fark",
    "WMD": "Ağırlıklı ortalama fark", "DOR": "Tanısal olasılık oranı", "sensitivity": "Duyarlılık",
    "specificity": "Özgüllük", "AUC": "AUC", "PPV": "Pozitif kestirim değeri", "NPV": "Negatif kestirim değeri",
    "accuracy": "Doğruluk", "LR+": "Pozitif olabilirlik oranı", "LR-": "Negatif olabilirlik oranı",
    "mean_change": "Ortalama değişim",
}

_ROLE_TR = {
    "primary": "Ana çalışma raporu",
    "secondary_analysis": "İkincil / post hoc / alt grup analizi",
    "pooled_analysis": "Havuzlanmış analiz",
    "updated_analysis": "Aynı çalışmanın güncellenmiş / ara analizi",
    "extended_follow_up": "Uzatılmış takip raporu",
    "evidence_synthesis": "Kanıt sentezi (sistematik derleme / meta-analiz)",
}


def _fmt_num(value: Optional[float]) -> str:
    if value is None:
        return ""
    text = f"{value:g}"
    return text.replace(".", ",")


def format_estimate_tr(est: EffectEstimate) -> str:
    label = _MEASURE_TR.get(est.measure, est.measure)
    if est.value is None:
        value = "nokta tahmini özette bildirilmedi"
    else:
        value = est.value_text.replace(".", ",")
    if est.contrast_value is not None:
        value += f" (karşılaştırma değeri {_fmt_num(est.contrast_value)})"
    if est.ci_low is not None and est.ci_high is not None:
        level = est.ci_level or 95
        ci = f"%{level} GA {_fmt_num(est.ci_low)} ile {_fmt_num(est.ci_high)}"
    else:
        ci = "GA özette bildirilmedi"
    p = f"; {est.p_value}" if est.p_value else ""
    flag = "" if est.usable else f" ⚠️ {est.validation_note}"
    sub = " (alt grup)" if est.subgroup else ""
    return f"{label}{sub}: {value} ({ci}{p}){flag}"


def outcome_label_tr(name: str) -> str:
    """Turkish outcome label. The source term is kept whenever translation could lose detail."""
    if not name:
        return "sonlanım özette adlandırılmadı"
    shown = rg._display_outcome_name(name)
    if not shown or shown == rg.UNTRANSLATED_OUTCOME_LABEL:
        return f"\"{name}\" (kaynak terim)"
    if shown.strip().lower() == name.strip().lower():
        return shown
    return f"{shown} (kaynak terim: \"{name}\")"


def claim_sentence_tr(study: Study, est: EffectEstimate) -> str:
    """Neutral, design-appropriate Turkish wording for one estimate. No causal verbs."""
    outcome = outcome_label_tr(est.outcome_name)
    stat = format_estimate_tr(est)
    if study.claim_type in ("causal_effect", "pooled_randomized"):
        lead = "Randomize karşılaştırmada"
        if study.report_role == "secondary_analysis" or est.subgroup:
            lead = "Randomize çalışmanın ikincil/alt grup analizinde (keşif amaçlı)"
        return f"{lead} {outcome} için {stat}."
    if study.claim_type in ("diagnostic_accuracy", "pooled_diagnostic"):
        target = f"hedef durum: {outcome}" if est.outcome_name else "hedef durum özette bu cümlede adlandırılmadı"
        return f"Tanısal doğruluk ({target}) — {stat}. Bu bir tedavi etkisi değildir."
    if study.claim_type in ("association", "pooled_observational", "pooled_unspecified"):
        return f"Gözlemsel ilişki: {outcome} için {stat}. Nedensellik çıkarılamaz."
    return f"{outcome} için {stat}. Kontrolsüz veri; nedensel çıkarım yapılmaz."


def render_study_card_lines(study: Study) -> List[str]:
    """Markdown lines used by Streamlit cards, section 6 and exported reports."""
    pmid = study.pmid or "yok"
    lines = [
        f"**Tasarım:** {study.design_label} | **Kanıt düzeyi:** {study.evidence_level}",
        f"**Yayın rolü:** {_ROLE_TR.get(study.report_role, study.report_role)} | **Çıkarım türü:** {study.claim_type_tr}",
    ]
    pop = study.population
    if pop.n_total:
        n_note = {
            "pooled": " (dahil edilen çalışmaların toplamı)",
            "arm_sum": " (kol sayılarının toplamı)",
            "cases": " (olgu sayısı)",
        }.get(pop.n_kind, "")
        lines.append(f"**Katılımcı (n):** {pop.n_total:,}".replace(",", ".") + n_note +
                     f" — Kaynak: \"{pop.source.sentence}\" (PMID: {pmid})")
    elif pop.n_planned:
        lines.append(f"**Katılımcı (n):** sonuç yok; planlanan örneklem {pop.n_planned} (PMID: {pmid})")
    else:
        lines.append(f"**Katılımcı (n):** {NOT_REPORTED_TR} (değer atanmadı; PMID: {pmid})")
    if pop.n_cases:
        lines.append(f"**Olgu sayısı (vaka-kontrol):** {pop.n_cases} — toplam katılımcı özette bildirilmedi")
    if study.arms:
        arm_text = "; ".join(f"{a.label}: n = {a.n}" for a in study.arms)
        lines.append(f"**Çalışma kolları:** {arm_text}")
    for intervention in study.interventions:
        lines.append(f"**{intervention.role_label}:** {intervention.name} (PMID: {pmid})")
    for comparator in study.comparators:
        lines.append(f"**Karşılaştırıcı:** {comparator.name} (PMID: {pmid})")
    if study.co_treatments:
        lines.append("**Eşlik eden / arka plan tedavi (müdahale sayılmadı):** " +
                     "; ".join(c.name for c in study.co_treatments))
    usable = [e for e in study.estimates if e.usable or e.validation == "eksik"]
    rejected = [e for e in study.estimates if e.validation == "tutarsiz"]
    if usable:
        lines.append("**Sonlanıma bağlı etki tahminleri:**")
        by_sentence: Dict[str, List[EffectEstimate]] = {}
        for est in usable:
            by_sentence.setdefault(est.source.sentence, []).append(est)
        for sentence, group in by_sentence.items():
            for est in group:
                basis = f" Sonlanım bağlama: {est.outcome_basis}." if est.outcome_basis else ""
                lines.append(f"- {claim_sentence_tr(study, est)}{basis}")
            lines.append(f"- Kaynak cümle: \"{sentence}\" (PMID: {pmid})")
    elif study.results_reported:
        lines.append(f"**Sonlanıma bağlı etki tahminleri:** özette ayrıştırılabilir etki ölçütü yok (PMID: {pmid})")
    else:
        lines.append(f"**Sonlanıma bağlı etki tahminleri:** sonuç bildirilmedi (PMID: {pmid})")
    if study.other_numeric_findings:
        bits = []
        for item in study.other_numeric_findings:
            bits.append(f"{item['outcome'] or 'sonlanım adı yok'}: {', '.join(item['metrics'])}")
        lines.append("**Özetteki diğer sayısal bulgular (etki ölçütü olarak yapılandırılmadı):** " + "; ".join(bits) +
                     f" (PMID: {pmid})")
    if rejected:
        lines.append(f"**Reddedilen eşleştirmeler:** {len(rejected)} (tutarsız güven aralığı veya geçersiz aralık; sentezde kullanılmadı)")
    lines.append(f"**Yanlılık riski:** {study.risk_of_bias.tool or 'araç seçilemedi'} — {NOT_ASSESSED_TR} (derece verilmedi)")
    lines.append(f"**GRADE:** {NOT_ASSESSED_TR}")
    if study.relations:
        rel = "; ".join(
            f"{_ROLE_TR.get(r.relation_type, r.relation_type) if r.relation_type != 'includes_trial' else 'İçerdiği çalışma'}"
            f" → PMID {r.related_pmid} ({r.basis}; {'kesin' if r.confidence == 'kesin' else 'olası, doğrulanmadı'})"
            for r in study.relations
        )
        lines.append(f"**Çalışma ilişkisi:** {rel}")
    if not study.counts_as_independent:
        lines.append("**Bağımsız kanıt sayımı:** Bu yayın bağımsız kanıt olarak sayılmadı (aynı katılımcılar veya kanıt sentezi).")
    return lines


def render_structured_evidence_section(studies: List[Study], summary: Dict[str, Any]) -> str:
    """Markdown block appended to section 6 from the same Study objects."""
    out = ["### 🧬 Yapılandırılmış Kanıt Kayıtları (Tek Veri Modeli)",
           f"Veri modeli sürümü: `{EVIDENCE_MODEL_VERSION}`. Her değer PMID ve kaynak cümleye bağlıdır. "
           "Hasta sayısı, olay sayısı ve kol sayısı ayrı alanlardadır. Eşlik eden tedavi müdahale sayılmaz. "
           "Nedensel dil yalnızca randomize karşılaştırmalarda kullanılır.\n"]
    for idx, study in enumerate(studies, 1):
        out.append(f"#### {idx}. PMID {study.pmid} — *{study.title}*")
        out.extend(f"- {line}" if not line.startswith("- ") else f"  {line}" for line in render_study_card_lines(study))
        out.append("")
    out.append("### 🔗 Çalışma İlişkileri ve Mükerrer Kanıt Kontrolü")
    out.append(f"- Bağımsız birincil kanıt birimi: **{summary.get('independent_primary_units', 0)}** "
               f"(toplam {len(studies)} yayın).")
    out.append(f"- Bağımsız birincil çalışmalardaki katılımcı toplamı (özette bildirilenler): "
               f"**{summary.get('independent_participants', 0):,}**".replace(",", ".") +
               ". İkincil analiz, güncellenmiş analiz, uzatılmış takip ve meta-analiz katılımcıları tekrar eklenmedi.")
    multi = {k: v for k, v in (summary.get("clusters") or {}).items() if len(v) > 1}
    if multi:
        for root, members in multi.items():
            out.append(f"- Aynı çalışma kümesi: PMID {', '.join(members)}")
    else:
        out.append("- Aynı çalışmaya ait birden fazla yayın saptanmadı.")
    for note in summary.get("overlap_notes") or []:
        out.append(f"- {note}")
    return "\n".join(out) + "\n"


def export_studies_json(studies: List[Study], summary: Dict[str, Any]) -> str:
    payload = {
        "evidence_model_version": EVIDENCE_MODEL_VERSION,
        "studies": [s.to_dict() for s in studies],
        "relations_summary": {
            "independent_primary_units": summary.get("independent_primary_units"),
            "independent_participants": summary.get("independent_participants"),
            "clusters": summary.get("clusters"),
            "overlap_notes": summary.get("overlap_notes"),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

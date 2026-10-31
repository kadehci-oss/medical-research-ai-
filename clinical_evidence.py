"""Canonical, provenance-preserving clinical evidence data model.

This module normalizes existing PubMed/abstract extraction without changing the
legacy API shape. It deliberately distinguishes bibliographic record presence
from independent validation of clinical claims.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, List, Optional

MODEL_VERSION = "1.0"
CLAIM_REVIEW_STATUS = "not_independently_clinically_validated"
_NOT_REPORTED = {None, "", "Belirtilmedi", "bildirilmedi", "belirtilmemiş", "Özette bildirilmedi", "özette açıkça bildirilmedi", "not reported", "not stated", "değerlendirilemedi", "unknown"}


def _is_not_reported(value: Any) -> bool:
    if value is None:
        return True
    folded = str(value).strip().casefold()
    return folded in {str(item).casefold() for item in _NOT_REPORTED if item is not None}


@dataclass
class EvidenceSource:
    pmid: str = ""
    doi: str = ""
    source_sentence: str = ""
    source_field: str = "abstract"
    verification_status: str = "not_verified"
    claim_validation_status: str = CLAIM_REVIEW_STATUS
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourcedValue:
    value: Any = None
    source: EvidenceSource = field(default_factory=EvidenceSource)

    def to_dict(self) -> Dict[str, Any]:
        return {"value": self.value, "source": self.source.to_dict()}


@dataclass
class Population:
    description: SourcedValue = field(default_factory=SourcedValue)
    total_participants: SourcedValue = field(default_factory=SourcedValue)
    characteristics: List[SourcedValue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description.to_dict(),
            "total_participants": self.total_participants.to_dict(),
            "characteristics": [x.to_dict() for x in self.characteristics],
        }


@dataclass
class Intervention:
    name: SourcedValue = field(default_factory=SourcedValue)
    concomitant_treatments: List[SourcedValue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name.to_dict(), "concomitant_treatments": [x.to_dict() for x in self.concomitant_treatments]}


@dataclass
class Comparator:
    name: SourcedValue = field(default_factory=SourcedValue)
    concomitant_treatments: List[SourcedValue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name.to_dict(), "concomitant_treatments": [x.to_dict() for x in self.concomitant_treatments]}


@dataclass
class StudyArm:
    role: str
    label: str
    participants_n: SourcedValue = field(default_factory=SourcedValue)
    events_n: SourcedValue = field(default_factory=SourcedValue)
    intervention: Optional[Intervention] = None
    comparator: Optional[Comparator] = None
    source: EvidenceSource = field(default_factory=EvidenceSource)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "label": self.label,
            "participants_n": self.participants_n.to_dict(),
            "events_n": self.events_n.to_dict(),
            "intervention": self.intervention.to_dict() if self.intervention else None,
            "comparator": self.comparator.to_dict() if self.comparator else None,
            "source": self.source.to_dict(),
        }


@dataclass
class EffectEstimate:
    outcome_id: str
    metric_type: str
    value: Optional[str] = None
    ci_lower: Optional[str] = None
    ci_upper: Optional[str] = None
    confidence_level: Optional[str] = None
    p_value: Optional[str] = None
    arm_label: Optional[str] = None
    population_subgroup: Optional[str] = None
    metric_label: Optional[str] = None
    reported_label: Optional[str] = None
    implausible_source_value: bool = False
    source: EvidenceSource = field(default_factory=EvidenceSource)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self) | {"source": self.source.to_dict()}


@dataclass
class ArmEventCount:
    arm_label: SourcedValue
    event_count: SourcedValue
    denominator: SourcedValue

    def to_dict(self) -> Dict[str, Any]:
        return {
            "arm_label": self.arm_label.to_dict(),
            "event_count": self.event_count.to_dict(),
            "denominator": self.denominator.to_dict(),
        }


@dataclass
class Outcome:
    id: str
    name: SourcedValue
    timepoint: SourcedValue = field(default_factory=SourcedValue)
    event_count: SourcedValue = field(default_factory=SourcedValue)
    denominator: SourcedValue = field(default_factory=SourcedValue)
    arm_event_counts: List[ArmEventCount] = field(default_factory=list)
    effect_estimates: List[EffectEstimate] = field(default_factory=list)
    source: EvidenceSource = field(default_factory=EvidenceSource)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name.to_dict(),
            "timepoint": self.timepoint.to_dict(),
            "event_count": self.event_count.to_dict(),
            "denominator": self.denominator.to_dict(),
            "arm_event_counts": [x.to_dict() for x in self.arm_event_counts],
            "effect_estimates": [x.to_dict() for x in self.effect_estimates],
            "source": self.source.to_dict(),
        }


@dataclass
class RiskOfBiasAssessment:
    tool: str = ""
    status: str = "not_assessed"
    assessed: bool = False
    overall_rating: str = "Değerlendirilmedi (Not Assessed)"
    domains: Dict[str, Any] = field(default_factory=dict)
    source: EvidenceSource = field(default_factory=EvidenceSource)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self) | {"source": self.source.to_dict()}


@dataclass
class Study:
    model_version: str
    study_id: str
    pmid: str
    doi: str
    title: str
    publication_year: str
    design_key: str
    design_label: str
    research_question: Dict[str, Any]
    population: Population
    intervention: Optional[Intervention]
    comparator: Optional[Comparator]
    arms: List[StudyArm]
    outcomes: List[Outcome]
    clinical_findings: List[SourcedValue]
    risk_of_bias: RiskOfBiasAssessment
    source: EvidenceSource
    relationship: Dict[str, Any]
    evidence_family_id: str
    evidence_family_basis: str
    causal_interpretation_status: str
    methodological_limitations: List[SourcedValue] = field(default_factory=list)
    exposure: Optional[SourcedValue] = None
    compatibility_view: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_version": self.model_version,
            "study_id": self.study_id,
            "pmid": self.pmid,
            "doi": self.doi,
            "title": self.title,
            "publication_year": self.publication_year,
            "design_key": self.design_key,
            "design_label": self.design_label,
            "research_question": self.research_question,
            "population": self.population.to_dict(),
            "intervention": self.intervention.to_dict() if self.intervention else None,
            "comparator": self.comparator.to_dict() if self.comparator else None,
            "exposure": self.exposure.to_dict() if self.exposure else None,
            "arms": [x.to_dict() for x in self.arms],
            "outcomes": [x.to_dict() for x in self.outcomes],
            "clinical_findings": [x.to_dict() for x in self.clinical_findings],
            "risk_of_bias": self.risk_of_bias.to_dict(),
            "source": self.source.to_dict(),
            "relationship": self.relationship,
            "evidence_family_id": self.evidence_family_id,
            "evidence_family_basis": self.evidence_family_basis,
            "causal_interpretation_status": self.causal_interpretation_status,
            "methodological_limitations": [x.to_dict() for x in self.methodological_limitations],
            "compatibility_view": self.compatibility_view,
        }


_FRAMEWORKS = {
    "PICO": {"label": "Tedavi / müdahale (PICO)", "components": ["Hasta grubu", "Müdahale", "Karşılaştırıcı", "Sonlanım"]},
    "PIRD": {"label": "Tanısal doğruluk (PIRD)", "components": ["Hasta grubu", "İndeks test", "Referans standart", "Hedef durum"]},
    "PECO": {"label": "Etiyoloji / epidemiyoloji / güvenlilik (PECO)", "components": ["Popülasyon", "Maruziyet", "Karşılaştırma", "Sonlanım"]},
    "PFO": {"label": "Prognoz (PFO)", "components": ["Popülasyon", "Prognostik faktör", "Sonlanım", "Zaman ufku"]},
    "PICOTS-S": {"label": "Tarama (PICOTS-S)", "components": ["Popülasyon", "Tarama stratejisi", "Karşılaştırma", "Sonlanım", "Zaman", "Ortam"]},
    "PICOT-HS": {"label": "Sağlık hizmetleri (PICOT-HS)", "components": ["Popülasyon", "Hizmet / sistem", "Karşılaştırma", "Sonlanım", "Ortam / zaman"]},
    "PCC": {"label": "Kapsam / betimleyici soru (PCC)", "components": ["Popülasyon", "Kavram", "Bağlam"]},
}


def select_research_question_framework(query: str, design_key: str = "") -> Dict[str, Any]:
    """Choose a question frame by the research question, not a mandatory PICO."""
    text = (query or "").casefold()
    diagnostic = ("diagnostic_accuracy" in (design_key or "")) or any(x in text for x in (
        "diagnos", "diagnostic", "sensitivity", "specificity", "auc", "tanı doğrulu", "duyarlılık", "özgüllük", "indeks test", "index test"
    ))
    screening = any(x in text for x in ("screening", "screen for", "tarama", "erken tanı program"))
    safety = any(x in text for x in ("safety", "adverse event", "adverse effect", "harm", "side effect", "güvenlilik", "yan etki", "zarar"))
    prognosis = any(x in text for x in ("prognos", "predict", "survival predictor", "prognoz", "öngörü", "tahmin et"))
    services = any(x in text for x in ("health service", "healthcare delivery", "care pathway", "health system", "sağlık hizmet", "sağlık sistemi", "bakım modeli"))
    epidemiology = any(x in text for x in ("incidence", "prevalence", "risk factor", "exposure", "association", "epidemiolog", "insidans", "prevalans", "maruziyet", "ilişki", "risk faktörü"))
    surgery = any(x in text for x in ("surgery", "surgical", "operative", "procedure", "cerrahi", "ameliyat", "prosedür"))
    treatment = any(x in text for x in ("treatment", "therapy", "efficacy", "effectiveness", "versus", "treated", "tedavi", "etkinlik", "etkililik", "müdahale"))

    if diagnostic:
        key, question_type = "PIRD", "diagnostic_accuracy"
    elif screening:
        key, question_type = "PICOTS-S", "screening"
    elif safety:
        key, question_type = "PECO", "safety"
    elif prognosis:
        key, question_type = "PFO", "prognosis"
    elif services:
        key, question_type = "PICOT-HS", "health_services"
    elif epidemiology:
        key, question_type = "PECO", "epidemiology"
    elif surgery:
        key, question_type = "PICO", "surgical"
    elif treatment:
        key, question_type = "PICO", "treatment"
    else:
        key, question_type = "PCC", "descriptive_or_unclear"
    spec = _FRAMEWORKS[key]
    return {"question_type": question_type, "framework": key, "label": spec["label"], "components": list(spec["components"])}


def _source(article: Dict[str, Any], sentence: str = "", source_field: str = "abstract") -> EvidenceSource:
    raw_status = str(article.get("verification_status") or "").casefold()
    if raw_status in {"verified", "record_found", "pubmed_record_found"}:
        status = "pubmed_record_found_identity_only"
    elif raw_status in {"unverified", "not_verified"}:
        status = "not_verified"
    elif article.get("pmid") and article.get("from_pubmed") is True:
        status = "pubmed_record_found_identity_only"
    else:
        status = "not_verified"
    pmid = str(article.get("pmid") or "")
    doi = str(article.get("doi") or "")
    url = str(article.get("pubmed_url") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""))
    return EvidenceSource(
        pmid=pmid,
        doi=doi,
        source_sentence=(sentence or "").strip(),
        source_field=source_field,
        verification_status=status if sentence else ("not_reported" if not sentence else status),
        source_url=url,
    )


def _fact(article: Dict[str, Any], value: Any, sentence: str = "", source_field: str = "abstract") -> SourcedValue:
    if value in _NOT_REPORTED:
        value = None
    return SourcedValue(value=value, source=_source(article, sentence, source_field))


def _clean_text(value: Any) -> str:
    value = str(value or "").strip()
    return "" if value in _NOT_REPORTED else value


def _extract_total_n(value: Any) -> Optional[int]:
    text = str(value or "")
    match = re.fullmatch(r"\s*n\s*=\s*([\d, ]+)\s*", text, re.IGNORECASE)
    if not match:
        return None
    digits = re.sub(r"[, ]", "", match.group(1))
    return int(digits) if digits.isdigit() else None


def _extract_total_participants(abstract: str, design_key: str) -> tuple[Optional[int], str]:
    """Extract only an explicitly described study-level participant total.

    Review strata, event denominators, and outcome-specific n values are not
    substituted for a study's overall participant count.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract or "") if s.strip()]
    is_review = design_key in {"meta_analysis", "systematic_review", "systematic_review_and_meta_analysis"}
    if is_review:
        review_patterns = (
            r"\b(?:comprising|including|with)\s+(?:a\s+)?total\s+of\s+([\d, ]+)\s+(?:participants|patients|individuals|subjects)\b",
            r"\btotal\s+of\s+([\d, ]+)\s+(?:participants|patients|individuals|subjects)\b",
            r"\b(?:among|representing|in|involving)\s+([\d, ]+)\s+(?:participants|patients|individuals|subjects)\b",
        )
        for sentence in sentences:
            for pattern in review_patterns:
                match = re.search(pattern, sentence, re.IGNORECASE)
                if match:
                    return int(re.sub(r"[, ]", "", match.group(1))), sentence
        return None, ""

    participant_modifier = r"(?:(?:adult|pediatric|paediatric|symptomatic|non[- ]?hospitalized|hospitalized|hospitalised|eligible|enrolled)\s+){0,3}"
    participant_pattern = participant_modifier + r"(?:patients|participants|subjects|children|adults|individuals|people|cases)"
    count_patterns = (
        rf"\b(?:randomly\s+assigned|assigned|enrolled|recruited|included|followed|evaluated|among|in|of\s+a\s+total\s+of|a\s+total\s+of|total\s+of|we\s+studied|we\s+included|we\s+followed|trial\s+of|study\s+of|study|case\s+series\s+included)\s+([\d, ]+)\s+{participant_pattern}\b",
        rf"\b([\d, ]+)\s+{participant_pattern}\s+(?:were|was)\s+(?:randomized|randomised|enrolled|included|followed|recruited)\b",
    )
    exclusion_terms = ("subgroup", "per arm", "in the intervention group", "in the control group", "event occurred", "events occurred")
    for sentence in sentences:
        lower = sentence.casefold()
        if any(term in lower for term in exclusion_terms):
            continue
        explicit_allocation_groups = re.findall(r"\b(?:to|into)\s+(?:the\s+)?[A-Za-z0-9-]+\s+(?:group|arm)\b", sentence, re.IGNORECASE)
        if re.search(r"\b(?:assigned|randomi[sz]ed)\b", lower) and len(explicit_allocation_groups) > 1:
            # Multiple allocation/subgroup counts in one sentence are not a
            # study-level total; arm counts are handled separately below.
            continue
        for pattern in count_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                return int(re.sub(r"[, ]", "", match.group(1))), sentence
    explicit_n = []
    excluded_n_context = ("subgroup", "sensitivity", "specificity", "agreement", "matching", "events", "cases with", "per arm")
    for sentence in sentences:
        if any(term in sentence.casefold() for term in excluded_n_context):
            continue
        if not re.search(r"\b(?:patients|participants|subjects|children|adults|individuals|people)\b", sentence, re.IGNORECASE):
            continue
        explicit_n.extend((int(m.group(1).replace(",", "")), sentence) for m in re.finditer(r"\b(?:N|n)\s*=\s*([\d,]+)\b", sentence))
    if len(explicit_n) == 1:
        return explicit_n[0]
    return None, ""


def _extract_explicit_arm_n(abstract: str, label: str) -> tuple[Optional[int], str]:
    if not label:
        return None, ""
    clean = re.sub(r"\([^)]*\)", " ", str(label)).strip()
    clean = re.sub(r"\bplasebo\b", "placebo", clean, flags=re.IGNORECASE)
    tokens = re.findall(r"[A-Za-z0-9]+", clean)
    if not tokens:
        return None, ""
    token = re.escape(tokens[0])
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract or "") if s.strip()]
    patterns = (
        rf"\b[\d,]+\s+of\s+([\d,]+)\s+(?:patients|participants|subjects)\b(?:(?!\b(?:group|arm)\b)[^;\n]){{0,80}}?\b(?:in\s+)?(?:the\s+)?{token}\s+(?:group|arm)\b",
        rf"\b([\d,]+)\s+(?:patients|participants|subjects)\b[^.;]{{0,180}}\b(?:assigned\s+to|in)\s+(?:the\s+)?{token}\s+(?:group|arm)\b",
        rf"\b([\d,]+)(?:\s*\([^)]*\))?\s*(?:patients|participants)?\s*(?:were\s+)?(?:randomly\s+)?(?:assigned\s+)?to\s+(?:the\s+)?{token}\s+(?:group|arm)\b",
        rf"\b{token}\s+(?:group|arm)\s*\(\s*n\s*=\s*([\d,]+)\s*\)",
    )
    for sentence in sentences:
        for index, pattern in enumerate(patterns):
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                group = match.group(1)
                return int(group.replace(",", "")), sentence
    return None, ""


def _extract_explicit_group_labels(abstract: str) -> tuple[List[str], str]:
    """Return two named arms only when a source sentence explicitly labels them."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract or "") if s.strip()]
    for sentence in sentences:
        if not re.search(r"\b(?:randomly\s+assigned|assigned|randomi[sz]ed)\b", sentence, re.IGNORECASE):
            continue
        parenthetical = [
            re.sub(r"\s+", " ", m.group(1)).strip()
            for m in re.finditer(r"\(([^()]{1,60}\b(?:group|arm))\)", sentence, re.IGNORECASE)
        ]
        labels = parenthetical if len(parenthetical) == 2 else [
            re.sub(r"\s+", " ", m.group(1)).strip()
            for m in re.finditer(r"\b(?:in|to)\s+(?:the\s+)?([A-Za-z0-9][A-Za-z0-9/-]*(?:\s+[A-Za-z0-9][A-Za-z0-9/-]*){0,3})\s+(?:group|arm)\b", sentence, re.IGNORECASE)
        ]
        if len(labels) == 2 and labels[0].casefold() != labels[1].casefold():
            return labels, sentence
    return [], ""


def _allocation_source_sentence(abstract: str, labels: List[str]) -> str:
    tokens = []
    for label in labels:
        found = re.findall(r"[A-Za-z0-9]+", str(label))
        if not found:
            return ""
        token = found[0]
        if token.casefold() == "plasebo":
            token = "placebo"
        tokens.append(token)
    cue = re.compile(r"\b(?:randomly\s+assigned|randomi[sz]ed|assigned|allocated|to\s+receive)\b", re.IGNORECASE)
    for sentence in [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract or "") if s.strip()]:
        if cue.search(sentence) and all(re.search(rf"\b{re.escape(token)}\b", sentence, re.IGNORECASE) for token in tokens):
            return sentence
    return ""


def _extract_direct_treatment_comparison(abstract: str) -> tuple[Optional[str], Optional[str], str]:
    action = r"(?:reduced|improved|increased|decreased|lowered|raised|prevented|prolonged|shortened|enhanced|worsened|was\s+associated\s+with|showed\s+no\s+difference|failed\s+to\s+show\s+(?:a\s+)?(?:any\s+)?(?:significant\s+)?(?:difference|benefit|improvement)|did\s+not\s+(?:significantly\s+)?(?:reduce|improve|increase|decrease|lower|raise))"
    for sentence in [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract or "") if s.strip()]:
        match = re.search(
            rf"\b([A-Za-z][A-Za-z0-9-]*(?:\s+(?!significantly\b)[A-Za-z][A-Za-z0-9-]*){{0,2}})\s+(?:significantly\s+)?{action}\b[^.;]{{0,140}}?\bcompared\s+(?:to|with)\s+(?:the\s+)?([^.,;(]+)",
            sentence,
            re.IGNORECASE,
        )
        if match:
            intervention = re.sub(r"\s+", " ", match.group(1)).strip()
            comparator = re.sub(r"\s+", " ", match.group(2)).strip(" .")
            if re.search(r"\b(?:have|has|had|was|were|is|are|patients|participants|subjects|group|groups)\b", intervention, re.IGNORECASE):
                continue
            if intervention and comparator:
                return intervention, comparator, sentence
    explicit_contrast = re.compile(
        rf"\b(?P<intervention>[A-Za-z][A-Za-z0-9/-]*(?:\s+[A-Za-z][A-Za-z0-9/-]*){{0,3}})"
        rf"\s+(?:versus|vs\.?)\s+(?P<comparator>placebos?|usual care|standard (?:care|treatment|therapy))"
        rf"\s+(?:was\s+|were\s+)?(?:significantly\s+)?{action}\b",
        re.IGNORECASE,
    )
    for sentence in [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract or "") if s.strip()]:
        match = explicit_contrast.search(sentence)
        if match:
            return match.group("intervention").strip(), match.group("comparator").strip(), sentence
    return None, None, ""


def _metric_type(metric: str) -> Optional[str]:
    text = metric.casefold()
    for pattern, kind in (
        (r"\b(?:hr|hazard\s*ratio|tehlike\s*oranı)\b", "HR"),
        (r"\b(?:rr|risk\s*ratio|relative\s*risk|risk\s*oranı)\b", "RR"),
        (r"\b(?:odds\s*ratio|odds\s*oranı)\b|\bOR\s*(?=(?:=|:)\s*-?\d|\s+-?\d)", "OR"),
        (r"\b(?:smd|standardi[sz]ed\s*mean\s*difference)\b", "SMD"),
        (r"\b(?:md|mean\s*difference)\b", "MD"),
        (r"\b(?:sensitivity|sensitivities|duyarlılık)\b", "sensitivity"),
        (r"\b(?:specificity|özgüllük)\b", "specificity"),
        (r"\b(?:auc|auroc|area\s+under\s+(?:the\s+)?curve)\b", "AUC"),
        (r"\b(?:stratified\s+)?win\s+ratio\b", "win_ratio"),
    ):
        if re.search(pattern, text, re.IGNORECASE):
            return kind
    return None


def _point_value(metric: str, kind: str) -> Optional[str]:
    if kind in {"HR", "RR", "OR", "MD", "SMD"}:
        label = {
            "HR": r"(?:HR|hazard\s*ratio|tehlike\s*oranı)", "RR": r"(?:RR|risk\s*ratio|relative\s*risk|risk\s*oranı)",
            "OR": r"(?:OR|odds\s*ratio|odds\s*oranı)", "MD": r"(?:MD|mean\s*difference)",
            "SMD": r"(?:SMD|standardi[sz]ed\s*mean\s*difference)",
        }[kind]
        match = re.search(rf"\b{label}\b\s*(?:=|:)?\s*(-?\d+(?:\.\d+)?)", metric, re.IGNORECASE)
    elif kind == "win_ratio":
        match = re.search(r"\b(?:stratified\s+)?win\s+ratio\b\s*(?:was|of|=|:)?\s*(\d+(?:\.\d+)?)", metric, re.IGNORECASE)
    else:
        label = {"sensitivity": r"(?:sensitivity|sensitivities|duyarlılık)", "specificity": r"(?:specificity|özgüllük)", "AUC": r"(?:AUC|AUROC|area\s+under\s+(?:the\s+)?curve)"}[kind]
        match = re.search(rf"\b{label}\b[^\d%]{{0,24}}(\d+(?:\.\d+)?%?)", metric, re.IGNORECASE)
    return match.group(1) if match else None


def _source_metric_label(metrics: List[str], kind: str, value: str) -> Optional[str]:
    labels = {
        "HR": r"HR|hazard\s*ratio|tehlike\s*oranı",
        "RR": r"RR|risk\s*ratio|relative\s*risk|risk\s*oranı",
        "OR": r"OR|odds\s*ratio|odds\s*oranı",
        "MD": r"MD|mean\s*difference",
        "SMD": r"SMD|standardi[sz]ed\s*mean\s*difference",
        "sensitivity": r"sensitivity|sensitivities|sens\.|duyarlılık",
        "specificity": r"specificity|spec\.|özgüllük",
        "AUC": r"AUC|AUROC|area\s+under\s+(?:the\s+)?curve",
        "win_ratio": r"(?:stratified\s+)?win\s+ratio",
    }
    label = labels.get(kind)
    if not label:
        return None
    for metric in metrics or []:
        if _metric_type(str(metric)) != kind or _point_value(str(metric), kind) != value:
            continue
        match = re.search(rf"\b(?:{label})\b\s*(?:=|:|was|of)?\s*{re.escape(value)}\s*%?", str(metric), re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return None


def _find_diagnostic_estimates(sentence: str) -> List[tuple[str, str]]:
    found: List[tuple[str, str]] = []
    patterns = (
        ("sensitivity", r"\b(?:sensitivity|sensitivities|sens\.)\b\s*(?:was|of|=|:)?\s*(\d+(?:\.\d+)?\s*%?)"),
        ("sensitivity", r"\b(\d+(?:\.\d+)?\s*%)\s+sensitivity\b"),
        ("specificity", r"\b(?:specificity|spec\.)\b\s*(?:was|of|=|:)?\s*(\d+(?:\.\d+)?\s*%?)"),
        ("specificity", r"\b(\d+(?:\.\d+)?\s*%)\s+specificity\b"),
        ("AUC", r"\b(?:AUC|AUROC|area under (?:the )?curve)\b\s*(?:was|of|=|:)?\s*(\d+(?:\.\d+)?)"),
    )
    for kind, pattern in patterns:
        for match in re.finditer(pattern, sentence or "", re.IGNORECASE):
            found.append((kind, match.group(1).replace(" ", "")))
    return found


def _paired_survival_proportions(sentence: str) -> List[Dict[str, Optional[str]]]:
    """Extract only explicitly paired OS/PFS percentages with their own labeled CIs."""
    pattern = re.compile(
        r"\b(?P<os>\d{1,2}-month\s+OS)\s+and\s+(?P<pfs>\d{1,2}-month\s+PFS)\s+at\s+"
        r"(?P<os_value>\d+(?:\.\d+)?\s*%)\s*\((?P<os_ci>[^()]*)\)\s+and\s+"
        r"(?P<pfs_value>\d+(?:\.\d+)?\s*%)\s*\((?P<pfs_ci>[^()]*)\)\s+respectively\b",
        re.IGNORECASE,
    )
    match = pattern.search(sentence or "")
    if not match:
        return []
    results: List[Dict[str, Optional[str]]] = []
    for label_key, value_key, ci_key, full_label in (
        ("os", "os_value", "os_ci", "overall survival"),
        ("pfs", "pfs_value", "pfs_ci", "progression-free survival"),
    ):
        low, high, confidence = _confidence_interval(match.group(ci_key))
        if low is None or high is None:
            continue
        month_match = re.match(r"(\d{1,2}-month)", match.group(label_key), re.IGNORECASE)
        month = month_match.group(1) if month_match else ""
        results.append({
            "label": f"{month} {full_label}".strip(),
            "value": re.sub(r"\s+", "", match.group(value_key)),
            "ci_lower": low,
            "ci_upper": high,
            "confidence_level": confidence,
        })
    return results


def _confidence_interval(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    match = re.search(
        r"(?:(\d{2,3})\s*%\s*(?:CI|confidence\s+interval)|(?:CI|confidence\s+interval))(?:\s*\[CI\])?\s*[:=,]?\s*[\[(]?\s*(-?\d+(?:\.\d+)?)\s*%?\s*(?:to|[-–—,])\s*(-?\d+(?:\.\d+)?)\s*%?",
        text or "", re.IGNORECASE,
    )
    if not match:
        return None, None, None
    return match.group(2), match.group(3), f"{match.group(1) or '95'}%"


def _ratio_interval_implausible(metric_type: str, estimate: Optional[str], low: Optional[str], high: Optional[str]) -> bool:
    """Flag source-reported HR/RR/OR intervals with nonpositive bounds or an outside point estimate."""
    if metric_type not in {"HR", "RR", "OR"} or estimate is None or low is None or high is None:
        return False
    def as_float(value: str) -> Optional[float]:
        try:
            return float(str(value).replace("−", "-").replace(",", "").replace("%", "").strip())
        except (TypeError, ValueError):
            return None
    point, lower, upper = as_float(estimate), as_float(low), as_float(high)
    if point is None or lower is None or upper is None:
        return False
    if lower <= 0 or upper <= 0:
        return True
    return point < min(lower, upper) - 1e-9 or point > max(lower, upper) + 1e-9


def _explicit_effect_mention_count(text: str) -> int:
    patterns = (
        r"\b(?:HR|hazard\s*ratio)\s*(?:=|:)?\s*-?\d+(?:\.\d+)?",
        r"\b(?:RR|risk\s*ratio|relative\s*risk)\s*(?:=|:)?\s*-?\d+(?:\.\d+)?",
        r"\b(?:OR|odds\s*ratio)\s*(?:=|:)?\s*-?\d+(?:\.\d+)?",
        r"\b(?:SMD|standardi[sz]ed\s*mean\s*difference)\s*(?:=|:)?\s*-?\d+(?:\.\d+)?",
        r"\b(?:MD|mean\s*difference)\s*(?:=|:)?\s*-?\d+(?:\.\d+)?",
        r"\b(?:sensitivity|specificity)\s*(?:was|of|=|:)?\s*\d+(?:\.\d+)?\s*%?",
        r"\b(?:AUC|AUROC)\s*(?:was|of|=|:)?\s*\d+(?:\.\d+)?",
        r"\b(?:stratified\s+)?win\s+ratio\s*(?:was|of|=|:)?\s*\d+(?:\.\d+)?",
    )
    return sum(len(re.findall(pattern, text or "", re.IGNORECASE)) for pattern in patterns)


def _p_value(text: str) -> Optional[str]:
    match = re.search(r"\bp\s*(?:=|<|>)\s*(?:0?\.\d+|\d+(?:\.\d+)?)", text or "", re.IGNORECASE)
    return re.sub(r"\s+", "", match.group(0)) if match else None


def _outcome_event_counts(sentence: str) -> tuple[Optional[int], Optional[int]]:
    # Only parse an explicit event-count construction; never reuse total sample n.
    match = re.search(r"\b([\d,]+)\s+events?\s+(?:occurred\s+)?(?:among|in)\s+([\d,]+)\s+(?:patients|participants|subjects|people)\b", sentence or "", re.IGNORECASE)
    if not match:
        return None, None
    return int(match.group(1).replace(",", "")), int(match.group(2).replace(",", ""))


def _extract_arm_event_counts(article: Dict[str, Any], sentence: str, arm_labels: List[str]) -> List[ArmEventCount]:
    """Read explicit outcome counts by named arm, preserving their denominators."""
    found: List[ArmEventCount] = []
    for label in arm_labels:
        if not label:
            continue
        clean = re.sub(r"\([^)]*\)", " ", str(label)).strip()
        clean = re.sub(r"\bplasebo\b", "placebo", clean, flags=re.IGNORECASE)
        tokens = re.findall(r"[A-Za-z0-9]+", clean)
        if not tokens:
            continue
        # The first distinctive term is sufficient for source matching and avoids
        # treating a dose as part of an arm label.
        token = re.escape(tokens[0])
        patterns = (
            rf"\b([\d,]+)\s+of\s+([\d,]+)\s+(?:patients|participants|subjects)\b(?:(?!\b(?:group|arm)\b)[^;\n]){{0,60}}?\b(?:in\s+)?(?:the\s+)?{token}\b",
            rf"\b([\d,]+)\s+events?\s+(?:occurred\s+)?(?:among|in)\s+([\d,]+)\s+(?:patients|participants|subjects|people)\b(?:(?!\b(?:group|arm)\b)[^;\n]){{0,60}}?\b(?:in\s+)?(?:the\s+)?{token}\b",
            rf"\b([\d,]+)\s+(?:with|in)\s+(?:the\s+)?{token}\b",
        )
        match = None
        for pattern in patterns:
            match = re.search(pattern, sentence or "", re.IGNORECASE)
            if match:
                break
        if not match:
            continue
        event_count = int(match.group(1).replace(",", ""))
        denominator = int(match.group(2).replace(",", "")) if match.lastindex and match.lastindex >= 2 else None
        source_label = next(
            (candidate for candidate in (clean, tokens[0]) if re.search(rf"\b{re.escape(candidate)}\b", sentence or "", re.IGNORECASE)),
            tokens[0],
        )
        found.append(ArmEventCount(
            arm_label=_fact(article, source_label, sentence),
            event_count=_fact(article, event_count, sentence),
            denominator=_fact(article, denominator, sentence if denominator is not None else ""),
        ))
    return found


def _concomitant_treatments(article: Dict[str, Any]) -> List[SourcedValue]:
    abstract = str(article.get("abstract") or "")
    results = []
    explicit = re.compile(r"\b(?:concomitant|co-?administered|adjunct(?:ive)?|added to (?:usual|standard) care|alongside (?:usual|standard) care)\b", re.IGNORECASE)
    for sentence in re.split(r"(?<=[.!?])\s+", abstract):
        if explicit.search(sentence):
            results.append(_fact(article, sentence.strip(), sentence.strip()))
    return results


def _relationship(article: Dict[str, Any], design_key: str) -> tuple[Dict[str, Any], str, str]:
    text = f"{article.get('title') or ''}. {article.get('abstract') or ''}"
    lower = text.casefold()
    if design_key in {"meta_analysis", "systematic_review", "systematic_review_and_meta_analysis"}:
        kind = "meta_analysis" if "meta_analysis" in design_key or "meta-analysis" in lower else "systematic_review"
    elif re.search(r"\b(subgroup analysis|subgroup analyses|alt grup analizi|subgrup analizi)\b", lower):
        kind = "subgroup_analysis"
    elif re.search(r"\b(secondary analysis|ancillary analysis|secondary outcome analysis|ikincil analiz)\b", lower):
        kind = "secondary_analysis"
    elif re.search(r"\b(extended follow[- ]?up|long[- ]term follow[- ]?up|extension study|uzatılmış takip|uzun dönem takip)\b", lower):
        kind = "extended_follow_up"
    else:
        kind = "primary_report"
    code = ""
    dashed_codes = re.finditer(r"\b([A-Z][A-Z0-9]{2,10}(?:-[A-Za-z0-9]{2,18})+)\b", text)
    for candidate in dashed_codes:
        neighborhood = text[max(0, candidate.start() - 40):candidate.end() + 40]
        if re.search(r"\b(trial|study|clinicaltrials?\.gov|NCT\d+)\b", neighborhood, re.IGNORECASE):
            code = candidate.group(1).strip()
            break
    if not code:
        named_trial = re.search(r"\b((?:[A-Z]{2,8}\s+){0,2}[A-Z]{2,8})\s+(?:trial|study)\b", text)
        code = named_trial.group(1).strip() if named_trial else ""
    pmid = str(article.get("pmid") or "")
    family_id = f"trial:{re.sub(r'[^a-z0-9]+', '-', code.casefold()).strip('-')}" if code else (f"pmid:{pmid}" if pmid else "")
    basis = "explicit_trial_name" if code else ("pmid_fallback_no_overlap_claim" if pmid else "unresolved")
    related_pmids = [str(x) for x in article.get("related_study_pmids", []) if str(x).isdigit()]
    return ({"kind": kind, "parent_study_id": None, "related_pmids": related_pmids, "overlap_status": "possible_same_trial" if code else "not_assessed"}, family_id, basis)


def _make_effect_estimates(article: Dict[str, Any], outcome_id: str, metrics: List[str], sentence: str) -> List[EffectEstimate]:
    parsed: List[tuple[str, str]] = []
    for metric in metrics or []:
        kind = _metric_type(str(metric))
        value = _point_value(str(metric), kind) if kind else None
        if kind and value is not None and (kind, value) not in parsed:
            parsed.append((kind, value))
    for kind, value in _find_diagnostic_estimates(sentence):
        if (kind, value) not in parsed:
            parsed.append((kind, value))

    ci_low, ci_high, confidence_level = _confidence_interval(" ".join([*(metrics or []), sentence]))
    p_value = _p_value(" ".join([*(metrics or []), sentence]))
    # A shared CI or p-value is attached only when exactly one point estimate is present.
    single_estimate_in_sentence = _explicit_effect_mention_count(sentence) == 1 if sentence else len(parsed) == 1
    shared_ci = (ci_low, ci_high, confidence_level) if len(parsed) == 1 and single_estimate_in_sentence else (None, None, None)
    shared_p = p_value if len(parsed) == 1 and single_estimate_in_sentence else None
    source = _source(article, sentence)
    return [
        EffectEstimate(
            outcome_id=outcome_id,
            metric_type=kind,
            value=value,
            ci_lower=shared_ci[0],
            ci_upper=shared_ci[1],
            confidence_level=shared_ci[2],
            p_value=shared_p,
            metric_label=_source_metric_label(metrics, kind, value),
            implausible_source_value=_ratio_interval_implausible(kind, value, shared_ci[0], shared_ci[1]),
            source=source,
        )
        for kind, value in parsed
    ]


def _grounded_effect(article: Dict[str, Any], outcome_id: str, item: Dict[str, Any]) -> Optional[EffectEstimate]:
    raw_effect = str(item.get("effect") or "").strip()
    sentence = str(item.get("sentence") or "").strip()
    if not raw_effect or not sentence:
        return None
    kind = _metric_type(raw_effect)
    value = _point_value(raw_effect, kind) if kind else None
    reported_label = None
    if kind is None:
        number = re.search(r"[-−]?\d+(?:\.\d+)?\s*%?", raw_effect)
        if not number:
            return None
        kind = "not_named_in_source"
        value = number.group(0).replace("−", "-").replace(" ", "")
        reported_label = raw_effect

    raw_ci = str(item.get("ci") or "")
    ci_low, ci_high, confidence_level = _confidence_interval(raw_ci)
    if ci_low is None:
        ci_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:to|ile|[-–—])\s*(-?\d+(?:\.\d+)?)", raw_ci, re.IGNORECASE)
        if ci_match:
            ci_low, ci_high = ci_match.group(1), ci_match.group(2)
    p_value = str(item.get("p") or "").strip() or None
    if p_value:
        p_match = re.search(r"p\s*(?:=|<|>)\s*(?:0?\.\d+|\d+(?:\.\d+)?)", p_value, re.IGNORECASE)
        p_value = re.sub(r"\s+", "", p_match.group(0)) if p_match else p_value

    arm_label = None
    value_match = re.search(re.escape(value), sentence, re.IGNORECASE)
    if value_match:
        tail = sentence[value_match.end():value_match.end() + 100]
        arm_match = re.search(r"\bwith\s+([A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z][A-Za-z0-9-]*){0,2})", tail, re.IGNORECASE)
        if arm_match:
            arm_label = re.sub(r"\s+(?:and|or)$", "", arm_match.group(1), flags=re.IGNORECASE)
    subgroup = None
    if value_match:
        tail = sentence[value_match.end():value_match.end() + 180]
        subgroup_match = re.search(r"\bin\s+the\s+([A-Za-z0-9-]+(?:\s+[A-Za-z0-9-]+){0,3})\s+population\b", tail, re.IGNORECASE)
        if subgroup_match:
            subgroup = subgroup_match.group(1)

    return EffectEstimate(
        outcome_id=outcome_id,
        metric_type=kind,
        value=value,
        ci_lower=ci_low,
        ci_upper=ci_high,
        confidence_level=confidence_level,
        p_value=p_value,
        arm_label=arm_label,
        population_subgroup=subgroup,
        metric_label=raw_effect,
        reported_label=reported_label,
        implausible_source_value=bool(item.get("implausible")) or _ratio_interval_implausible(kind, value, ci_low, ci_high),
        source=_source(article, sentence),
    )


def build_study_model(
    article: Dict[str, Any],
    query: str = "",
    clinical_details: Optional[Dict[str, Any]] = None,
    study_design: Optional[Dict[str, Any]] = None,
    risk_of_bias: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the canonical study object from a PubMed article and existing extractors."""
    article = dict(article or {})
    from report_generator import _allocation_arms, _canonical_patient_group, _sourced_population_characteristics, assess_risk_of_bias, classify_study_design, extract_article_clinical_details, extract_clinical_profile, extract_grounded_clinical_findings, extract_methodological_limitations, extract_study_metrics

    details = clinical_details or article.get("clinical_details") or extract_article_clinical_details(article, query)
    design = study_design or article.get("study_design_info") or classify_study_design(
        article.get("publication_types") or [], article.get("title") or "", article.get("abstract") or ""
    )
    rob = risk_of_bias or article.get("risk_of_bias") or assess_risk_of_bias(article)
    provenance = details.get("provenance") or {}
    pmid = str(article.get("pmid") or "")
    doi = str(article.get("doi") or "")
    title = str(article.get("title") or "")
    source = _source(article, title, "pubmed_metadata")

    abstract = str(article.get("abstract") or "")
    sample_value, sample_sentence = _extract_total_participants(
        abstract, str(design.get("design_key") or "")
    )
    profile_items = extract_clinical_profile(abstract)
    pop_value, pop_sentence = _canonical_patient_group(
        abstract,
        profile_items,
        extract_study_metrics(abstract),
    )
    if str(pop_value or "").strip().casefold() in {"özette bildirilmedi", "not reported", "unknown"}:
        pop_value, pop_sentence = "", ""
    population_characteristics = _sourced_population_characteristics(
        abstract, title, profile_items, pop_value, pop_sentence
    )
    population = Population(
        description=_fact(article, pop_value, pop_sentence, "canonical_patient_group"),
        total_participants=_fact(article, sample_value, sample_sentence),
        characteristics=[
            _fact(article, item["value"], item["source_sentence"], item["source_field"])
            for item in population_characteristics
        ],
    )

    intervention_info = provenance.get("intervention") or {}
    comparator_info = provenance.get("comparison") or {}
    intervention_value = _clean_text(intervention_info.get("value") or details.get("intervention"))
    comparator_value = _clean_text(comparator_info.get("value") or details.get("comparison"))
    explicit_group_labels, group_source_sentence = _extract_explicit_group_labels(abstract)
    allocated_intervention, allocated_comparator = _allocation_arms(abstract)
    allocation_source_sentence = _allocation_source_sentence(abstract, [allocated_intervention, allocated_comparator]) if allocated_intervention and allocated_comparator else ""
    direct_intervention, direct_comparator, direct_source_sentence = _extract_direct_treatment_comparison(abstract)
    intervention_source_sentence = intervention_info.get("source_sentence", "")
    comparator_source_sentence = comparator_info.get("source_sentence", "")
    exposure_value = ""
    exposure_source_sentence = ""
    if len(explicit_group_labels) == 2:
        intervention_value, comparator_value = explicit_group_labels
        intervention_source_sentence = comparator_source_sentence = group_source_sentence
    elif allocated_intervention and allocated_comparator and allocation_source_sentence:
        intervention_value, comparator_value = allocated_intervention, allocated_comparator
        intervention_source_sentence = comparator_source_sentence = allocation_source_sentence
    elif direct_intervention and direct_comparator:
        intervention_value, comparator_value = direct_intervention, direct_comparator
        intervention_source_sentence = comparator_source_sentence = direct_source_sentence
    elif str(design.get("design_key") or "") in {"cohort", "case_control", "cross_sectional", "retrospective_comparative", "observational_unspecified"}:
        # An observational exposure is not a treatment arm. Keep it missing unless
        # the comparison sentence explicitly provides a treatment contrast.
        candidate_sentence = str(intervention_source_sentence or "").strip()
        if not _is_not_reported(intervention_value) and candidate_sentence and candidate_sentence in abstract:
            exposure_value = intervention_value
            exposure_source_sentence = candidate_sentence
        intervention_value = comparator_value = ""
        intervention_source_sentence = comparator_source_sentence = ""
    if _is_not_reported(intervention_value):
        intervention_value = ""
    if _is_not_reported(comparator_value):
        comparator_value = ""
    concomitant = _concomitant_treatments(article)
    intervention = Intervention(
        name=_fact(article, intervention_value, intervention_source_sentence, intervention_info.get("source") or "abstract"),
        concomitant_treatments=concomitant,
    ) if intervention_value else None
    comparator = Comparator(
        name=_fact(article, comparator_value, comparator_source_sentence, comparator_info.get("source") or "abstract"),
        concomitant_treatments=concomitant,
    ) if comparator_value else None
    exposure = _fact(article, exposure_value, exposure_source_sentence, "abstract") if exposure_value and exposure_source_sentence else None

    arms: List[StudyArm] = []
    if intervention:
        arm_source = intervention.name.source
        arms.append(StudyArm(role="intervention", label=str(intervention_value), intervention=intervention, source=arm_source))
    if comparator:
        arm_source = comparator.name.source
        arms.append(StudyArm(role="comparator", label=str(comparator_value), comparator=comparator, source=arm_source))
    # Arm sample sizes remain missing unless a source explicitly supplies per-arm n.
    for arm in arms:
        arm_n, arm_sentence = _extract_explicit_arm_n(str(article.get("abstract") or ""), arm.label)
        arm.participants_n = _fact(article, arm_n, arm_sentence)
        if arm_sentence:
            arm.source = _source(article, arm_sentence)

    raw_outcome_items = list(details.get("outcome_metrics") or [])
    outcome_items = []
    grounded_findings = extract_grounded_clinical_findings(str(article.get("abstract") or ""))
    grounded_sentence_keys = {
        re.sub(r"\W+", " ", str(item.get("sentence") or "").casefold()).strip()
        for item in grounded_findings if item.get("sentence")
    }
    for item in raw_outcome_items:
        sentence = str(item.get("source_sentence") or item.get("sentence") or "")
        sentence_key = re.sub(r"\W+", " ", sentence.casefold()).strip()
        if any(
            sentence_key == key or (len(sentence_key) >= 40 and len(key) >= 40 and (sentence_key in key or key in sentence_key))
            for key in grounded_sentence_keys
        ):
            continue
        explicit_effects = _make_effect_estimates(article, "candidate", list(item.get("metrics") or []), sentence)
        event_count, _ = _outcome_event_counts(sentence)
        if explicit_effects or event_count is not None:
            outcome_items.append(item)
    # The legacy extractor does not yet recognize diagnostic metrics. Add only
    # explicit named estimates from a source sentence and bind them to that sentence.
    for sentence in re.split(r"(?<=[.!?])\s+", str(article.get("abstract") or "")):
        diagnostic = _find_diagnostic_estimates(sentence)
        known = {
            kind
            for item in outcome_items
            for metric in (item.get("metrics") or [])
            if (kind := _metric_type(str(metric)))
        }
        missing = [(kind, value) for kind, value in diagnostic if kind not in known]
        if missing:
            outcome_items.extend(
                {
                    "outcome": kind,
                    "metrics": [f"{kind} {value}"],
                    "sentence": sentence.strip(),
                    "source_sentence": sentence.strip(),
                }
                for kind, value in missing
            )

    # Preserve an explicitly reported event count as its own outcome record;
    # do not repurpose it as study or arm sample size.
    for sentence in re.split(r"(?<=[.!?])\s+", str(article.get("abstract") or "")):
        event_count, denominator = _outcome_event_counts(sentence)
        arm_counts = _extract_arm_event_counts(
            article, sentence, [x for x in (intervention_value, comparator_value) if x]
        )
        if (event_count is not None or arm_counts) and not any(
            (item.get("source_sentence") or item.get("sentence") or "").strip() == sentence.strip()
            for item in outcome_items
        ):
            outcome_items.append({
                "outcome": "Reported event count",
                "metrics": [],
                "sentence": sentence.strip(),
                "source_sentence": sentence.strip(),
            })

    outcomes: List[Outcome] = []
    for index, item in enumerate(outcome_items, 1):
        sentence = str(item.get("source_sentence") or item.get("sentence") or "")
        name = _clean_text(item.get("outcome"))
        outcome_id = f"{pmid or 'study'}:outcome:{index}"
        event_count, denominator = _outcome_event_counts(sentence)
        outcomes.append(Outcome(
            id=outcome_id,
            name=_fact(article, name, sentence),
            event_count=_fact(article, event_count, sentence if event_count is not None else ""),
            denominator=_fact(article, denominator, sentence if denominator is not None else ""),
            arm_event_counts=_extract_arm_event_counts(
                article,
                sentence,
                [x for x in (intervention_value, comparator_value) if x],
            ),
            effect_estimates=_make_effect_estimates(article, outcome_id, list(item.get("metrics") or []), sentence),
            source=_source(article, sentence),
        ))

    # Preserve the clearly labeled OS/PFS percentage pair without assigning one
    # endpoint's confidence interval to the other. The metric is left explicitly
    # unnamed because the result sentence uses the endpoint labels, not the word
    # "proportion" itself.
    for sentence in re.split(r"(?<=[.!?])\s+", abstract):
        for estimate in _paired_survival_proportions(sentence):
            outcome_id = f"{pmid or 'study'}:outcome:{len(outcomes) + 1}"
            outcomes.append(Outcome(
                id=outcome_id,
                name=_fact(article, estimate["label"], sentence),
                effect_estimates=[EffectEstimate(
                    outcome_id=outcome_id,
                    metric_type="not_named_in_source",
                    value=estimate["value"],
                    ci_lower=estimate["ci_lower"],
                    ci_upper=estimate["ci_upper"],
                    confidence_level=estimate["confidence_level"],
                    reported_label=estimate["label"],
                    source=_source(article, sentence),
                )],
                source=_source(article, sentence),
            ))

    # Add the existing sentence-bound finding extractor's point estimates to
    # the canonical outcome objects. It supplies per-effect CI/p bindings for
    # abstracts where the legacy metric splitter sees only fragments.
    for finding in grounded_findings:
        sentence = str(finding.get("sentence") or "").strip()
        outcome_name = _clean_text(finding.get("outcome")) or "Özette adlandırılmadı"
        estimate = _grounded_effect(article, f"{pmid or 'study'}:outcome:grounded", finding)
        if estimate is None:
            continue
        normalized_sentence = re.sub(r"\W+", " ", sentence.casefold()).strip()
        normalized_name = re.sub(r"\W+", " ", outcome_name.casefold()).strip()
        candidate = next((
            existing for existing in outcomes
            if (lambda old: old and (old in normalized_sentence or normalized_sentence in old))(
                re.sub(r"\W+", " ", str((existing.source or EvidenceSource()).source_sentence or "").casefold()).strip()
            )
            and (
                normalized_name in {"özette adlandırılmadı", "reported event count"}
                or re.sub(r"\W+", " ", str((existing.name or SourcedValue()).value or "").casefold()).strip() == normalized_name
                or "adlandırılmadı" in str((existing.name or SourcedValue()).value or "").casefold()
            )
        ), None)
        if candidate is None:
            new_id = f"{pmid or 'study'}:outcome:{len(outcomes) + 1}"
            estimate.outcome_id = new_id
            candidate = Outcome(
                id=new_id,
                name=_fact(article, outcome_name, sentence),
                source=_source(article, sentence),
            )
            outcomes.append(candidate)
        else:
            candidate.name = _fact(article, outcome_name, sentence)
            candidate.source = _source(article, sentence)
        estimate.outcome_id = candidate.id
        duplicate = next((e for e in candidate.effect_estimates if e.metric_type == estimate.metric_type and e.value == estimate.value), None)
        if duplicate:
            duplicate.ci_lower = estimate.ci_lower or duplicate.ci_lower
            duplicate.ci_upper = estimate.ci_upper or duplicate.ci_upper
            duplicate.confidence_level = estimate.confidence_level or duplicate.confidence_level
            duplicate.p_value = estimate.p_value or duplicate.p_value
            duplicate.metric_label = estimate.metric_label or duplicate.metric_label
            duplicate.implausible_source_value = estimate.implausible_source_value or duplicate.implausible_source_value
            duplicate.arm_label = estimate.arm_label or duplicate.arm_label
            duplicate.population_subgroup = estimate.population_subgroup or duplicate.population_subgroup
            duplicate.reported_label = estimate.reported_label or duplicate.reported_label
            duplicate.source = estimate.source
        else:
            candidate.effect_estimates.append(estimate)

    clinical_findings = [
        _fact(article, item.get("line"), item.get("sentence", ""))
        for item in profile_items
        if item.get("category") != "sample" and item.get("line") and item.get("sentence")
    ]
    methodological_limitations = [
        _fact(article, item.get("label"), item.get("source_sentence", ""), f"{item.get('kind') or 'limitation'}_limitation")
        for item in extract_methodological_limitations(article)
        if item.get("label") and item.get("source_sentence")
    ]

    rob_source_sentence = str(article.get("abstract") or "")[:0]
    risk = RiskOfBiasAssessment(
        tool=str(rob.get("tool") or ""),
        status="assessed" if rob.get("risk_assigned") else "not_assessed",
        assessed=bool(rob.get("risk_assigned")),
        overall_rating=str(rob.get("overall_rating") or "Değerlendirilmedi (Not Assessed)"),
        domains=dict(rob.get("domains") or {}),
        source=_source(article, rob_source_sentence, "methodological_assessment"),
    )
    relationship, family_id, family_basis = _relationship(article, str(design.get("design_key") or ""))
    if str(design.get("design_key") or "") == "rct":
        causal_status = "randomized_design_reported; independent_causal_assessment_not_performed"
    elif str(design.get("design_key") or "") in {"cohort", "case_control", "cross_sectional", "retrospective_comparative", "observational_unspecified"}:
        causal_status = "association_only; no_causal_superiority_claim"
    elif relationship.get("kind") in {"meta_analysis", "systematic_review"}:
        causal_status = "review_of_prior_studies; not_a_new_primary_cohort"
    else:
        causal_status = "descriptive_or_unclear; no_causal_superiority_claim"
    study = Study(
        model_version=MODEL_VERSION,
        study_id=f"pmid:{pmid}" if pmid else (f"doi:{doi}" if doi else "unidentified-study"),
        pmid=pmid,
        doi=doi,
        title=title,
        publication_year=str(article.get("pub_year") or ""),
        design_key=str(design.get("design_key") or "unclassified"),
        design_label=str(design.get("design") or "Çalışma tasarımı belirlenemedi"),
        research_question=select_research_question_framework(query, str(design.get("design_key") or "")),
        population=population,
        intervention=intervention,
        comparator=comparator,
        exposure=exposure,
        arms=arms,
        outcomes=outcomes,
        clinical_findings=clinical_findings,
        risk_of_bias=risk,
        source=source,
        relationship=relationship,
        evidence_family_id=family_id,
        evidence_family_basis=family_basis,
        causal_interpretation_status=causal_status,
        methodological_limitations=methodological_limitations,
        compatibility_view=details,
    )
    result = study.to_dict()
    result["extraction_validation"] = validate_study_model(result)
    return result


def ensure_study_model(article: Dict[str, Any], query: str = "") -> Dict[str, Any]:
    existing = article.get("evidence_model")
    if isinstance(existing, dict) and existing.get("model_version"):
        return existing
    return build_study_model(article, query=query)


def legacy_details_from_study(study: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility adapter for callers that still consume the pre-model detail dictionary."""
    compatibility_view = study.get("compatibility_view") or {}
    if not isinstance(compatibility_view, dict):
        compatibility_view = {}

    def value_at(path: Dict[str, Any]) -> Any:
        return path.get("value") if isinstance(path, dict) else None

    def source_at(path: Dict[str, Any]) -> Dict[str, Any]:
        source = (path or {}).get("source") or {}
        return {"value": value_at(path), "source_sentence": source.get("source_sentence", ""), "pmid": source.get("pmid", ""), "source": source.get("source_field", "missing"), "verification_status": source.get("verification_status", "not_verified")}

    population = study.get("population") or {}
    description = population.get("description") or {}
    total = population.get("total_participants") or {}
    intervention = study.get("intervention") or {}
    comparator = study.get("comparator") or {}
    exposure = study.get("exposure") or {}
    outcomes = []
    provenance_outcomes = []
    excluded_inconsistent_effects = 0
    for outcome in study.get("outcomes") or []:
        source = outcome.get("source") or {}
        metrics = []
        synthesis_metrics = []
        for effect in outcome.get("effect_estimates") or []:
            metric = effect.get("reported_label") or effect.get("metric_label") or (f"{effect.get('metric_type')} {effect.get('value')}" if effect.get("value") is not None else effect.get("metric_type", ""))
            if effect.get("ci_lower") is not None and effect.get("ci_upper") is not None:
                metric += f", {effect.get('confidence_level') or '95%'} CI {effect['ci_lower']}-{effect['ci_upper']}"
            if effect.get("p_value"):
                metric += f", {effect['p_value']}"
            metrics.append(metric)
            if effect.get("implausible_source_value"):
                excluded_inconsistent_effects += 1
            else:
                synthesis_metrics.append(metric)
        for arm_count in outcome.get("arm_event_counts") or []:
            arm_label = value_at(arm_count.get("arm_label")) or "kol"
            event_count = value_at(arm_count.get("event_count"))
            denominator = value_at(arm_count.get("denominator"))
            if event_count is not None:
                event_metric = f"{arm_label}: olay {event_count}" + (f"/{denominator}" if denominator is not None else "")
                metrics.append(event_metric)
                synthesis_metrics.append(event_metric)
        if not metrics and value_at(outcome.get("event_count")) is not None:
            count = value_at(outcome.get("event_count"))
            denominator = value_at(outcome.get("denominator"))
            event_metric = f"olay {count}" + (f"/{denominator}" if denominator is not None else "")
            metrics.append(event_metric)
            synthesis_metrics.append(event_metric)
        row = {"outcome": value_at(outcome.get("name")) or "değerlendirilemedi", "metrics": metrics, "synthesis_metrics": synthesis_metrics, "sentence": source.get("source_sentence", ""), "source_sentence": source.get("source_sentence", ""), "pmid": source.get("pmid", study.get("pmid", "")), "implausible": any(bool(effect.get("implausible_source_value")) for effect in outcome.get("effect_estimates") or [])}
        outcomes.append(row)
        provenance_outcomes.append(row)
    design_label = study.get("design_label") or "Çalışma tasarımı belirlenemedi"
    evidence_level = "Değerlendirilemedi"
    intervention_name = intervention.get("name") if isinstance(intervention, dict) else None
    comparator_name = comparator.get("name") if isinstance(comparator, dict) else None
    intervention_fact = source_at(intervention_name or {}) if intervention_name else {"value": "değerlendirilemedi", "source_sentence": "", "pmid": "", "source": "missing"}
    comparator_fact = source_at(comparator_name or {}) if comparator_name else {"value": "değerlendirilemedi", "source_sentence": "", "pmid": "", "source": "missing"}
    exposure_fact = source_at(exposure) if exposure else {"value": "değerlendirilemedi", "source_sentence": "", "pmid": "", "source": "missing"}
    sample_n = value_at(total)
    sample_size = f"n = {sample_n}" if sample_n is not None else "özette bildirilmedi"
    population_parts = []
    base_population = value_at(description)
    if base_population and not _is_not_reported(base_population):
        population_parts.append(str(base_population))
    population_characteristics = [
        source_at(item) for item in population.get("characteristics") or []
        if value_at(item) and (item.get("source") or {}).get("source_sentence")
    ]
    for item in population_characteristics:
        value = str(item["value"])
        if value.casefold() not in {part.casefold() for part in population_parts}:
            population_parts.append(value)
    patient_group = "; ".join(population_parts) if population_parts else "Belirtilmedi"
    finding_lines = [str(x.get("value")) for x in study.get("clinical_findings") or [] if x.get("value")]
    synthesis_rows = [o for o in outcomes if o.get("synthesis_metrics")]
    synthesis_outcomes = "; ".join(f"{o['outcome']}: {', '.join(o['synthesis_metrics'])}" for o in synthesis_rows)
    if not synthesis_outcomes:
        synthesis_outcomes = "Özette senteze uygun nicel etki ölçütü bildirilmedi"
    if excluded_inconsistent_effects:
        synthesis_outcomes += f" (Kaynakla matematiksel olarak tutarsız {excluded_inconsistent_effects} etki ölçütü sentez dışında bırakıldı.)"
    canonical_details = {
        "patient_group": patient_group,
        "sample_size": sample_size,
        "study_design": design_label,
        "evidence_level": evidence_level,
        "evidence_level_note": "Kanıt düzeyi çalışma tasarımından üretilmez; GRADE değerlendirmesi yapılmadı.",
        "design_key": study.get("design_key", "unclassified"),
        "intervention": value_at(intervention_name or {}) or "Belirtilmedi",
        "comparison": value_at(comparator_name or {}) or "Belirtilmedi",
        "exposure": value_at(exposure) or "Belirtilmedi",
        "outcome_metrics": outcomes,
        "outcomes_summary": synthesis_outcomes,
        "synthesis_outcomes": synthesis_outcomes,
        "real_findings": "; ".join(finding_lines) if finding_lines else "Özette kaynaklı nitel klinik bulgu bildirilmedi.",
        "provenance": {
            "pmid": study.get("pmid", ""),
            "population": source_at(description),
            "population_characteristics": population_characteristics,
            "sample_size": source_at(total),
            "intervention": intervention_fact,
            "comparison": comparator_fact,
            "exposure": exposure_fact,
            "outcomes": provenance_outcomes,
        },
        "pmid": study.get("pmid", ""),
    }
    return {**compatibility_view, **canonical_details}


def validate_study_model(study: Dict[str, Any]) -> Dict[str, Any]:
    """Structural/source-sentence checks; does not assess clinical truth or GRADE."""
    errors: List[str] = []
    pmid = str(study.get("pmid") or "")
    if not pmid.isdigit():
        errors.append("missing_or_invalid_pmid")
    missing_provenance = []
    candidates = []
    pop = study.get("population") or {}
    candidates.extend([("population", pop.get("description")), ("total_participants", pop.get("total_participants"))])
    candidates.extend((f"population_characteristic:{index}", item) for index, item in enumerate(pop.get("characteristics") or []))
    for key in ("intervention", "comparator"):
        obj = study.get(key)
        if obj:
            candidates.append((key, obj.get("name")))
            candidates.extend((f"{key}:concomitant", x) for x in obj.get("concomitant_treatments") or [])
    if study.get("exposure"):
        candidates.append(("exposure", study.get("exposure")))
    for arm in study.get("arms") or []:
        candidates.extend([
            (f"arm:{arm.get('role')}:participants_n", arm.get("participants_n")),
            (f"arm:{arm.get('role')}:events_n", arm.get("events_n")),
        ])
    for outcome in study.get("outcomes") or []:
        candidates.extend([
            (f"outcome:{outcome.get('id')}", outcome.get("name")),
            (f"outcome:{outcome.get('id')}:timepoint", outcome.get("timepoint")),
            (f"outcome:{outcome.get('id')}:event_count", outcome.get("event_count")),
            (f"outcome:{outcome.get('id')}:denominator", outcome.get("denominator")),
        ])
        for arm_count in outcome.get("arm_event_counts") or []:
            candidates.extend([
                (f"outcome:{outcome.get('id')}:arm_label", arm_count.get("arm_label")),
                (f"outcome:{outcome.get('id')}:arm_event_count", arm_count.get("event_count")),
                (f"outcome:{outcome.get('id')}:arm_denominator", arm_count.get("denominator")),
            ])
        for effect in outcome.get("effect_estimates") or []:
            candidates.append((f"effect:{outcome.get('id')}:{effect.get('metric_type')}", {"value": effect.get("value"), "source": effect.get("source")}))
    candidates.extend((f"clinical_finding:{index}", fact) for index, fact in enumerate(study.get("clinical_findings") or []))
    candidates.extend((f"methodological_limitation:{index}", fact) for index, fact in enumerate(study.get("methodological_limitations") or []))
    for label, fact in candidates:
        if not isinstance(fact, dict) or _is_not_reported(fact.get("value")):
            continue
        source = fact.get("source") or {}
        if not source.get("pmid") or not source.get("source_sentence"):
            missing_provenance.append(label)
    if missing_provenance:
        errors.append("missing_source_sentence:" + ",".join(missing_provenance))
    source_warnings = [
        f"implausible_ratio_interval:{outcome.get('id')}:{effect.get('metric_type')}"
        for outcome in study.get("outcomes") or []
        for effect in outcome.get("effect_estimates") or []
        if effect.get("implausible_source_value")
    ]
    return {
        "valid": not errors,
        "status": "structurally_valid" if not errors else "needs_source_review",
        "errors": errors,
        "warnings": source_warnings,
        "source_provenance_complete": not missing_provenance,
        "missing_provenance_fields": missing_provenance,
        "record_verification_status": (study.get("source") or {}).get("verification_status", "not_verified"),
        "clinical_claim_validation": CLAIM_REVIEW_STATUS,
        "formal_grade_status": "not_assessed",
    }

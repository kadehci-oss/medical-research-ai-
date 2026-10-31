"""Statistical direction of one reported outcome (fix for finding B1).

Replaces the substring-based logic of ``_determine_statistical_direction``.

What changed and why
--------------------
* p-values are parsed as numbers (operator + value) and compared with alpha.
  The old code looked for the text ``= 0.0`` inside the string, so ``p = 0.08``
  counted as significant.
* Direction comes from the effect estimate (HR/OR/RR against 1, MD against 0)
  and from the *polarity of the outcome* (is a lower value good or bad?).
  The old code checked "increase" before "increased risk", so a harmful
  increase was labelled positive.
* The label no longer means "significant". It is one of:
  ``benefit``, ``harm``, ``neutral`` (no significant difference),
  ``significant_unclear`` (significant, but the direction cannot be read
  safely) or ``uncertain`` (significance itself is unknown or contradictory).
  The code never guesses a direction. When the effect estimate and the verb
  disagree (for example "reduced symptoms (OR 2.15)", where the ratio is
  probably the odds of response) the result is ``significant_unclear``.

Assumptions (keep them in mind when reading results)
----------------------------------------------------
* A ratio (HR/OR/RR) is read as "intervention vs comparator". An abstract
  that reports the reverse ratio will be read the wrong way. This cannot be
  detected from the abstract alone.
* ``p = 0.05`` is NOT significant (p < alpha is required). ``p <= 0.05`` is
  treated as significant, as most journals do.
* Polarity comes from a small keyword lexicon (English + a few Turkish
  terms). Unknown outcomes give ``uncertain``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

ALPHA = 0.05

LABEL_BENEFIT = "benefit"
LABEL_HARM = "harm"
LABEL_NEUTRAL = "neutral"
LABEL_UNCERTAIN = "uncertain"
LABEL_SIG_UNCLEAR = "significant_unclear"

HAZARD_KINDS = {"HR"}

_NUM = r"[-\u2212]?\d*\.?\d+"
_PNUM = r"\d*\.?\d+(?:[eE][-\u2212+]?\d+)?"


def _to_float(raw: str) -> float:
    return float(raw.replace("\u2212", "-"))


# --------------------------------------------------------------------------
# p-values
# --------------------------------------------------------------------------

_P_RE = re.compile(
    r"(?<![A-Za-z])[pP]\s*(?:-?\s*value)?\s*(<=|\u2264|<|>=|\u2265|>|=)\s*(" + _PNUM + r")"
)


def parse_p_values(text: str) -> List[Tuple[str, float]]:
    """Return every (operator, value) pair such as ('<', 0.001)."""
    found: List[Tuple[str, float]] = []
    for match in _P_RE.finditer(text or ""):
        try:
            found.append((match.group(1), _to_float(match.group(2))))
        except ValueError:
            continue
    return found


def classify_p(op: str, value: float, alpha: float = ALPHA) -> Optional[bool]:
    """True = significant, False = not significant, None = cannot tell.

    ``p < 0.1`` says nothing about alpha 0.05, so it returns None.
    """
    if op in ("<", "<=", "\u2264"):
        return True if value <= alpha else None
    if op == "=":
        return value < alpha
    if op in (">", ">=", "\u2265"):
        return False if value >= alpha else None
    return None


def p_significance(
    p_values: Iterable[Tuple[str, float]], alpha: float = ALPHA
) -> Tuple[Optional[bool], bool]:
    """Combine several p-values. Returns (significant, mixed).

    ``mixed`` is True when some p-values say significant and others do not.
    The caller must then call the result uncertain.
    """
    verdicts = [classify_p(op, val, alpha) for op, val in p_values]
    verdicts = [v for v in verdicts if v is not None]
    if not verdicts:
        return None, False
    if all(verdicts):
        return True, False
    if not any(verdicts):
        return False, False
    return None, True


# --------------------------------------------------------------------------
# effect estimates and confidence intervals
# --------------------------------------------------------------------------

_CI_RE = re.compile(
    r"(?:95\s*%?\s*(?:CI|C\.I\.|confidence\s+interval)|\bCI)\s*[:=,]?\s*[\(\[]?\s*"
    r"(" + _NUM + r")\s*(?:to|,|;|\u2013|\u2014|-|\u2212)\s*(" + _NUM + r")",
    re.IGNORECASE,
)

_BARE_PAIR_RE = re.compile(
    r"^\s*(?:95\s*%?\s*)?[\(\[]?\s*(" + _NUM + r")\s*(?:to|,|;|\u2013|\u2014|-|\u2212)\s*("
    + _NUM + r")\s*[\)\]]?\s*$",
    re.IGNORECASE,
)


def parse_ci(text: str) -> Optional[Tuple[float, float]]:
    """First labelled confidence interval in ``text`` as (low, high)."""
    match = _CI_RE.search(text or "")
    if not match:
        return None
    low, high = _to_float(match.group(1)), _to_float(match.group(2))
    return (low, high) if low <= high else (high, low)


def parse_ci_strings(strings: Iterable[str]) -> Optional[Tuple[float, float]]:
    """CI from strings the caller already knows are intervals.

    Accepts labelled ('95% CI 0.62-1.15') and bare ('0.62-1.15') forms.
    """
    for raw in strings or []:
        if not isinstance(raw, str):
            continue
        labelled = parse_ci(raw)
        if labelled:
            return labelled
        bare = _BARE_PAIR_RE.match(raw)
        if bare:
            low, high = _to_float(bare.group(1)), _to_float(bare.group(2))
            return (low, high) if low <= high else (high, low)
    return None


_RATIO_RE = re.compile(
    r"(?:\b(?P<abbr>(?-i:aHR|HR|aOR|OR|aRR|RR|IRR|RRR))"
    r"|\b(?P<long>hazard\s+ratio|odds\s+ratio|relative\s+risk|risk\s+ratio|rate\s+ratio))"
    r"\s*(?:\([^)]{0,20}\))?\s*(?:of|was)?\s*[:=,]?\s*(?P<v>\d*\.?\d+)",
    re.IGNORECASE,
)

_LONG_KIND = {
    "hazard ratio": "HR",
    "odds ratio": "OR",
    "relative risk": "RR",
    "risk ratio": "RR",
    "rate ratio": "IRR",
}


def parse_ratio(text: str) -> Optional[Tuple[str, float]]:
    """First ratio estimate as (kind, value), kind in HR/OR/RR/IRR/RRR."""
    match = _RATIO_RE.search(text or "")
    if not match:
        return None
    if match.group("abbr"):
        kind = match.group("abbr").upper()
        if kind.startswith("A") and kind != "A":
            kind = kind[1:]
    else:
        kind = _LONG_KIND.get(re.sub(r"\s+", " ", match.group("long").lower()), "RR")
    try:
        return kind, _to_float(match.group("v"))
    except ValueError:
        return None


_MD_RE = re.compile(
    r"(?:\b(?-i:MD|SMD|WMD)\b|mean\s+difference|difference\s+in\s+means?)"
    r"\s*(?:\([^)]{0,20}\))?\s*(?:of|was)?\s*[:=,]?\s*(?P<v>[-\u2212]?\d*\.?\d+)",
    re.IGNORECASE,
)


def parse_mean_difference(text: str) -> Optional[float]:
    match = _MD_RE.search(text or "")
    if not match:
        return None
    try:
        return _to_float(match.group("v"))
    except ValueError:
        return None


# --------------------------------------------------------------------------
# outcome polarity
# --------------------------------------------------------------------------

GENERIC_OUTCOMES = {
    "",
    "de\u011ferlendirilemedi",
    "degerlendirilemedi",
    "genel sonlan\u0131m / \u00f6zet istatisti\u011fi",
    "primer klinik sonlan\u0131m / \u00f6zet istatisti\u011fi",
    "primer klinik sonlan\u0131m \u00f6l\u00e7\u00fct\u00fc",
}

_FREE_RE = re.compile(
    r"(?:seizure|event|progression|relapse|disease|failure|recurrence|symptom)[- ]free"
    r"|seizure freedom|freedom from|n\u00f6betsiz|nobetsiz",
    re.IGNORECASE,
)

_UNDESIRABLE_RE = re.compile(
    r"mortalit|death|\bdied\b|fatal|\bmace\b|major adverse|cardiovascular event"
    r"|myocardial infarction|\bmi\b|stroke|hospitali[sz]|readmission|adverse"
    r"|complication|bleed|h(?:a)?emorrhag|infection|relapse|recurren|progression"
    r"|failure|exacerbation|seizure|\bpain\b|hba1c|blood pressure|\bldl\b"
    r"|triglycerid|length of stay|amputation|severity|symptom score|disease activity"
    r"|mortalite|\u00f6l\u00fcm|olum|hastaneye yat|yan etki|kanama|enfeksiyon|n\u00fcks|nuks"
    r"|ilerleme|komplikasyon",
    re.IGNORECASE,
)

_DESIRABLE_RE = re.compile(
    r"remission|response|responder|\bcure\b|healing|survival|quality of life|\bqol\b"
    r"|ejection fraction|\blvef\b|patency|clearance|eradication|adherence|success"
    r"|\brelief\b|\bhdl\b|sa\u011fkal\u0131m|sagkalim|remisyon|ya\u015fam kalitesi|yasam kalitesi"
    r"|yan\u0131t|iyile\u015fme",
    re.IGNORECASE,
)


def outcome_polarity(
    outcome: str, measure_kind: Optional[str] = None, sentence: str = ""
) -> Optional[str]:
    """'desirable' (higher is better), 'undesirable' (lower is better) or None.

    A hazard ratio is the hazard of the *event*, so 'overall survival' with an
    HR is undesirable (a lower HR is good), while 'median survival' is
    desirable.
    """
    name = (outcome or "").strip().lower()
    source = name if name not in GENERIC_OUTCOMES else (sentence or "").lower()
    if not source:
        return None
    is_hazard = measure_kind in HAZARD_KINDS
    if _FREE_RE.search(source):
        return "undesirable" if is_hazard else "desirable"
    if "survival" in source or "sa\u011fkal\u0131m" in source or "sagkalim" in source:
        return "undesirable" if is_hazard else "desirable"
    desirable = bool(_DESIRABLE_RE.search(source))
    undesirable = bool(_UNDESIRABLE_RE.search(source))
    if desirable and undesirable:
        return None
    if desirable:
        return "desirable"
    if undesirable:
        return "undesirable"
    return None


def _map_delta(delta: str, polarity: Optional[str]) -> Optional[str]:
    if polarity is None:
        return None
    good = (delta == "higher") == (polarity == "desirable")
    return LABEL_BENEFIT if good else LABEL_HARM


# --------------------------------------------------------------------------
# verbs (used only when no numeric estimate is available)
# --------------------------------------------------------------------------

_NEG_RE = re.compile(
    r"\bno\s+(?:statistically\s+)?significant\b"
    r"|\bnot\s+(?:statistically\s+)?significant"
    r"|\bnon-?significant"
    r"|\bno\s+(?:statistical\s+)?difference"
    r"|\bnot\s+(?:statistically\s+)?different"
    r"|\bdid\s+not\s+(?:significantly\s+)?(?:reduce|improve|differ|change|increase|decrease|affect|lower)"
    r"|\bdoes\s+not\s+(?:significantly\s+)?(?:reduce|improve|differ|change|increase|decrease|affect|lower)"
    r"|anlaml\u0131 (?:fark|de\u011fi\u015fiklik) (?:yok|saptanmad\u0131|bulunmad\u0131)"
    r"|fark saptanmad\u0131",
    re.IGNORECASE,
)

_DEC_RE = re.compile(
    r"\b(?:reduc\w*|decreas\w*|lower(?:ed|ing|s)?|declin\w*|fewer|diminish\w*)\b", re.IGNORECASE
)
_INC_RE = re.compile(
    r"\b(?:increas\w*|elevat\w*|rais(?:ed|es|ing)|higher|greater)\b", re.IGNORECASE
)
_IMPROVE_RE = re.compile(r"\bimprov\w*\b", re.IGNORECASE)
_WORSEN_RE = re.compile(r"\b(?:worsen\w*|deteriorat\w*)\b", re.IGNORECASE)


def _verb_labels(sentence: str, polarity: Optional[str]) -> set:
    implied = set()
    if _IMPROVE_RE.search(sentence):
        implied.add(LABEL_BENEFIT)
    if _WORSEN_RE.search(sentence):
        implied.add(LABEL_HARM)
    has_dec = bool(_DEC_RE.search(sentence))
    has_inc = bool(_INC_RE.search(sentence))
    if has_dec and has_inc:
        implied.add(LABEL_UNCERTAIN)
    elif has_dec or has_inc:
        implied.add(_map_delta("lower" if has_dec else "higher", polarity) or LABEL_UNCERTAIN)
    return implied


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------


def assess_direction(
    sentence: str = "",
    metrics: Optional[Iterable[str]] = None,
    outcome: str = "",
    alpha: float = ALPHA,
) -> Dict[str, Any]:
    """Full assessment with the evidence behind the label."""
    sentence = sentence or ""
    metric_strs = [m for m in (metrics or []) if isinstance(m, str)]
    text = " ".join([sentence] + metric_strs)
    notes: List[str] = []

    p_list = parse_p_values(text)
    sig_p, mixed = p_significance(p_list, alpha)
    if mixed:
        notes.append("Birden fazla p-de\u011feri birbiriyle \u00e7eli\u015fiyor.")

    ratio = parse_ratio(text)
    md = None if ratio else parse_mean_difference(text)
    ci = parse_ci(text)

    sig_ci: Optional[bool] = None
    if ci and ratio:
        sig_ci = not (ci[0] <= 1.0 <= ci[1])
    elif ci and md is not None:
        sig_ci = not (ci[0] <= 0.0 <= ci[1])

    flags = [s for s in (sig_p, sig_ci) if s is not None]
    conflict = mixed
    significant: Optional[bool] = None
    if flags:
        if len(set(flags)) == 1:
            significant = flags[0]
        else:
            conflict = True
            notes.append("p-de\u011feri ve g\u00fcven aral\u0131\u011f\u0131 \u00e7eli\u015fiyor.")

    if _NEG_RE.search(sentence) and not conflict:
        if significant is None:
            significant = False
            notes.append("Say\u0131sal veri yok; metin anlaml\u0131 fark olmad\u0131\u011f\u0131n\u0131 s\u00f6yl\u00fcyor.")
        elif significant is True:
            significant = None
            conflict = True
            notes.append("Metin 'anlaml\u0131 fark yok' diyor, say\u0131sal veri anlaml\u0131.")

    measure = ratio[0] if ratio else ("MD" if md is not None else None)
    polarity = outcome_polarity(outcome, ratio[0] if ratio else None, sentence)

    delta: Optional[str] = None
    if ratio:
        delta = "lower" if ratio[1] < 1 else "higher" if ratio[1] > 1 else None
    elif md is not None:
        delta = "lower" if md < 0 else "higher" if md > 0 else None

    if conflict:
        label = LABEL_UNCERTAIN
    elif significant is False:
        label = LABEL_NEUTRAL
    elif significant is None:
        label = LABEL_UNCERTAIN
        notes.append("Anlaml\u0131l\u0131k belirlenemedi (p-de\u011feri veya g\u00fcven aral\u0131\u011f\u0131 yok).")
    else:
        verbs = _verb_labels(sentence, polarity) - {LABEL_UNCERTAIN}
        if delta:
            estimate = _map_delta(delta, polarity)
            if estimate is None or (verbs and verbs != {estimate}):
                implied = {LABEL_SIG_UNCLEAR}
                if estimate and verbs and verbs != {estimate}:
                    notes.append("Etki tahmini ile metindeki fiil farkl\u0131 y\u00f6n\u00fc i\u015faret ediyor.")
            else:
                implied = {estimate}
        else:
            implied = verbs or {LABEL_SIG_UNCLEAR}
        label = implied.pop() if len(implied) == 1 else LABEL_SIG_UNCLEAR
        if label == LABEL_SIG_UNCLEAR:
            notes.append("Anlaml\u0131 fark var; y\u00f6n veya sonlan\u0131m kutbu (iyi/k\u00f6t\u00fc) g\u00fcvenle belirlenemedi.")

    return {
        "label": label,
        "significant": significant,
        "delta": delta,
        "polarity": polarity,
        "measure": measure,
        "p_values": p_list,
        "ci": ci,
        "notes": notes,
    }


def determine_direction(outcome_entry: Dict[str, Any]) -> str:
    """Drop-in replacement for ``_determine_statistical_direction``.

    ``outcome_entry`` is one item of ``extract_outcome_metrics``: it has
    ``outcome``, ``metrics`` and ``sentence``. Returns one of
    ``benefit``, ``harm``, ``neutral``, ``significant_unclear``, ``uncertain``.
    """
    entry = outcome_entry or {}
    sentence = entry.get("sentence") or entry.get("source_sentence") or ""
    return assess_direction(
        sentence=sentence,
        metrics=entry.get("metrics") or [],
        outcome=entry.get("outcome") or "",
    )["label"]

"""Strict PICO compatibility between two primary studies (fix for finding B2).

Replaces ``_evaluate_pico_compatibility`` and the outcome loop in
``compare_cross_article_findings``.

What changed and why
--------------------
* One shared word is no longer enough. Population, intervention and
  comparator need a Jaccard overlap of at least ``JACCARD_MIN`` on content
  tokens, and must not contradict each other on qualifiers such as
  type 1 vs type 2, acute vs chronic, adult vs pediatric.
* Unknown is not compatible. A missing comparator used to count as a match.
  Now a missing field makes the pair "not comparable" and says why.
* The study design class must be equal (RCT with RCT, cohort with cohort).
* Outcomes are matched only by their own names. The synthetic fallback label
  and the "first outcome of each study" fallback are gone. The function
  returns the matched ``(entry1, entry2)`` pairs so the caller compares the
  right entries.

Failure mode: synonyms ("T2DM" vs "type 2 diabetes mellitus") are not
recognised, so some truly comparable pairs will be reported as not
comparable. That is the safe direction. MeSH normalisation is the real fix.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

JACCARD_MIN = 0.6

STOP_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with", "and", "or", "by",
    "from", "as", "is", "are", "was", "were", "be", "been", "this", "that", "these",
    "those", "patients", "patient", "adults", "adult", "children", "child", "people",
    "participants", "subjects", "study", "studies", "group", "groups", "population",
    "treatment", "therapy", "versus", "vs", "than", "who", "had", "have", "has",
    "belirtilmedi", "belirtilmemi\u015f", "belirtilmemis", "\u00f6zette", "ozette",
    "bildirilmedi", "bilinmiyor", "belirsiz", "unknown", "not", "specified", "stated",
    "hasta", "hastalar", "hastalarda", "ve", "ile", "bir", "bu",
}

_ADULT = {"adult", "adults", "elderly", "older", "geriatric", "eri\u015fkin", "eriskin",
          "yeti\u015fkin", "yetiskin", "ya\u015fl\u0131", "yasli"}
_PEDIATRIC = {"pediatric", "paediatric", "child", "children", "infant", "infants", "neonate",
              "neonates", "neonatal", "adolescent", "adolescents", "\u00e7ocuk", "cocuk",
              "\u00e7ocuklarda", "cocuklarda", "yenido\u011fan", "yenidogan"}

_CONFLICT_GROUPS: List[Dict[str, Set[str]]] = [
    {"pediatric": _PEDIATRIC, "adult": _ADULT},
    {"acute": {"acute", "akut"}, "chronic": {"chronic", "kronik"}},
    {"ischemic": {"ischemic", "ischaemic", "iskemik"},
     "hemorrhagic": {"hemorrhagic", "haemorrhagic", "hemorajik"}},
    {"paroxysmal": {"paroxysmal"}, "persistent": {"persistent"}, "permanent": {"permanent"}},
    {"reduced": {"hfref", "reduced"}, "preserved": {"hfpef", "preserved"}},
    {"male": {"male", "men", "man", "erkek"},
     "female": {"female", "women", "woman", "kad\u0131n", "kadin"}},
]

GENERIC_OUTCOMES = {
    "",
    "de\u011ferlendirilemedi",
    "degerlendirilemedi",
    "genel sonlan\u0131m / \u00f6zet istatisti\u011fi",
    "primer klinik sonlan\u0131m / \u00f6zet istatisti\u011fi",
    "primer klinik sonlan\u0131m \u00f6l\u00e7\u00fct\u00fc",
    "sonlan\u0131m ad\u0131 g\u00fcvenle \u00e7evrilemedi",
    "\u00f6zette adland\u0131r\u0131lmad\u0131",
}


_SAMPLE_SIZE_RE = re.compile(
    r"\(?\s*\b[nN]\s*=\s*[\d,.]+\s*\)?|\b\d[\d,.]*\s+(?:patients|participants|subjects|hasta|olgu)\b",
)


def _norm(text: Optional[str]) -> str:
    """Lowercase (Turkish-safe) and drop sample sizes such as '(n=4000)'."""
    cleaned = _SAMPLE_SIZE_RE.sub(" ", text or "")
    return cleaned.replace("\u0130", "i").lower()


def _stem(token: str) -> str:
    """Very light English plural stripping: inhibitors -> inhibitor."""
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def all_tokens(text: Optional[str]) -> Set[str]:
    return {_stem(t) for t in re.findall(r"[^\W_]+", _norm(text))}


def content_tokens(text: Optional[str]) -> Set[str]:
    return {t for t in all_tokens(text) if t not in STOP_WORDS}


_QUALIFIED_NUMBER_RE = re.compile(
    r"\b(type|tip|stage|evre|grade|class|s\u0131n\u0131f|derece|nyha)\s*[-:]?\s*(\d+|iv|iii|ii|i|v)\b"
    r"|\bt([12])dm\b",
    re.IGNORECASE,
)


def qualified_numbers(raw_text: Optional[str]) -> Set[str]:
    """Numbers that name a disease subtype: 'type 2', 'stage III', 'T1DM'."""
    found: Set[str] = set()
    for match in _QUALIFIED_NUMBER_RE.finditer(_norm(raw_text)):
        if match.group(3):
            found.add(f"type:{match.group(3)}")
        else:
            kind = match.group(1).lower().replace("tip", "type").replace("evre", "stage")
            found.add(f"{kind}:{match.group(2).lower()}")
    return found


def _numbers_conflict(text1: Optional[str], text2: Optional[str]) -> bool:
    q1, q2 = qualified_numbers(text1), qualified_numbers(text2)
    kinds = {k.split(":")[0] for k in q1} & {k.split(":")[0] for k in q2}
    for kind in kinds:
        v1 = {k for k in q1 if k.startswith(kind + ":")}
        v2 = {k for k in q2 if k.startswith(kind + ":")}
        if not (v1 & v2):
            return True
    return False


def _group_hits(tokens: Set[str], group: Dict[str, Set[str]]) -> Set[str]:
    return {name for name, words in group.items() if tokens & words}


def has_qualifier_conflict(tokens1: Set[str], tokens2: Set[str]) -> bool:
    for group in _CONFLICT_GROUPS:
        h1, h2 = _group_hits(tokens1, group), _group_hits(tokens2, group)
        if h1 and h2 and not (h1 & h2):
            return True
    return False


def compare_terms(
    text1: Optional[str], text2: Optional[str], jaccard_min: float = JACCARD_MIN
) -> Tuple[Optional[bool], str]:
    """(match, reason). match is None when either side is unknown."""
    ct1, ct2 = content_tokens(text1), content_tokens(text2)
    if not ct1 or not ct2:
        return None, "unknown"
    raw1, raw2 = all_tokens(text1), all_tokens(text2)
    if has_qualifier_conflict(raw1, raw2):
        return False, "qualifier_conflict"
    if _numbers_conflict(text1, text2):
        return False, "numeric_conflict"
    jaccard = len(ct1 & ct2) / len(ct1 | ct2)
    return jaccard >= jaccard_min, f"jaccard={jaccard:.2f}"


# --------------------------------------------------------------------------
# study design class
# --------------------------------------------------------------------------

_KEY_TO_CLASS = {
    "rct": "rct",
    "randomized_controlled_trial": "rct",
    "clinical_trial": "trial",
    "cohort": "cohort",
    "case_control": "case_control",
    "cross_sectional": "cross_sectional",
    "comparative": "observational_other",
    "retrospective_comparative": "observational_other",
    "observational_unspecified": "observational_other",
    "case_series": "case_series",
    "retrospective_case_series": "case_series",
    "diagnostic_accuracy": "diagnostic",
}

_LABEL_HINTS = [
    ("rct", "rct"),
    ("rastgele", "rct"),
    ("randomi", "rct"),
    ("kohort", "cohort"),
    ("cohort", "cohort"),
    ("vaka-kontrol", "case_control"),
    ("case-control", "case_control"),
    ("kesitsel", "cross_sectional"),
    ("cross-sectional", "cross_sectional"),
    ("olgu serisi", "case_series"),
    ("case series", "case_series"),
    ("tan\u0131 do\u011frulu\u011fu", "diagnostic"),
    ("kontroll\u00fc klinik", "trial"),
    ("kar\u015f\u0131la\u015ft\u0131rmal\u0131", "observational_other"),
    ("g\u00f6zlemsel", "observational_other"),
]


def design_class(study_design: Any) -> Optional[str]:
    """Class of a ``study_design`` dict (preferred) or label string; None if unknown."""
    key, label = None, ""
    if isinstance(study_design, dict):
        key = study_design.get("design_key")
        label = study_design.get("design") or ""
    elif isinstance(study_design, str):
        label = study_design
    if key and key in _KEY_TO_CLASS:
        return _KEY_TO_CLASS[key]
    lowered = _norm(label)
    for hint, cls in _LABEL_HINTS:
        if hint in lowered:
            return cls
    return None


# --------------------------------------------------------------------------
# outcomes
# --------------------------------------------------------------------------


def _outcome_name(entry: Dict[str, Any]) -> str:
    name = (entry.get("outcome") or "").strip().lower()
    return "" if name in GENERIC_OUTCOMES else name


def match_outcomes(
    outcomes1: List[Dict[str, Any]],
    outcomes2: List[Dict[str, Any]],
    jaccard_min: float = JACCARD_MIN,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """One-to-one pairs of named outcomes with enough token overlap."""
    scored: List[Tuple[float, int, int]] = []
    for i, e1 in enumerate(outcomes1 or []):
        n1 = _outcome_name(e1)
        t1 = content_tokens(n1)
        if not t1:
            continue
        for j, e2 in enumerate(outcomes2 or []):
            n2 = _outcome_name(e2)
            t2 = content_tokens(n2)
            if not t2:
                continue
            if has_qualifier_conflict(all_tokens(n1), all_tokens(n2)):
                continue
            jac = len(t1 & t2) / len(t1 | t2)
            if jac >= jaccard_min:
                scored.append((jac, i, j))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    used1: Set[int] = set()
    used2: Set[int] = set()
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for _, i, j in scored:
        if i in used1 or j in used2:
            continue
        used1.add(i)
        used2.add(j)
        pairs.append((outcomes1[i], outcomes2[j]))
    return pairs


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

_FIELDS = (
    ("patient_population", "pop_match", "Pop\u00fclasyon", "population"),
    ("intervention", "int_match", "M\u00fcdahale", "intervention"),
    ("comparison", "comp_match", "Kar\u015f\u0131la\u015ft\u0131r\u0131c\u0131", "comparison"),
)


def _evidence_text(study: Dict[str, Any]) -> str:
    """The study's own title and outcome sentences."""
    parts = [study.get("title") or ""]
    for entry in study.get("outcome_metrics") or []:
        parts.append(entry.get("sentence") or entry.get("source_sentence") or "")
    return " ".join(parts)


def _evidence_tokens(study: Dict[str, Any]) -> Set[str]:
    return all_tokens(_evidence_text(study))


def _evidence_conflict(p1: Dict[str, Any], p2: Dict[str, Any], v1: Any, v2: Any) -> bool:
    """Subtype or qualifier clash between the two studies' own texts.

    Used when a field had to be resolved through the query term: "diabetes"
    may appear in both abstracts while one says type 1 and the other type 2.
    """
    text1 = f"{v1 or ''} {_evidence_text(p1)}"
    text2 = f"{v2 or ''} {_evidence_text(p2)}"
    return _numbers_conflict(text1, text2) or has_qualifier_conflict(all_tokens(text1), all_tokens(text2))


def _side_matches_query(value: Any, study: Dict[str, Any], query_value: str) -> Optional[bool]:
    """Does one study fit the query's term for this field?

    True when the extracted value matches the query term, or when every
    content word of the query term appears in the study's own title or
    outcome sentences. The second test also covers values the extractor has
    translated (an English query "Drug X" vs an extracted "ila\u00e7 X").
    """
    wanted = content_tokens(query_value)
    if not wanted:
        return None
    if content_tokens(value) and compare_terms(value, query_value)[0]:
        return True
    return wanted <= _evidence_tokens(study)


def evaluate_pico_compatibility(
    p1: Dict[str, Any],
    p2: Dict[str, Any],
    query_pico: Optional[Dict[str, Any]] = None,
    quote: Optional[Callable[[Any], str]] = None,
) -> Dict[str, Any]:
    """Drop-in replacement for ``_evaluate_pico_compatibility``.

    Keeps the old keys (``compatible``, ``matching_outcomes``,
    ``unmatched_reasons``, ``pop_match``, ``int_match``, ``comp_match``) and
    adds ``outcome_pairs``, ``unknown_fields`` and ``notes``.

    When a field was not extracted for a study, the query's own PICO term
    (``query_pico``, from ``extract_pico(query)``) may stand in: the pair
    matches on that field only if every content word of the query term appears
    in each such study's title or outcome sentences. Otherwise the field stays
    unknown and the pair is not comparable.

    ``quote`` formats a field value for the Turkish reason text (the repo
    passes ``report_generator.safe_pico_quote``).
    """
    show = quote or (lambda value: str(value))
    result: Dict[str, Any] = {}
    reasons: List[str] = []
    notes: List[str] = []
    unknown: List[str] = []
    verdicts: List[bool] = []
    query_pico = query_pico or {}

    for field, out_key, title, query_key in _FIELDS:
        v1, v2 = p1.get(field), p2.get(field)
        match, why = compare_terms(v1, v2)
        if match is None:
            query_value = query_pico.get(query_key) or ""
            if content_tokens(query_value):
                s1 = _side_matches_query(v1, p1, query_value)
                s2 = _side_matches_query(v2, p2, query_value)
                if s1 is True and s2 is True and _evidence_conflict(p1, p2, v1, v2):
                    match = False
                    why = "evidence_conflict"
                elif s1 is True and s2 is True:
                    match = True
                    notes.append(f"{title} \u00f6zetten \u00e7\u0131kar\u0131lamad\u0131; sorgudaki '{query_value}' "
                                 f"terimi her iki \u00e7al\u0131\u015fman\u0131n ba\u015fl\u0131\u011f\u0131nda veya sonu\u00e7 c\u00fcmlesinde ge\u00e7iyor.")
                elif s1 is False or s2 is False:
                    match = False
                    why = "query_mismatch"
        result[out_key] = match
        if match is None:
            unknown.append(title)
            reasons.append(f"{title} \u00f6zette belirtilmemi\u015f; kar\u015f\u0131la\u015ft\u0131r\u0131lamaz.")
        elif not match:
            reasons.append(f"{title} uyu\u015fmazl\u0131\u011f\u0131 ('{show(v1)}' / '{show(v2)}'; {why}).")
        verdicts.append(match is True)

    sd1, sd2 = p1.get("study_design"), p2.get("study_design")
    c1, c2 = design_class(sd1), design_class(sd2)
    design_ok = c1 is not None and c1 == c2
    result["design_compatible"] = design_ok
    if not design_ok:
        l1 = sd1.get("design") if isinstance(sd1, dict) else sd1
        l2 = sd2.get("design") if isinstance(sd2, dict) else sd2
        reasons.append(f"\u00c7al\u0131\u015fma tasar\u0131m\u0131 uyu\u015fmuyor veya belirsiz ('{l1}' / '{l2}').")

    pairs = match_outcomes(p1.get("outcome_metrics") or [], p2.get("outcome_metrics") or [])
    if not pairs:
        reasons.append("Ortak ve adland\u0131r\u0131lm\u0131\u015f bir sonlan\u0131m \u00f6l\u00e7\u00fct\u00fc saptanamad\u0131.")

    result["outcome_pairs"] = pairs
    result["matching_outcomes"] = [_outcome_name(a) for a, _ in pairs]
    result["unmatched_reasons"] = reasons
    result["unknown_fields"] = unknown
    result["notes"] = notes
    result["compatible"] = all(verdicts) and design_ok and bool(pairs)
    return result

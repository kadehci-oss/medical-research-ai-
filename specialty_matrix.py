"""
Specialty awareness for disease-agnostic PubMed queries.

Loads ``all_specialty_matrix.json`` (88 specialties) and maps a clinical query
to the best-matching specialty. Query enhancement never discards the user's
original terms: it only OR-expands a few high-confidence abbreviations, and
it leaves boolean or field-tagged queries unchanged.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_MATRIX_PATH = Path(__file__).resolve().parent / "all_specialty_matrix.json"

# Keywords that appear on most matrix rows and must not decide a specialty.
_GENERIC_KEYWORDS = {
    "clinical research",
    "evidence synthesis",
    "pubmed",
    "clinical",
    "research",
    "evidence",
    "synthesis",
}

_TR_FOLDS = str.maketrans({
    "ç": "c",
    "ğ": "g",
    "ı": "i",
    "ö": "o",
    "ş": "s",
    "ü": "u",
    "â": "a",
    "î": "i",
    "û": "u",
})

# phrase -> list of (specialty_id, weight). Weights are explicit so a disease
# term outranks a modality term when both are present (sickle cell > CRISPR).
_ALIASES: Dict[str, List[Tuple[str, int]]] = {
    "hfpef": [("kardiyoloji", 6)],
    "hfref": [("kardiyoloji", 6)],
    "hfimpf": [("kardiyoloji", 6)],
    "heart failure": [("kardiyoloji", 5)],
    "ejection fraction": [("kardiyoloji", 4)],
    "kalp yetersizligi": [("kardiyoloji", 6)],
    "kalp yetmezligi": [("kardiyoloji", 6)],
    "myocardial infarction": [("kardiyoloji", 4)],
    "atrial fibrillation": [("kardiyoloji", 4)],
    "diabetes": [("endokrinoloji_ve_metabolizma", 5)],
    "type 2 diabetes": [("endokrinoloji_ve_metabolizma", 6)],
    "t2dm": [("endokrinoloji_ve_metabolizma", 6)],
    "diyabet": [("endokrinoloji_ve_metabolizma", 5)],
    "glp-1": [("endokrinoloji_ve_metabolizma", 4)],
    "glp1": [("endokrinoloji_ve_metabolizma", 4)],
    "hba1c": [("endokrinoloji_ve_metabolizma", 4)],
    "depression": [("ruh_sagligi_ve_psikiyatri", 5)],
    "depressive": [("ruh_sagligi_ve_psikiyatri", 5)],
    "depresyon": [("ruh_sagligi_ve_psikiyatri", 5)],
    "depresif": [("ruh_sagligi_ve_psikiyatri", 5)],
    "psilocybin": [("ruh_sagligi_ve_psikiyatri", 5)],
    "psilosibin": [("ruh_sagligi_ve_psikiyatri", 5)],
    "mdd": [("ruh_sagligi_ve_psikiyatri", 4)],
    "antidepressant": [("ruh_sagligi_ve_psikiyatri", 4)],
    "sickle cell": [("hematoloji", 6)],
    "sickle": [("hematoloji", 5)],
    "orak hucre": [("hematoloji", 6)],
    "orak hucreli": [("hematoloji", 6)],
    "crispr": [("tibbi_biyoteknoloji", 5), ("tibbi_genetik", 3)],
    "gene editing": [("tibbi_biyoteknoloji", 5)],
    "gene therapy": [("tibbi_biyoteknoloji", 4)],
    "febrile seizure": [("cocuk_norolojisi", 7)],
    "febrile seizures": [("cocuk_norolojisi", 7)],
    "febril nobet": [("cocuk_norolojisi", 7)],
    "febril konvulziyon": [("cocuk_norolojisi", 7)],
    "seizure": [("noroloji", 4)],
    "seizures": [("noroloji", 4)],
    "epilepsy": [("noroloji", 4)],
    "epilepsi": [("noroloji", 4)],
    "nobet": [("noroloji", 4)],
    "stroke": [("noroloji", 4)],
    "inme": [("noroloji", 4)],
}

# Synonym expansions applied only for the detected specialty. Each value is
# OR-ed with the original token so the user's wording stays mandatory-capable.
_EXPANSIONS: Dict[str, Dict[str, str]] = {
    "kardiyoloji": {
        "hfpef": "heart failure with preserved ejection fraction",
        "hfref": "heart failure with reduced ejection fraction",
        "hfimpf": "heart failure with mildly reduced ejection fraction",
        "sglt2": "sodium-glucose cotransporter 2",
    },
    "cocuk_kardiyolojisi": {
        "hfpef": "heart failure with preserved ejection fraction",
        "hfref": "heart failure with reduced ejection fraction",
    },
    "endokrinoloji_ve_metabolizma": {
        "glp-1": "glucagon-like peptide-1",
        "glp1": "glucagon-like peptide-1",
        "t2dm": "type 2 diabetes mellitus",
        "sglt2": "sodium-glucose cotransporter 2",
    },
    "cocuk_endokrinolojisi": {
        "glp-1": "glucagon-like peptide-1",
        "glp1": "glucagon-like peptide-1",
        "t1dm": "type 1 diabetes mellitus",
    },
    "nefroloji": {
        "ckd": "chronic kidney disease",
        "sglt2": "sodium-glucose cotransporter 2",
    },
    "ruh_sagligi_ve_psikiyatri": {
        "mdd": "major depressive disorder",
    },
    "cocuk_ruh_sagligi": {
        "mdd": "major depressive disorder",
    },
    "hematoloji": {
        "scd": "sickle cell disease",
    },
    "cocuk_hematolojisi": {
        "scd": "sickle cell disease",
    },
    "tibbi_biyoteknoloji": {
        "crispr": "CRISPR-Cas9",
    },
    "tibbi_genetik": {
        "crispr": "CRISPR-Cas9",
    },
}

_PEDIATRIC_VARIANT = {
    "noroloji": "cocuk_norolojisi",
    "kardiyoloji": "cocuk_kardiyolojisi",
    "hematoloji": "cocuk_hematolojisi",
    "endokrinoloji_ve_metabolizma": "cocuk_endokrinolojisi",
    "enfeksiyon_hastaliklari": "cocuk_enfeksiyon_hastaliklari",
    "gastroenteroloji": "cocuk_gastroenterolojisi",
    "gogus_hastaliklari": "cocuk_gogus_hastaliklari",
    "tibbi_onkoloji": "cocuk_onkolojisi",
    "ruh_sagligi_ve_psikiyatri": "cocuk_ruh_sagligi",
    "acil_tip": "cocuk_acil_tip",
    "alerji_ve_immunoloji": "cocuk_alerji_immunoloji",
}

_CHILD_MARKERS = (
    "child",
    "children",
    "pediatric",
    "paediatric",
    "infant",
    "infants",
    "neonate",
    "neonatal",
    "cocuk",
    "cocuklar",
    "cocuklarda",
    "pediatrik",
    "bebek",
    "yenidogan",
)
_ADULT_MARKERS = (
    "adult",
    "adults",
    "elderly",
    "geriatric",
    "eriskin",
    "eriskinlerde",
    "yetiskin",
    "yetiskinlerde",
    "yasli",
)

_MIN_SCORE = 4
_CACHE: Dict[str, Tuple[Tuple[Any, ...], Dict[str, Any]]] = {}

_BOOLEAN_QUERY_RE = re.compile(r"\b(AND|OR|NOT)\b|[()\[\]]|\"", re.IGNORECASE)


def _empty_matrix(error: str) -> Dict[str, Any]:
    logger.warning("%s", error)
    return {
        "specialties": [],
        "total_specialties": 0,
        "schema_version": None,
        "error": error,
    }


def _norm(text: str) -> str:
    """Lowercase, fold Turkish characters, and keep letters, digits, and hyphens."""
    if not text:
        return ""
    folded = str(text).casefold().replace("\u0307", "").translate(_TR_FOLDS)
    folded = re.sub(r"[^a-z0-9\-\s]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    phrase_n = _norm(phrase)
    if not phrase_n or phrase_n in _GENERIC_KEYWORDS:
        return False
    return re.search(rf"(?:^|\s){re.escape(phrase_n)}(?:\s|$)", normalized_text) is not None


def load_specialty_matrix(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the specialty matrix JSON.

    A missing file, an unreadable file, or malformed JSON returns an empty
    specialty list and an ``error`` string. Callers should keep searching
    with the original query when that happens.
    """
    matrix_path = Path(path).expanduser() if path else _DEFAULT_MATRIX_PATH
    try:
        resolved = str(matrix_path.resolve())
    except OSError:
        resolved = str(matrix_path)

    try:
        stat_result = matrix_path.stat()
    except OSError as exc:
        return _empty_matrix(f"Specialty matrix not found or unreadable: {matrix_path} ({exc})")

    cache_key = (stat_result.st_mtime_ns, stat_result.st_size)
    cached = _CACHE.get(resolved)
    if cached and cached[0] == cache_key:
        return cached[1]

    try:
        raw = matrix_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _empty_matrix(f"Specialty matrix not found or unreadable: {matrix_path} ({exc})")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _empty_matrix(f"Malformed specialty matrix JSON: {exc}")

    if not isinstance(data, dict) or not isinstance(data.get("specialties"), list):
        return _empty_matrix("Specialty matrix is missing a specialties list")

    _CACHE[resolved] = (cache_key, data)
    return data


def _iter_specialties(matrix: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for entry in matrix.get("specialties") or []:
        if isinstance(entry, dict) and entry.get("id"):
            yield entry


def _keyword_weight(phrase: str) -> int:
    words = [part for part in _norm(phrase).split() if part]
    if not words:
        return 0
    return 4 + max(0, len(words) - 1)


def _prune_subphrases(hits: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
    """Drop a shorter phrase when a longer matched phrase already contains it."""
    best: Dict[str, int] = {}
    for phrase, weight in hits:
        if phrase not in best or weight > best[phrase]:
            best[phrase] = weight
    phrases = list(best)
    kept = []
    for phrase in phrases:
        if any(phrase != other and _contains_phrase(other, phrase) for other in phrases):
            continue
        kept.append((phrase, best[phrase]))
    return kept


def _score_specialties(
    normalized_query: str,
    specialties: Sequence[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    hits: Dict[str, List[Tuple[str, int]]] = {}

    def add(specialty_id: str, phrase: str, weight: int) -> None:
        phrase_n = _norm(phrase)
        if not phrase_n or phrase_n in _GENERIC_KEYWORDS or weight <= 0:
            return
        if not _contains_phrase(normalized_query, phrase_n):
            return
        hits.setdefault(specialty_id, []).append((phrase_n, weight))

    known_ids = {str(entry.get("id")) for entry in specialties}
    for phrase, targets in _ALIASES.items():
        for specialty_id, weight in targets:
            if specialty_id in known_ids:
                add(specialty_id, phrase, weight)

    for entry in specialties:
        specialty_id = str(entry.get("id"))
        for field in ("specialty_name", "specialty_name_en"):
            name = entry.get(field) or ""
            add(specialty_id, str(name), 5)
        keywords = entry.get("search_keywords") or []
        if not isinstance(keywords, list):
            continue
        for keyword in keywords:
            if not isinstance(keyword, str):
                continue
            add(specialty_id, keyword, _keyword_weight(keyword))

    scored: Dict[str, Dict[str, Any]] = {}
    for specialty_id, specialty_hits in hits.items():
        pruned = _prune_subphrases(specialty_hits)
        if not pruned:
            continue
        scored[specialty_id] = {
            "score": sum(weight for _, weight in pruned),
            "matched_terms": [phrase for phrase, _ in sorted(pruned)],
            "longest": max(len(phrase) for phrase, _ in pruned),
        }
    return scored


def _compact_specialty(entry: Dict[str, Any], score: int, matched_terms: Sequence[str]) -> Dict[str, Any]:
    return {
        "id": entry.get("id"),
        "specialty_name": entry.get("specialty_name") or "",
        "specialty_name_en": entry.get("specialty_name_en") or "",
        "category": entry.get("category") or "",
        "score": score,
        "matched_terms": list(matched_terms),
    }


def detect_specialty(
    query: str,
    matrix: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Return the best-matching specialty for ``query``, or None.

    Generic matrix keywords (``clinical research``, ``pubmed``,
    ``evidence synthesis``) are ignored. A pediatric subspecialty is preferred
    when the query names children and a pediatric variant of the winning
    specialty exists in the matrix. The result includes up to two
    ``alternatives`` that also cleared the confidence threshold.
    """
    normalized = _norm(query or "")
    if not normalized:
        return None

    loaded = matrix if matrix is not None else load_specialty_matrix(path)
    if not isinstance(loaded, dict):
        return None
    specialties = list(_iter_specialties(loaded))
    if not specialties:
        return None

    by_id = {str(entry.get("id")): entry for entry in specialties}
    scored = _score_specialties(normalized, specialties)
    ranked = [
        (specialty_id, info)
        for specialty_id, info in scored.items()
        if info["score"] >= _MIN_SCORE and specialty_id in by_id
    ]
    if not ranked:
        return None

    ranked.sort(key=lambda item: (-item[1]["score"], -item[1]["longest"], item[0]))
    winner_id, winner_info = ranked[0]

    has_child = any(_contains_phrase(normalized, marker) for marker in _CHILD_MARKERS)
    has_adult = any(_contains_phrase(normalized, marker) for marker in _ADULT_MARKERS)
    if has_child and not has_adult and winner_id in _PEDIATRIC_VARIANT:
        variant_id = _PEDIATRIC_VARIANT[winner_id]
        if variant_id in by_id:
            winner_id = variant_id
            matched = list(winner_info["matched_terms"])
            if "pediatric context" not in matched:
                matched.append("pediatric context")
            winner_info = {
                "score": winner_info["score"],
                "matched_terms": matched,
                "longest": winner_info["longest"],
            }

    result = _compact_specialty(by_id[winner_id], winner_info["score"], winner_info["matched_terms"])
    alternatives = []
    for specialty_id, info in ranked:
        if specialty_id == result["id"]:
            continue
        alternatives.append(_compact_specialty(by_id[specialty_id], info["score"], info["matched_terms"]))
        if len(alternatives) == 2:
            break
    result["alternatives"] = alternatives
    return result


def _base_enhancement(query: str) -> Dict[str, Any]:
    cleaned = (query or "").strip()
    return {
        "original_query": cleaned,
        "enhanced_query": cleaned,
        "specialty": None,
        "applied": False,
        "added_terms": [],
        "strategy": "unchanged",
        "fallback_to_original": False,
    }


def enhance_query_with_specialty(
    query: str,
    specialty: Optional[Dict[str, Any]] = None,
    matrix: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
    apply: bool = True,
) -> Dict[str, Any]:
    """
    Optionally OR-expand abbreviations that belong to the detected specialty.

    The original tokens are always retained. Boolean queries, parentheses,
    field tags, and quoted strings are not rewritten. No specialty name is
    AND-filtered onto the query, because that can drop relevant records or
    return an empty set when the MeSH heading is missing.

    ``apply=False`` still reports the detected specialty but does not change
    the query string.
    """
    result = _base_enhancement(query)
    original = result["original_query"]
    if not original:
        result["strategy"] = "empty_query"
        return result

    if specialty is None:
        try:
            specialty = detect_specialty(original, matrix=matrix, path=path)
        except Exception as exc:  # defensive: detection must not break search
            logger.warning("Specialty detection failed: %s", exc)
            result["strategy"] = "detection_error"
            return result

    if specialty:
        result["specialty"] = specialty

    if not apply:
        result["strategy"] = "disabled"
        return result

    if not specialty or not specialty.get("id"):
        matrix_error = None
        if matrix is not None and isinstance(matrix, dict):
            matrix_error = matrix.get("error")
        elif matrix is None:
            loaded = load_specialty_matrix(path)
            matrix_error = loaded.get("error") if isinstance(loaded, dict) else None
        result["strategy"] = "matrix_unavailable" if matrix_error else "no_specialty"
        return result

    if _BOOLEAN_QUERY_RE.search(original):
        result["strategy"] = "preserved_boolean_query"
        return result

    expansions = _EXPANSIONS.get(str(specialty.get("id")), {})
    if not expansions:
        result["strategy"] = "no_expansion_for_specialty"
        return result

    normalized_query = _norm(original)
    parts: List[str] = []
    added: List[str] = []
    for token in original.split():
        key = _norm(token)
        phrase = expansions.get(key)
        if phrase and _norm(phrase) not in normalized_query and len(added) < 3:
            parts.append(f'({token} OR "{phrase}")')
            added.append(phrase)
        else:
            parts.append(token)

    if not added:
        result["strategy"] = "no_expandable_terms"
        return result

    enhanced = " ".join(parts)
    if not _original_terms_preserved(original, enhanced):
        result["strategy"] = "rejected_term_loss"
        return result

    result["enhanced_query"] = enhanced
    result["added_terms"] = added
    result["applied"] = True
    result["strategy"] = "synonym_or_expansion"
    return result


def _original_terms_preserved(original: str, enhanced: str) -> bool:
    """Every original whitespace token must still occur verbatim."""
    if not enhanced:
        return False
    return all(token in enhanced for token in original.split())

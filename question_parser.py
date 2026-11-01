"""PICO elements from questions written as sentences, in English or Turkish.

``report_generator.extract_pico`` handles keyword strings ("X versus Y in Z").
Physicians often type a question instead: "Does empagliflozin reduce mortality
in heart failure?" or "Kalp yetersizliğinde SGLT2 inhibitörleri mortaliteyi
azaltır mı?". This module recognises a small set of such sentence forms and
returns the parts of the query that fill each element.

Rules:
- Every value is a span of the query (with case and question endings removed).
  Nothing is translated, inferred or added.
- An element the sentence does not state stays empty.
- A sentence that matches none of the forms returns ``None`` so the caller can
  fall back to the keyword extractor.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

Parsed = Dict[str, str]

_TR_VOWELS = "aeıioöuüAEIİOÖUÜ"


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip(" ,;:.?!")
    return re.sub(r"^(?:the|a|an)\s+", "", text, flags=re.IGNORECASE)


def _result(population="", intervention="", comparison="", outcome="") -> Parsed:
    return {"population": _clean(population), "intervention": _clean(intervention),
            "comparison": _clean(comparison), "outcome": _clean(outcome)}


# ---------------------------------------------------------------- English ---

_EN_COMPARATOR = r"(?:compared\s+(?:with|to)|in\s+comparison\s+(?:with|to)|versus|vs\.?|relative\s+to|rather\s+than)"
_EN_VERBS = (r"reduce|lower|decrease|increase|raise|improve|prevent|prolong|extend|shorten|affect|change|delay|"
             r"worsen|cause|predict|alter|slow|halve")
_EN_POPULATION_SPLIT = re.compile(r"\s+(?:in|among)\s+")

_EN_AUX_VERB = re.compile(
    rf"^(?:does|do|did|can|could|will|would|should|may|might)\s+(?P<i>.+?)\s+(?P<verb>{_EN_VERBS})(?:s|es|d|ed)?\s+(?P<rest>.+)$",
    re.IGNORECASE,
)
_EN_AS_EFFECTIVE = re.compile(
    r"^(?:is|are)\s+(?P<i>.+?)\s+(?:as|more|less)\s+(?:effective|efficacious|safe|beneficial|accurate)\s+"
    r"(?:as|than)\s+(?P<c>.+?)(?:\s+(?:for|in|among)\s+(?P<p>.+))?$",
    re.IGNORECASE,
)
_EN_EFFECT_OF_ON = re.compile(
    r"^(?:what\s+(?:is|are)\s+)?(?:the\s+)?(?:effects?|impact|influence)\s+of\s+(?P<i>.+?)\s+on\s+(?P<rest>.+)$",
    re.IGNORECASE,
)
_EN_RISK_AFTER = re.compile(
    r"^(?:what\s+is\s+)?(?:the\s+)?(?:risk|incidence|odds|likelihood)\s+of\s+(?P<o>.+?)\s+"
    r"(?:after|following|with|among\s+users\s+of|in\s+users\s+of)\s+(?P<rest>.+)$",
    re.IGNORECASE,
)
_EN_WHAT_IS = re.compile(r"^what\s+(?:is|are)\s+(?:the\s+)?", re.IGNORECASE)


def _split_outcome_population(rest: str):
    """'mortality in heart failure compared with placebo' -> (outcome, population, comparator)."""
    comparator = ""
    match = re.search(rf"\s+{_EN_COMPARATOR}\s+(?P<c>.+)$", rest, re.IGNORECASE)
    if match:
        comparator = match.group("c")
        rest = rest[:match.start()]
    parts = _EN_POPULATION_SPLIT.split(rest, maxsplit=1)
    outcome = parts[0]
    population = parts[1] if len(parts) > 1 else ""
    return outcome, population, comparator


def _parse_english(query: str) -> Optional[Parsed]:
    q = _clean(query)
    m = _EN_AUX_VERB.match(q)
    if m:
        intervention = m.group("i")
        comparator = ""
        inner = re.search(rf"\s+{_EN_COMPARATOR}\s+(?P<c>.+)$", intervention, re.IGNORECASE)
        if inner:
            comparator, intervention = inner.group("c"), intervention[:inner.start()]
        outcome, population, tail_comparator = _split_outcome_population(m.group("rest"))
        return _result(population, intervention, comparator or tail_comparator, outcome)
    m = _EN_AS_EFFECTIVE.match(q)
    if m:
        return _result(m.group("p") or "", m.group("i"), m.group("c"), "")
    m = _EN_EFFECT_OF_ON.match(q)
    if m:
        outcome, population, comparator = _split_outcome_population(m.group("rest"))
        return _result(population, m.group("i"), comparator, outcome)
    m = _EN_RISK_AFTER.match(q)
    if m:
        exposure, population, comparator = _split_outcome_population(m.group("rest"))
        return _result(population, exposure, comparator, m.group("o"))
    return None


def strip_english_question(query: str) -> str:
    """'What is the sensitivity of X for Y?' -> 'sensitivity of X for Y' for the keyword extractor."""
    return _EN_WHAT_IS.sub("", _clean(query))


# ---------------------------------------------------------------- Turkish ---

_TR_QUESTION_END = r"(?:\s+m[ıiuü](?:dır|dir|dur|dür|yız|yiz)?)?\s*$"
_TR_EFFECT_VERB = re.compile(
    r"^(?P<body>.+?)\s+(?P<verb>azalt\w*|artır\w*|arttır\w*|düşür\w*|önle\w*|iyileştir\w*|sağla\w*|uzat\w*|"
    r"kısalt\w*|etkile\w*|değiştir\w*|geciktir\w*|yavaşlat\w*)" + _TR_QUESTION_END,
    re.IGNORECASE,
)
_TR_EFFICACY_END = re.compile(
    r"^(?P<body>.+?)\s+(?:daha\s+)?(?:etkili|etkin|güvenli|üstün|yararlı|faydalı)" + _TR_QUESTION_END,
    re.IGNORECASE,
)
_TR_COMPARATOR_CUE = re.compile(
    r"\s+(?P<cue>ile\s+karşılaştırıldığında|ile\s+kıyaslandığında|kıyasla|göre|oranla|kadar|yerine)(?:\s+|$)",
    re.IGNORECASE,
)
_TR_COMPARISON_NOUN = re.compile(
    r"^(?P<i>.+?)\s+ile\s+(?P<c>.+?)\s+(?:karşılaştırılması|karşılaştırması|kıyaslanması)$",
    re.IGNORECASE,
)
_TR_RISK = re.compile(
    r"^(?:(?P<i>.+?)\s+sonrası\s+)?(?P<o>.+?)\s+(?:riski|sıklığı|prevalansı|insidansı|görülme\s+sıklığı)\s+nedir$",
    re.IGNORECASE,
)
_TR_ACCURACY = re.compile(
    r"^(?P<i>.+?)\s+(?P<o>tanısal\s+doğruluğu|duyarlılığı|özgüllüğü|doğruluğu|performansı)\s+nedir$",
    re.IGNORECASE,
)
# Words that may precede the comparator's head noun inside the same phrase.
_TR_MODIFIERS = {"en", "iyi", "standart", "tıbbi", "medikal", "düşük", "yüksek", "doz", "dozda", "konvansiyonel",
                 "geleneksel", "açık", "laparoskopik", "erken", "geç", "cerrahi", "konservatif", "destek",
                 "aktif", "olağan", "rutin", "mevcut", "plasebo"}
_TR_NOT_LOCATIVE = {"ile", "göre", "kadar", "sonra", "önce", "olarak", "de", "da", "nedir", "midir", "mıdır"}


def _strip_locative(word: str) -> str:
    """'yetersizliğinde' -> 'yetersizliği', 'apandisitte' -> 'apandisit', 'hastalarda' -> 'hastalar'."""
    # Possessive + locative ("yetersizliğ-i-nde", "hastalar-ı-nda"); "hipertansiyon-da" keeps its n.
    if re.search(r"[ıiuü]n[dt][ae]$", word):
        return word[:-3]
    return word[:-2]


def _strip_dative(word: str) -> str:
    """'plaseboya' -> 'plasebo', 'tedaviye' -> 'tedavi', 'metformine' -> 'metformin'."""
    if re.search(r"[" + _TR_VOWELS + r"]y[ae]$", word):
        return word[:-2]
    if re.search(r"[ıiuü]n[ae]$", word):  # possessive + dative: "blokerleri-ne"
        return word[:-2]
    if re.search(r"[^" + _TR_VOWELS + r"][ae]$", word) and len(word) >= 4:
        return word[:-1]
    return word


def _strip_genitive(word: str) -> str:
    """'taramasının' -> 'taraması', 'tedavinin' -> 'tedavi', 'MR'ın' -> 'MR'."""
    word = re.sub(r"['’](?:n?[ıiuü]n)$", "", word)
    if re.search(r"[" + _TR_VOWELS + r"]n[ıiuü]n$", word):
        return word[:-3]
    if re.search(r"[^" + _TR_VOWELS + r"][ıiuü]n$", word) and len(word) > 4:
        return word[:-2]
    return word


def _strip_accusative(phrase: str) -> str:
    """'mortaliteyi' -> 'mortalite', 'kilo kaybını' -> 'kilo kaybı'; other endings are kept."""
    words = phrase.split()
    if not words:
        return phrase
    last = words[-1]
    if re.search(r"[" + _TR_VOWELS + r"]y[ıiuü]$", last):
        last = last[:-2]
    elif re.search(r"[" + _TR_VOWELS + r"]n[ıiuü]$", last) and len(words) > 1:
        last = last[:-2]
    return " ".join(words[:-1] + [last])


def _peel_population(text: str):
    """Leading phrase that ends in a locative ('Kalp yetersizliğinde', 'yaşlı hastalarda')."""
    words = text.split()
    for index, word in enumerate(words[:7]):
        bare = word.lower().strip(",")
        if bare in _TR_NOT_LOCATIVE or len(bare) < 4:
            continue
        if re.search(r"(?:d[ae]|t[ae])$", bare):
            phrase = words[:index] + [_strip_locative(word.strip(","))]
            return " ".join(phrase), " ".join(words[index + 1:])
    return "", text


def _split_comparator(text: str):
    """'SGLT2 inhibitörleri plaseboya kıyasla mortaliteyi' -> (intervention, comparator, after)."""
    match = _TR_COMPARATOR_CUE.search(text)
    if not match:
        return text, "", ""
    before, after = text[:match.start()].split(), text[match.end():]
    if not before:
        return text, "", ""
    head = before[-1]
    if match.group("cue").lower() in ("kıyasla", "göre", "oranla"):
        head = _strip_dative(head)
    start = len(before) - 1
    # The intervention phrase usually ends in a plural or possessive noun ("inhibitörleri", "tedavisi");
    # the comparator starts right after it. Otherwise extend back over known modifiers only.
    boundary = next((i + 1 for i, w in enumerate(before[:-1]) if re.search(r"(?:leri|ları|s[ıiuü])$", w.lower())), None)
    if boundary is not None:
        start = boundary
    else:
        while start > 1 and before[start - 1].lower() in _TR_MODIFIERS:
            start -= 1
    comparator = " ".join(before[start:-1] + [head])
    return " ".join(before[:start]), comparator, after


def _split_intervention_outcome(text: str):
    """Last noun phrase before the verb is the outcome: 'GLP-1 agonistleri kilo kaybı' -> ('GLP-1 agonistleri', 'kilo kaybı')."""
    words = text.split()
    if len(words) < 2:
        return "", text
    last = words[-1]
    take = 1 if re.search(r"[" + _TR_VOWELS + r"]y[ıiuü]$", last) else 2 if (
        re.search(r"(?:[ıiuü]|s[ıiuü]|[ıiuü]n[ıiuü])$", last) and len(words) >= 3) else 1
    return " ".join(words[:-take]), _strip_accusative(" ".join(words[-take:]))


def _parse_turkish(query: str) -> Optional[Parsed]:
    q = _clean(query)
    population, body = _peel_population(q)

    m = _TR_COMPARISON_NOUN.match(body)
    if m:
        return _result(population, m.group("i"), _strip_genitive(m.group("c").split()[-1]) if len(m.group("c").split()) == 1
                       else " ".join(m.group("c").split()[:-1] + [_strip_genitive(m.group("c").split()[-1])]), "")
    m = _TR_RISK.match(body)
    if m:
        return _result(population, m.group("i") or "", "", m.group("o"))
    m = _TR_ACCURACY.match(body)
    if m:
        words = m.group("i").split()
        index_test = " ".join(words[:-1] + [_strip_genitive(words[-1])])
        return _result(population, index_test, "", m.group("o"))
    m = _TR_EFFECT_VERB.match(body)
    if m:
        intervention, comparator, after = _split_comparator(m.group("body"))
        if comparator:
            outcome = _strip_accusative(after) if after else ""
        else:
            intervention, outcome = _split_intervention_outcome(intervention)
        if intervention or outcome:
            return _result(population, intervention, comparator, outcome)
    m = _TR_EFFICACY_END.match(body)
    if m:
        intervention, comparator, _after = _split_comparator(m.group("body"))
        if intervention:
            return _result(population, intervention, comparator, "")
    return None


def _looks_turkish(query: str) -> bool:
    return bool(re.search(r"[çğıöşüÇĞİÖŞÜ]", query or "")) or bool(
        re.search(r"\b(?:m[ıiuü]|m[ıiuü]d[ıiuü]r|nedir|hastalarda|ile)\s*\??\s*$", query or "", re.IGNORECASE)
        or re.search(r"\b(?:azaltır|artırır|sağlar|önler|iyileştirir)\b", query or "", re.IGNORECASE))


def parse_question(query: str) -> Optional[Parsed]:
    """P/I/C/O spans from a sentence-form question, or None when no form matches."""
    if not query or not query.strip():
        return None
    if _looks_turkish(query):
        return _parse_turkish(query)
    return _parse_english(query)

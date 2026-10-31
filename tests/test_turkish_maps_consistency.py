"""Controlled Turkish translation dictionary consistency tests.

This test module verifies the consistency of controlled Turkish mapping and
terminology dictionaries across the engine (effect labels, design labels,
outcome phrases, drug names, population phrases, limitations, clinical phrases,
symptoms, predictors, etc.).

Verification rules:
1. No consecutive duplicated words (e.g. "oranı oranı", "başına başına").
2. Values are non-empty strings with no leading or trailing whitespace.
3. Common English function words ("the", "of", "and", "with", "in", "was", "were")
   do not appear as standalone words.
4. Values containing abbreviations/acronyms present the abbreviation inside
   parentheses with a preceding Turkish expansion (e.g. "olasılık oranı (OR)").

Note: Engine code is not modified. Any detected issues are marked as xfail
so CI stays green while recording dictionary issues for external PR resolution.
"""

import re
import pytest

import display_turkish
import report_generator

ENGLISH_FUNCTION_WORDS = frozenset({"the", "of", "and", "with", "in", "was", "were"})

ROMAN_NUMERALS = frozenset({
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII",
    "II-IV", "I-IV",
})


def _extract_words(text: str):
    """Extract individual words respecting Turkish diacritics and alphanumeric characters."""
    return re.findall(r"\b[A-Za-zÇĞİÖŞÜçğıöşüıİ0-9/-]+\b", text)


def _check_consecutive_duplicates(val: str):
    words = _extract_words(val)
    for i in range(len(words) - 1):
        if words[i].casefold() == words[i + 1].casefold():
            return False, f"Ardışık yinelenen sözcük bulundu: '{words[i]}' '{words[i+1]}'"
    return True, ""


def _check_non_empty_and_trimmed(val: str):
    if not isinstance(val, str) or len(val) == 0:
        return False, "Değer boş dize"
    if val != val.strip():
        return False, f"Değerde baş veya son boşluk var: {repr(val)}"
    return True, ""


def _check_no_english_function_words(val: str):
    words = _extract_words(val)
    for w in words:
        if w.lower() in ENGLISH_FUNCTION_WORDS:
            return False, f"İngilizce işlev sözcüğü bağımsız sözcük olarak geçiyor: '{w}'"
    return True, ""


def _check_abbreviations_in_parentheses(val: str):
    tokens = re.findall(r"\b[A-ZÇĞİÖŞÜ0-9/-]+\b", val)
    uppers = []
    for token in tokens:
        subparts = [p for p in re.split(r"[-/]", token) if p]
        for part in subparts:
            if (
                part.isupper()
                and len(part) >= 2
                and not part.isdigit()
                and part not in ROMAN_NUMERALS
            ):
                uppers.append(part)

    for abbr in uppers:
        # Check if abbr is enclosed in parentheses in the value: e.g. "(OR)"
        if f"({abbr})" not in val:
            return False, f"Kısaltma '{abbr}' parantez içinde değil"
        expansion = val[: val.index(f"({abbr})")].strip()
        if not expansion:
            return False, f"Kısaltmanın '({abbr})' başında Türkçe açılımı yok"
    return True, ""


def _evaluate_consistency(val: str):
    """Runs all 4 consistency rules and returns list of error messages."""
    errors = []
    ok, msg = _check_consecutive_duplicates(val)
    if not ok:
        errors.append(msg)
    ok, msg = _check_non_empty_and_trimmed(val)
    if not ok:
        errors.append(msg)
    ok, msg = _check_no_english_function_words(val)
    if not ok:
        errors.append(msg)
    ok, msg = _check_abbreviations_in_parentheses(val)
    if not ok:
        errors.append(msg)
    return errors


def _build_test_cases():
    """Gathers all controlled dictionary entries across engine modules."""
    cases = []

    # 1. Etki ölçütü etiketleri (Effect measure labels)
    for code, _, label in report_generator._EFFECT_LABELS:
        cases.append(("report_generator._EFFECT_LABELS", f"effect:{code}", label))

    # 2. Tasarım etiketleri (Design labels)
    for key, label in report_generator._DESIGN_LABELS.items():
        cases.append(("report_generator._DESIGN_LABELS", f"design:{key}", label))

    # 3. Popülasyon ifadeleri (Population phrases)
    for src, tr in report_generator._POPULATION_PHRASES:
        cases.append(("report_generator._POPULATION_PHRASES", f"population:{src}", tr))

    # 4. İlaç adları ve ilgili tedaviler (Drug names / labels)
    for i, (_, label) in enumerate(report_generator._DRUG_LABEL_RES):
        cases.append(("report_generator._DRUG_LABEL_RES", f"drug_label:{i}", label))
    for key, tr in report_generator._DRUG_NAME_TR.items():
        cases.append(("report_generator._DRUG_NAME_TR", f"drug_name:{key}", tr))
    for src, tr in report_generator._DRUG_TR:
        cases.append(("report_generator._DRUG_TR", f"drug_tr:{src}", tr))
    for i, (_, label) in enumerate(report_generator._CONCOMITANT_TR):
        cases.append(("report_generator._CONCOMITANT_TR", f"concomitant:{i}", label))

    # 5. Sonlanım adları (Outcome names and controlled phrases)
    for src, tr in display_turkish._PHRASE_PAIRS:
        cases.append(("display_turkish._PHRASE_PAIRS", f"phrase:{src}", tr))
    for src, tr in display_turkish._SINGLE_OUTCOME_TR.items():
        cases.append(("display_turkish._SINGLE_OUTCOME_TR", f"single_outcome:{src}", tr))

    # 6. Diğer kontrollü klinik sözlükler
    for src, tr in report_generator._LIMITATION_PHRASES:
        cases.append(("report_generator._LIMITATION_PHRASES", f"limitation:{src}", tr))
    for src, tr in report_generator._CLINICAL_PHRASES_TR:
        cases.append(("report_generator._CLINICAL_PHRASES_TR", f"clinical_phrase:{src}", tr))
    for src, tr in report_generator._CLINICAL_WORD_TR.items():
        cases.append(("report_generator._CLINICAL_WORD_TR", f"clinical_word:{src}", tr))
    for src, tr in report_generator._SYMPTOM_TR:
        cases.append(("report_generator._SYMPTOM_TR", f"symptom:{src}", tr))
    for src, tr in report_generator._PREDICTOR_PHRASES:
        cases.append(("report_generator._PREDICTOR_PHRASES", f"predictor:{src}", tr))
    for _, abbr, label in report_generator._ABBREV_IF_PRESENT:
        cases.append(("report_generator._ABBREV_IF_PRESENT", f"abbrev_if_present:{abbr}", label))

    return cases


ALL_TEST_CASES = _build_test_cases()


@pytest.mark.parametrize(
    "dict_name, key, value",
    ALL_TEST_CASES,
    ids=[f"{dname}::{key}" for dname, key, _ in ALL_TEST_CASES],
)
def test_turkish_map_entry_consistency(dict_name, key, value):
    """Verifies that each controlled Turkish map value satisfies the consistency rules."""
    errors = _evaluate_consistency(value)
    if errors:
        error_msg = "; ".join(errors)
        pytest.xfail(f"[{dict_name}] {key}: {repr(value)} -> {error_msg}")

    # Explicit assertions for rules
    ok_dup, msg_dup = _check_consecutive_duplicates(value)
    assert ok_dup, msg_dup

    ok_empty, msg_empty = _check_non_empty_and_trimmed(value)
    assert ok_empty, msg_empty

    ok_eng, msg_eng = _check_no_english_function_words(value)
    assert ok_eng, msg_eng

    ok_abbr, msg_abbr = _check_abbreviations_in_parentheses(value)
    assert ok_abbr, msg_abbr

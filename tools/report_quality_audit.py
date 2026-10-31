#!/usr/bin/env python3
"""Report Quality Auditor for Turkish Evidence Synthesis Markdown reports.

Analyzes generated Markdown reports for clinical quality, language purity,
formatting consistency, and contradiction indicators.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Set


ENGLISH_FUNCTION_WORDS: Set[str] = {
    "the", "of", "and", "with", "was", "were", "patients", "in", "to", "for",
    "by", "is", "that", "this", "between", "study", "treatment", "results",
    "group", "from", "are", "which", "after", "not", "had", "have", "been",
    "also", "than", "or", "an", "at", "as", "we", "trial", "associated",
    "clinical", "compared", "efficacy", "safety", "risk", "hazard", "ratio",
    "incidence", "outcomes", "analysis", "cohort", "placebo", "significant",
    "significantly", "controlled", "randomized", "increase", "decrease"
}

P_VALUE_REGEX = re.compile(
    r"\b[pP]\s*([<=<>]|==|değeri)?\s*0?\.0\d+\b|"
    r"\b[pP]\s*<\s*0\.05\b|"
    r"\b[pP]\s*=\s*0\.0[0-4]\d*\b|"
    r"\b[pP]\s*=\s*0\.00\b|"
    r"\b[pP]\s*<0\.05\b"
)


def _strip_markdown_formatting(text: str) -> str:
    """Strip basic Markdown emphasis and links while preserving text."""
    # Replace markdown links [anchor](url) with anchor
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove bold / italic markers
    text = re.sub(r"[*_]{1,3}", "", text)
    # Remove backticks
    text = re.sub(r"`", "", text)
    return text.strip()


def _is_table_divider(line: str) -> bool:
    """Check if line is a markdown table separator like |---|---|."""
    clean = line.strip().strip("|")
    return bool(clean and all(c in "-: |" for c in clean))


def _extract_auditable_lines(report_text: str) -> List[tuple[int, str, str]]:
    """Return list of (line_num, line_text, block_name) skipping bibliography."""
    lines = report_text.splitlines()
    auditable: List[tuple[int, str, str]] = []
    current_block = "Giriş"
    in_bibliography = False

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        # Check section headers
        if line.startswith("#"):
            header_text = line.lstrip("#").strip()
            current_block = header_text
            # Identify bibliography / references section
            if re.search(r"\b(kaynakça|bibliyografya|references)\b", header_text, re.IGNORECASE):
                in_bibliography = True
            else:
                # If we encounter a new major numbered heading after bibliography, reset
                if re.match(r"^\d+\.", header_text) and not re.search(r"\b(kaynakça|bibliyografya)\b", header_text, re.IGNORECASE):
                    in_bibliography = False
            continue

        if in_bibliography:
            continue

        if _is_table_divider(line):
            continue

        auditable.append((idx, raw_line, current_block))

    return auditable


def check_raw_english_sentences(report_text: str) -> List[Dict[str, Any]]:
    """Detect raw English sentences outside allowed quote, source, bibliography, or title areas.

    Exclusions:
      - 'Kaynak cümle:' blocks or quotes
      - Direct quotes ("> ...", or text in double quotes)
      - Bibliography / references sections
      - Headers (#, ##, ###)
      - Citation links / author lines in tables if purely metadata
    """
    findings: List[Dict[str, Any]] = []
    auditable_lines = _extract_auditable_lines(report_text)

    for line_num, raw_line, block in auditable_lines:
        line = raw_line.strip()

        # Skip markdown quotes
        if line.startswith(">"):
            continue

        # Skip table headers
        if line.startswith("|") and any(h in line.lower() for h in ["pmid", "doi", "yazar", "çalışma", "tasarım"]):
            continue

        # Remove "Kaynak cümle: ..." patterns (e.g. Kaynak cümle: "...", Kaynak cümle yok)
        cleaned_line = re.sub(
            r'Kaynak\s+cümle\s*:\s*(\"[^\"]*\"|[^.,;\n]+)',
            "",
            line,
            flags=re.IGNORECASE,
        )
        cleaned_line = re.sub(r'Kaynak\s+cümle\s+yok[^.,;\n]*', "", cleaned_line, flags=re.IGNORECASE)

        # Remove direct quoted strings "...":
        cleaned_line = re.sub(r'\"[^\"]*\"', "", cleaned_line)
        cleaned_line = re.sub(r'\'[^\']*\'', "", cleaned_line)

        # Remove URLs and markdown links [text](url) -> if text was an english title, strip URLs
        cleaned_line = re.sub(r'https?://\S+', '', cleaned_line)
        cleaned_line = re.sub(r'\[PMID:[^\]]+\]\([^)]+\)', '', cleaned_line, flags=re.IGNORECASE)
        cleaned_line = re.sub(r'\[DOI:[^\]]+\]\([^)]+\)', '', cleaned_line, flags=re.IGNORECASE)
        cleaned_line = re.sub(r'PMID:\s*\d+', '', cleaned_line, flags=re.IGNORECASE)
        cleaned_line = re.sub(r'DOI:\s*10\.\d+/\S+', '', cleaned_line, flags=re.IGNORECASE)

        # Split into sentence-like segments
        # Split on '.', '!', '?', or ';' or '|'
        segments = re.split(r"(?<=[.!?|])\s+", cleaned_line)

        for segment in segments:
            seg = _strip_markdown_formatting(segment).strip()
            if len(seg) < 20:
                continue

            # Tokenize words
            words = [w.lower() for w in re.findall(r"\b[a-zA-ZçğıöşüÇĞİÖŞÜ]+\b", seg)]
            if len(words) < 5:
                continue

            eng_count = sum(1 for w in words if w in ENGLISH_FUNCTION_WORDS)
            eng_ratio = eng_count / len(words)

            # Heuristic: English sentence if ratio of English function words >= 0.20 and at least 3 English function words,
            # or >= 4 English function words.
            if (eng_count >= 3 and eng_ratio >= 0.20) or eng_count >= 4:
                # Double check that it's not a common Turkish boilerplate with medical terms
                tr_indicator_words = {"ve", "ile", "için", "olan", "bir", "bu", "de", "da", "çalışma", "hastalarında", "bulgular", "olarak"}
                tr_count = sum(1 for w in words if w in tr_indicator_words)
                if eng_count > tr_count * 2:
                    findings.append({
                        "line_num": line_num,
                        "block": block,
                        "text": seg,
                        "english_word_count": eng_count,
                        "ratio": round(eng_ratio, 2),
                    })

    return findings


def check_consecutive_duplicate_words(report_text: str) -> List[Dict[str, Any]]:
    """Detect consecutive repeated words (e.g. 'oranı oranı', 've ve')."""
    findings: List[Dict[str, Any]] = []
    lines = report_text.splitlines()

    # Pattern for adjacent words (case-insensitive)
    # Ignore numbers and single characters
    pattern = re.compile(r"\b([a-zA-ZçğıöşüÇĞİÖŞÜ]{2,})\s+\1\b", re.IGNORECASE)

    for idx, raw_line in enumerate(lines, start=1):
        line = _strip_markdown_formatting(raw_line)
        matches = pattern.finditer(line)
        for match in matches:
            word = match.group(1)
            # Filter out intentional Turkish reduplications if needed (e.g., 'yavaş yavaş', 'ayrı ayrı')
            if word.lower() in {"yavas", "yavaş", "ayri", "ayrı", "adim", "adım", "tek", "cok", "çok"}:
                continue
            findings.append({
                "line_num": idx,
                "repeated_word": word,
                "matched_text": match.group(0),
                "line": raw_line.strip(),
            })

    return findings


def check_duplicate_lines_in_block(report_text: str) -> List[Dict[str, Any]]:
    """Detect exact duplicate lines or bullet points within the same section/block."""
    findings: List[Dict[str, Any]] = []
    auditable_lines = _extract_auditable_lines(report_text)

    # Group lines by block
    blocks: Dict[str, List[tuple[int, str]]] = {}
    for line_num, line_text, block in auditable_lines:
        clean = line_text.strip()
        # Skip empty or very short or generic lines
        if len(clean) < 15 or _is_table_divider(clean):
            continue
        blocks.setdefault(block, []).append((line_num, clean))

    for block, items in blocks.items():
        seen: Dict[str, int] = {}
        for line_num, text in items:
            if text in seen:
                findings.append({
                    "block": block,
                    "first_seen_line": seen[text],
                    "duplicate_line": line_num,
                    "text": text,
                })
            else:
                seen[text] = line_num

    return findings


def check_unlabeled_number_lists(report_text: str) -> List[Dict[str, Any]]:
    """Detect unlabelled number sequences (e.g. '15 hasta; 15 hasta; 5 hasta' or '10; 20; 30')."""
    findings: List[Dict[str, Any]] = []
    lines = report_text.splitlines()

    # Repeated identical number with unit (e.g., "15 hasta; 15 hasta") or comma/semicolon series of numbers
    pattern1 = re.compile(
        r"\b(\d+\s*[a-zA-ZçğıöşüÇĞİÖŞÜ]+)\s*;\s*\1(?:\s*;\s*\d+\s*[a-zA-ZçğıöşüÇĞİÖŞÜ]+)*",
        re.IGNORECASE,
    )
    # Repeated unlabelled raw numbers: "15; 15; 5" or "15, 15, 5"
    pattern2 = re.compile(r"\b(\d+)\s*;\s*\1\s*;\s*\d+\b")

    for idx, raw_line in enumerate(lines, start=1):
        if pattern1.search(raw_line) or pattern2.search(raw_line):
            findings.append({
                "line_num": idx,
                "line": raw_line.strip(),
            })

    return findings


def check_significance_contradictions(report_text: str) -> List[Dict[str, Any]]:
    """Detect statistical contradictions within the same sentence or bullet item.

    Contradictions:
      - 'anlamlı bir fark saptanmamıştır' (or similar lack of difference) co-occurring with p < 0.05
      - 'değerlendirilemedi' co-occurring with p < 0.05 in the same sentence/item
    CRITICAL issue.
    """
    findings: List[Dict[str, Any]] = []
    lines = report_text.splitlines()

    not_significant_regex = re.compile(
        r"(anlamlı\s+(?:bir\s+)?fark\s+(?:saptanmamıştır|bulunmamıştır|yoktur|yok)|istatistiksel\s+olarak\s+anlamsız)",
        re.IGNORECASE,
    )
    # Contradiction where outcome/significance is stated as unevaluated while low p is provided
    # Avoid false matching 'kanıt düzeyi: Değerlendirilemedi' or 'Yanlılık riski: değerlendirilemedi'
    unevaluated_significance_regex = re.compile(
        r"(anlamlılık\s+değerlendirilemedi|(?:sonlanım|etki|istatistik)(?:\s+ve\s+istatistik)?:\s*değerlendirilemedi|değerlendirilemedi\s*\([^)]*p\s*[<==]\s*0\.0)",
        re.IGNORECASE,
    )

    for idx, raw_line in enumerate(lines, start=1):
        # Examine sentences within the line or the line itself
        # Bullet items or table cells can contain statements
        items = re.split(r"(?<=[.!?|])\s+", raw_line)
        for item in items:
            item_clean = item.strip()
            if not item_clean:
                continue

            has_p_sig = bool(P_VALUE_REGEX.search(item_clean))
            has_not_sig = bool(not_significant_regex.search(item_clean))
            has_unevaluated = bool(unevaluated_significance_regex.search(item_clean))

            if has_p_sig and has_not_sig:
                findings.append({
                    "line_num": idx,
                    "type": "not_significant_with_low_p",
                    "text": item_clean,
                    "critical": True,
                })
            elif has_p_sig and has_unevaluated:
                findings.append({
                    "line_num": idx,
                    "type": "unevaluated_with_low_p",
                    "text": item_clean,
                    "critical": True,
                })

    return findings


def check_raw_english_ci(report_text: str) -> List[Dict[str, Any]]:
    """Detect raw English CI terms ('confidence interval', 'CI') in Turkish GA contexts.

    Expected Turkish format is 'GA', '%95 GA', etc.
    """
    findings: List[Dict[str, Any]] = []
    auditable_lines = _extract_auditable_lines(report_text)

    # Looking for 'confidence interval' anywhere outside quotes, or 'CI' specifically where 'GA' is expected
    ci_pattern = re.compile(
        r"(\bconfidence\s+interval\b|(?:\b95%\s*CI\b)|(?:\bCI\s*:\s*[\d\.\-,\s]+\b)|(?:\bCI\s+[\d\.\-]+))",
        re.IGNORECASE,
    )

    for line_num, raw_line, block in auditable_lines:
        line = raw_line.strip()
        # Remove quotes
        line_no_quotes = re.sub(r'\"[^\"]*\"', '', line)
        line_no_quotes = re.sub(r'Kaynak\s+cümle\s*:.*', '', line_no_quotes, flags=re.IGNORECASE)

        matches = ci_pattern.findall(line_no_quotes)
        if matches:
            findings.append({
                "line_num": line_num,
                "block": block,
                "matches": matches,
                "line": raw_line.strip(),
            })

    return findings


def check_expert_review_claim(report_text: str) -> List[Dict[str, Any]]:
    """Detect claims that expert physician evaluation was done/completed.

    The expected statement is 'Yapılmadı' / 'yapılmamıştır'. Any claim of completion
    ('yapıldı', 'onaylandı', 'tamamlandı' for expert physician review) is a CRITICAL violation.
    """
    findings: List[Dict[str, Any]] = []
    lines = report_text.splitlines()

    claim_pattern = re.compile(
        r"uzman\s+hekim\s+(?:değerlendirmesi|incelemesi|görüşü|onayı)\s*:\s*(?!yapılmadı|yapılmamıştır)(?:yapıldı|tamamlandı|alındı|onaylandı|var)\b|"
        r"uzman\s+hekim\s+(?:değerlendirmesi|incelemesi|tarafından)\s+(?:yapılmıştır|tamamlanmıştır|onaylanmıştır)\b",
        re.IGNORECASE,
    )

    for idx, raw_line in enumerate(lines, start=1):
        if claim_pattern.search(raw_line):
            findings.append({
                "line_num": idx,
                "line": raw_line.strip(),
                "critical": True,
            })

    return findings


def audit_report_quality(report_text: str) -> Dict[str, Any]:
    """Execute all quality audit checks on a Markdown report string.

    Returns a dict with summary metrics, counts, and detailed findings.
    """
    english_sentences = check_raw_english_sentences(report_text)
    consecutive_words = check_consecutive_duplicate_words(report_text)
    duplicate_lines = check_duplicate_lines_in_block(report_text)
    unlabeled_numbers = check_unlabeled_number_lists(report_text)
    significance_contradictions = check_significance_contradictions(report_text)
    raw_english_ci = check_raw_english_ci(report_text)
    expert_review_claimed = check_expert_review_claim(report_text)

    critical_count = (
        len(significance_contradictions) +
        len(expert_review_claimed)
    )

    total_issues = (
        len(english_sentences) +
        len(consecutive_words) +
        len(duplicate_lines) +
        len(unlabeled_numbers) +
        len(significance_contradictions) +
        len(raw_english_ci) +
        len(expert_review_claimed)
    )

    return {
        "summary": {
            "total_issues": total_issues,
            "critical_issues": critical_count,
            "passed_critical": critical_count == 0,
        },
        "counts": {
            "raw_english_sentences": len(english_sentences),
            "consecutive_duplicate_words": len(consecutive_words),
            "duplicate_lines": len(duplicate_lines),
            "unlabeled_number_lists": len(unlabeled_numbers),
            "significance_contradictions": len(significance_contradictions),
            "raw_english_ci": len(raw_english_ci),
            "expert_review_claimed": len(expert_review_claimed),
        },
        "details": {
            "raw_english_sentences": english_sentences,
            "consecutive_duplicate_words": consecutive_words,
            "duplicate_lines": duplicate_lines,
            "unlabeled_number_lists": unlabeled_numbers,
            "significance_contradictions": significance_contradictions,
            "raw_english_ci": raw_english_ci,
            "expert_review_claimed": expert_review_claimed,
        },
    }


def main() -> int:
    """CLI entry point for report quality auditor."""
    parser = argparse.ArgumentParser(
        description="Audit Turkish Evidence Synthesis Markdown report for quality, consistency, and contradictions."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to report markdown file. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON audit result.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail (exit 1) on any issue, not just critical issues.",
    )

    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            print(f"Hata: Dosya okunamadı: {e}", file=sys.stderr)
            return 2
    else:
        if sys.stdin.isatty():
            parser.print_help()
            return 2
        content = sys.stdin.read()

    result = audit_report_quality(content)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=== RAPOR KALİTE DENETİM SONUCU ===")
        print(f"Toplam Sorun Sayısı: {result['summary']['total_issues']}")
        print(f"Kritik Sorun Sayısı: {result['summary']['critical_issues']}")
        print(f"Kritik Denetim Durumu: {'GEÇTİ' if result['summary']['passed_critical'] else 'BAŞARISIZ'}")
        print("\nSayım Detayları:")
        for k, v in result["counts"].items():
            print(f"  - {k}: {v}")

        if result["summary"]["critical_issues"] > 0:
            print("\n⚠️ KRİTİK İHLALLER:")
            for issue in result["details"]["significance_contradictions"]:
                print(f"  - [Anlamlılık Çelişkisi] Satır {issue['line_num']}: {issue['text']}")
            for issue in result["details"]["expert_review_claimed"]:
                print(f"  - [Uzman Hekim İddiası] Satır {issue['line_num']}: {issue['line']}")

    if args.strict:
        return 0 if result["summary"]["total_issues"] == 0 else 1
    return 0 if result["summary"]["passed_critical"] else 1


if __name__ == "__main__":
    sys.exit(main())

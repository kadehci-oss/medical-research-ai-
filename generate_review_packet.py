"""Prepare an expert-review packet. This does not perform the physician review.

The independent assessment in UZMAN_HEKIM_DEGERLENDIRME.md must be completed by
real specialists. This script only writes draft reports and a blank scoring CSV.
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from report_generator import generate_html_report, generate_turkish_evidence_report
from universal_evidence_engine import UniversalEvidenceEngine

# A starter set across specialties. It is not the protocol's frozen 30-question bank.
DEFAULT_QUESTIONS: List[Dict[str, str]] = [
    {"case_id": "KARD-01", "specialty": "Kardiyoloji", "query": "SGLT2 inhibitors vs placebo in HFpEF"},
    {"case_id": "ENDO-01", "specialty": "Endokrinoloji", "query": "GLP-1 agonists in type 2 diabetes"},
    {"case_id": "NORO-01", "specialty": "Nöroloji", "query": "thrombectomy for acute ischemic stroke"},
    {"case_id": "PSIK-01", "specialty": "Psikiyatri", "query": "psilocybin for major depressive disorder"},
    {"case_id": "HEMA-01", "specialty": "Hematoloji", "query": "CRISPR in sickle cell disease"},
    {"case_id": "COCU-01", "specialty": "Çocuk Nörolojisi", "query": "febrile seizure in children"},
    {"case_id": "ENFE-01", "specialty": "Enfeksiyon Hastalıkları", "query": "antibiotic stewardship in sepsis"},
    {"case_id": "GOGUS-01", "specialty": "Göğüs Hastalıkları", "query": "inhaled corticosteroids for COPD exacerbations"},
]

CSV_COLUMNS = [
    "vaka_id",
    "soru",
    "beklenen_uzmanlik",
    "rapor_markdown",
    "rapor_html",
    "arama_durumu",
    "pmid_listesi",
    "inceleyen_uzman_kodu",
    "tarih",
    "klinik_soru_ve_pico_0_2",
    "kaynak_kimligi_0_2",
    "iddia_kaynak_uyumu_0_2",
    "calisma_tasarimi_kanit_0_2",
    "guvenlik_uygulanabilirlik_0_2",
    "belirsizlik_ve_sinirlar_0_2",
    "kritik_hata_var_mi",
    "kritik_hata_aciklamasi",
    "uzman_degerlendirmesi",
    "uzman_adi",
    "kurum",
    "uzmanlik_alani",
    "imza",
]


def _safe_slug(case_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", case_id.strip())
    return slug or "vaka"


def _default_search(query: str, max_results: int) -> Dict[str, Any]:
    engine = UniversalEvidenceEngine()
    return engine.search_and_verify(query=query, max_results=max_results)


def _default_report(query: str, articles: List[Dict[str, Any]]) -> str:
    return generate_turkish_evidence_report(query, articles, api_key=None, use_llm=False)


def build_review_packet(
    output_dir: Path,
    questions: Sequence[Dict[str, str]],
    max_results: int = 5,
    pause_seconds: float = 0,
    search_fn: Optional[Callable[[str, int], Dict[str, Any]]] = None,
    report_fn: Optional[Callable[[str, List[Dict[str, Any]]], str]] = None,
) -> Path:
    """Write Markdown/HTML drafts and a blank scoring CSV. Scores stay empty."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    search = search_fn or _default_search
    report = report_fn or _default_report
    rows = []
    readme = [
        "# Uzman hekim inceleme paketi",
        "",
        "Bu klasör inceleme malzemesidir. Bağımsız uzman değerlendirmesi yapılmış değildir.",
        "Puan hücreleri boştur. Form ölçütleri `UZMAN_HEKIM_DEGERLENDIRME.md` ile aynıdır.",
        "Raporlar özet (abstract) düzeyindedir ve klinik onay iddiası taşımaz.",
        "",
    ]
    for index, item in enumerate(questions):
        if index and pause_seconds:
            time.sleep(pause_seconds)
        case_id = item.get("case_id") or f"VAKA-{index + 1:02d}"
        query = (item.get("query") or "").strip()
        specialty = item.get("specialty") or ""
        slug = _safe_slug(case_id)
        md_name = f"{slug}.md"
        html_name = f"{slug}.html"
        status = "ok"
        pmids: List[str] = []
        try:
            if not query:
                raise ValueError("Boş klinik soru.")
            found = search(query, max_results)
            articles = list(found.get("articles") or [])
            pmids = [str(art.get("pmid")) for art in articles if art.get("pmid")]
            if found.get("status") == "error" and not articles:
                status = "arama_hatasi"
                markdown = (
                    f"# {case_id}\n\nSorgu: {query}\n\n"
                    f"Arama hatası: {found.get('error', 'bilinmeyen hata')}\n\n"
                    "Bu dosya bir inceleme taslağıdır. Uzman değerlendirmesi yapılmamıştır.\n"
                )
                html = f"<h1>{case_id}</h1><p>Arama hatası. Uzman değerlendirmesi yapılmamıştır.</p>"
            else:
                markdown = report(query, articles)
                markdown += (
                    "\n\n---\n\n> Bu rapor uzman hekim değerlendirmesi için hazırlanmış bir taslaktır. "
                    "Uzman değerlendirmesi yapılmış değildir. Resmi GRADE değerlendirmesi Not Assessed durumundadır.\n"
                )
                html = generate_html_report(query, articles, markdown)
        except Exception as exc:
            status = "hata"
            markdown = (
                f"# {case_id}\n\nSorgu: {query}\n\nPaket üretiminde hata: {exc}\n\n"
                "Uzman değerlendirmesi yapılmamıştır.\n"
            )
            html = f"<h1>{case_id}</h1><p>Paket üretiminde hata. Uzman değerlendirmesi yapılmamıştır.</p>"
        (output_dir / md_name).write_text(markdown, encoding="utf-8")
        (output_dir / html_name).write_text(html, encoding="utf-8")
        rows.append({
            "vaka_id": case_id,
            "soru": query,
            "beklenen_uzmanlik": specialty,
            "rapor_markdown": md_name,
            "rapor_html": html_name,
            "arama_durumu": status,
            "pmid_listesi": " ".join(pmids),
            "inceleyen_uzman_kodu": "",
            "tarih": "",
            "klinik_soru_ve_pico_0_2": "",
            "kaynak_kimligi_0_2": "",
            "iddia_kaynak_uyumu_0_2": "",
            "calisma_tasarimi_kanit_0_2": "",
            "guvenlik_uygulanabilirlik_0_2": "",
            "belirsizlik_ve_sinirlar_0_2": "",
            "kritik_hata_var_mi": "",
            "kritik_hata_aciklamasi": "",
            "uzman_degerlendirmesi": "",
            "uzman_adi": "",
            "kurum": "",
            "uzmanlik_alani": "",
            "imza": "",
        })
        readme.append(f"- {case_id}: {query} → `{md_name}`")
    csv_path = output_dir / "puanlama.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "OKU.txt").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Boş puanlı uzman inceleme paketi üretir. İncelemeyi yapmaz.")
    parser.add_argument("--output", default="review_packet", help="Çıktı klasörü")
    parser.add_argument("--limit", type=int, default=len(DEFAULT_QUESTIONS), help="Kaç soru üretileceği")
    parser.add_argument("--max-results", type=int, default=5, help="Sorgu başına PubMed kaydı")
    parser.add_argument("--pause", type=float, default=2.0, help="Canlı NCBI çağrıları arasındaki bekleme (saniye)")
    args = parser.parse_args()
    questions = DEFAULT_QUESTIONS[: max(0, args.limit)]
    build_review_packet(
        Path(args.output),
        questions,
        max_results=args.max_results,
        pause_seconds=args.pause,
    )
    print(f"Paket yazıldı: {args.output} ({len(questions)} vaka). Uzman incelemesi yapılmamıştır.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

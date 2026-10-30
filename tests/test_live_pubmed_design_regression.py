"""Live PubMed regression. Skipped unless RUN_LIVE_PUBMED=1.

The offline suite does not call NCBI. Run this file on its own:

    RUN_LIVE_PUBMED=1 python -m pytest tests/test_live_pubmed_design_regression.py -q
"""
import os
import re
import unittest

import pytest

from pubmed_client import search_pubmed, verify_pmid
from report_generator import assess_risk_of_bias, classify_study_design

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBMED") != "1",
    reason="Gerçek PubMed çağrısı ayrı çalıştırılır. RUN_LIVE_PUBMED=1 gerekir.",
)

_RISK_DEGREE = re.compile(
    r"\b(low risk|high risk|some concerns|moderate risk|düşük risk|yüksek risk|orta risk)\b",
    re.IGNORECASE,
)

# Eight specialties, each tied to an NLM publication-type filter that the
# classifier must follow. Case series has no separate MeSH publication type.
# Publication-type filters that exist in PubMed, plus title words for designs
# that NLM does not store as their own publication type (cohort, cross-sectional,
# case-control, case series).
LIVE_CASES = [
    ("Kardiyoloji", 'heart failure AND "Randomized Controlled Trial"[pt]', {"rct"}),
    ("Nöroloji", "stroke cohort[ti]", {"cohort"}),
    ("Onkoloji", 'breast cancer AND "Meta-Analysis"[pt]', {"meta_analysis", "systematic_review_and_meta_analysis"}),
    ("Göğüs hastalıkları", 'asthma AND "Systematic Review"[pt] NOT "Meta-Analysis"[pt]', {"systematic_review", "systematic_review_and_meta_analysis"}),
    ("Endokrinoloji", "type 2 diabetes cross-sectional[ti]", {"cross_sectional"}),
    ("Enfeksiyon hastalıkları", "tuberculosis case-control[ti]", {"case_control"}),
    ("Romatoloji", 'rheumatoid arthritis AND "Case Reports"[pt]', {"case_report", "case_series"}),
    ("Kulak burun boğaz", 'otitis media AND "Practice Guideline"[pt]', {"guideline"}),
]


class TestLivePubMedDesignRegression(unittest.TestCase):
    def test_live_publication_types_do_not_receive_an_evidence_grade(self):
        failures = []
        for specialty, query, allowed_keys in LIVE_CASES:
            try:
                result = search_pubmed(query, max_results=1)
            except Exception as exc:  # noqa: BLE001 - the report must name the access barrier
                failures.append(f"{specialty}: PubMed erişim hatası: {exc}")
                continue
            if result.get("error") or result.get("status") == "error":
                failures.append(
                    f"{specialty}: PubMed erişim engeli: {result.get('error') or result.get('status')}"
                )
                continue
            articles = result.get("articles") or []
            if not articles:
                failures.append(f"{specialty}: PubMed kayıt döndürmedi ({query})")
                continue
            article = articles[0]
            design = classify_study_design(
                article.get("publication_types") or [],
                article.get("title") or "",
                article.get("abstract") or "",
            )
            rob = assess_risk_of_bias(article)
            pmid = article.get("pmid")
            if design["design_key"] not in allowed_keys:
                failures.append(
                    f"{specialty}: PMID {pmid} tasarımı {design['design_key']} "
                    f"(kabul edilen {sorted(allowed_keys)}); yayın türleri {article.get('publication_types')}"
                )
            if design["level"] != "Değerlendirilemedi":
                failures.append(f"{specialty}: PMID {pmid} kanıt düzeyi {design['level']}")
            if rob["overall_rating"] != "Değerlendirilmedi (Not Assessed)":
                failures.append(f"{specialty}: PMID {pmid} risk derecesi {rob['overall_rating']}")
            if _RISK_DEGREE.search(rob["overall_rating"] or ""):
                failures.append(f"{specialty}: PMID {pmid} için değerlendirmeden risk derecesi üretildi")
            if not rob.get("tool"):
                failures.append(f"{specialty}: PMID {pmid} için yanlılık aracı seçilmedi")
        if failures:
            self.fail("Gerçek PubMed regresyonu:\n" + "\n".join(failures))


# Statin-associated IMNM records. A generic Review tag must not hide a case report.
LIVE_IMNM_DESIGNS = {
    "33372889": "case_report",
    "36896367": "case_series",
    "41458822": "systematic_review",
    "35955495": "narrative_review",
    "32581543": "narrative_review",
}


class TestLiveImnmDesigns(unittest.TestCase):
    def test_live_imnm_pmids_keep_case_reports_out_of_reviews(self):
        failures = []
        for pmid, expected in LIVE_IMNM_DESIGNS.items():
            try:
                article = verify_pmid(pmid)
            except Exception as exc:  # noqa: BLE001 - report the access barrier
                failures.append(f"PMID {pmid}: PubMed erişim engeli: {exc}")
                continue
            if not isinstance(article, dict) or not article.get("valid"):
                error = article.get("error") if isinstance(article, dict) else article
                failures.append(f"PMID {pmid}: PubMed erişim engeli: {error}")
                continue
            design = classify_study_design(
                article.get("publication_types") or [],
                article.get("title") or "",
                article.get("abstract") or "",
            )
            if design["design_key"] != expected:
                failures.append(
                    f"PMID {pmid}: tasarım {design['design_key']} ({design['design']}), "
                    f"beklenen {expected}; yayın türleri {article.get('publication_types')}"
                )
            if expected in ("case_report", "case_series") and "Derleme" in design["design"]:
                failures.append(f"PMID {pmid} olgu kanıtı derleme olarak göründü: {design['design']}")
            if design["level"] != "Değerlendirilemedi":
                failures.append(f"PMID {pmid} kanıt düzeyi {design['level']}")
        if failures:
            self.fail("Gerçek PubMed IMNM regresyonu:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()

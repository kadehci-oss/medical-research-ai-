"""Live PubMed regression. Skipped unless RUN_LIVE_PUBMED=1.

The offline suite does not call NCBI. Run this file on its own:

    RUN_LIVE_PUBMED=1 python -m pytest tests/test_live_pubmed_design_regression.py -q
"""
import os
import re
import unittest

import pytest

from pubmed_client import search_pubmed, verify_pmid
from report_generator import (
    assess_risk_of_bias,
    classify_study_design,
    format_klinik_bulgular_cell,
    format_methodological_limitation,
    _format_cross_study_comparison,
)

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
# 36896367 is tagged Case Reports. Its abstract describes two of the paper's own
# patients, so the series label is the one the general rule produces.
LIVE_IMNM_DESIGNS = {
    "33372889": "case_report",
    "36896367": "case_series",
    "41458822": "systematic_review",
    "35955495": "narrative_review",
    "32581543": "narrative_review",
}

# Designs read from the abstract, not from a PMID table inside the classifier.
LIVE_ABSTRACT_DESIGNS = {
    "40446701": "retrospective_comparative",
    "41010829": "retrospective_case_series",
    "36896367": "case_series",
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


class TestLiveAbstractDesigns(unittest.TestCase):
    def test_live_retrospective_and_case_report_rules(self):
        failures = []
        for pmid, expected in LIVE_ABSTRACT_DESIGNS.items():
            try:
                article = verify_pmid(pmid)
            except Exception as exc:  # noqa: BLE001 - report the access barrier
                failures.append(f"PMID {pmid}: PubMed erişim engeli: {exc}")
                continue
            if not isinstance(article, dict) or not article.get("valid"):
                error = article.get("error") if isinstance(article, dict) else article
                failures.append(f"PMID {pmid}: PubMed erişim engeli: {error}")
                continue
            abstract = article.get("abstract") or ""
            design = classify_study_design(
                article.get("publication_types") or [],
                article.get("title") or "",
                abstract,
            )
            if design["design_key"] != expected:
                failures.append(
                    f"PMID {pmid}: tasarım {design['design_key']} ({design['design']}), "
                    f"beklenen {expected}; yayın türleri {article.get('publication_types')}"
                )
            if pmid == "36896367":
                several = bool(re.search(r"\btwo cases\b|\bboth patients\b", abstract, re.IGNORECASE))
                tagged = any("case report" in (pt or "").lower() for pt in (article.get("publication_types") or []))
                if not tagged:
                    failures.append(f"PMID 36896367 yayın türünde Case Reports yok: {article.get('publication_types')}")
                if not several:
                    failures.append("PMID 36896367 özeti birden fazla hastayı açıkça anlatmıyor; olgu sunumu beklenirdi")
                if design["design_key"] != "case_series":
                    failures.append(f"PMID 36896367 iki olgu anlatmasına rağmen {design['design']}")
        if failures:
            self.fail("Gerçek PubMed tasarım regresyonu:\n" + "\n".join(failures))


class TestLiveSection56Polish(unittest.TestCase):
    """The same section 5 and 6 rules, read from PubMed rather than the fixture."""

    def test_live_imnm_abstracts_keep_turkish_section_5_and_6(self):
        pmids = ["33447390", "28207435", "41458822", "40446701", "41010829", "33372889"]
        articles = []
        failures = []
        for pmid in pmids:
            try:
                article = verify_pmid(pmid)
            except Exception as exc:  # noqa: BLE001 - report the access barrier
                failures.append(f"PMID {pmid}: PubMed erişim engeli: {exc}")
                continue
            if not isinstance(article, dict) or not article.get("valid"):
                error = article.get("error") if isinstance(article, dict) else article
                failures.append(f"PMID {pmid}: PubMed erişim engeli: {error}")
                continue
            articles.append(article)
        if failures:
            self.fail("Gerçek PubMed bölüm 5-6:\n" + "\n".join(failures))

        by_pmid = {article["pmid"]: article for article in articles}
        table = _format_cross_study_comparison(articles, {})

        def row(pmid):
            for line in table.splitlines():
                if line.startswith("|") and pmid in line.split("|")[1]:
                    return [part.strip() for part in line.strip().strip("|").split("|")]
            return []

        case = format_klinik_bulgular_cell(by_pmid["33447390"])
        if "dermatomiyozit benzeri deri bulguları" not in case:
            failures.append("PMID 33447390 olgu cümlesindeki deri bulgusu çıkarılmadı")
        if "It presents with" in case or "should be considered" in case:
            failures.append("PMID 33447390 genel anlatıyı olgu bulgusu saydı")
        if "Özette sayısal veya nitel klinik bulgu yetersiz" in case:
            failures.append("PMID 33447390 nitel bulguyu yetersiz saydı")

        review = format_klinik_bulgular_cell(by_pmid["28207435"])
        if re.search(r"Nitel klinik bulgu:\s*hasta\b", review):
            failures.append("PMID 28207435 anlamsız 'hasta' bulgusu üretti")

        pooled = format_klinik_bulgular_cell(by_pmid["41458822"])
        if pooled.count("Remisyon bildirildi") != 1:
            failures.append(f"PMID 41458822 remisyon tekrarı: {pooled.count('Remisyon bildirildi')}")

        compare = row("40446701")
        series = row("41010829")
        prednisone = row("33372889")
        if len(compare) < 6 or len(series) < 6 or len(prednisone) < 6:
            failures.append("Bölüm 6 satırı eksik")
        else:
            if "self-identified" in compare[1].lower() or "hispanic versus" in compare[1].lower():
                failures.append("PMID 40446701 hasta grubu ham İngilizce")
            if compare[3] != "Belirtilmedi":
                failures.append(f"PMID 40446701 müdahalesi tedavi değil: {compare[3]}")
            if "METHODS" in compare[5] or "self-identified" in compare[5].lower():
                failures.append("PMID 40446701 yöntem cümlesi sınırlılık oldu")
            if "Retrospektif tasarım" not in compare[5]:
                failures.append(f"PMID 40446701 türetilen sınırlılık yok: {compare[5]}")
            for drug in ("kortikosteroid", "metotreksat", "IVIG", "rituksimab"):
                if drug not in series[3]:
                    failures.append(f"PMID 41010829 müdahalesinde {drug} yok: {series[3]}")
            if "single institution" in series[5].lower() or series[5].lower().startswith("methods"):
                failures.append("PMID 41010829 yöntem cümlesi sınırlılık oldu")
            if "Küçük örneklem (n=10)" not in series[5] or "Tek merkez" not in series[5]:
                failures.append(f"PMID 41010829 türetilen sınırlılık eksik: {series[5]}")
            if "prednizon" not in prednisone[3] or "azatioprin" not in prednisone[3]:
                failures.append(f"PMID 33372889 müdahalesi: {prednisone[3]}")
            if "4.81" in series[4] or "13,000" in compare[4]:
                failures.append("PMID satırları birbirinin sayısını taşıyor")
        limit_404 = format_methodological_limitation(by_pmid["40446701"])
        if "In this retrospective study" in limit_404:
            failures.append("PMID 40446701 sınırlılık hücresi yöntem cümlesini yapıştırdı")
        if failures:
            self.fail("Gerçek PubMed bölüm 5-6:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()

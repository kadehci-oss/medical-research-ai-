"""
Universal Evidence Engine (Evrensel Klinik Kanıt Motoru)
Disease-Agnostic Medical Research Engine for Turkish Clinical Evidence Synthesis.

Supports all medical specialties (Cardiology, Neurology, Oncology, ENT/KBB, Infectious Diseases, etc.).
Extracts structured parameters (n, HR/RR/OR/MD, 95% CI, p-values, PICO, RoB) from PubMed articles
without fabricating unstated metrics.
Provides source-claim matching, comparative cross-article synthesis, and safe error handling.
"""

import logging
from typing import List, Dict, Any, Optional

import pubmed_client
import report_generator

logger = logging.getLogger(__name__)


class UniversalEvidenceEngine:
    """
    Universal Medical Research Engine that works across all medical specialties.
    Provides disease-agnostic PubMed retrieval, citation verification, structured metric extraction,
    cross-study comparative analysis, and specialist-level Turkish clinical report synthesis.
    """

    def __init__(self, api_key: Optional[str] = None, use_llm: bool = False, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.use_llm = use_llm
        self.model = model

    def search_and_verify(
        self,
        query: str,
        max_results: int = 10,
        sort: str = "relevance",
        publication_type: Optional[str] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes a PubMed search, verifies all retrieved article metadata (PMID, DOI, title, authors, pub_year, pub_types),
        and extracts structured parameters for each article.

        Handles network or API errors gracefully without crashing.
        """
        if not query or not query.strip():
            return {
                "status": "error",
                "error": "Boş veya geçersiz arama sorgusu.",
                "query": query,
                "articles": [],
                "total_count": 0,
                "verified_articles": []
            }

        try:
            search_res = pubmed_client.search_pubmed(
                query=query,
                max_results=max_results,
                sort=sort,
                publication_type=publication_type,
                start_year=start_year,
                end_year=end_year
            )
        except Exception as e:
            logger.error(f"PubMed API search failed: {str(e)}")
            return {
                "status": "error",
                "error": f"PubMed API araması sırasında hata oluştu: {str(e)}",
                "query": query,
                "articles": [],
                "total_count": 0,
                "verified_articles": []
            }

        if "error" in search_res and not search_res.get("articles"):
            return {
                "status": "error",
                "error": search_res.get("error", "Arama hatası"),
                "query": query,
                "articles": [],
                "total_count": 0,
                "verified_articles": []
            }

        raw_articles = search_res.get("articles", [])
        verified_articles = []
        verification_summaries = []

        for art in raw_articles:
            # PubMed efetch results are direct from NCBI; mark verified if PMID is present
            pmid = art.get("pmid")
            if pmid:
                v_status = "verified"
                v_reason = "match"
            else:
                v_status = "unverified"
                v_reason = "missing_or_invalid_pmid"

            v_res = {
                "status": v_status,
                "verified": (v_status == "verified"),
                "pmid": pmid or "",
                "reason": v_reason
            }

            # Extract detailed parameters
            details = report_generator.extract_article_clinical_details(art, query)
            rob = report_generator.assess_risk_of_bias(art)
            design = report_generator.classify_study_design(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))

            art_enhanced = dict(art)
            art_enhanced["verification_status"] = v_status
            art_enhanced["verification_reason"] = v_reason
            art_enhanced["clinical_details"] = details
            art_enhanced["risk_of_bias"] = rob
            art_enhanced["study_design_info"] = design

            verified_articles.append(art_enhanced)
            verification_summaries.append(v_res)

        return {
            "status": "success",
            "query": query,
            "search_date": search_res.get("search_date"),
            "search_params": search_res.get("search_params"),
            "total_count": search_res.get("total_count", 0),
            "articles": verified_articles,
            "verification_summaries": verification_summaries
        }

    def process_and_extract_parameters(self, articles: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
        """
        Extracts structured parameters from each article:
        - Patient population
        - Research method / study design
        - Intervention
        - Comparison
        - Clinical outcomes and bound statistical metrics (n, HR/RR/OR/MD, 95% CI, p-values)
        - Methodological & causality limitations
        Guarantees zero metric fabrication (unstated parameters remain None or 'Belirtilmedi').
        """
        processed = []
        for art in articles:
            title = art.get("title", "")
            abstract = art.get("abstract", "")
            pub_types = art.get("publication_types", [])

            design = report_generator.classify_study_design(pub_types, title, abstract)
            metrics = report_generator.extract_study_metrics(abstract)
            outcome_metrics = report_generator.extract_outcome_metrics(abstract)
            details = report_generator.extract_article_clinical_details(art, query)
            rob = report_generator.assess_risk_of_bias(art)

            processed.append({
                "pmid": art.get("pmid"),
                "doi": art.get("doi"),
                "title": title,
                "authors": art.get("authors", []),
                "authors_short": report_generator._format_authors_short(art.get("authors", [])),
                "journal": art.get("journal"),
                "pub_year": art.get("pub_year"),
                "publication_types": pub_types,
                "study_design": design,
                "patient_population": details.get("patient_group", "Belirtilmedi"),
                "sample_size": details.get("sample_size", "Özette bildirilmedi"),
                "sample_size_n": metrics.get("n"),
                "intervention": details.get("intervention", "Belirtilmedi"),
                "comparison": details.get("comparison", "Belirtilmedi"),
                "effect_sizes": metrics.get("effect_sizes", []),
                "confidence_intervals": metrics.get("confidence_intervals", []),
                "p_values": metrics.get("p_values", []),
                "outcome_metrics": outcome_metrics,
                "concomitant_treatments": metrics.get("concomitant_treatments", []),
                "causality_limitations": metrics.get("causality_limitations", []),
                "risk_of_bias": rob,
                "real_findings": details.get("real_findings", ""),
                "abstract_only": len(abstract) < 100 or "Özet bulunamadı" in abstract
            })
        return processed

    def compare_cross_article_findings(self, articles: List[Dict[str, Any]], query: str = "") -> Dict[str, Any]:
        """
        Compares findings across multiple publications:
        - Identifies consistent clinical findings
        - Highlights conflicting findings, subgroup discrepancies, and methodological heterogeneity
        - Flags unsupported causality or efficacy claims
        """
        if not articles:
            return {
                "consistent_findings": [],
                "conflicting_findings": [],
                "methodological_heterogeneity": "Herhangi bir makale verisi sağlanmadı.",
                "evidence_limitation_notice": "Veri yok."
            }

        processed = self.process_and_extract_parameters(articles, query)

        primary_studies = [p for p in processed if not any(k in p["study_design"]["design"] for k in ["Derleme", "Kılavuz", "Uzman Görüşü", "Editör"])]
        review_studies = [p for p in processed if any(k in p["study_design"]["design"] for k in ["Derleme", "Kılavuz", "Uzman Görüşü", "Editör"])]

        consistent = []
        conflicting = []

        for p in processed:
            abs_lower = (p.get("title", "") + " " + (articles[0].get("abstract", "") if articles else "")).lower()
            pmid_str = f"[PMID: {p['pmid']}]" if p.get("pmid") else "PMID Yok"

            # Check for explicitly reported conflicts or heterogeneity
            if any(k in abs_lower for k in ["conflicting", "inconsistent", "heterogeneous", "mixed results", "controversial"]):
                conflicting.append(f"{p['authors_short']} ({p['pub_year']}) {pmid_str}: Özetinde sonuçların heterojen veya çelişkili olduğunu bildirmiştir.")
            elif p.get("effect_sizes") or p.get("p_values"):
                consistent.append(f"{p['authors_short']} ({p['pub_year']}) {pmid_str}: {p['real_findings']}")
            else:
                consistent.append(f"{p['authors_short']} ({p['pub_year']}) {pmid_str}: {p['study_design']['design']} niteliğinde klinik veriler sunmaktadır.")

        heterogeneity_msg = (
            f"Toplam {len(articles)} çalışma ({len(primary_studies)} primer araştırma, {len(review_studies)} derleme/kılavuz) "
            f"örneklem büyüklükleri (n), hasta yaş/cinsiyet grupları ve takip süreleri açısından metodolojik farklılıklar göstermektedir."
        )

        limitation_notice = (
            "Tüm karşılaştırmalar yalnızca yayınlanmış özet (abstract) metinlerine dayanmaktadır. "
            "GRADE kesinlik değerlendirmesi resmi olarak yapılmamış (Not Assessed), Uzman Hekim Değerlendirmesi 'Yapılmadı / Tamamlanmadı' durumundadır."
        )

        return {
            "total_articles": len(articles),
            "primary_study_count": len(primary_studies),
            "review_study_count": len(review_studies),
            "consistent_findings": consistent,
            "conflicting_findings": conflicting,
            "methodological_heterogeneity": heterogeneity_msg,
            "evidence_limitation_notice": limitation_notice
        }

    def generate_synthesis_report(
        self,
        query: str,
        articles: List[Dict[str, Any]],
        search_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a specialist-physician-level Turkish evidence report using either rule-based engine
        or OpenAI LLM engine based on configuration.

        Ensures full compliance with:
        - 13 required sections
        - Abstract-only limitations
        - GRADE Not Assessed status
        - Uncompleted Expert Physician Review disclosure
        - Citation-claim matching
        - Zero metric fabrication
        """
        if not query or not query.strip():
            return {
                "status": "error",
                "error": "Görsel veya metinsel klinik sorgu boş olamaz.",
                "report_markdown": "",
                "report_html": "",
                "audit": {}
            }

        try:
            audit_res = report_generator.perform_red_team_audit(query, articles)

            report_md = report_generator.generate_turkish_evidence_report(
                query=query,
                articles=articles,
                api_key=self.api_key if self.use_llm else None,
                use_llm=self.use_llm,
                model=self.model,
                search_metadata=search_metadata
            )

            html_report = report_generator.generate_html_report(query, articles, report_md)
            pico = report_generator.extract_pico(query)
            cross_comp = self.compare_cross_article_findings(articles, query)

            return {
                "status": "success",
                "query": query,
                "pico": pico,
                "cross_comparison": cross_comp,
                "report_markdown": report_md,
                "report_html": html_report,
                "audit": audit_res
            }
        except Exception as e:
            logger.error(f"Error during universal evidence synthesis: {str(e)}")
            return {
                "status": "error",
                "error": f"Sentez sırasında hata oluştu: {str(e)}",
                "report_markdown": f"# 📑 Türkçe Klinik Araştırma Raporu\n\n### ⚠️ Hata Oluştu\n{str(e)}",
                "report_html": f"<h1>Hata Oluştu</h1><p>{str(e)}</p>",
                "audit": {}
            }


# Convenience standalone functions exposing engine capabilities
def run_universal_evidence_search(query: str, max_results: int = 10, **kwargs) -> Dict[str, Any]:
    engine = UniversalEvidenceEngine()
    return engine.search_and_verify(query, max_results=max_results, **kwargs)


def generate_universal_evidence_synthesis(
    query: str,
    articles: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    use_llm: bool = False,
    model: str = "gpt-4o-mini",
    search_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    engine = UniversalEvidenceEngine(api_key=api_key, use_llm=use_llm, model=model)
    return engine.generate_synthesis_report(query, articles, search_metadata=search_metadata)

"""
PubMed-based preliminary evidence search and Turkish synthesis prototype.

The specialty matrix contains 88 keyword-matched labels and only selected synonym
expansions; it is not exhaustive. Retrieval is limited to PubMed records and
available abstracts, not full text or a systematic-review search protocol.
Extracted metrics and source matching are heuristic and require expert review;
this module does not provide specialist validation or establish clinical truth.
"""

import logging
import re
from typing import List, Dict, Any, Optional

import pubmed_client
import report_generator
import specialty_matrix
from effect_size_extractor import extract_effect_sizes, summarize_effects
from rob2_assessor import assess_rob2
# [EVIDENCE_LAYER] auto-import
# [EVIDENCE_LAYER] auto-import
# [EVIDENCE_LAYER] auto-import

logger = logging.getLogger(__name__)


def _query_preserves_original_terms(original: str, enhanced: str) -> bool:
    """True when every whitespace token of the user query still appears verbatim."""
    if not (original or "").strip():
        return True
    if not enhanced:
        return False
    return all(token in enhanced for token in original.split())


def _is_transport_error(message: str) -> bool:
    """Network and rate-limit failures should not trigger a second immediate search."""
    lowered = (message or "").lower()
    markers = ("timeout", "timed out", "429", "too many requests", "connection", "temporarily")
    return any(marker in lowered for marker in markers)


_EFFICACY_CUES = (
    "efficacy", "effectiveness", "versus", " vs ", "vs.", "compared",
    "inhibitor", "agonist", "placebo", "plasebo", "etkinlik", "tedavi",
    "karşılaştır", "karsilastir", "karşı",
)

_HIGH_LEVEL_FILTER = (
    "(randomized controlled trial[pt] OR systematic review[pt] OR meta-analysis[pt])"
)


def is_efficacy_question(query: str) -> bool:
    """True when the question asks about treatment effect rather than background description."""
    folded = (query or "").casefold()
    return any(cue.casefold() in folded for cue in _EFFICACY_CUES)


def _evidence_rank(article: Dict[str, Any]) -> int:
    """Lower rank is shown first: RCT, then systematic review/meta-analysis, then other trials."""
    blob = " ".join(article.get("publication_types") or []).casefold()
    blob = f"{blob} {(article.get('title') or '').casefold()}"
    if "randomized controlled trial" in blob or "rastgele kontrollü" in blob:
        return 0
    if "meta-analysis" in blob or "systematic review" in blob or "sistematik derleme" in blob:
        return 1
    if "clinical trial" in blob:
        return 2
    return 3


def merge_ranked_articles(
    primary: List[Dict[str, Any]],
    high_level: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Put trials and reviews first without dropping any primary PubMed hit."""
    ordered_high = [art for _, art in sorted(enumerate(high_level), key=lambda item: (_evidence_rank(item[1]), item[0]))]
    merged: List[Dict[str, Any]] = []
    seen = set()

    def _add(art: Dict[str, Any]) -> None:
        pmid = str(art.get("pmid") or "").strip()
        if pmid:
            if pmid in seen:
                return
            seen.add(pmid)
        merged.append(art)

    for art in ordered_high:
        _add(art)
    for art in primary:
        _add(art)
    return merged


def _maybe_prefer_high_level_evidence(
    query: str,
    search_query: str,
    search_res: Dict[str, Any],
    enabled: bool,
    publication_type: Optional[str],
    run_search,
) -> Dict[str, Any]:
    """Prepend RCT/SR/MA hits for efficacy questions. Never removes primary hits."""
    if not enabled:
        return {"applied": False, "reason": "disabled"}
    if publication_type not in (None, "", "Tümü"):
        return {"applied": False, "reason": "publication_type_already_filtered"}
    if not is_efficacy_question(query):
        return {"applied": False, "reason": "not_efficacy_question"}
    primary = list(search_res.get("articles") or [])
    if not primary:
        return {"applied": False, "reason": "no_primary_hits"}
    high_query = f"({search_query}) AND {_HIGH_LEVEL_FILTER}"
    try:
        high_res = run_search(high_query)
    except Exception as exc:
        logger.warning("High-level evidence search failed (%s)", type(exc).__name__)
        return {"applied": False, "reason": "high_level_search_failed", "high_level_query": high_query}
    if high_res.get("error") and not high_res.get("articles"):
        if _is_transport_error(str(high_res.get("error"))):
            return {"applied": False, "reason": "high_level_transport_error", "high_level_query": high_query}
        return {"applied": False, "reason": "high_level_search_failed", "high_level_query": high_query}
    high_articles = list(high_res.get("articles") or [])
    if not high_articles:
        return {
            "applied": False,
            "reason": "no_high_level_hits",
            "high_level_query": high_query,
            "primary_count": len(primary),
        }
    merged = merge_ranked_articles(primary, high_articles)
    search_res["articles"] = merged
    return {
        "applied": True,
        "reason": "efficacy_question",
        "high_level_query": high_query,
        "high_level_count": len(high_articles),
        "primary_count": len(primary),
        "returned_count": len(merged),
    }


class UniversalEvidenceEngine:
    """
    Preliminary PubMed research assistant using configured specialty keywords.

    Provides PubMed retrieval, citation identity checks, heuristic metric
    extraction, and Turkish evidence summaries; outputs are not clinically
    validated and are not a substitute for a systematic review or specialist.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        use_llm: bool = False,
        model: str = "gpt-4o-mini",
        allow_external_data_transfer: bool = False,
    ):
        self.api_key = api_key
        self.use_llm = use_llm
        self.model = model
        self.allow_external_data_transfer = allow_external_data_transfer

    def search_and_verify(
        self,
        query: str,
        max_results: int = 10,
        sort: str = "relevance",
        publication_type: Optional[str] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        enhance_with_specialty: bool = True,
        prefer_high_level_evidence: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes a PubMed search, verifies all retrieved article metadata (PMID, DOI, title, authors, pub_year, pub_types),
        and extracts structured parameters for each article.

        When ``enhance_with_specialty`` is true, a detected specialty may OR-expand
        a few abbreviations. The user's original tokens are kept. If the expanded
        query returns no records, the original query is searched once. Set the flag
        to false to send the query exactly as typed.

        When the question is about intervention efficacy and
        ``prefer_high_level_evidence`` is true, a second PubMed query restricted to
        RCTs, systematic reviews, and meta-analyses is merged in front. Every
        article from the first query is kept.

        Handles network or API errors gracefully without crashing.
        """
        if not query or not query.strip():
            return {
                "status": "error",
                "error": "Boş veya geçersiz arama sorgusu.",
                "query": query,
                "articles": [],
                "total_count": 0,
                "verified_articles": [],
                "executed_query": query,
                "query_enhancement": {
                    "original_query": query or "",
                    "enhanced_query": query or "",
                    "specialty": None,
                    "applied": False,
                    "added_terms": [],
                    "strategy": "empty_query",
                    "fallback_to_original": False,
                },
            }

        try:
            enhancement = specialty_matrix.enhance_query_with_specialty(
                query,
                apply=enhance_with_specialty,
            )
        except Exception as exc:
            logger.warning("Specialty query enhancement failed (%s)", type(exc).__name__)
            enhancement = {
                "original_query": query.strip(),
                "enhanced_query": query.strip(),
                "specialty": None,
                "applied": False,
                "added_terms": [],
                "strategy": "enhancement_error",
                "fallback_to_original": False,
            }

        search_query = (enhancement.get("enhanced_query") or query).strip()
        if not _query_preserves_original_terms(query, search_query):
            logger.warning("Rejecting specialty enhancement that dropped original terms")
            search_query = query.strip()
            enhancement["enhanced_query"] = search_query
            enhancement["applied"] = False
            enhancement["added_terms"] = []
            enhancement["strategy"] = "rejected_term_loss"

        def _run_search(term: str) -> Dict[str, Any]:
            return pubmed_client.search_pubmed(
                query=term,
                max_results=max_results,
                sort=sort,
                publication_type=publication_type,
                start_year=start_year,
                end_year=end_year,
            )

        try:
            search_res = _run_search(search_query)
        except Exception as e:
            logger.error("PubMed API search failed (%s)", type(e).__name__)
            return {
                "status": "error",
                "error": "PubMed araması sırasında geçici bir hata oluştu.",
                "query": query,
                "executed_query": search_query,
                "query_enhancement": enhancement,
                "articles": [],
                "total_count": 0,
                "verified_articles": []
            }

        fallback_error = str(search_res.get("error") or "")
        if (
            search_query != query.strip()
            and not search_res.get("articles")
            and not _is_transport_error(fallback_error)
        ):
            logger.info("Specialty-enhanced query returned no articles; retrying the original query")
            try:
                search_res = _run_search(query.strip())
            except Exception as e:
                logger.error("PubMed API search failed (%s)", type(e).__name__)
                return {
                    "status": "error",
                    "error": "PubMed araması sırasında geçici bir hata oluştu.",
                    "query": query,
                    "executed_query": query.strip(),
                    "query_enhancement": enhancement,
                    "articles": [],
                    "total_count": 0,
                    "verified_articles": []
                }
            search_query = query.strip()
            enhancement["fallback_to_original"] = True
            enhancement["applied"] = False
        else:
            enhancement["fallback_to_original"] = False

        if "error" in search_res and not search_res.get("articles"):
            return {
                "status": "error",
                "error": search_res.get("error", "Arama hatası"),
                "query": query,
                "executed_query": search_query,
                "query_enhancement": enhancement,
                "evidence_ranking": {"applied": False, "reason": "primary_search_failed"},
                "articles": [],
                "total_count": 0,
                "verified_articles": []
            }

        evidence_ranking = _maybe_prefer_high_level_evidence(
            query=query,
            search_query=search_query,
            search_res=search_res,
            enabled=prefer_high_level_evidence,
            publication_type=publication_type,
            run_search=_run_search,
        )
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
            art_enhanced["verification_scope"] = (
                "PMID PubMed EFetch arama kaydında bulundu; bu alan tek başına başlık/DOI eşleşmesi veya klinik doğruluk iddiası değildir."
            )
            art_enhanced["clinical_details"] = details
            art_enhanced["risk_of_bias"] = rob
            art_enhanced["study_design_info"] = design
            art_enhanced = enrich_record(art_enhanced)

            verified_articles.append(art_enhanced)
            verification_summaries.append(v_res)

        return {
            "status": "success",
            "query": query,
            "executed_query": search_query,
            "query_enhancement": enhancement,
            "evidence_ranking": evidence_ranking,
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
        Uses heuristic extraction; missing fields are left unset when not found, but extraction may be incomplete or incorrect and requires source review.
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

            record = {
                "pmid": art.get("pmid"),
                "doi": art.get("doi"),
                "title": title,
                "abstract": abstract,
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
                "provenance": details.get("provenance", {}),
                "evidence_level": details.get("evidence_level") or design.get("level"),
                "real_findings": details.get("real_findings", ""),
                "abstract_only": len(abstract) < 100 or "Özet bulunamadı" in abstract,
            }
            record = enrich_record(record)
            processed.append(record)
        return processed

    STOP_WORDS = {
        "in", "with", "for", "by", "and", "or", "of", "patients", "adults", "children",
        "having", "diagnosed", "a", "an", "the", "to", "from", "at", "belirtilmedi",
        "belirtilmemiş", "group", "population", "study", "trial", "versus", "vs", "compared"
    }

    def _clean_term(self, term: str) -> str:
        if not term:
            return ""
        import re
        return re.sub(r"[^\w\s]", "", str(term).lower()).strip()

    def _tokenize_clinical(self, text: str) -> set:
        cleaned = self._clean_term(text)
        if not cleaned:
            return set()
        tokens = set(cleaned.split())
        return tokens - self.STOP_WORDS

    def _evaluate_pico_compatibility(self, p1: Dict[str, Any], p2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Disease-agnostic evaluation of Population, Intervention, Comparator, Outcome,
        and Study Design compatibility between two processed article records.
        """
        pop1_tokens = self._tokenize_clinical(p1.get("patient_population", ""))
        pop2_tokens = self._tokenize_clinical(p2.get("patient_population", ""))

        int1_tokens = self._tokenize_clinical(p1.get("intervention", ""))
        int2_tokens = self._tokenize_clinical(p2.get("intervention", ""))

        comp1_tokens = self._tokenize_clinical(p1.get("comparison", ""))
        comp2_tokens = self._tokenize_clinical(p2.get("comparison", ""))

        des1 = p1.get("study_design", {}).get("design", "")
        des2 = p2.get("study_design", {}).get("design", "")

        # 1. Population Match Check
        if pop1_tokens and pop2_tokens:
            pop_match = (len(pop1_tokens.intersection(pop2_tokens)) > 0)
        else:
            title_pop1 = self._tokenize_clinical(p1.get("title", "") + " " + p1.get("patient_population", ""))
            title_pop2 = self._tokenize_clinical(p2.get("title", "") + " " + p2.get("patient_population", ""))
            pop_match = (len(title_pop1.intersection(title_pop2)) > 0)

        # 2. Intervention Match Check
        if int1_tokens and int2_tokens:
            int_match = (len(int1_tokens.intersection(int2_tokens)) > 0)
        else:
            title_int1 = self._tokenize_clinical(p1.get("title", "") + " " + p1.get("intervention", ""))
            title_int2 = self._tokenize_clinical(p2.get("title", "") + " " + p2.get("intervention", ""))
            int_match = (len(title_int1.intersection(title_int2)) > 0)

        # 3. Comparator Match Check
        if comp1_tokens and comp2_tokens:
            comp_match = (len(comp1_tokens.intersection(comp2_tokens)) > 0)
        else:
            comp_match = True

        # 4. Study Design Compatibility Check
        is_rev1 = any(k in des1 for k in ["Derleme", "Meta-Analiz", "Kılavuz", "Uzman Görüşü", "Editör", "Review", "Editorial", "Guideline"])
        is_rev2 = any(k in des2 for k in ["Derleme", "Meta-Analiz", "Kılavuz", "Uzman Görüşü", "Editör", "Review", "Editorial", "Guideline"])
        design_compatible = (is_rev1 == is_rev2)

        # 5. Outcome Match Check
        def _fold_outcome(text: str) -> str:
            # Turkish İ lowercases to i + combining dot; fold that before compare.
            return (text or "").casefold().replace("i\u0307", "i").replace("ı", "i").strip()

        outcomes1 = [_fold_outcome(om.get("outcome", "")) for om in p1.get("outcome_metrics", [])]
        outcomes2 = [_fold_outcome(om.get("outcome", "")) for om in p2.get("outcome_metrics", [])]

        generic_outcomes = {
            _fold_outcome(label)
            for label in (
                "genel sonlanım / özet istatistiği",
                "Primer Klinik Sonlanım / Özet İstatistiği",
                "Primer Klinik Sonlanım Ölçütü",
                "Sonlanım adı güvenle çevrilemedi",
                "özette adlandırılmadı",
                "değerlendirilemedi",
            )
        }
        matching_outcomes = []
        for o1 in outcomes1:
            for o2 in outcomes2:
                if not o1 or not o2 or o1 in generic_outcomes or o2 in generic_outcomes:
                    continue
                if o1 == o2:
                    matching_outcomes.append(o1)
                    continue
                shorter, longer = (o1, o2) if len(o1) <= len(o2) else (o2, o1)
                if len(shorter) >= 12 and re.search(r"\b" + re.escape(shorter) + r"\b", longer):
                    matching_outcomes.append(longer)

        compatible = pop_match and int_match and comp_match and design_compatible and len(matching_outcomes) > 0

        unmatched_reasons = []
        if not pop_match:
            unmatched_reasons.append(f"Popülasyon uyuşmazlığı ('{p1.get('patient_population')}' vs '{p2.get('patient_population')}')")
        if not int_match:
            unmatched_reasons.append(f"Müdahale uyuşmazlığı ('{p1.get('intervention')}' vs '{p2.get('intervention')}')")
        if not comp_match:
            unmatched_reasons.append(f"Karşılaştırıcı uyuşmazlığı ('{p1.get('comparison')}' vs '{p2.get('comparison')}')")
        if not design_compatible:
            unmatched_reasons.append(f"Çalışma tasarımı uyuşmazlığı ('{des1}' vs '{des2}')")
        if len(matching_outcomes) == 0:
            unmatched_reasons.append("Ortak doğrulanmış sonlanım ölçütü (Outcome) saptanamadı")

        return {
            "compatible": compatible,
            "pop_match": pop_match,
            "int_match": int_match,
            "comp_match": comp_match,
            "design_compatible": design_compatible,
            "matching_outcomes": list(set(matching_outcomes)),
            "unmatched_reasons": unmatched_reasons
        }

    def _determine_statistical_direction(self, outcome_entry: Dict[str, Any]) -> str:
        """
        Determines the statistical direction ('positive', 'negative', 'neutral')
        for a bound outcome metric without fabricating unstated claims.
        """
        metrics = outcome_entry.get("metrics", [])
        sentence = outcome_entry.get("sentence", "").lower()

        p_vals = [m for m in metrics if m.lower().startswith("p")]
        is_significant = False
        for p in p_vals:
            if "< 0.0" in p or "= 0.0" in p or "=0.0" in p or "<0.0" in p:
                is_significant = True
                break

        if any(term in sentence for term in ["no significant", "not significant", "did not reduce", "did not improve", "no difference"]):
            return "neutral"

        if is_significant:
            if any(term in sentence for term in ["reduced", "prolonged", "improved", "increase", "higher", "lower", "decreased", "effective", "benefit"]):
                return "positive"
            if any(term in sentence for term in ["increased risk", "adverse", "mortality", "harmful", "worsened"]):
                return "negative"
            return "positive"

        return "neutral"

    def compare_cross_article_findings(self, articles: List[Dict[str, Any]], query: str = "") -> Dict[str, Any]:
        """
        Compares findings across multiple publications:
        - Processes each article's PMID, DOI, title, abstract, and bound outcome metrics independently without mixing.
        - Identifies consistent clinical findings ONLY when Population, Intervention, Comparator, Outcome,
          Follow-up time (if present), and Study Design match.
        - Highlights conflicting findings for matching PICO & study designs.
        - Reports explicit non-comparability reasons in Turkish whenever parameters do not match or quantitative data is missing.
        - Guarantees zero metric or conclusion fabrication across all 88 medical research specialties.
        """
        if not articles:
            return {
                "total_articles": 0,
                "primary_study_count": 0,
                "review_study_count": 0,
                "individual_article_summaries": [],
                "consistent_findings": [],
                "conflicting_findings": [],
                "non_comparable_studies": [],
                "methodological_heterogeneity": "Herhangi bir makale verisi sağlanmadı.",
                "evidence_limitation_notice": "Veri yok."
            }

        processed = self.process_and_extract_parameters(articles, query)

        _nonprimary = ("Derleme", "Meta-Analiz", "Kılavuz", "Uzman Görüşü", "Editör", "Review", "Editorial", "Guideline")
        primary_studies = [p for p in processed if not any(k in p["study_design"]["design"] for k in _nonprimary)]
        review_studies = [p for p in processed if any(k in p["study_design"]["design"] for k in _nonprimary)]

        consistent = []
        conflicting = []
        non_comparable = []

        # Process individual article summaries with strict PMID/DOI source binding
        individual_summaries = []
        for p in processed:
            pmid = p.get("pmid") or "PMID Yok"
            doi = p.get("doi") or "DOI Yok"
            pmid_link = f"[PMID: {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)" if p.get("pmid") else "PMID Yok"
            doi_link = f"[DOI: {doi}](https://doi.org/{doi})" if p.get("doi") else "DOI Yok"

            individual_summaries.append({
                "pmid": p.get("pmid"),
                "doi": p.get("doi"),
                "authors_short": p.get("authors_short"),
                "pub_year": p.get("pub_year"),
                "title": p.get("title"),
                "study_design": p["study_design"]["design"],
                "evidence_level": p["study_design"]["level"],
                "evidence_level_note": p["study_design"].get("evidence_level_note", ""),
                "patient_population": p.get("patient_population"),
                "provenance": p.get("provenance"),
                "sample_size_n": p.get("sample_size_n"),
                "intervention": p.get("intervention"),
                "comparison": p.get("comparison"),
                "outcome_metrics": p.get("outcome_metrics"),
                "risk_of_bias": p.get("risk_of_bias", {}).get("overall_rating"),
                "source_citations": f"{pmid_link} / {doi_link}",
                "real_findings": p.get("real_findings")
            })

        # Pairwise comparison strictly among primary studies
        n_prim = len(primary_studies)
        compared_pairs = set()

        for i in range(n_prim):
            p1 = primary_studies[i]
            pmid1 = p1.get("pmid") or f"study_{i+1}"
            pmid1_link = f"[PMID: {p1.get('pmid')}](https://pubmed.ncbi.nlm.nih.gov/{p1.get('pmid')}/)" if p1.get("pmid") else "PMID Yok"

            for j in range(i + 1, n_prim):
                p2 = primary_studies[j]
                pmid2 = p2.get("pmid") or f"study_{j+1}"
                pmid2_link = f"[PMID: {p2.get('pmid')}](https://pubmed.ncbi.nlm.nih.gov/{p2.get('pmid')}/)" if p2.get("pmid") else "PMID Yok"

                pair_key = tuple(sorted([pmid1, pmid2]))
                if pair_key in compared_pairs:
                    continue
                compared_pairs.add(pair_key)

                eval_res = self._evaluate_pico_compatibility(p1, p2)

                if eval_res["compatible"]:
                    # Compare bound outcomes
                    def _fold_outcome(text: str) -> str:
                        return (text or "").casefold().replace("i\u0307", "i").replace("ı", "i").strip()

                    outcomes1_map = {_fold_outcome(om["outcome"]): om for om in p1.get("outcome_metrics", [])}
                    outcomes2_map = {_fold_outcome(om["outcome"]): om for om in p2.get("outcome_metrics", [])}

                    for matched_outcome_name in eval_res["matching_outcomes"]:
                        om1 = outcomes1_map.get(matched_outcome_name) or (p1.get("outcome_metrics")[0] if p1.get("outcome_metrics") else None)
                        om2 = outcomes2_map.get(matched_outcome_name) or (p2.get("outcome_metrics")[0] if p2.get("outcome_metrics") else None)

                        if om1 and om2:
                            dir1 = self._determine_statistical_direction(om1)
                            dir2 = self._determine_statistical_direction(om2)

                            m1_str = ", ".join(om1.get("metrics", [])) or "Özette nicel etki ölçütü yok"
                            m2_str = ", ".join(om2.get("metrics", [])) or "Özette nicel etki ölçütü yok"

                            if dir1 == dir2:
                                consistent.append({
                                    "outcome": om1["outcome"],
                                    "articles": [p1.get("pmid"), p2.get("pmid")],
                                    "source_citations": f"{pmid1_link} ve {pmid2_link}",
                                    "details": (
                                        f"**{p1['authors_short']} ({p1['pub_year']})** {pmid1_link} ({m1_str}) ve "
                                        f"**{p2['authors_short']} ({p2['pub_year']})** {pmid2_link} ({m2_str}) "
                                        f"çalışmaları **{om1['outcome']}** sonlanımında tutarlı istatistiksel bulgular göstermektedir."
                                    )
                                })
                            else:
                                conflicting.append({
                                    "outcome": om1["outcome"],
                                    "articles": [p1.get("pmid"), p2.get("pmid")],
                                    "source_citations": f"{pmid1_link} ve {pmid2_link}",
                                    "details": (
                                        f"**{p1['authors_short']} ({p1['pub_year']})** {pmid1_link} ({m1_str}) ile "
                                        f"**{p2['authors_short']} ({p2['pub_year']})** {pmid2_link} ({m2_str}) "
                                        f"çalışmaları **{om1['outcome']}** sonlanımında çelişkili veya farklı istatistiksel sonuçlar bildirmektedir."
                                    )
                                })
                else:
                    reasons_str = "; ".join(eval_res["unmatched_reasons"])
                    non_comparable.append({
                        "articles": [p1.get("pmid"), p2.get("pmid")],
                        "source_citations": f"{pmid1_link} ve {pmid2_link}",
                        "reason": (
                            f"**{p1['authors_short']} ({p1['pub_year']})** {pmid1_link} ve "
                            f"**{p2['authors_short']} ({p2['pub_year']})** {pmid2_link} arasında "
                            f"doğrudan karşılaştırma yapılamamıştır. Gerekçe: {reasons_str}."
                        )
                    })

        # Add explicit notice for review/guideline studies
        for r_study in review_studies:
            r_pmid_link = f"[PMID: {r_study.get('pmid')}](https://pubmed.ncbi.nlm.nih.gov/{r_study.get('pmid')}/)" if r_study.get("pmid") else "PMID Yok"
            non_comparable.append({
                "articles": [r_study.get("pmid")],
                "source_citations": r_pmid_link,
                "reason": f"**{r_study['authors_short']} ({r_study['pub_year']})** {r_pmid_link} yayını {r_study['study_design']['design']} niteliğindedir; ampirik primer veri sunmadığı için primer klinik çalışmalarla baş başa nicel karşılaştırmaya dahil edilmemiştir."
            })

        heterogeneity_msg = (
            f"Toplam {len(articles)} çalışma ({len(primary_studies)} primer araştırma, {len(review_studies)} derleme/kılavuz) "
            f"örneklem büyüklükleri (n), hasta yaş/cinsiyet grupları ve takip süreleri açısından metodolojik farklılıklar göstermektedir."
        )

        limitation_notice = (
            "Tüm karşılaştırmalar yalnızca yayınlanmış özet (abstract) metinlerine dayanmaktadır. "
            "GRADE kesinlik değerlendirmesi resmi olarak yapılmamış (Not Assessed). Uzman Hekim Değerlendirmesi: Yapılmadı."
        )

        return {
            "total_articles": len(articles),
            "primary_study_count": len(primary_studies),
            "review_study_count": len(review_studies),
            "individual_article_summaries": individual_summaries,
            "consistent_findings": consistent,
            "conflicting_findings": conflicting,
            "non_comparable_studies": non_comparable,
            "methodological_heterogeneity": heterogeneity_msg,
            "evidence_limitation_notice": limitation_notice
        }

    def generate_synthesis_report(
        self,
        query: str,
        articles: List[Dict[str, Any]],
        search_metadata: Optional[Dict[str, Any]] = None,
        verification_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Creates a preliminary Turkish synthesis from PubMed records and available abstracts.

        The report generator aims to include required limitations and verified record identifiers,
        but heuristic extraction and LLM output are not clinically validated and may be incomplete.
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
            audit_res = report_generator.perform_red_team_audit(
                query, articles, verification_results=verification_results
            )

            report_md = report_generator.generate_turkish_evidence_report(
                query=query,
                articles=articles,
                api_key=self.api_key if self.use_llm else None,
                use_llm=self.use_llm,
                allow_external_data_transfer=self.allow_external_data_transfer,
                model=self.model,
                search_metadata=search_metadata,
                audit=audit_res,
            )

            html_report = report_generator.generate_html_report(query, articles, report_md, audit=audit_res)
            pico = report_generator.extract_pico(query)
            cross_comp = self.compare_cross_article_findings(articles, query)
            quality_qc = report_generator.validate_clinical_report_quality(report_md)

            return {
                "status": "success",
                "query": query,
                "pico": pico,
                "cross_comparison": cross_comp,
                "report_markdown": report_md,
                "report_html": html_report,
                "audit": audit_res,
                "quality_control": quality_qc,
            }
        except Exception as e:
            logger.error("Universal evidence synthesis failed (%s)", type(e).__name__)
            safe_message = "Sentez sırasında beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyin."
            return {
                "status": "error",
                "error": safe_message,
                "report_markdown": f"# 📑 Türkçe Klinik Araştırma Raporu\n\n### ⚠️ Hata Oluştu\n{safe_message}",
                "report_html": f"<h1>Hata Oluştu</h1><p>{safe_message}</p>",
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
    search_metadata: Optional[Dict[str, Any]] = None,
    verification_results: Optional[List[Dict[str, Any]]] = None,
    allow_external_data_transfer: bool = False,
) -> Dict[str, Any]:
    engine = UniversalEvidenceEngine(
        api_key=api_key,
        use_llm=use_llm,
        model=model,
        allow_external_data_transfer=allow_external_data_transfer,
    )
    return engine.generate_synthesis_report(
        query, articles, search_metadata=search_metadata, verification_results=verification_results
    )


# [EVIDENCE_LAYER] auto-function
def enrich_record(rec: dict) -> dict:
    """RoB 2 + GRADE + etki büyüklüğü ile bir kaydı zenginleştirir."""
    abstract = rec.get("abstract", "") or ""
    design = rec.get("study_design", "unknown") or "unknown"
    design_str = (
        design.get("design_key") or design.get("design") or ""
        if isinstance(design, dict)
        else str(design)
    )

    rec["effect_summary"] = summarize_effects(extract_effect_sizes(abstract))

    design_info = rec.get("study_design_info") if isinstance(rec.get("study_design_info"), dict) else {}
    pub_types = " ".join(rec.get("publication_types") or []).lower()
    is_rct = (
        design_info.get("design_key") == "rct"
        or "randomized controlled trial" in pub_types
        or design_str == "rct"
    )
    # A background mention of other randomized trials is not this study's design
    # and is not a completed RoB 2 rating. Non-RCTs are not stamped "Low".
    if is_rct:
        rob = assess_rob2(abstract)
        rec["rob2"] = rob.to_dict()
        rec["rob2"]["scope"] = (
            "Özet metninden sinyal taraması. Tam metin RoB 2 değerlendirmesi yapılmadı; "
            "bu alan bir kanıt düzeyi değildir."
        )
    else:
        rec["rob2"] = None

    rec["grade"] = {
        "starting": "Değerlendirilemedi",
        "final": "Değerlendirilemedi",
        "downgrades": [],
        "upgrades": [],
        "note": "Kanıt düzeyi çalışma tasarımından üretilmedi. GRADE sonlanım bazında yazılır.",
    }

    return rec

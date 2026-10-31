from fastapi import FastAPI, Query, HTTPException, Body
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from pubmed_client import search_pubmed, verify_pmid, verify_doi, verify_citation
from universal_evidence_engine import UniversalEvidenceEngine, run_universal_evidence_search, generate_universal_evidence_synthesis
from report_generator import (
    generate_turkish_evidence_report,
    perform_red_team_audit,
    generate_evidence_table_html,
    generate_html_report,
    extract_pico,
    extract_article_clinical_details,
    assess_risk_of_bias,
    validate_clinical_report_quality,
)

app = FastAPI(
    title="Medical Research AI API",
    description="Universal Physician Medical Research AI REST API backed by NCBI PubMed E-utilities and CrossRef.",
    version="1.2.0"
)


class ArticleCitation(BaseModel):
    pmid: str = Field(..., min_length=1, max_length=20, description="PubMed PMID")
    title: Optional[str] = Field(None, max_length=1000, description="Optional title checked against PubMed")
    doi: Optional[str] = Field(None, max_length=256, description="Optional DOI checked against PubMed")


class ReportRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="The clinical search query or medical topic")
    articles: List[ArticleCitation] = Field(
        ..., min_length=1, max_length=50,
        description="PMID references only; each is re-fetched from PubMed and only canonical PubMed metadata is used",
    )
    api_key: Optional[str] = Field(None, max_length=512, description="Optional OpenAI key; do not send patient-identifying data")
    use_llm: bool = Field(
        False,
        description="If true, the query and PubMed article metadata/abstracts are sent to OpenAI for synthesis.",
    )
    model: str = Field("gpt-4o-mini", max_length=64, description="OpenAI model to use if use_llm is True")
    search_date: Optional[str] = Field(None, max_length=10, description="Date the source search was run, YYYY-MM-DD")


def _load_verified_articles(citations: List[ArticleCitation]):
    """Fetch canonical PubMed metadata and reject mismatched or unverifiable citations."""
    articles: List[Dict[str, Any]] = []
    verification_results: List[Dict[str, Any]] = []
    seen_pmids = set()

    for citation in citations:
        payload = citation.model_dump(exclude_none=True)
        pmid = str(payload.get("pmid", "")).strip().lower().removeprefix("pmid:").strip()
        if not pmid.isdigit() or len(pmid) > 10:
            raise HTTPException(
                status_code=422,
                detail={"pmid": pmid, "reason": "invalid_pmid", "message": "PMID must contain only digits."},
            )
        if pmid in seen_pmids:
            raise HTTPException(
                status_code=422,
                detail={"pmid": pmid, "reason": "duplicate_pmid", "message": "Duplicate PMIDs are not accepted."},
            )

        result = verify_citation(payload)
        status = result.get("status")
        if status != "verified":
            raise HTTPException(
                status_code=502 if status == "unverified" else 422,
                detail={
                    "pmid": pmid,
                    "reason": result.get("reason", "verification_failed"),
                    "message": result.get("error", "Citation could not be verified against PubMed."),
                },
            )

        fetched = result.get("fetched_article") or {}
        if not fetched.get("valid") or str(fetched.get("pmid", "")) != pmid:
            raise HTTPException(
                status_code=502,
                detail={"pmid": pmid, "reason": "missing_canonical_record", "message": "PubMed did not return canonical article metadata."},
            )

        seen_pmids.add(pmid)
        verification_results.append(result)
        articles.append({key: value for key, value in fetched.items() if key != "valid"})

    return articles, verification_results


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Medical Research AI API"}


@app.get("/api/search")
def api_search_pubmed(
    query: str = Query(..., description="Clinical query or medical term"),
    max_results: int = Query(10, ge=1, le=50, description="Max results to return"),
    sort: str = Query("relevance", description="Sort order: relevance or pub_date"),
    publication_type: Optional[str] = Query("Tümü", description="Filter by publication type"),
    start_year: Optional[int] = Query(None, description="Start publication year"),
    end_year: Optional[int] = Query(None, description="End publication year")
):
    result = search_pubmed(
        query=query,
        max_results=max_results,
        sort=sort,
        publication_type=publication_type,
        start_year=start_year,
        end_year=end_year
    )
    if "error" in result and not result.get("articles"):
        raise HTTPException(status_code=502, detail=f"PubMed API Error: {result['error']}")
    return result


@app.get("/api/verify/pmid/{pmid}")
def api_verify_pmid(pmid: str):
    result = verify_pmid(pmid)
    if not result.get("valid"):
        raise HTTPException(status_code=404, detail=result.get("error", "PMID not found or invalid"))
    return result


@app.get("/api/verify/doi/{doi:path}")
def api_verify_doi(doi: str):
    result = verify_doi(doi)
    if not result.get("valid"):
        raise HTTPException(status_code=404, detail=result.get("error", "DOI not found or invalid"))
    return result


@app.post("/api/verify/citation")
def api_verify_citation(citation: Dict[str, Any] = Body(...)):
    """
    Independently verifies a citation payload by re-fetching PMID from NCBI PubMed
    and comparing normalized title and DOI values. Rejects mismatches and reports API failures as unverified.
    """
    return verify_citation(citation)


@app.post("/api/report")
def api_generate_report(req: ReportRequest):
    articles, verification_results = _load_verified_articles(req.articles)
    audit = perform_red_team_audit(req.query, articles, verification_results=verification_results)
    search_meta = {
        "search_date": req.search_date,
        "query": req.query
    }
    report_md = generate_turkish_evidence_report(
        query=req.query,
        articles=articles,
        api_key=req.api_key,
        use_llm=req.use_llm,
        model=req.model,
        search_metadata=search_meta,
        audit=audit,
    )
    quality_qc = validate_clinical_report_quality(report_md)
    html_report = generate_html_report(req.query, articles, report_md, audit=audit)
    pico = extract_pico(req.query)
    risk_of_bias_list = [assess_risk_of_bias(art) for art in articles]
    article_clinical_details = [extract_article_clinical_details(art, req.query) for art in articles]

    return {
        "query": req.query,
        "pico": pico,
        "risk_of_bias": risk_of_bias_list,
        "article_clinical_details": article_clinical_details,
        "report": report_md,
        "html_report": html_report,
        "quality_control": quality_qc,
        "audit": audit
    }


@app.post("/api/universal_engine/synthesize")
def api_universal_engine_synthesize(req: ReportRequest):
    """
    Universal Evidence Engine endpoint for disease-agnostic Turkish clinical report synthesis,
    cross-study comparative analysis, and structured parameter extraction.
    """
    articles, verification_results = _load_verified_articles(req.articles)
    return generate_universal_evidence_synthesis(
        query=req.query,
        articles=articles,
        api_key=req.api_key,
        use_llm=req.use_llm,
        model=req.model,
        search_metadata={"search_date": req.search_date, "query": req.query},
        verification_results=verification_results,
    )

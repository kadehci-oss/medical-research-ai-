from fastapi import FastAPI, Query, HTTPException, Body
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from pubmed_client import search_pubmed, verify_pmid, verify_doi, verify_citation
from report_generator import (
    generate_turkish_evidence_report,
    perform_red_team_audit,
    generate_evidence_table_html,
    generate_html_report,
    extract_pico,
    assess_risk_of_bias
)

app = FastAPI(
    title="Medical Research AI API",
    description="Physician Medical Research AI REST API backed by NCBI PubMed E-utilities and CrossRef.",
    version="1.1.0"
)


class ReportRequest(BaseModel):
    query: str = Field(..., description="The clinical search query or medical topic")
    articles: List[Dict[str, Any]] = Field(..., description="List of verified article dicts from pubmed search/verification")
    api_key: Optional[str] = Field(None, description="Optional OpenAI API key for LLM report synthesis")
    use_llm: bool = Field(False, description="Whether to use OpenAI LLM synthesis or rule-based engine")
    model: str = Field("gpt-4o-mini", description="OpenAI model to use if use_llm is True")


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
    report_md = generate_turkish_evidence_report(
        query=req.query,
        articles=req.articles,
        api_key=req.api_key,
        use_llm=req.use_llm,
        model=req.model
    )
    audit = perform_red_team_audit(req.query, req.articles)
    html_report = generate_html_report(req.query, req.articles, report_md)
    combined_abstracts = " ".join([a.get("abstract", "") for a in req.articles if a.get("abstract")])
    pico = extract_pico(req.query, combined_abstracts)
    risk_of_bias_list = [assess_risk_of_bias(art) for art in req.articles]

    return {
        "query": req.query,
        "pico": pico,
        "risk_of_bias": risk_of_bias_list,
        "report": report_md,
        "html_report": html_report,
        "audit": audit
    }

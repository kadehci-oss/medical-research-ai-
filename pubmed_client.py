import logging
import os
import re
import time
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
import requests
from typing import List, Dict, Any, Optional
from evidence_guards import fill_date_range  # [mrai-fixes]

logger = logging.getLogger(__name__)

# NCBI returns 429 when E-utilities is called faster than the unkeyed rate limit.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CROSSREF_API_URL = "https://api.crossref.org/works/"
MAX_ESEARCH_RESULT_WINDOW = 10_000


def build_author_search_query(first_name: str, last_name: str) -> str:
    """Build PubMed's supported natural-order full-author-name query ([FAU])."""
    parts = []
    for value in (first_name, last_name):
        if not isinstance(value, str):
            raise ValueError("Araştırmacının adı ve soyadı metin olmalıdır.")
        normalized = " ".join(value.split())
        if not normalized or not re.fullmatch(
            r"[^\W\d_]+(?:[ '\u2019-][^\W\d_]+)*", normalized, flags=re.UNICODE
        ) or any(token.upper() in {"AND", "OR", "NOT"} for token in normalized.split()):
            raise ValueError(
                "Ad ve soyad yalnızca harf, boşluk, kesme işareti veya tire içerebilir."
            )
        parts.append(normalized)
    return f"{parts[0]} {parts[1]}[FAU]"


# Non-personal fallback for the tool name. Operators should set NCBI_EMAIL.
DEFAULT_NCBI_TOOL = "MedicalResearchAI"


def ncbi_tool_name() -> str:
    """Return the E-utilities tool name from ``NCBI_TOOL`` or the project default."""
    value = os.environ.get("NCBI_TOOL", "").strip()
    return value or DEFAULT_NCBI_TOOL


def ncbi_contact_email() -> Optional[str]:
    """Return a configured NCBI contact, or ``None`` rather than a fake address."""
    value = os.environ.get("NCBI_EMAIL", "").strip()
    return value or None


def ncbi_api_key() -> Optional[str]:
    """Return ``NCBI_API_KEY`` when set, otherwise ``None`` so requests omit it."""
    value = os.environ.get("NCBI_API_KEY", "").strip()
    return value or None


def ncbi_request_headers() -> Dict[str, str]:
    """Build a User-Agent that identifies this client to NCBI and CrossRef."""
    user_agent = f"{ncbi_tool_name()}/1.0"
    email = ncbi_contact_email()
    if email:
        user_agent += f" (mailto:{email})"
    return {"User-Agent": user_agent}


def eutils_identity_params() -> Dict[str, str]:
    """Attach NCBI etiquette fields to an E-utilities query.

    ``tool`` is always sent; ``email`` and ``api_key`` are included only when
    configured.
    """
    params: Dict[str, str] = {"tool": ncbi_tool_name()}
    email = ncbi_contact_email()
    if email:
        params["email"] = email
    api_key = ncbi_api_key()
    if api_key:
        params["api_key"] = api_key
    return params


def _retry_delay_seconds(response: requests.Response, default_delay: float) -> float:
    """Honor a numeric Retry-After header when NCBI sends one, capped at 30s."""
    headers = getattr(response, "headers", None)
    raw_after = headers.get("Retry-After") if headers is not None and hasattr(headers, "get") else None
    if isinstance(raw_after, str):
        try:
            return min(max(float(raw_after), 0.0), 30.0)
        except ValueError:
            return default_delay
    return default_delay


def _get_with_retry(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 10,
) -> requests.Response:
    """
    GET with a short bounded backoff on transient network errors, HTTP 429, and 5xx.

    Headers come from ``ncbi_request_headers`` (tool name and configured contact email, if any).
    E-utilities callers attach ``tool`` plus optional ``email`` and ``api_key``
    values on ``params`` before calling this helper. Non-integer status codes (for
    example test doubles) are not retried. The final response is returned
    even if it is still retryable so callers keep their existing error handling.
    """
    response: Optional[requests.Response] = None
    attempts = len(_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params, headers=ncbi_request_headers(), timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if attempt >= len(_RETRY_DELAYS_SECONDS):
                raise
            delay = _RETRY_DELAYS_SECONDS[attempt]
            logger.warning(
                "Transient %s from %s; retrying in %.1fs (attempt %s/%s)",
                type(exc).__name__,
                url,
                delay,
                attempt + 1,
                attempts,
            )
            time.sleep(delay)
            continue
        status = response.status_code if isinstance(getattr(response, "status_code", None), int) else None
        if status in _RETRYABLE_STATUS and attempt < len(_RETRY_DELAYS_SECONDS):
            delay = _retry_delay_seconds(response, _RETRY_DELAYS_SECONDS[attempt])
            logger.warning(
                "HTTP %s from %s; retrying in %.1fs (attempt %s/%s)",
                status,
                url,
                delay,
                attempt + 1,
                attempts,
            )
            time.sleep(delay)
            continue
        return response
    return response  # pragma: no cover


def _get_element_text(elem: Optional[Any]) -> str:
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


class PubMedXMLParseError(ValueError):
    """A non-empty NCBI XML response was malformed or unsafe to parse."""


def parse_pubmed_xml(xml_content: str) -> List[Dict[str, Any]]:
    """Parses PubMed efetch XML content and extracts structured article metadata."""
    articles = []
    if not xml_content or not xml_content.strip():
        return articles

    try:
        root = ET.fromstring(xml_content)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise PubMedXMLParseError("PubMed XML response could not be parsed safely.") from exc

    for article_elem in root.findall(".//PubmedArticle"):
        medline = article_elem.find("MedlineCitation")
        if medline is None:
            continue

        pmid = _get_element_text(medline.find("PMID"))
        article = medline.find("Article")
        if article is None:
            continue

        title = _get_element_text(article.find("ArticleTitle"))

        # Extract Authors
        authors = []
        author_list = article.find("AuthorList")
        if author_list is not None:
            for auth in author_list.findall("Author"):
                last_name = _get_element_text(auth.find("LastName"))
                fore_name = _get_element_text(auth.find("ForeName"))
                initials = _get_element_text(auth.find("Initials"))
                collective = _get_element_text(auth.find("CollectiveName"))

                if last_name and fore_name:
                    authors.append(f"{fore_name} {last_name}")
                elif last_name and initials:
                    authors.append(f"{last_name} {initials}")
                elif last_name:
                    authors.append(last_name)
                elif collective:
                    authors.append(collective)

        # Extract Journal Name & Publication Date
        journal_elem = article.find("Journal")
        journal_title = ""
        pub_year = ""
        if journal_elem is not None:
            journal_title = _get_element_text(journal_elem.find("Title")) or _get_element_text(journal_elem.find("ISOAbbreviation"))
            pub_date_elem = journal_elem.find(".//JournalIssue/PubDate")
            if pub_date_elem is not None:
                year = _get_element_text(pub_date_elem.find("Year"))
                medline_date = _get_element_text(pub_date_elem.find("MedlineDate"))
                if year:
                    pub_year = year
                elif medline_date:
                    match = re.search(r"\b(19|20)\d{2}\b", medline_date)
                    if match:
                        pub_year = match.group(0)
                    else:
                        pub_year = medline_date

        # Extract Publication Types
        pub_types = []
        pub_type_list = article.find("PublicationTypeList")
        if pub_type_list is not None:
            for pt in pub_type_list.findall("PublicationType"):
                pt_text = _get_element_text(pt)
                if pt_text:
                    pub_types.append(pt_text)

        # Extract Abstract
        abstract_parts = []
        abstract_elem = article.find("Abstract")
        if abstract_elem is not None:
            for abs_text in abstract_elem.findall("AbstractText"):
                label = abs_text.attrib.get("Label", "")
                text = _get_element_text(abs_text)
                if label and text:
                    abstract_parts.append(f"{label}: {text}")
                elif text:
                    abstract_parts.append(text)
        abstract = "\n\n".join(abstract_parts) if abstract_parts else "Özet bulunamadı."

        # Extract DOI
        doi = None
        # Check ArticleIdList in PubmedData
        pubmed_data = article_elem.find("PubmedData")
        if pubmed_data is not None:
            article_id_list = pubmed_data.find("ArticleIdList")
            if article_id_list is not None:
                for aid in article_id_list.findall("ArticleId"):
                    if aid.attrib.get("IdType") == "doi":
                        doi = _get_element_text(aid)
                        break

        # Fallback check for DOI in ELocationID
        if not doi:
            for eloc in article.findall("ELocationID"):
                if eloc.attrib.get("EIdType") == "doi":
                    doi = _get_element_text(eloc)
                    break

        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        doi_url = f"https://doi.org/{doi}" if doi else ""

        articles.append({
            "pmid": pmid,
            "title": title or "Başlık bulunamadı",
            "authors": authors,
            "journal": journal_title or "Dergisi belirtilmemiş",
            "pub_year": pub_year or "Tarih belirtilmemiş",
            "publication_types": pub_types,
            "abstract": abstract,
            "doi": doi,
            "pubmed_url": pubmed_url,
            "doi_url": doi_url
        })

    return articles


def _pagination_metadata(
    retstart: int,
    requested_page_size: int,
    page_size: int,
    total_count: int,
    id_count: int = 0,
    returned_count: int = 0,
    result_available: bool = True,
) -> Dict[str, Any]:
    next_offset = retstart + id_count
    has_more = next_offset < total_count
    return {
        "retstart": retstart,
        "requested_page_size": requested_page_size,
        "page_size": page_size,
        "id_count": id_count,
        "returned_count": returned_count,
        "total_count": total_count,
        "has_more": has_more,
        "truncated": has_more,
        "complete_result_set": result_available and retstart == 0 and not has_more,
        "next_retstart": (next_offset if id_count > 0 and has_more
                          and next_offset < MAX_ESEARCH_RESULT_WINDOW else None),
        "limit_applied": page_size < requested_page_size or has_more,
        "max_retrievable_ids": MAX_ESEARCH_RESULT_WINDOW,
        "retrieval_window_exhausted": next_offset >= MAX_ESEARCH_RESULT_WINDOW and total_count > MAX_ESEARCH_RESULT_WINDOW,
    }


def search_pubmed(
    query: str,
    max_results: int = 10,
    retstart: int = 0,
    sort: str = "relevance",
    publication_type: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> Dict[str, Any]:
    """
    Searches PubMed using E-utilities esearch and efetch.

    Records the search date and parameters, and deduplicates articles by PMID
    and DOI. Every E-utilities request includes ``tool`` from ``NCBI_TOOL`` or
    the project default; ``email`` and ``api_key`` are included only when
    ``NCBI_EMAIL`` and ``NCBI_API_KEY`` are configured, respectively.
    Returns a dict with ``articles``, ``total_count``, ``query``, ``search_date``,
    and ``search_params``.
    """
    import datetime
    search_date_str = datetime.date.today().strftime("%Y-%m-%d")

    requested_page_size = int(max_results)
    requested_retstart = int(retstart)
    if requested_page_size < 1 or requested_retstart < 0 or requested_retstart >= MAX_ESEARCH_RESULT_WINDOW:
        return {
            "articles": [], "total_count": 0, "query": query, "search_date": search_date_str,
            "search_params": {"max_results": max_results, "retstart": retstart, "sort": sort,
                              "publication_type": publication_type, "start_year": start_year, "end_year": end_year},
            "error": f"Sayfalama sınırları geçersiz; retstart 0–{MAX_ESEARCH_RESULT_WINDOW - 1} ve max_results en az 1 olmalıdır.",
            "pagination": _pagination_metadata(max(0, requested_retstart), max(0, requested_page_size), 0, 0,
                                               result_available=False),
        }
    effective_page_size = min(requested_page_size, MAX_ESEARCH_RESULT_WINDOW - requested_retstart)

    search_params_summary = {
        "max_results": requested_page_size,
        "effective_max_results": effective_page_size,
        "retstart": requested_retstart,
        "sort": sort,
        "publication_type": publication_type,
        "start_year": start_year,
        "end_year": end_year
    }

    if not query or not query.strip():
        return {
            "articles": [],
            "total_count": 0,
            "query": query,
            "search_date": search_date_str,
            "search_params": search_params_summary,
            "pagination": _pagination_metadata(requested_retstart, requested_page_size, effective_page_size, 0)
        }

    term = query.strip()
    if publication_type and publication_type != "Tümü":
        term += f" AND {publication_type}[pt]"

    esearch_params = {
        "db": "pubmed",
        "term": term,
        "retmax": effective_page_size,
        "retstart": requested_retstart,
        "retmode": "json",
        "sort": sort,
    }

    # [mrai-fixes B6] NCBI needs mindate and maxdate together; fill the missing bound.
    try:
        _date_range = fill_date_range(start_year or None, end_year or None)
    except ValueError as exc:
        return {
            "articles": [],
            "total_count": 0,
            "query": query,
            "search_date": search_date_str,
            "search_params": search_params_summary,
            "pagination": _pagination_metadata(requested_retstart, requested_page_size, effective_page_size, 0,
                                               result_available=False),
            "error": str(exc)
        }
    if _date_range:
        esearch_params["datetype"] = "pdat"
        esearch_params["mindate"], esearch_params["maxdate"] = _date_range

    esearch_params.update(eutils_identity_params())

    try:
        response = _get_with_retry(PUBMED_ESEARCH_URL, params=esearch_params, timeout=10)
        response.raise_for_status()
        data = response.json()
        esearch_result = data.get("esearchresult", {})

        if "ERROR" in esearch_result:
            return {
                "articles": [],
                "total_count": 0,
                "query": query,
                "search_date": search_date_str,
                "search_params": search_params_summary,
                "pagination": _pagination_metadata(requested_retstart, requested_page_size, effective_page_size, 0,
                                                   result_available=False),
                "error": "PubMed arama isteği işlenemedi. Sorgu biçimini kontrol edin veya daha sonra tekrar deneyin."
            }
        if "errorlist" in esearch_result:
            return {
                "articles": [],
                "total_count": 0,
                "query": query,
                "search_date": search_date_str,
                "search_params": search_params_summary,
                "pagination": _pagination_metadata(requested_retstart, requested_page_size, effective_page_size, 0,
                                                   result_available=False),
                "error": "PubMed arama isteği işlenemedi. Sorgu biçimini kontrol edin veya daha sonra tekrar deneyin."
            }

        id_list = esearch_result.get("idlist", [])
        total_count = int(esearch_result.get("count", "0"))

        if not id_list:
            return {
                "articles": [],
                "total_count": total_count,
                "query": query,
                "search_date": search_date_str,
                "search_params": search_params_summary,
                "pagination": _pagination_metadata(requested_retstart, requested_page_size,
                                                   effective_page_size, total_count)
            }

        # Fetch article metadata using efetch
        efetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        efetch_params.update(eutils_identity_params())
        fetch_response = _get_with_retry(PUBMED_EFETCH_URL, params=efetch_params, timeout=15)
        fetch_response.raise_for_status()

        raw_articles = parse_pubmed_xml(fetch_response.text)

        # Deduplicate articles by PMID and DOI
        seen_pmids = set()
        seen_dois = set()
        deduped_articles = []

        for art in raw_articles:
            pmid = art.get("pmid")
            norm_doi = normalize_doi(art.get("doi"))

            if pmid and pmid in seen_pmids:
                continue
            if norm_doi and norm_doi in seen_dois:
                continue

            if pmid:
                seen_pmids.add(pmid)
            if norm_doi:
                seen_dois.add(norm_doi)

            deduped_articles.append(art)

        return {
            "articles": deduped_articles,
            "total_count": total_count,
            "query": query,
            "search_date": search_date_str,
            "search_params": search_params_summary,
            "pagination": _pagination_metadata(requested_retstart, requested_page_size,
                                               effective_page_size, total_count, len(id_list),
                                               len(deduped_articles))
        }

    except Exception as e:
        logger.warning("PubMed search failed (%s)", type(e).__name__)
        return {
            "articles": [],
            "total_count": 0,
            "query": query,
            "search_date": search_date_str,
            "search_params": search_params_summary,
            "pagination": _pagination_metadata(requested_retstart, requested_page_size, effective_page_size, 0,
                                               result_available=False),
            "error": "PubMed'e erişim sırasında geçici bir hata oluştu."
        }


def verify_pmid(pmid: str) -> Dict[str, Any]:
    """Verify that a PMID exists and return its PubMed metadata.

    The E-utilities request includes ``tool`` and adds ``email`` and ``api_key``
    only when ``NCBI_EMAIL`` and ``NCBI_API_KEY`` are configured.
    """
    clean_pmid = pmid.strip().lower().replace("pmid:", "").strip()
    if not clean_pmid.isdigit():
        return {
            "valid": False,
            "pmid": pmid,
            "error": "Geçersiz PMID formatı. PMID yalnızca rakamlardan oluşmalıdır."
        }

    efetch_params = {
        "db": "pubmed",
        "id": clean_pmid,
        "retmode": "xml"
    }
    efetch_params.update(eutils_identity_params())

    try:
        response = _get_with_retry(PUBMED_EFETCH_URL, params=efetch_params, timeout=10)
        response.raise_for_status()
        articles = parse_pubmed_xml(response.text)
        if articles and articles[0].get("pmid") == clean_pmid:
            article = articles[0]
            article["valid"] = True
            return article
        else:
            return {
                "valid": False,
                "pmid": clean_pmid,
                "error": f"PMID {clean_pmid} PubMed veritabanında bulunamadı."
            }
    except Exception as e:
        logger.warning("PubMed PMID verification failed (%s)", type(e).__name__)
        return {
            "valid": False,
            "pmid": clean_pmid,
            "reason": "upstream_error",
            "error": "PubMed kaydı doğrulanırken geçici bir hata oluştu."
        }


def normalize_title(title: Optional[str]) -> str:
    """Normalizes article title for string comparison by stripping HTML tags, punctuation, and extra whitespace, and lowercasing."""
    if not title:
        return ""
    clean = re.sub(r"<[^>]+>", "", str(title))
    clean = re.sub(r"[^\w\s]", "", clean)
    return " ".join(clean.lower().split())


def normalize_doi(doi: Optional[str]) -> str:
    """Normalizes DOI for comparison by stripping URL prefixes, 'doi:' prefix, whitespace, and lowercasing."""
    if not doi:
        return ""
    clean = str(doi).strip()
    clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^doi:\s*", "", clean, flags=re.IGNORECASE).strip()
    return clean.lower()


def verify_citation(citation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Independently verifies a citation by re-fetching its PMID directly from NCBI PubMed
    and comparing normalized article title and DOI values.
    Rejects mismatches and flags API failures as unverified.
    """
    if not isinstance(citation, dict):
        return {
            "status": "rejected",
            "verified": False,
            "reason": "invalid_input",
            "error": "Girdi bir sözlük (dict) olmalıdır."
        }

    raw_pmid = str(citation.get("pmid") or "").strip()
    clean_pmid = raw_pmid.lower().replace("pmid:", "").strip()

    if not clean_pmid or not clean_pmid.isdigit():
        return {
            "status": "rejected",
            "verified": False,
            "pmid": raw_pmid,
            "reason": "missing_or_invalid_pmid",
            "error": "Geçersiz veya eksik PMID formatı."
        }

    fetched = verify_pmid(clean_pmid)

    if not fetched.get("valid"):
        err_msg = fetched.get("error", "")
        if "bulunamadı" in err_msg or "Geçersiz" in err_msg:
            return {
                "status": "rejected",
                "verified": False,
                "pmid": clean_pmid,
                "reason": "not_found",
                "error": err_msg
            }
        else:
            return {
                "status": "unverified",
                "verified": False,
                "pmid": clean_pmid,
                "reason": "api_failure",
                "error": err_msg
            }

    # Compare normalized title if present in input citation
    input_title = citation.get("title")
    if input_title and str(input_title).strip() and str(input_title).strip() != "Başlık bulunamadı":
        norm_input_title = normalize_title(str(input_title))
        norm_fetched_title = normalize_title(fetched.get("title", ""))
        if norm_input_title and norm_fetched_title and norm_input_title != norm_fetched_title:
            return {
                "status": "rejected",
                "verified": False,
                "pmid": clean_pmid,
                "reason": "title_mismatch",
                "error": f"Başlık uyuşmazlığı nedeniyle reddedildi: Girdi başlığı ('{input_title}') ile PubMed kaydı ('{fetched.get('title')}') eşleşmiyor.",
                "fetched_article": fetched
            }

    # Compare normalized DOI if present in input citation and fetched record
    input_doi = citation.get("doi")
    if input_doi and str(input_doi).strip():
        norm_input_doi = normalize_doi(str(input_doi))
        norm_fetched_doi = normalize_doi(fetched.get("doi", ""))
        if norm_input_doi and not norm_fetched_doi:
            return {
                "status": "unverified",
                "verified": False,
                "pmid": clean_pmid,
                "reason": "doi_missing_from_pubmed_record",
                "error": "DOI PubMed kaydında bulunmadığı için PMID–DOI eşleşmesi doğrulanamadı.",
                "fetched_article": fetched
            }
        if norm_input_doi and norm_fetched_doi != norm_input_doi:
            return {
                "status": "rejected",
                "verified": False,
                "pmid": clean_pmid,
                "reason": "doi_mismatch",
                "error": f"DOI uyuşmazlığı nedeniyle reddedildi: Girdi DOI ('{input_doi}') ile PubMed kaydı ('{fetched.get('doi')}') eşleşmiyor.",
                "fetched_article": fetched
            }

    return {
        "status": "verified",
        "verified": True,
        "pmid": clean_pmid,
        "reason": "match",
        "fetched_article": fetched
    }


def verify_doi(doi: str) -> Dict[str, Any]:
    """Verify a DOI against CrossRef and, if needed, PubMed.

    The CrossRef request uses the same configurable User-Agent as NCBI calls.
    ``NCBI_API_KEY`` is sent only on E-utilities requests, not to CrossRef.
    """
    clean_doi = doi.strip()
    clean_doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", clean_doi, flags=re.IGNORECASE)
    clean_doi = re.sub(r"^doi:\s*", "", clean_doi, flags=re.IGNORECASE).strip()

    if not clean_doi:
        return {
            "valid": False,
            "doi": doi,
            "error": "Geçersiz DOI formatı."
        }

    # First try CrossRef API
    crossref_url = f"{CROSSREF_API_URL}{clean_doi}"
    try:
        response = _get_with_retry(crossref_url, timeout=10)
        if response.status_code == 200:
            data = response.json().get("message", {})
            title_list = data.get("title", [])
            title = title_list[0] if title_list else "Başlık bulunamadı"

            authors = []
            for auth in data.get("author", []):
                given = auth.get("given", "")
                family = auth.get("family", "")
                if given or family:
                    authors.append(f"{given} {family}".strip())

            journal_list = data.get("container-title", [])
            journal = journal_list[0] if journal_list else "Dergisi belirtilmemiş"

            published = data.get("published-print") or data.get("published-online") or data.get("created")
            year = ""
            if published and "date-parts" in published and published["date-parts"]:
                year = str(published["date-parts"][0][0])

            # Try to check if PubMed has this DOI as well
            pubmed_search = search_pubmed(f"{clean_doi}[Location ID] OR {clean_doi}[AID]", max_results=1)
            pmid = None
            pubmed_url = None
            abstract = "Özet CrossRef API üzerinden sağlanmıyor."
            pub_types = []
            if pubmed_search.get("articles"):
                pm_article = pubmed_search["articles"][0]
                pmid = pm_article.get("pmid")
                pubmed_url = pm_article.get("pubmed_url")
                pub_types = pm_article.get("publication_types", [])
                if pm_article.get("abstract") and pm_article["abstract"] != "Özet bulunamadı.":
                    abstract = pm_article["abstract"]

            return {
                "valid": True,
                "doi": clean_doi,
                "title": title,
                "authors": authors,
                "journal": journal,
                "pub_year": year,
                "publication_types": pub_types,
                "pmid": pmid,
                "pubmed_url": pubmed_url,
                "doi_url": f"https://doi.org/{clean_doi}",
                "abstract": abstract
            }
    except Exception:
        pass

    # Fallback search PubMed directly for the DOI
    pubmed_search = search_pubmed(f"{clean_doi}[Location ID] OR {clean_doi}[AID]", max_results=1)
    if pubmed_search.get("articles"):
        article = pubmed_search["articles"][0]
        article["valid"] = True
        return article

    return {
        "valid": False,
        "doi": clean_doi,
        "error": f"DOI '{clean_doi}' ne CrossRef ne de PubMed veritabanında doğrulanamadı."
    }

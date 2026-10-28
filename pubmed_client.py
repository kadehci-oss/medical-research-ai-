import os
import re
import xml.etree.ElementTree as ET
import requests
from typing import List, Dict, Any, Optional

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CROSSREF_API_URL = "https://api.crossref.org/works/"

DEFAULT_HEADERS = {
    "User-Agent": "MedicalResearchAI/1.0 (mailto:medical_ai_app@example.com)"
}


def _get_element_text(elem: Optional[ET.Element]) -> str:
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def parse_pubmed_xml(xml_content: str) -> List[Dict[str, Any]]:
    """Parses PubMed efetch XML content and extracts structured article metadata."""
    articles = []
    if not xml_content or not xml_content.strip():
        return articles

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        return articles

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
    Searches PubMed using E-utilities esearch & efetch.
    Returns dict with 'articles', 'total_count', 'query'.
    """
    if not query or not query.strip():
        return {"articles": [], "total_count": 0, "query": query}

    term = query.strip()
    if publication_type and publication_type != "Tümü":
        term += f" AND {publication_type}[pt]"

    esearch_params = {
        "db": "pubmed",
        "term": term,
        "retmax": max_results,
        "retstart": retstart,
        "retmode": "json",
        "sort": sort,
    }

    if start_year or end_year:
        esearch_params["datetype"] = "pdat"
        if start_year:
            esearch_params["mindate"] = str(start_year)
        if end_year:
            esearch_params["maxdate"] = str(end_year)

    try:
        response = requests.get(PUBMED_ESEARCH_URL, params=esearch_params, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        esearch_result = data.get("esearchresult", {})

        if "ERROR" in esearch_result:
            return {"articles": [], "total_count": 0, "query": query, "error": esearch_result.get("ERROR")}
        if "errorlist" in esearch_result:
            err_list = esearch_result.get("errorlist", {})
            return {"articles": [], "total_count": 0, "query": query, "error": f"PubMed esearch error: {err_list}"}

        id_list = esearch_result.get("idlist", [])
        total_count = int(esearch_result.get("count", "0"))

        if not id_list:
            return {"articles": [], "total_count": 0, "query": query}

        # Fetch article metadata using efetch
        efetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        fetch_response = requests.get(PUBMED_EFETCH_URL, params=efetch_params, headers=DEFAULT_HEADERS, timeout=15)
        fetch_response.raise_for_status()

        articles = parse_pubmed_xml(fetch_response.text)
        return {"articles": articles, "total_count": total_count, "query": query}

    except Exception as e:
        return {"articles": [], "total_count": 0, "query": query, "error": str(e)}


def verify_pmid(pmid: str) -> Dict[str, Any]:
    """
    Verifies PMID existence and fetches full metadata.
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

    try:
        response = requests.get(PUBMED_EFETCH_URL, params=efetch_params, headers=DEFAULT_HEADERS, timeout=10)
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
        return {
            "valid": False,
            "pmid": clean_pmid,
            "error": f"Doğrulama sırasında hata oluştu: {str(e)}"
        }


def verify_doi(doi: str) -> Dict[str, Any]:
    """
    Verifies DOI existence against CrossRef API and PubMed.
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
        response = requests.get(crossref_url, headers=DEFAULT_HEADERS, timeout=10)
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

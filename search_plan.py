"""Rule-based literature search plan ("Arama Planı") for a clinical question.

The plan turns a question into the pieces a systematic search needs: the
question framework (PICO, PIRD, PFO, ...), concept blocks, a suggested PubMed
query, proposed inclusion/exclusion criteria, other databases worth checking and
an empty evidence-table template.

Honesty rules (same spirit as ``question_framework``):

* Concept terms come only from the query text. Nothing is invented or translated.
* MeSH headings are never guessed. They are filled only when PubMed's own
  automatic term mapping returns them (``verify_mesh=True`` or ``mesh_lookup``);
  otherwise the plan says they are unverified.
* The plan is a *proposal*. What was actually executed (database, query, filters,
  counts) is reported separately, and records are never screened against the
  proposed criteria here, so the plan says so.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

import question_framework

logger = logging.getLogger(__name__)

NOT_STATED_TR = question_framework.NOT_STATED_TR

# Positions (in the framework's element list) that go into the PubMed query.
# Comparison and outcome are left out on purpose: adding them narrows the search
# and can hide relevant records whose abstracts word them differently.
_SEARCH_ELEMENT_INDEXES: Dict[str, tuple] = {
    "therapy": (0, 1),          # P, I
    "surgery": (0, 1),          # P, I
    "safety": (0, 1),           # P, E
    "diagnosis": (0, 1),        # P, index test
    "screening": (0, 1),        # P, screening test
    "prognosis": (0, 1),        # P, prognostic factor
    "etiology": (0, 1),         # P, exposure
    "epidemiology": (0, 2),     # condition, population
    "health_services": (0, 2),  # setting, intervention
}

_EDGE_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "with", "among", "to", "by", "versus", "vs",
    "patient", "patients", "adult", "adults", "people", "subjects", "participants", "individuals",
    "hasta", "hastalar", "hastalarda", "hastalarında", "erişkin", "erişkinlerde", "ile",
}
_SPLIT_RE = re.compile(r"\s*(?:,|;|/|\bor\b|\bveya\b)\s*", re.IGNORECASE)
# Case-insensitive matching would let Turkish "ı"/"İ" match English "i"/"I", so the
# letter check is case-sensitive and only the word check ignores case.
_TURKISH_LETTERS_RE = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
_TURKISH_WORDS_RE = re.compile(r"\b(?:ile|ve|veya|hastalarında|tedavisi|etkisi)\b", re.IGNORECASE)
_MESH_RE = re.compile(r'"([^"]+)"\[MeSH Terms\]')
_MAX_TERMS_PER_CONCEPT = 5
_MAX_MESH_PER_CONCEPT = 3

STATUS_PROPOSAL_TR = "öneri; kayıtlara uygulanmadı"

TABLE_COLUMNS_TR = [
    "Yazar-Yıl", "PMID", "Tasarım", "Örneklem", "Sonlanım / sonuç", "Sınırlılık", "Dahil / dışla (elle)",
]

# Database facts that do not depend on the query.
DATABASE_NOTES_TR = [
    {"name": "PubMed", "note": "Ücretsiz; MEDLINE tabanlı. Bu uygulamanın taradığı tek kaynak."},
    {"name": "Cochrane Library", "note": "Randomize çalışma kaydı (CENTRAL) ve Cochrane sistematik derlemeleri için."},
    {"name": "Embase", "note": "Abonelik gerektirir; ilaç ve Avrupa kaynaklı literatür için tamamlayıcı."},
    {"name": "Scopus", "note": "Abonelik gerektirir; atıf takibi ve disiplinler arası tarama için."},
]

_DEFAULT_EXCLUSIONS_TR = [
    "Editoryal, mektup ve yorum yazıları (birincil veri içermez)",
    "Hayvan veya laboratuvar (in vitro) çalışmaları",
    "Özeti olmayan kayıtlar (değerlendirme yalnızca özete dayanır)",
    "PubMed'de geri çekilmiş (retracted) olarak işaretli yayınlar",
]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("`", "'").split())


def _concept_terms(value: str) -> List[str]:
    """Split one element value into search phrases, using only words from the value."""
    text = re.sub(r'["\[\]()]', " ", value or "")
    terms: List[str] = []
    for part in _SPLIT_RE.split(text):
        tokens = part.split()
        while tokens and tokens[0].lower() in _EDGE_STOPWORDS:
            tokens.pop(0)
        while tokens and tokens[-1].lower() in _EDGE_STOPWORDS:
            tokens.pop()
        term = " ".join(tokens).strip(" .:-")
        if len(term) >= 2 and term.lower() not in {t.lower() for t in terms}:
            terms.append(term)
    return terms[:_MAX_TERMS_PER_CONCEPT]


def _tiab(term: str) -> str:
    return f'"{term}"[tiab]' if re.search(r"[^A-Za-z0-9]", term) else f"{term}[tiab]"


def lookup_mesh_headings(term: str, limit: int = _MAX_MESH_PER_CONCEPT) -> List[str]:
    """MeSH headings PubMed's automatic term mapping assigns to ``term``.

    The term is sent untagged so PubMed applies its own mapping; the headings are
    read from the returned query translation. Any network or parsing failure
    returns an empty list, so a plan never fails because NCBI is unreachable.
    """
    import pubmed_client

    params: Dict[str, Any] = {"db": "pubmed", "term": term, "retmax": 0, "retmode": "json"}
    params.update(pubmed_client.eutils_identity_params())
    try:
        response = pubmed_client._get_with_retry(pubmed_client.PUBMED_ESEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        translation = (response.json().get("esearchresult") or {}).get("querytranslation") or ""
    except Exception as exc:  # network, HTTP or JSON failure: plan stays usable without MeSH
        logger.warning("MeSH lookup failed (%s)", type(exc).__name__)
        return []
    headings: List[str] = []
    for heading in _MESH_RE.findall(translation):
        if heading.lower() not in {h.lower() for h in headings}:
            headings.append(heading)
    return headings[:limit]


def _build_concept(element: Dict[str, Any], lookup: Optional[Callable[[str], List[str]]]) -> Dict[str, Any]:
    value = element["value"]
    stated = value != NOT_STATED_TR
    terms = _concept_terms(value) if stated else []
    mesh: List[str] = []
    if lookup and terms:
        for term in terms[:_MAX_MESH_PER_CONCEPT]:
            for heading in lookup(term) or []:
                if heading.lower() not in {h.lower() for h in mesh}:
                    mesh.append(heading)
        mesh = mesh[:_MAX_MESH_PER_CONCEPT]
    free_text = " OR ".join(_tiab(t) for t in terms)
    mesh_text = " OR ".join(f'"{h}"[MeSH Terms]' for h in mesh)
    block = ""
    if free_text:
        block = f"({mesh_text} OR {free_text})" if mesh_text else f"({free_text})"
    return {
        "key": element["key"],
        "label": element["label"],
        "value": value,
        "stated": stated,
        "terms": terms,
        "mesh_headings": mesh,
        "free_text_block": f"({free_text})" if free_text else "",
        "block": block,
    }


def _filters_text(params: Dict[str, Any]) -> str:
    parts = []
    pub_type = params.get("publication_type")
    if pub_type and pub_type != "Tümü":
        parts.append(f"yayın tipi: {pub_type}")
    start, end = params.get("start_year"), params.get("end_year")
    if start or end:
        parts.append(f"yıl: {start or '…'}–{end or '…'}")
    return "; ".join(parts) if parts else "uygulanmadı"


def build_search_plan(
    query: str,
    search_metadata: Optional[Dict[str, Any]] = None,
    retrieved_count: Optional[int] = None,
    verify_mesh: bool = False,
    mesh_lookup: Optional[Callable[[str], List[str]]] = None,
) -> Dict[str, Any]:
    """Build the plan as a plain dict. Network is used only if MeSH lookup is requested."""
    query = _clean_text(query)
    selection = question_framework.select_question_framework(query)
    qtype = selection["question_type"]
    elements = selection["elements"]
    search_idx = _SEARCH_ELEMENT_INDEXES.get(qtype, (0, 1))
    lookup = mesh_lookup or (lookup_mesh_headings if verify_mesh else None)

    concepts = []
    for position, element in enumerate(elements):
        if position in search_idx:
            concept = _build_concept(element, lookup)
        else:
            concept = {"key": element["key"], "label": element["label"], "value": element["value"],
                       "stated": element["value"] != NOT_STATED_TR, "terms": [], "mesh_headings": [],
                       "free_text_block": "", "block": ""}
        concept["in_search"] = position in search_idx
        concepts.append(concept)

    searched = [c for c in concepts if c["in_search"]]
    suggested_query = " AND ".join(c["block"] for c in searched if c["block"])
    free_text_query = " AND ".join(c["free_text_block"] for c in searched if c["free_text_block"])

    warnings: List[str] = []
    missing = [c["label"] for c in searched if not c["stated"]]
    if missing:
        warnings.append("Sorguda belirtilmeyen arama kavramı: " + ", ".join(missing)
                        + ". Bu kavram aramaya eklenmedi; sonuçlar geniş olabilir.")
    query_is_fallback = False
    if not suggested_query and query:
        suggested_query = query
        query_is_fallback = True
        warnings.append("Sorgudan kavramlar ayrıştırılamadı; önerilen ifade olarak sorgu metni olduğu gibi "
                        "bırakıldı (PubMed otomatik terim eşleştirmesi uygular). Kavram bloklarını elle yazın.")
    if _TURKISH_LETTERS_RE.search(query) or _TURKISH_WORDS_RE.search(query):
        warnings.append("Sorgu Türkçe görünüyor. PubMed İngilizce terimlerle indekslenir; "
                        "terimleri İngilizce yazarak arayın (terimler otomatik çevrilmedi).")
    if any(len(c["terms"]) > 1 for c in searched):
        warnings.append("Virgül, noktalı virgül veya 'or' ile ayrılan ifadeler OR ile birleştirildi; "
                        "eş anlamlı olmayan kavramlar varsa ayırın.")

    if lookup is None:
        mesh_status = "doğrulanmadı"
        mesh_note = ("MeSH başlıkları tahmin edilmedi. PubMed'in MeSH veri tabanında kendiniz doğrulayın "
                     "veya doğrulamayı açın.")
    elif any(c["mesh_headings"] for c in searched):
        mesh_status = "PubMed terim eşleştirmesinden alındı"
        mesh_note = "Başlıklar PubMed'in otomatik terim eşleştirmesinden geldi; MeSH veri tabanında yine de kontrol edin."
    else:
        mesh_status = "eşleşme bulunamadı"
        mesh_note = "PubMed bu terimler için MeSH başlığı döndürmedi veya arama yapılamadı; yalnızca serbest metin kullanıldı."

    params = (search_metadata or {}).get("search_params") or {}
    executed = None
    if search_metadata is not None or retrieved_count is not None:
        meta = search_metadata or {}
        executed = {
            "databases": ["PubMed (NCBI E-utilities)"],
            "query": _clean_text(meta.get("query") or query),
            "search_date": meta.get("search_date"),
            "filters": _filters_text(params),
            "sort": params.get("sort"),
            "total_count": meta.get("total_count"),
            "retrieved_count": retrieved_count,
        }

    inclusion = []
    for position in search_idx:
        if position < len(elements):
            el = elements[position]
            inclusion.append(f"{el['label']}: {el['value'] if el['value'] != NOT_STATED_TR else 'sorguda belirtilmedi; ölçüt yazmadan önce netleştirin'}")
    inclusion.append(f"Uygun çalışma türü: {selection['preferred_designs']}")
    inclusion.append(f"Yayın filtreleri: {_filters_text(params)}")

    return {
        "query": query,
        "question_type": qtype,
        "question_type_tr": selection["question_type_tr"],
        "framework": selection["framework"],
        "concepts": concepts,
        "suggested_query": suggested_query,
        "query_is_fallback": query_is_fallback,
        "free_text_query": free_text_query,
        "mesh_status": mesh_status,
        "mesh_note": mesh_note,
        "inclusion_criteria": inclusion,
        "exclusion_criteria": list(_DEFAULT_EXCLUSIONS_TR),
        "criteria_status": STATUS_PROPOSAL_TR,
        "screened_against_criteria": False,
        "other_databases": [dict(d) for d in DATABASE_NOTES_TR],
        "table_columns": list(TABLE_COLUMNS_TR),
        "executed": executed,
        "warnings": warnings,
        "is_proposal": True,
    }


def render_table_template_markdown(columns: Optional[List[str]] = None) -> str:
    columns = columns or TABLE_COLUMNS_TR
    return "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |\n"


def render_search_plan_markdown(
    plan: Dict[str, Any],
    heading_level: int = 3,
    include_executed: bool = True,
    include_table_template: bool = True,
) -> str:
    """Turkish markdown for the plan. Starts with a heading of ``heading_level`` ``#``."""
    h = "#" * max(1, heading_level)
    sub = "#" * (max(1, heading_level) + 1)
    executed = plan.get("executed")
    if include_executed and executed:
        scope = "Yalnızca \"Uygulanan arama\" başlığı altında yazılanlar gerçekten çalıştırılmıştır"
    else:
        scope = "Bu bölümdeki öneriler çalıştırılmamıştır; gerçekten çalıştırılan arama yalnızca yukarıda belirtilen arama ifadesidir"
    lines = [
        f"{h} 🔎 Arama Planı",
        f"Bu bölüm sorudan kurallarla üretilmiş bir **öneridir**. {scope}; "
        "kayıtlar önerilen ölçütlere göre **taranmamıştır**.",
        "",
    ]
    if include_executed and executed:
        lines.append(f"{sub} Uygulanan arama")
        lines.append(f"- **Veri tabanı:** {', '.join(executed['databases'])}")
        lines.append(f"- **Arama ifadesi:** `{executed['query']}`")
        if executed.get("search_date"):
            lines.append(f"- **Tarama tarihi:** {executed['search_date']}")
        lines.append(f"- **Filtreler:** {executed['filters']}")
        if executed.get("total_count") is not None:
            lines.append(f"- **PubMed'deki toplam eşleşme:** {executed['total_count']}")
        if executed.get("retrieved_count") is not None:
            lines.append(f"- **İncelenen kayıt:** {executed['retrieved_count']}")
        lines.append("")

    lines.append(f"{sub} Önerilen arama stratejisi (çalıştırılmadı)")
    lines.append(f"- **Soru türü ve çerçeve:** {plan['question_type_tr']} — {plan['framework']}")
    for c in plan["concepts"]:
        if c["in_search"]:
            shown = ", ".join(c["terms"]) if c["terms"] else NOT_STATED_TR
            lines.append(f"- **{c['key']} — {c['label']}; aramada:** {shown}")
            if c["mesh_headings"]:
                lines.append(f"  - MeSH: {', '.join(c['mesh_headings'])}")
        else:
            lines.append(f"- **{c['key']} — {c['label']}; aramaya eklenmedi:** {c['value']} "
                         "(sonuçları gereksiz daraltmamak için)")
    if plan["suggested_query"]:
        lines.append(f"- **Önerilen PubMed ifadesi:** `{plan['suggested_query']}`")
    lines.append(f"- **MeSH durumu:** {plan['mesh_status']}. {plan['mesh_note']}")
    lines.append("")

    lines.append(f"{sub} Önerilen dahil etme ölçütleri ({plan['criteria_status']})")
    lines.extend(f"- {item}" for item in plan["inclusion_criteria"])
    lines.append("")
    lines.append(f"{sub} Önerilen dışlama ölçütleri ({plan['criteria_status']})")
    lines.extend(f"- {item}" for item in plan["exclusion_criteria"])
    lines.append("")

    lines.append(f"{sub} Bakılabilecek veri tabanları")
    lines.extend(f"- **{d['name']}:** {d['note']}" for d in plan["other_databases"])
    lines.append("")

    if plan["warnings"]:
        lines.append(f"{sub} Uyarılar")
        lines.extend(f"- {w}" for w in plan["warnings"])
        lines.append("")

    if include_table_template:
        lines.append(f"{sub} Çalışma tablosu şablonu (elle doldurulacak)")
        lines.append(render_table_template_markdown(plan["table_columns"]))
    return "\n".join(lines).rstrip() + "\n"

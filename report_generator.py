import os
import re
from typing import List, Dict, Any, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from pubmed_client import verify_citation


def _format_authors_short(authors: List[str]) -> str:
    if not authors:
        return "Bilinmeyen Yazar"
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} ve {authors[1]}"
    return f"{authors[0]} et al."


def classify_study_design(pub_types: List[str], title: str, abstract: str) -> Dict[str, Any]:
    """
    Classifies study design and evidence level using NLM publication types for preliminary
    classification, falling back to title and abstract heuristics.
    """
    pts = [pt.lower() for pt in (pub_types or []) if pt]

    # 1. Preliminary classification via official NLM Publication Types (in priority order)
    if any("meta-analysis" in pt or "sistematik derleme" in pt for pt in pts):
        return {
            "design": "Sistematik Derleme / Meta-Analiz",
            "level": "Seviye 1",
            "level_num": 1,
            "badge_color": "#1E40AF"
        }
    if any("systematic review" in pt for pt in pts):
        return {
            "design": "Sistematik Derleme / Meta-Analiz",
            "level": "Seviye 1",
            "level_num": 1,
            "badge_color": "#1E40AF"
        }
    if any("randomized controlled trial" in pt for pt in pts):
        return {
            "design": "Rastgele Kontrollü Çalışma (RCT)",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#047857"
        }
    if any("clinical trial" in pt or "controlled clinical trial" in pt for pt in pts):
        return {
            "design": "Kontrollü Klinik Araştırma",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#059669"
        }
    if any("observational study" in pt or "cohort" in pt or "longitudinal" in pt or "prospective study" in pt for pt in pts):
        return {
            "design": "Kohort Çalışması (Gözlemsel)",
            "level": "Seviye 3",
            "level_num": 3,
            "badge_color": "#D97706"
        }
    if any("case reports" in pt or "case report" in pt for pt in pts):
        return {
            "design": "Olgu Sunumu / Vaka Serisi",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    if any("review" in pt or "derleme" in pt for pt in pts):
        return {
            "design": "Niteliksel Derleme / Uzman Görüşü",
            "level": "Seviye 5",
            "level_num": 5,
            "badge_color": "#4B5563"
        }

    # 2. Secondary check based on Title
    title_lower = (title or "").lower()
    if "systematic review" in title_lower or "meta-analysis" in title_lower or "sistematik derleme" in title_lower:
        return {
            "design": "Sistematik Derleme / Meta-Analiz",
            "level": "Seviye 1",
            "level_num": 1,
            "badge_color": "#1E40AF"
        }
    elif "randomized" in title_lower or "rct" in title_lower or "rastgele kontrollü" in title_lower:
        return {
            "design": "Rastgele Kontrollü Çalışma (RCT)",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#047857"
        }
    elif "clinical trial" in title_lower or "klinik araştırma" in title_lower:
        return {
            "design": "Kontrollü Klinik Araştırma",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#059669"
        }
    elif "cohort" in title_lower or "prospective" in title_lower or "longitudinal" in title_lower or "kohort" in title_lower:
        return {
            "design": "Kohort Çalışması (Gözlemsel)",
            "level": "Seviye 3",
            "level_num": 3,
            "badge_color": "#D97706"
        }
    elif "case-control" in title_lower or "vaka-kontrol" in title_lower or "case control" in title_lower:
        return {
            "design": "Vaka-Kontrol Çalışması",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    elif "case report" in title_lower or "case series" in title_lower or "olgu sunumu" in title_lower:
        return {
            "design": "Olgu Sunumu / Vaka Serisi",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    elif "review" in title_lower or "derleme" in title_lower:
        return {
            "design": "Niteliksel Derleme / Uzman Görüşü",
            "level": "Seviye 5",
            "level_num": 5,
            "badge_color": "#4B5563"
        }

    # 3. Tertiary fallback based on Abstract
    abstract_lower = (abstract or "").lower()
    if "systematic review" in abstract_lower or "meta-analysis" in abstract_lower or "sistematik derleme" in abstract_lower:
        return {
            "design": "Sistematik Derleme / Meta-Analiz",
            "level": "Seviye 1",
            "level_num": 1,
            "badge_color": "#1E40AF"
        }
    elif "randomized controlled trial" in abstract_lower or "randomized trial" in abstract_lower or "rastgele kontrollü" in abstract_lower:
        return {
            "design": "Rastgele Kontrollü Çalışma (RCT)",
            "level": "Seviye 2",
            "level_num": 2,
            "badge_color": "#047857"
        }
    elif "cohort study" in abstract_lower or "prospective cohort" in abstract_lower or "kohort çalışması" in abstract_lower:
        return {
            "design": "Kohort Çalışması (Gözlemsel)",
            "level": "Seviye 3",
            "level_num": 3,
            "badge_color": "#D97706"
        }
    elif "case-control study" in abstract_lower or "vaka-kontrol çalışması" in abstract_lower:
        return {
            "design": "Vaka-Kontrol Çalışması",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    elif "case report" in abstract_lower or "olgu sunumu" in abstract_lower:
        return {
            "design": "Olgu Sunumu / Vaka Serisi",
            "level": "Seviye 4",
            "level_num": 4,
            "badge_color": "#DC2626"
        }
    elif "review" in abstract_lower or "derleme" in abstract_lower:
        return {
            "design": "Niteliksel Derleme / Uzman Görüşü",
            "level": "Seviye 5",
            "level_num": 5,
            "badge_color": "#4B5563"
        }

    return {
        "design": "Primer Araştırma / Dergi Makalesi",
        "level": "Seviye 3-5",
        "level_num": 4,
        "badge_color": "#6B7280"
    }


def _classify_evidence_level(pub_types: List[str], title: str, abstract: str) -> str:
    res = classify_study_design(pub_types, title, abstract)
    return f"{res['level']} ({res['design']})"


def extract_pico(query: str, abstract: str = "") -> Dict[str, str]:
    """
    Extracts PICO (Population, Intervention, Comparison, Outcome) framework components
    from clinical search query and/or study abstract text.
    """
    text = (query + " " + abstract).strip()

    # Population extraction heuristics
    population = "Belirtilmedi / Genel Hasta Grubu"
    pop_matches = re.findall(r"\b(patients?|adults?|children|elderly|infants?|women|men|subjects?|cohort|cases?)\b.*?\b(with|having|diagnosed|suffering|in)\b\s+([^,.;]+)", text, re.IGNORECASE)
    if pop_matches:
        population = f"{pop_matches[0][0]} {pop_matches[0][1]} {pop_matches[0][2]}".strip()
    elif "in " in query.lower():
        parts = query.lower().split("in ")
        if len(parts) > 1:
            population = parts[1].strip().capitalize()

    # Intervention extraction heuristics
    intervention = "Belirtilmedi / Temel Müdahale"
    if query:
        words = query.split()
        if len(words) >= 1:
            intervention = query.strip()

    # Comparison extraction heuristics
    comparison = "Plasebo / Standart Tedavi / Kontrol Grubu"
    comp_matches = re.search(r"\b(versus|vs\.?|compared (?:to|with)|against|placebo|standard care|control)\b\s+([^,.;]+)", text, re.IGNORECASE)
    if comp_matches:
        comparison = comp_matches.group(0).strip()

    # Outcome extraction heuristics
    outcome = "Klinik Etkinlik, Güvenlilik ve Primer Sonlanım Noktaları"
    out_matches = re.search(r"\b(reduced|increased|associated with|improved|mortality|survival|risk|hospitalization|events|endpoint|efficacy|safety|primary outcome)\b\s+([^,.;]+)", text, re.IGNORECASE)
    if out_matches:
        outcome = out_matches.group(0).strip()

    return {
        "population": population,
        "intervention": intervention,
        "comparison": comparison,
        "outcome": outcome
    }


def assess_risk_of_bias(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates Risk of Bias status for RoB 2 (RCTs) or ROBINS-I (Non-Randomized Studies).
    Formal risk of bias is marked as 'Değerlendirilmedi (Not Assessed)' because abstract-only
    data is insufficient for automated methodological bias scoring.
    """
    pub_types = article.get("publication_types", [])
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    design_info = classify_study_design(pub_types, title, abstract)

    is_rct = "RCT" in design_info["design"] or "Rastgele" in design_info["design"] or "Randomized" in " ".join(pub_types)

    not_assessed_msg = "Değerlendirilmedi (Not Assessed - Tam Metin Gereklidir)"

    if is_rct:
        domains = {
            "D1: Rastgeleleştirme Süreci": not_assessed_msg,
            "D2: Öngörülen Müdahalelerden Sapmalar": not_assessed_msg,
            "D3: Eksik Sonuç Verileri": not_assessed_msg,
            "D4: Sonuç Ölçümü": not_assessed_msg,
            "D5: Bildirilen Sonucun Seçimi": not_assessed_msg
        }
        return {
            "tool": "RoB 2 (Cochrane Risk of Bias for RCTs)",
            "study_type": "Randomize Kontrollü Çalışma",
            "overall_rating": "Değerlendirilmedi (Not Assessed)",
            "badge_color": "#6B7280",
            "domains": domains,
            "note": "Resmi RoB 2 değerlendirmesi yalnızca özet (abstract) metnine dayanarak otomatik yapılamaz; tam metin (full-text) incelemesi gereklidir."
        }
    else:
        domains = {
            "D1: Karıştırıcı Değişken Yanlılığı (Confounding)": not_assessed_msg,
            "D2: Katılımcı Seçimi Yanlılığı": not_assessed_msg,
            "D3: Müdahale Sınıflandırma Yanlılığı": not_assessed_msg,
            "D4: Müdahaleden Sapma Yanlılığı": not_assessed_msg,
            "D5: Eksik Veri Yanlılığı": not_assessed_msg,
            "D6: Sonuç Ölçüm Yanlılığı": not_assessed_msg,
            "D7: Bildirilen Sonuç Seçim Yanlılığı": not_assessed_msg
        }
        return {
            "tool": "ROBINS-I (Risk of Bias in Non-Randomized Studies)",
            "study_type": "Gözlemsel / Randomize Olmayan Çalışma",
            "overall_rating": "Değerlendirilmedi (Not Assessed)",
            "badge_color": "#6B7280",
            "domains": domains,
            "note": "Resmi ROBINS-I değerlendirmesi yalnızca özet (abstract) metnine dayanarak otomatik yapılamaz; tam metin (full-text) incelemesi gereklidir."
        }


def generate_evidence_table_markdown(articles: List[Dict[str, Any]]) -> str:
    """Generates a structured Markdown table of evidence with PICO & Risk of Bias for the report."""
    if not articles:
        return "*Tablo için gösterilecek veri bulunamadı.*"

    rows = [
        "| # | Çalışma / Yazar (Yıl) | Tasarım & Kanıt Seviyesi | Yanlılık Riski (RoB 2 / ROBINS-I) | PMID / DOI | Klinik Bulgular |",
        "|---|---|---|---|---|---|"
    ]

    for idx, art in enumerate(articles, 1):
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        title = art.get("title", "Başlıksız")
        journal = art.get("journal", "Bilinmeyen Dergi")
        pmid = art.get("pmid", "")
        doi = art.get("doi", "")

        classification = classify_study_design(
            art.get("publication_types", []),
            title,
            art.get("abstract", "")
        )
        design_str = f"**{classification['level']}**<br>*{classification['design']}*"

        rob = assess_risk_of_bias(art)
        rob_str = f"**{rob['overall_rating']}**<br>*{rob['tool']}*"

        pmid_link = f"[PMID: {pmid}]({art.get('pubmed_url', '#')})" if pmid else "-"
        if doi:
            pmid_link += f"<br>[DOI: {doi}]({art.get('doi_url', '#')})"

        abstract_text = art.get("abstract", "").replace("|", "-").replace("\n", " ").strip()
        if len(abstract_text) > 200:
            abstract_snippet = abstract_text[:197] + "..."
        else:
            abstract_snippet = abstract_text or "Özet bilgisi bulunamadı."

        title_clean = title.replace("|", "-")

        rows.append(
            f"| {idx} | **{first_author}** ({year})<br>*{title_clean}* | {design_str} | {rob_str} | {pmid_link} | {abstract_snippet} |"
        )

    return "\n".join(rows)


def generate_evidence_table_html(articles: List[Dict[str, Any]]) -> str:
    """Generates a clean HTML evidence table for web display and HTML exports."""
    if not articles:
        return "<p><em>Gösterilecek literatür verisi bulunamadı.</em></p>"

    html_rows = []
    for idx, art in enumerate(articles, 1):
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        title = art.get("title", "Başlıksız")
        journal = art.get("journal", "Bilinmeyen Dergi")
        pmid = art.get("pmid", "")
        doi = art.get("doi", "")

        classification = classify_study_design(
            art.get("publication_types", []),
            title,
            art.get("abstract", "")
        )

        rob = assess_risk_of_bias(art)

        abstract_text = art.get("abstract", "").replace("\n", " ").strip()
        if len(abstract_text) > 220:
            abstract_snippet = abstract_text[:217] + "..."
        else:
            abstract_snippet = abstract_text or "Özet bulunamadı."

        pmid_html = f'<a href="{art.get("pubmed_url", "#")}" target="_blank" style="color: #1E40AF; text-decoration: none; font-weight: bold;">PMID: {pmid}</a>' if pmid else "-"
        doi_html = f'<br><a href="{art.get("doi_url", "#")}" target="_blank" style="color: #3730A3; text-decoration: none; font-size: 0.85em;">DOI: {doi}</a>' if doi else ""

        html_rows.append(f"""
        <tr style="border-bottom: 1px solid #E5E7EB;">
            <td style="padding: 10px; font-weight: bold; text-align: center;">{idx}</td>
            <td style="padding: 10px;">
                <strong>{first_author}</strong> ({year})<br>
                <span style="font-size: 0.9em; color: #374151;">{title}</span><br>
                <small style="color: #6B7280;">{journal}</small>
            </td>
            <td style="padding: 10px; text-align: center;">
                <span style="background-color: {classification['badge_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">
                    {classification['level']}
                </span><br>
                <small style="color: #4B5563;">{classification['design']}</small>
            </td>
            <td style="padding: 10px; text-align: center;">
                <span style="background-color: {rob['badge_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">
                    {rob['overall_rating']}
                </span><br>
                <small style="color: #4B5563;">{rob['tool']}</small>
            </td>
            <td style="padding: 10px; font-size: 0.85em;">{pmid_html}{doi_html}</td>
            <td style="padding: 10px; font-size: 0.88em; color: #1F2937;">{abstract_snippet}</td>
        </tr>
        """)

    return f"""
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-family: sans-serif; font-size: 14px;">
        <thead>
            <tr style="background-color: #F3F4F6; color: #1F2937; text-align: left; border-bottom: 2px solid #D1D5DB;">
                <th style="padding: 10px; width: 4%;">#</th>
                <th style="padding: 10px; width: 24%;">Çalışma / Yazar</th>
                <th style="padding: 10px; width: 16%; text-align: center;">Tasarım & Kanıt</th>
                <th style="padding: 10px; width: 18%; text-align: center;">Yanlılık Riski</th>
                <th style="padding: 10px; width: 12%;">Kimlik</th>
                <th style="padding: 10px; width: 26%;">Klinik Bulgular</th>
            </tr>
        </thead>
        <tbody>
            {"".join(html_rows)}
        </tbody>
    </table>
    """


def perform_red_team_audit(query: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executes an evidence quality and citation integrity audit on the provided article set.
    Re-fetches each PMID independently to compare normalized article titles and DOI values.
    Rejects mismatches, shows API failures as unverified, includes abstract-only limitations,
    formal GRADE Not Assessed status, and excludes false claims or claims of clinical validation.
    """
    total = len(articles)

    verified_count = 0
    rejected_count = 0
    unverified_count = 0
    verification_details = []

    for art in articles:
        v_res = verify_citation(art)
        v_status = v_res.get("status", "unverified")
        verification_details.append(v_res)

        if v_status == "verified":
            verified_count += 1
        elif v_status == "rejected":
            rejected_count += 1
        else:
            unverified_count += 1

    pmid_list = [a.get("pmid") for a in articles if a.get("pmid")]
    has_duplicate_pmids = len(pmid_list) != len(set(pmid_list))
    missing_abstracts = sum(1 for a in articles if not a.get("abstract") or a.get("abstract") == "Özet bulunamadı.")
    missing_titles = sum(1 for a in articles if not a.get("title") or a.get("title") == "Başlık bulunamadı")

    designs_count = {}
    for art in articles:
        cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))
        d_name = cd["design"]
        designs_count[d_name] = designs_count.get(d_name, 0) + 1

    rct_and_meta_count = sum(
        count for d, count in designs_count.items()
        if "Sistematik" in d or "Rastgele" in d or "Meta-Analiz" in d or "RCT" in d
    )

    warnings = []
    if total > 0 and rct_and_meta_count == 0:
        warnings.append("İncelenen kaynaklar arasında yüksek seviyeli (Seviye 1 veya Seviye 2 - RCT/Meta-analiz) kanıt bulunmamaktadır.")

    if total < 3:
        warnings.append("Literatür örneklem sayısı düşüktür (3'ten az çalışma). Klinik genelleme yapılırken dikkatli olunmalıdır.")

    if has_duplicate_pmids:
        warnings.append("Girdi verileri arasında mükerrer (duplicate) PMID kayıtları mevcuttur.")

    if missing_abstracts > 0:
        warnings.append(f"{missing_abstracts} makalede özet (abstract) verisi bulunmamaktadır.")

    if missing_titles > 0:
        warnings.append(f"{missing_titles} makalede başlık verisi eksiktir.")

    if rejected_count > 0:
        warnings.append(f"{rejected_count} atıf kaydı bağımsız PubMed doğrulamasında başlık/DOI uyuşmazlığı veya eksik PMID nedeniyle reddedilmiştir.")

    if unverified_count > 0:
        warnings.append(f"{unverified_count} atıf kaydı API/ağ hatası nedeniyle bağımsız olarak doğrulanamadı (Unverified / API Failure).")

    abstract_only_count = sum(1 for a in articles if len(a.get("abstract", "")) < 100)
    if abstract_only_count > 0:
        warnings.append(f"{abstract_only_count} makalede yalnızca kısıtlı özet bilgisi bulunmaktadır. Tam metin incelemesi önerilir.")

    reason_counts = {}
    for v_res in verification_details:
        r = v_res.get("reason", "unknown")
        reason_counts[r] = reason_counts.get(r, 0) + 1

    return {
        "status": "DENETLEME TAMAMLANDI (AUDIT COMPLETE)",
        "metadata_retrieval_source": "NCBI PubMed E-utilities API",
        "abstract_only_limitation": "Tüm sentez ve analizler yalnızca yayınlanmış özet (abstract) metinlerine dayanmaktadır. Tam metin (full-text) değerlendirmesi yapılmamıştır.",
        "clinical_validation_status": "Klinik Doğrulama Yapılmamıştır (No Clinical Validation Claimed)",
        "citation_integrity": {
            "total_articles": total,
            "verified_citations": verified_count,
            "rejected_citations": rejected_count,
            "unverified_citations": unverified_count,
            "reason_breakdown": reason_counts,
            "metadata_retrieval": "PubMed E-utilities API üzerinden çekildi",
            "independent_verification": "NCBI PubMed E-utilities re-fetch ve title/DOI normalizasyon eşleştirmesi",
            "duplicate_pmids_found": has_duplicate_pmids,
            "missing_abstracts_count": missing_abstracts,
            "mismatch_or_invalid_citations_detected": rejected_count
        },
        "verification_results": verification_details,
        "study_design_distribution": designs_count,
        "grade_rating_policy": {
            "grade_status": "GRADE Değerlendirilmedi (Not Assessed)",
            "compliant": True,
            "notice": "GRADE (Grading of Recommendations Assessment, Development and Evaluation) derecelendirmesi otomatik olarak atanmamıştır ve 'GRADE Değerlendirilmedi (Not Assessed)' statüsündedir. Formal GRADE kanıt kesinlik değerlendirmesi, yanlılık riski (risk of bias), tutarsızlık, dolaylılık ve imprezisyon kriterlerinin uzmanlarca manuel meta-analitik sentezi ile yapılmalıdır."
        },
        "methodological_warnings": warnings
    }


def generate_rule_based_turkish_report(query: str, articles: List[Dict[str, Any]]) -> str:
    """Generates an advanced structured, deterministic Turkish evidence report from verified articles."""
    if not articles:
        return f"""# 📑 Türkçe Kanıt Raporu

**Klinik Sorgu / Araştırma Konusu:** {query}

---

### ⚠️ Sonuç Bulunamadı
Aranan klinik sorgu için doğrulanan PubMed veritabanında kriterlere uygun makale bulunamamıştır.
Lütfen arama terimlerini veya filtreleri genişleterek tekrar deneyiniz.
"""

    total_articles = len(articles)
    audit = perform_red_team_audit(query, articles)

    report = []
    report.append("# 📑 Türkçe Kanıt Raporu")
    report.append(f"**Klinik Sorgu / Araştırma Konusu:** {query}")
    report.append("**Rapor Tarihi & Veri Kaynağı:** NCBI PubMed E-utilities Canlı Veritabanı (Özet Metadata)")
    report.append(f"**İncelenen Makale Sayısı:** {total_articles}\n")
    report.append("---")

    # 1. PICO Yapısı ve Klinik Özet
    report.append("## 1. 🔍 PICO Yapısı ve Klinik Özet Sentezi")
    report.append(f"Bu rapor, **PubMed E-utilities API** vasıtasıyla çekilen **{total_articles} adet makale özeti (abstract)** temel alınarak hekimlerin literatür inceleme süreçlerini desteklemek amacıyla hazırlanmıştır.")
    report.append("**Özet Metin Sınırlılığı Uyarısı:** Bu rapordaki klinik bulgular yalnızca yayınlanmış özet (abstract) metinlerine dayanmakta olup tam metin (full-text) değerlendirmesi içermez.\n")

    pico = extract_pico(query, articles[0].get("abstract", "") if articles else "")
    report.append("### 📋 Klinik PICO Çerçevesi")
    report.append(f"- **P (Population / Hasta Grubu):** {pico['population']}")
    report.append(f"- **I (Intervention / Müdahale):** {pico['intervention']}")
    report.append(f"- **C (Comparison / Karşılaştırma):** {pico['comparison']}")
    report.append(f"- **O (Outcome / Klinik Sonlanım):** {pico['outcome']}\n")

    for idx, art in enumerate(articles, 1):
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        title = art.get("title", "Başlıksız")
        abstract = art.get("abstract", "Özet bilgisi mevcut değil.")
        pmid = art.get("pmid", "Yok")
        cd = classify_study_design(art.get("publication_types", []), title, abstract)
        rob = assess_risk_of_bias(art)

        abstract_snippet = abstract.strip()
        if len(abstract_snippet) > 400:
            abstract_snippet = abstract_snippet[:397] + "..."

        report.append(f"### {idx}. {title}")
        report.append(f"- **Yazar(lar) ve Yıl:** {first_author} ({year})")
        report.append(f"- **Çalışma Tasarımı & Seviyesi:** {cd['level']} ({cd['design']})")
        report.append(f"- **Yanlılık Riski Değerlendirmesi:** {rob['overall_rating']} ({rob['tool']})")
        report.append(f"- **Dergi:** *{art.get('journal', 'Bilinmiyor')}*")
        report.append(f"- **Klinik Özet & Bulgular:** {abstract_snippet}")
        report.append(f"- **Kaynak Doğrulama:** [PMID: {pmid}]({art.get('pubmed_url', '#')})" + (f" | [DOI: {art.get('doi')}]({art.get('doi_url', '#')})" if art.get("doi") else "") + "\n")

    # 2. Yapılandırılmış Kanıt Tablosu
    report.append("## 2. 📊 Yapılandırılmış Kanıt Tablosu (Evidence Table)")
    report.append("İncelenen çalışmaların metodolojik karşılaştırması ve özet tablosu aşağıda sunulmuştur:\n")
    report.append(generate_evidence_table_markdown(articles))
    report.append("\n")

    # 3. Metodolojik Sınırlılıklar ve Klinik Uyarılar
    report.append("## 3. ⚠️ Metodolojik Sınırlılıklar ve Klinik Uyarılar")
    report.append("### A. Özet Metin Sınırlılığı (Abstract-Only Limitation)")
    report.append("- **Sadece Özet Verisi:** Bu rapordaki sentez strictly makalelerin yayınlanmış özet (abstract) verilerine dayanmaktadır. Tam metin (full-text) metot, protokole uyum, ham veri ve hasta bazlı metodolojik detaylar incelenmemiştir. Klinik kararlardan önce tam metin değerlendirmesi şarttır.")
    report.append("- **Gözlemsel Yanlılık Riski:** Kohort ve vaka-kontrol tasarımlı çalışmalarda karıştırıcı değişkenler (confounding factors) ve seçim yanlılığı (selection bias) riski mevcuttur.")
    report.append("- **Yayın Yanlılığı (Publication Bias):** Pozitif sonuçlu çalışmaların yayınlanma olasılığının daha yüksek olması nedeniyle literatür genelinde yayın yanlılığı riski mevcuttur.")

    report.append("\n### B. Formal GRADE Derecelendirme Statüsü")
    report.append(f"- **GRADE Statüsü:** **{audit['grade_rating_policy']['grade_status']}**")
    report.append(f"- {audit['grade_rating_policy']['notice']}\n")

    report.append("### C. Klinik Doğrulama Sorumluluk Reddi (Clinical Validation Disclaimer)")
    report.append("- **Klinik Doğrulama İddiası Yoktur (No Clinical Validation Claimed):** Bu sistem klinik olarak doğrulanmış bir tıbbi cihaz veya doğrudan tanı/tedavi kararı veren bir yazılım değildir. Yalnızca tıbbi araştırmalarda hekimlere literatür taraması kolaylığı sağlayan bir araştırma yardımcısıdır.")
    report.append("- **Hekim Sorumluluğu:** Klinik kararlar her hastanın bireysel özellikleri göz önünde bulundurularak sorumlu hekim tarafından verilmelidir.\n")

    # 4. Red Team Denetimi ve Atıf Dürüstlüğü Analizi
    report.append("## 4. 🛡️ Red Team Denetimi ve Atıf Dürüstlüğü Analizi")
    report.append(f"- **Denetim Statüsü:** `{audit['status']}`")
    report.append(f"- **PubMed Metadata Alımı:** {audit['citation_integrity']['total_articles']} makale kaydı NCBI PubMed E-utilities API üzerinden indirildi.")
    report.append(f"- **Bağımsız Atıf Doğrulaması (Re-Fetch & Matching):** {audit['citation_integrity']['verified_citations']} Doğrulanmış (Verified), {audit['citation_integrity']['rejected_citations']} Reddedilen (Rejected Mismatch), {audit['citation_integrity']['unverified_citations']} Doğrulanamadı (Unverified / API Failure)")
    report.append(f"- **GRADE Statüsü:** {audit['grade_rating_policy']['grade_status']}")
    report.append(f"- **Kapsam:** Yalnızca Özet Metin Analizi (Abstract-Only Limitation)")
    report.append(f"- **Klinik Doğrulama:** {audit['clinical_validation_status']}")
    report.append("- **Çalışma Tasarımı Dağılımı:**")
    for d_name, count in audit["study_design_distribution"].items():
        report.append(f"  - {d_name}: {count} adet")

    if audit["methodological_warnings"]:
        report.append("- **Metodolojik Uyarılar:**")
        for warn in audit["methodological_warnings"]:
            report.append(f"  - ⚠️ {warn}")
    else:
        report.append("- **Metodolojik Uyarılar:** Herhangi bir kritik metodolojik uyarı tespit edilmedi.")
    report.append("\n")

    # 5. Doğrulanmış Kaynaklar ve Literatür Listesi
    report.append("## 5. 📚 Doğrulanmış Kaynaklar ve Literatür Listesi")
    for idx, art in enumerate(articles, 1):
        authors_str = ", ".join(art.get("authors", [])) if art.get("authors") else "Yazar bilgisi yok"
        title = art.get("title", "")
        journal = art.get("journal", "")
        year = art.get("pub_year", "")
        pmid = art.get("pmid", "")
        doi = art.get("doi", "")

        ref_line = f"{idx}. **{authors_str}** ({year}). *{title}*. {journal}."
        if pmid:
            ref_line += f" PMID: [{pmid}]({art.get('pubmed_url', '#')})."
        if doi:
            ref_line += f" DOI: [{doi}]({art.get('doi_url', '#')})."

        report.append(ref_line)

    return "\n".join(report)


def generate_llm_turkish_report(query: str, articles: List[Dict[str, Any]], api_key: str, model: str = "gpt-4o-mini") -> str:
    """Generates a Turkish evidence report using LLM with strict grounding and limitation constraints."""
    if not OpenAI:
        return generate_rule_based_turkish_report(query, articles)

    client = OpenAI(api_key=api_key)

    context_blocks = []
    for idx, art in enumerate(articles, 1):
        cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))
        context_blocks.append(
            f"--- MAKALE [{idx}] ---\n"
            f"PMID: {art.get('pmid')}\n"
            f"DOI: {art.get('doi', 'Yok')}\n"
            f"Başlık: {art.get('title')}\n"
            f"Yazarlar: {', '.join(art.get('authors', []))}\n"
            f"Dergi / Yıl: {art.get('journal')} ({art.get('pub_year')})\n"
            f"Makale Türü & Tasarım: {', '.join(art.get('publication_types', []))} ({cd['level']} - {cd['design']})\n"
            f"Özet: {art.get('abstract')}\n"
        )

    context_str = "\n".join(context_blocks)
    evidence_table_md = generate_evidence_table_markdown(articles)

    system_prompt = (
        "Sen uzman bir tıbbi araştırmacı ve klinik kanıt analistisin. Görevin, sağlanan PubMed makale özetlerini "
        "kullanarak tıp hekimleri için Türkçe Klinik Kanıt Raporu hazırlamaktır.\n\n"
        "KESİN KURALLAR VE KLİNİK RAPORLAMA KISITLARI:\n"
        "1. KESİNLİKLE uydurma atıf, uydurma PMID, uydurma makale veya kaynak gösterme! Yalnızca verilen makalelerdeki gerçek verileri kullan.\n"
        "2. KESİNLİKLE '100/100 doğrulandı', '0% halüsinasyon riski' veya 'klinik olarak doğrulanmıştır' gibi asılsız iddialarda BULUNMA!\n"
        "3. KESİNLİKLE otomatik GRADE derecelendirmesi uydurma! GRADE statüsünün 'GRADE Değerlendirilmedi (Not Assessed)' olduğunu açıkça belirt.\n"
        "4. Raporda analizlerin yalnızca özet (abstract) metinlerine dayandığını, tam metin incelemesi olmadığını vurgula.\n"
        "5. Her iddia ve klinik bulgudan sonra metin içinde ilgili makalenin PMID'sine veya yazar/yılına atıf yap (örneğin [PMID: 12345678]).\n"
        "6. Raporu şu ana başlıklar altında Türkçe olarak yaz:\n"
        "   - # 📑 Türkçe Kanıt Raporu\n"
        "   - ## 1. 🔍 Klinik Özet ve Sentez\n"
        "   - ## 2. 📊 Yapılandırılmış Kanıt Tablosu (Evidence Table)\n"
        "   - ## 3. ⚠️ Metodolojik Sınırlılıklar ve Klinik Uyarılar\n"
        "   - ## 4. 🛡️ Red Team Denetimi ve Atıf Dürüstlüğü Analizi\n"
        "   - ## 5. 📚 Doğrulanmış Kaynaklar ve Literatür Listesi (Yalnızca verilen makaleler tam formatta listelenmeli)\n"
    )

    user_prompt = (
        f"Klinik Sorgu: {query}\n\n"
        f"Önceden Üretilmiş Kanıt Tablosu (Lütfen 2. bölümde aynen kullan):\n{evidence_table_md}\n\n"
        f"Sağlanan Literatür Kaynakları:\n{context_str}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        rule_report = generate_rule_based_turkish_report(query, articles)
        return f"*(LLM Üretiminde Hata: {str(e)} - Otomatik Kural Tabanlı Rapor Oluşturuldu)*\n\n" + rule_report


def generate_turkish_evidence_report(
    query: str,
    articles: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    use_llm: bool = False,
    model: str = "gpt-4o-mini"
) -> str:
    """Main entry point to generate Turkish evidence reports."""
    if use_llm and api_key and api_key.strip():
        return generate_llm_turkish_report(query, articles, api_key.strip(), model=model)
    else:
        return generate_rule_based_turkish_report(query, articles)


def generate_html_report(query: str, articles: List[Dict[str, Any]], markdown_content: str) -> str:
    """
    Generates a full standalone, print-friendly HTML report for Turkish evidence synthesis.
    """
    audit = perform_red_team_audit(query, articles)

    content_html = markdown_content
    content_html = re.sub(r"^# (.*)$", r'<h1 style="color: #1E3A8A; border-bottom: 2px solid #1E3A8A; padding-bottom: 8px;">\1</h1>', content_html, flags=re.MULTILINE)
    content_html = re.sub(r"^## (.*)$", r'<h2 style="color: #1E40AF; margin-top: 24px;">\1</h2>', content_html, flags=re.MULTILINE)
    content_html = re.sub(r"^### (.*)$", r'<h3 style="color: #1F2937;">\1</h3>', content_html, flags=re.MULTILINE)
    content_html = re.sub(r"\*\*(.*?)\*\*", r'<strong>\1</strong>', content_html)
    content_html = re.sub(r"\*(.*?)\*", r'<em>\1</em>', content_html)
    content_html = re.sub(r"^> (.*)$", r'<blockquote style="border-left: 4px solid #3B82F6; background-color: #EFF6FF; margin: 10px 0; padding: 10px 15px;">\1</blockquote>', content_html, flags=re.MULTILINE)
    content_html = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" target="_blank" style="color: #2563EB;">\1</a>', content_html)
    content_html = content_html.replace("\n\n", "<br><br>")

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Türkçe Klinik Kanıt Raporu - {query}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #1F2937;
            max-width: 1000px;
            margin: 0 auto;
            padding: 30px;
            background-color: #FFFFFF;
        }}
        .header-box {{
            background-color: #F0F9FF;
            border: 1px solid #BAE6FD;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
        }}
        .audit-badge {{
            background-color: #D1FAE5;
            color: #065F46;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        @media print {{
            body {{ padding: 0; max-width: 100%; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="header-box">
        <h1 style="margin-top: 0; color: #0369A1;">🩺 Türkçe Klinik Kanıt Raporu</h1>
        <p><strong>Klinik Sorgu:</strong> {query}</p>
        <p><strong>Rapor Türü:</strong> Tıbbi Araştırma Destek Raporu (NCBI PubMed Veritabanı)</p>
        <p><strong>Denetim Statüsü:</strong> <span class="audit-badge">{audit['status']}</span></p>
        <p><strong>GRADE Statüsü:</strong> {audit['grade_rating_policy']['grade_status']}</p>
        <p><strong>Veri Kapsamı:</strong> Yalnızca Özet Metin (Abstract-Only Limitation)</p>
    </div>

    <div>
        {content_html}
    </div>

    <hr style="margin-top: 40px; border: 0; border-top: 1px solid #E5E7EB;">
    <p style="font-size: 0.85em; color: #6B7280; text-align: center;">
        Medical Research AI Platformu - Doğrulanmış NCBI PubMed Veritabanı Araştırma Destek Modülü.<br>
        <em>Uyarı: Bu sistem klinik olarak doğrulanmış bir teşhis/tedavi aracı değildir (No Clinical Validation claimed). Bireysel klinik kararlar sorumlu hekim tarafından verilmelidir.</em>
    </p>
</body>
</html>
"""

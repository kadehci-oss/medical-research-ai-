import os

from typing import List, Dict, Any, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _format_authors_short(authors: List[str]) -> str:
    if not authors:
        return "Bilinmeyen Yazar"
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} ve {authors[1]}"
    return f"{authors[0]} et al."


def _classify_evidence_level(pub_types: List[str], title: str, abstract: str) -> str:
    combined = " ".join(pub_types + [title, abstract]).lower()
    if "systematic review" in combined or "meta-analysis" in combined or "sistematik derleme" in combined:
        return "Seviye 1 (Sistematik Derleme / Meta-Analiz)"
    elif "randomized controlled trial" in combined or "clinical trial" in combined or "rct" in combined:
        return "Seviye 2 (Rastgele Kontrollü Çalışma / Klinik Araştırma)"
    elif "cohort" in combined or "kohort" in combined:
        return "Seviye 3 (Kohort Çalışması / Gözlemsel)"
    elif "case-control" in combined or "vaka-kontrol" in combined or "case study" in combined or "olgu sunumu" in combined:
        return "Seviye 4 (Vaka-Kontrol / Olgu Sunumu)"
    elif "review" in combined or "derleme" in combined:
        return "Seviye 5 (Derleme / Uzman Görüşü)"
    return "Seviye 3-5 (Belirtilmemiş / Primer Araştırma)"


def generate_rule_based_turkish_report(query: str, articles: List[Dict[str, Any]]) -> str:
    """Generates a structured, deterministic Turkish evidence report from verified articles."""
    if not articles:
        return f"""# 📑 Türkçe Kanıt Raporu

**Klinik Sorgu:** {query}

### ⚠️ Sonuç Bulunamadı
Aranan klinik sorgu için doğrulanan PubMed veritabanında kriterlere uygun makale bulunamamıştır.
Lütfen arama terimlerini veya filtreleri genişleterek tekrar deneyiniz.
"""

    total_articles = len(articles)

    # Analyze publication types and evidence distribution
    evidence_levels_summary = {}
    for art in articles:
        level = _classify_evidence_level(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))
        evidence_levels_summary[level] = evidence_levels_summary.get(level, 0) + 1

    report = []
    report.append(f"# 📑 Türkçe Kanıt Raporu")
    report.append(f"**Klinik Sorgu / Araştırma Konusu:** {query}\n")
    report.append("---")

    # 1. Klinik Özet
    report.append("## 1. 🔍 Klinik Özet ve Sentez")
    report.append(f"Bu rapor, **PubMed E-utilities** veritabanı üzerinden erişilen **{total_articles} adet doğrulanmış literatür kaynağı** temel alınarak tıp doktorları için hazırlanmıştır.")
    report.append("Seçilen yayınların klinik bulguları incelendiğinde öne çıkan temel noktalar aşağıda özetlenmiştir:\n")

    for idx, art in enumerate(articles, 1):
        first_author = _format_authors_short(art.get("authors", []))
        year = art.get("pub_year", "Tarih Yok")
        title = art.get("title", "Başlıksız")
        abstract = art.get("abstract", "Özet bilgisi mevcut değil.")
        pmid = art.get("pmid", "Yok")

        # Take key sentences from abstract for synthesis
        abstract_snippet = abstract.strip()
        if len(abstract_snippet) > 350:
            abstract_snippet = abstract_snippet[:347] + "..."

        report.append(f"**{idx}. [{first_author}, {year}] - {title}**")
        report.append(f"> *Bulgular/Özet:* {abstract_snippet}")
        report.append(f"> *Atıf Referansı:* [PMID: {pmid}]({art.get('pubmed_url', '#')})\n")

    # 2. Kanıt Seviyeleri ve Metodolojik Değerlendirme
    report.append("## 2. 📊 Kanıt Seviyeleri ve Metodolojik Dağılım")
    report.append("Incelenen literatürün metodolojik kalitesi ve kanıt hiyerarşisi dağılımı aşağıdaki şekildedir:\n")
    for lvl, count in evidence_levels_summary.items():
        report.append(f"- **{lvl}:** {count} makale")
    report.append("\n*Metodolojik Değerlendirme:* Çalışmalar PubMed indeksli hakemli dergilerden çekilmiş olup, metodolojik güçleri makale türlerine (RCT, Derleme, Kohort vb.) göre değişiklik göstermektedir.\n")

    # 3. Klinik Uyarılar ve Sınırlılıklar
    report.append("## 3. ⚠️ Klinik Uyarılar ve Sınırlılıklar")
    report.append("- **Sınırlılıklar:** Rapor sadece taranan makalelerin özet (abstract) verilerine ve doğrulanmış yayın kayıtlarına dayanmaktadır. Tam metin (full-text) değerlendirmesi yapılmalıdır.")
    report.append("- **Aydınlatılmış Onam & Sorumluluk Reddi:** Bu rapor karar destek amacı taşır, doğrudan hekimin klinik yargısının yerini alamaz. Tedavi protokolleri hastaya özel değerlendirilmelidir.\n")

    # 4. Doğrulanmış Referanslar (Strictly No Fabricated Citations)
    report.append("## 4. 📚 Doğrulanmış Kaynaklar ve Literatür Listesi")
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
    """Generates a Turkish evidence report using LLM with strict anti-hallucination prompt constraints."""
    if not OpenAI:
        return generate_rule_based_turkish_report(query, articles)

    client = OpenAI(api_key=api_key)

    # Format source context clearly
    context_blocks = []
    for idx, art in enumerate(articles, 1):
        context_blocks.append(
            f"--- MAKALE [{idx}] ---\n"
            f"PMID: {art.get('pmid')}\n"
            f"DOI: {art.get('doi', 'Yok')}\n"
            f"Başlık: {art.get('title')}\n"
            f"Yazarlar: {', '.join(art.get('authors', []))}\n"
            f"Dergi / Yıl: {art.get('journal')} ({art.get('pub_year')})\n"
            f"Makale Türü: {', '.join(art.get('publication_types', []))}\n"
            f"Özet: {art.get('abstract')}\n"
        )

    context_str = "\n".join(context_blocks)

    system_prompt = (
        "Sen uzman bir tıbbi araştırmacı ve klinik kanıt analistisin. Görevin, sağlanan PubMed makale özetlerini "
        "kullanarak tıp hekimleri için Türkçe Klinik Kanıt Raporu hazırlamaktır.\n\n"
        "KESİN KURALLAR (Anti-Hallucination Constraints):\n"
        "1. KESİNLİKLE uydurma atıf, uydurma PMID, uydurma makale veya kaynak gösterme!\n"
        "2. Yalnızca sağlanan makalelerdeki gerçek verileri kullan.\n"
        "3. Her iddia ve klinik bulgudan sonra metin içinde ilgili makalenin PMID'sine veya yazar/yılına atıf yap (örneğin [PMID: 12345678]).\n"
        "4. Raporu şu ana başlıklar altında Türkçe olarak yaz:\n"
        "   - # 📑 Türkçe Kanıt Raporu\n"
        "   - ## 1. 🔍 Klinik Özet ve Sentez\n"
        "   - ## 2. 📊 Kanıt Seviyeleri ve Metodolojik Değerlendirme\n"
        "   - ## 3. ⚠️ Klinik Uyarılar ve Sınırlılıklar\n"
        "   - ## 4. 📚 Doğrulanmış Kaynaklar ve Literatür Listesi (Yalnızca verilen makaleler tam formatta listelenmeli)\n"
    )

    user_prompt = f"Klinik Sorgu: {query}\n\nSağlanan Literatür Kaynakları:\n{context_str}"

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
        # Fallback to rule-based if LLM fails
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

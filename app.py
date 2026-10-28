import os
import streamlit as st
import pandas as pd
from pubmed_client import search_pubmed, verify_pmid, verify_doi, verify_citation
from report_generator import (
    generate_turkish_evidence_report,
    generate_evidence_table_html,
    generate_html_report,
    perform_red_team_audit,
    classify_study_design,
    extract_pico,
    assess_risk_of_bias
)

# Page config
st.set_page_config(
    page_title="Medical Research AI - Turkish Evidence Report Engine",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        color: #1E3A8A;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .stCard {
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        background-color: #FFFFFF;
    }
    .badge-pmid {
        background-color: #DBEAFE;
        color: #1E40AF;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-doi {
        background-color: #E0E7FF;
        color: #3730A3;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .audit-card {
        background-color: #F0FDF4;
        border: 1px solid #BBF7D0;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
    }
    .grade-notice-card {
        background-color: #FEF3C7;
        border: 1px solid #FDE68A;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 15px;
        color: #92400E;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown('<div class="main-header">🩺 Medical Research AI - Gelişmiş Tıbbi Literatür & Kanıt Raporu Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Hekimler için Gerçek Literatür Taraması, PMID/DOI Doğrulama, Yapılandırılmış Kanıt Tablosu ve Türkçe Kanıt Raporu Modülü</div>', unsafe_allow_html=True)

    # Sidebar Configuration
    st.sidebar.title("⚙️ Ayarlar & Yapılandırma")

    openai_api_key_env = os.environ.get("OPENAI_API_KEY", "")
    openai_api_key = st.sidebar.text_input(
        "OpenAI API Key (Opsiyonel)",
        value=openai_api_key_env,
        type="password",
        help="LLM destekli rapor sentezi için API anahtarı. Girilmezse kural tabanlı deterministik kanıt motoru çalışır."
    )

    use_llm_synth = st.sidebar.checkbox(
        "OpenAI Sentez Motorunu Kullan",
        value=bool(openai_api_key),
        help="İşaretlenirse, bulunan PubMed özetleri OpenAI GPT modeli ile sentezlenerek raporlanır."
    )

    llm_model = st.sidebar.selectbox(
        "Model Seçimi",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0
    )

    st.sidebar.markdown("---")
    st.sidebar.info(
        "**🔍 Doğrulanmış Kaynak & Atıf Dürüstlüğü Politikası:**\n"
        "Bu sistem canlı NCBI PubMed ve CrossRef E-utilities API verilerini kullanır. "
        "Metin sentezi özet (abstract) verilerine dayanır; klinik doğrulama veya otomatik GRADE derecelendirmesi iddiasında bulunulmaz. "
        "Çalışma tasarımları (Seviye 1-5) yalnızca yayın türü hiyerarşisini gösterir, GRADE kanıt kesinliğini ifade etmez."
    )

    # Main Tabs
    tab1, tab2, tab3 = st.tabs([
        "🔎 PubMed Literatür Taraması",
        "✅ PMID / DOI Doğrulama",
        "📑 Türkçe Klinik Kanıt Raporu"
    ])

    # Tab 1: PubMed Search
    with tab1:
        st.subheader("PubMed Gerçek Zamanlı Literatür Arama")

        col_search, col_type, col_count = st.columns([3, 1.5, 1])
        with col_search:
            search_query = st.text_input("Klinik Sorgu veya Tıbbi Terimler (İngilizce/Latince)", placeholder="örneğin, SGLT2 inhibitors in heart failure with preserved ejection fraction")
        with col_type:
            pub_type_filter = st.selectbox(
                "Yayın Türü Filtresi",
                ["Tümü", "Clinical Trial", "Randomized Controlled Trial", "Systematic Review", "Meta-Analysis", "Review"]
            )
        with col_count:
            max_results = st.number_input("Sonuç Sayısı", min_value=1, max_value=50, value=10)

        col_y1, col_y2, col_sort, col_btn = st.columns([1, 1, 1.5, 1])
        with col_y1:
            start_year = st.number_input("Başlangıç Yılı", min_value=1950, max_value=2026, value=None, placeholder="Örn: 2018")
        with col_y2:
            end_year = st.number_input("Bitiş Yılı", min_value=1950, max_value=2026, value=None, placeholder="Örn: 2026")
        with col_sort:
            sort_by = st.selectbox("Sıralama", ["relevance", "pub_date"])
        with col_btn:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            search_submitted = st.button("🔍 Ara", use_container_width=True)

        if search_submitted and search_query:
            start_yr = int(start_year) if start_year and not pd.isna(start_year) else None
            end_yr = int(end_year) if end_year and not pd.isna(end_year) else None
            with st.spinner("PubMed veritabanı sorgulanıyor..."):
                search_res = search_pubmed(
                    query=search_query,
                    max_results=max_results,
                    sort=sort_by,
                    publication_type=pub_type_filter,
                    start_year=start_yr,
                    end_year=end_yr
                )
                st.session_state["search_results"] = search_res
                st.session_state["active_query"] = search_query

        if "search_results" in st.session_state:
            res = st.session_state["search_results"]
            articles = res.get("articles", [])
            total_count = res.get("total_count", 0)
            error_msg = res.get("error")

            if error_msg:
                st.error(f"❌ PubMed API Hatası: {error_msg}")
            elif not articles:
                st.warning("Belirtilen kriterlere uygun literatür kaydı bulunamadı.")
            else:
                st.markdown(f"**Bulunan Toplam Kayıt:** {total_count} | **Gösterilen:** {len(articles)}")
                for idx, art in enumerate(articles, 1):
                    cd = classify_study_design(art.get("publication_types", []), art.get("title", ""), art.get("abstract", ""))
                    rob = assess_risk_of_bias(art)
                    with st.expander(f"{idx}. {art['title']} ({art['pub_year']}) - [{cd['level']}]", expanded=(idx <= 3)):
                        st.markdown(f"**Yazarlar:** {', '.join(art['authors']) if art['authors'] else 'Bilinmiyor'}")
                        st.markdown(f"**Dergi:** {art['journal']} ({art['pub_year']})")
                        st.markdown(f"**Çalışma Tasarımı:** `{cd['design']}` ({cd['level']})")
                        st.markdown(f"**Yanlılık Riski ({rob['tool']}):** `{rob['overall_rating']}`")

                        badges_html = []
                        if art['pmid']:
                            badges_html.append(f'<span class="badge-pmid">PMID: {art["pmid"]}</span>')
                        if art['doi']:
                            badges_html.append(f'<span class="badge-doi">DOI: {art["doi"]}</span>')
                        st.markdown(" ".join(badges_html), unsafe_allow_html=True)

                        st.markdown("**Özet (Abstract):**")
                        st.text_area(f"Özet #{idx}", art['abstract'], height=150, key=f"abs_{idx}")

                        links = []
                        if art['pubmed_url']:
                            links.append(f"[PubMed Sayfası]({art['pubmed_url']})")
                        if art['doi_url']:
                            links.append(f"[DOI Bağlantısı]({art['doi_url']})")
                        st.markdown(" | ".join(links))

    # Tab 2: PMID/DOI Verification
    with tab2:
        st.subheader("PMID veya DOI Kimlik Doğrulama Servisi")
        st.write("Şüpheli veya doğrulanması gereken PMID veya DOI numarasını girerek PubMed ve CrossRef veritabanlarında geçerliliğini kontrol edin.")

        v_col1, v_col2 = st.columns([3, 1])
        with v_col1:
            identifier_input = st.text_input("PMID veya DOI Giriniz", placeholder="Örn: 33264510 veya 10.1056/NEJMoa2022190")
        with v_col2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            verify_btn = st.button("✅ Doğrula", use_container_width=True)

        if verify_btn and identifier_input:
            clean_input = identifier_input.strip()
            with st.spinner("Doğrulanıyor..."):
                if clean_input.isdigit() or clean_input.lower().startswith("pmid:"):
                    v_cit = verify_citation({"pmid": clean_input})
                    if v_cit.get("status") == "verified":
                        result = v_cit.get("fetched_article", {})
                        result["valid"] = True
                    else:
                        result = {
                            "valid": False,
                            "status": v_cit.get("status"),
                            "error": v_cit.get("error")
                        }
                else:
                    result = verify_doi(clean_input)

            if result.get("valid"):
                st.success("✅ Yayın Başarıyla Doğrulandı! Veritabanlarında Mevcut.")
                cd = classify_study_design(result.get("publication_types", []), result.get("title", ""), result.get("abstract", ""))
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.markdown(f"**Başlık:** {result.get('title')}")
                    st.markdown(f"**Yazarlar:** {', '.join(result.get('authors', []))}")
                    st.markdown(f"**Dergi / Yıl:** {result.get('journal')} ({result.get('pub_year')})")
                    st.markdown(f"**Çalışma Tasarımı:** `{cd['design']}` ({cd['level']})")
                with col_info2:
                    if result.get("pmid"):
                        st.markdown(f"**PMID:** [{result.get('pmid')}]({result.get('pubmed_url')})")
                    if result.get("doi"):
                        st.markdown(f"**DOI:** [{result.get('doi')}]({result.get('doi_url')})")

                st.markdown("**Özet / Yayın Detayı:**")
                st.info(result.get("abstract", "Özet bilgisi bulunamadı."))
            else:
                status_label = result.get("status")
                if status_label == "unverified":
                    st.warning(f"⚠️ Doğrulama Tamamlanamadı (API Failure): {result.get('error', 'API yanıt vermedi.')}")
                else:
                    st.error(f"❌ Doğrulama Başarısız (Reddedildi): {result.get('error', 'Kayıt bulunamadı veya uyuşmazlık tespit edildi.')}")

    # Tab 3: Turkish Evidence Report Generator & Structured Evidence Module
    with tab3:
        st.subheader("Türkçe Klinik Kanıt Raporu ve Yapılandırılmış Kanıt Tablosu Engine")
        st.write("Doğrulanmış makalelerinizden çalışma tasarımları, kanıt seviyeleri, Red Team güvenlik denetimi ve indirilebilir raporlar üretin.")

        if "search_results" in st.session_state and st.session_state["search_results"].get("articles"):
            articles = st.session_state["search_results"]["articles"]
            query = st.session_state.get("active_query", "Klinik Araştırma")

            audit_res = perform_red_team_audit(query, articles)

            # Audit Summary Cards
            col_a1, col_a2, col_a3, col_a4 = st.columns(4)
            with col_a1:
                st.metric("Toplam Kaynak", len(articles))
            with col_a2:
                st.metric("Doğrulanmış Atıf", audit_res["citation_integrity"]["verified_citations"])
            with col_a3:
                st.metric("Veri Kapsamı", "Yalnızca Özet (Abstract)")
            with col_a4:
                st.metric("GRADE Statüsü", "Değerlendirilmedi")

            st.markdown(
                f"""<div class="grade-notice-card">
                📌 <strong>GRADE Derecelendirme Politikası:</strong> {audit_res['grade_rating_policy']['notice']}
                </div>""",
                unsafe_allow_html=True
            )

            if st.button("📑 Türkçe Kanıt Raporunu ve Tabloları Oluştur", type="primary", use_container_width=True):
                with st.spinner("Klinik kanıt raporu, Red Team denetimi ve HTML/Markdown tabloları hazırlanıyor..."):
                    report_md = generate_turkish_evidence_report(
                        query=query,
                        articles=articles,
                        api_key=openai_api_key if use_llm_synth else None,
                        use_llm=use_llm_synth,
                        model=llm_model
                    )
                    html_report = generate_html_report(query, articles, report_md)
                    st.session_state["generated_report"] = report_md
                    st.session_state["generated_html_report"] = html_report

            if "generated_report" in st.session_state:
                st.markdown("---")

                pico_res = extract_pico(query, articles[0].get("abstract", "") if articles else "")

                report_subtab1, report_subtab2, report_subtab3, report_subtab4 = st.tabs([
                    "📄 Tam Kanıt Raporu (Markdown)",
                    "📊 Yapılandırılmış Kanıt Tablosu",
                    "🎯 PICO & RoB Değerlendirmesi",
                    "🛡️ Red Team Denetim Detayları"
                ])

                with report_subtab1:
                    st.markdown(st.session_state["generated_report"])

                with report_subtab2:
                    st.subheader("📊 Yapılandırılmış Tıbbi Kanıt Tablosu")
                    html_table = generate_evidence_table_html(articles)
                    st.components.v1.html(html_table, height=500, scrolling=True)

                with report_subtab3:
                    st.subheader("🎯 Klinik PICO Çerçevesi")
                    p1, p2, p3, p4 = st.columns(4)
                    with p1:
                        st.info(f"**P (Hasta Grubu):**\n\n{pico_res['population']}")
                    with p2:
                        st.success(f"**I (Müdahale):**\n\n{pico_res['intervention']}")
                    with p3:
                        st.warning(f"**C (Karşılaştırma):**\n\n{pico_res['comparison']}")
                    with p4:
                        st.error(f"**O (Sonlanım):**\n\n{pico_res['outcome']}")

                    st.markdown("---")
                    st.subheader("🔬 Yanlılık Riski (RoB 2 / ROBINS-I) İncelemesi")
                    for a_idx, a_item in enumerate(articles, 1):
                        a_rob = assess_risk_of_bias(a_item)
                        with st.expander(f"Makale #{a_idx}: {a_item.get('title')} — {a_rob['overall_rating']}"):
                            st.markdown(f"**Değerlendirme Aracı:** {a_rob['tool']}")
                            st.markdown(f"**Genel Derecelendirme:** `{a_rob['overall_rating']}`")
                            st.markdown("**Domain Detayları:**")
                            st.json(a_rob["domains"])

                with report_subtab4:
                    st.subheader("🛡️ Red Team Denetimi & Metodolojik Değerlendirme")
                    st.json(audit_res)

                st.markdown("---")
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        label="📥 Kanıt Raporunu İndir (.md)",
                        data=st.session_state["generated_report"],
                        file_name=f"turkce_kanit_raporu_{query.replace(' ', '_')}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                with col_dl2:
                    st.download_button(
                        label="🌐 Basılmaya Hazır HTML Raporunu İndir (.html)",
                        data=st.session_state["generated_html_report"],
                        file_name=f"turkce_kanit_raporu_{query.replace(' ', '_')}.html",
                        mime="text/html",
                        use_container_width=True
                    )
        else:
            st.info("💡 Henüz bir arama yapılmadı. Lütfen önce **'🔎 PubMed Literatür Taraması'** sekmesinden bir sorgu çalıştırınız.")

if __name__ == "__main__":
    main()

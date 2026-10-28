import os
import streamlit as st
import pandas as pd
from pubmed_client import search_pubmed, verify_pmid, verify_doi
from report_generator import generate_turkish_evidence_report

# Page config
st.set_page_config(
    page_title="Medical Research AI - Physician Assistant",
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
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown('<div class="main-header">🩺 Medical Research AI MVP</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Hekimler için Gerçek Literatür Taraması, PMID/DOI Doğrulama ve Türkçe Kanıt Raporu Asistanı</div>', unsafe_allow_html=True)

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
        "**🔍 Doğrulanmış Kaynak Garantisi:**\n"
        "Bu sistem halüsinasyonları önlemek için yalnızca canlı NCBI PubMed ve CrossRef E-utilities API verilerini kullanır. "
        "Uydurma PMID, DOI veya makale kesinlikle üretilmez."
    )

    # Main Tabs
    tab1, tab2, tab3 = st.tabs([
        "🔎 PubMed Literatür Taraması",
        "✅ PMID / DOI Doğrulama",
        "📑 Türkçe Kanıt Raporu"
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
                    with st.expander(f"{idx}. {art['title']} ({art['pub_year']})", expanded=(idx <= 3)):
                        st.markdown(f"**Yazarlar:** {', '.join(art['authors']) if art['authors'] else 'Bilinmiyor'}")
                        st.markdown(f"**Dergi:** {art['journal']} ({art['pub_year']})")

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
                    result = verify_pmid(clean_input)
                else:
                    result = verify_doi(clean_input)

            if result.get("valid"):
                st.success("✅ Yayın Başarıyla Doğrulandı! Veritabanlarında Mevcut.")
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.markdown(f"**Başlık:** {result.get('title')}")
                    st.markdown(f"**Yazarlar:** {', '.join(result.get('authors', []))}")
                    st.markdown(f"**Dergi / Yıl:** {result.get('journal')} ({result.get('pub_year')})")
                with col_info2:
                    if result.get("pmid"):
                        st.markdown(f"**PMID:** [{result.get('pmid')}]({result.get('pubmed_url')})")
                    if result.get("doi"):
                        st.markdown(f"**DOI:** [{result.get('doi')}]({result.get('doi_url')})")

                st.markdown("**Özet / Yayın Detayı:**")
                st.info(result.get("abstract", "Özet bilgisi bulunamadı."))
            else:
                st.error(f"❌ Doğrulama Başarısız: {result.get('error', 'Kayıt bulunamadı.')}")

    # Tab 3: Turkish Evidence Report Generator
    with tab3:
        st.subheader("Türkçe Klinik Kanıt Raporu Oluşturucu")
        st.write("Arama sonuçlarınızdan çekilen doğrulanmış makaleleri kullanarak kanıt hiyerarşisine uygun Türkçe sentez raporu üretin.")

        if "search_results" in st.session_state and st.session_state["search_results"].get("articles"):
            articles = st.session_state["search_results"]["articles"]
            query = st.session_state.get("active_query", "Klinik Araştırma")

            st.markdown(f"**Rapor Yapılandırılacak Kaynak Sayısı:** {len(articles)} Makale")

            if st.button("📑 Türkçe Kanıt Raporunu Oluştur", type="primary"):
                with st.spinner("Rapor hazırlanıyor (Kanıt seviyeleri ve sentez oluşturuluyor)..."):
                    report_md = generate_turkish_evidence_report(
                        query=query,
                        articles=articles,
                        api_key=openai_api_key if use_llm_synth else None,
                        use_llm=use_llm_synth,
                        model=llm_model
                    )
                    st.session_state["generated_report"] = report_md

            if "generated_report" in st.session_state:
                st.markdown("---")
                st.markdown(st.session_state["generated_report"])
                st.download_button(
                    label="📥 Kanıt Raporunu İndir (.md)",
                    data=st.session_state["generated_report"],
                    file_name=f"turkce_kanit_raporu_{query.replace(' ', '_')}.md",
                    mime="text/markdown"
                )
        else:
            st.info("💡 Henüz bir arama yapılmadı. Lütfen önce **'🔎 PubMed Literatür Taraması'** sekmesinden bir sorgu çalıştırınız.")

if __name__ == "__main__":
    main()

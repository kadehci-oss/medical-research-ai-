# Evrensel Medical Research AI Mimarisi ve Uygulama Dokümantasyonu (IMPLEMENTATION.md)

Bu doküman, **Medical Research AI** platformunun uçtan uca mimarisini, PubMed/MEDLINE kaynak tarama mekanizmasını, bilimsel kanıt değerlendirme süreçlerini, kaynak doğrulama motorunu, Türkçe uzman hekim raporlama sistemini ve **Veri Doğrulama ve Güvenlik Katmanını** detaylandırmaktadır.

---

## 📑 İçindekiler

1. [Genel Mimari ve Bileşen Yapısı](#1-genel-mimari-ve-bileşen-yapısı)
2. [PubMed/MEDLINE Kaynak Taraması ve Okuma Katmanı](#2-pubmedmedline-kaynak-taraması-ve-okuma-katmanı)
3. [Bilimsel Kanıt Değerlendirmesi ve Parametre Çıkarımı](#3-bilimsel-kanıt-değerlendirmesi-ve-parametre-çıkarımı)
4. [Kaynak Doğrulama ve Doğrusal Eşleştirme Motoru](#4-kaynak-doğrulama-ve-doğrusal-eşleştirme-motoru)
5. [Türkçe Uzman Hekim Raporlama Sistemi](#5-türkçe-uzman-hekim-raporlama-sistemi)
6. [Veri Doğrulama ve Güvenlik Katmanı](#6-veri-doğrulama-ve-güvenlik-katmanı)
7. [Tıbbi Branş ve Uzmanlık Matrisi (all_specialty_matrix.json)](#7-tıbbi-branş-ve-uzmanlık-matrisi)

---

## 1. Genel Mimari ve Bileşen Yapısı

**Medical Research AI**, tıbbi araştırmacılar ve uzman hekimler için tasarlanmış, halüsinasyonsuz (*zero-hallucination*), canlı NCBI PubMed verileriyle desteklenen evrensel bir klinik kanıt sentez platformudur.

### 🏗 Sistem Mimarisi Şeması

```
[ Kullanıcı Arayüzü / Uzman Hekim ]
       │
       ├──► Streamlit Web Uygulaması (app.py)
       └──► REST API İstemcileri (api.py - FastAPI)
               │
               ▼
   ┌────────────────────────────────────────────────────────┐
   │ Universal Evidence Engine (universal_evidence_engine)  │
   └───────────────────────────┬────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│ PubMed Client│     │ Verification     │     │ Report         │
│ (NCBI API)   │     │ Engine (CrossRef)│     │ Generator      │
└──────┬───────┘     └────────┬─────────┘     └───────┬────────┘
       │                      │                       │
       ▼                      ▼                       ▼
[ NCBI PubMed ]      [ CrossRef REST API ]    [ Türkçe Rapor ]
(eSearch/eFetch)     (DOI Doğrulama)          (13 Zorunlu Bölüm)
```

### 🧩 Temel Modüller ve Sorumlulukları

1. **`app.py` (Streamlit Kullanıcı Arayüzü)**:
   - Uzman hekimler ve araştırmacılar için çok sekmeli (*multi-tab*) etkileşimli arayüz sunar.
   - PubMed Literatür Taraması, PMID/DOI Kaynak Doğrulama ve Türkçe Kanıt Raporu Oluşturma modüllerini içerir.
   - Yeni arama yapıldığında eski rapor durumunu otomatik temizleyerek bayat (*stale*) veri gösterimini engeller.

2. **`api.py` (FastAPI REST Servis Katmanı)**:
   - Dış sistemler ve sağlık bilişimi entegrasyonları için modüler REST API uç noktaları sağlar:
     - `/api/search`: PubMed literatür araması.
     - `/api/verify/citation`: PMID ve DOI doğrulama servisi.
     - `/api/universal_engine/synthesize`: Evrensel kanıt sentez servisi.

3. **`pubmed_client.py` (NCBI & CrossRef İletişim İstemcisi)**:
   - NCBI E-utilities (`esearch.fcgi`, `efetch.fcgi`) ve CrossRef REST API ile güvenli HTTPS entegrasyonu sağlar.
   - XML yanıtlarını `xml.etree.ElementTree` ile güvenli şekilde ayrıştırır.
   - PMID ve DOI bazlı makale tekleştirme (*deduplication*) ve normalizasyon işlemlerini yürütür.

4. **`report_generator.py` (Klinik Kanıt Sentez Motoru)**:
   - PubMed çıktılarından nicel parametreleri ($n$, HR, OR, RR, MD, %95 GA, p değerleri) ve PICO bileşenlerini çıkarır.
   - Çalışma tasarımlarını Hiyerarşik Kanıt Piramidine (Seviye 1-5) göre sınıflandırır.
   - Kural tabanlı deterministik sentezleyici ve OpenAI LLM sentezleyicisi ile 13 zorunlu bölümden oluşan Türkçe klinik rapor üretir.

5. **`universal_evidence_engine.py` (Evrensel Klinik Kanıt Motoru)**:
   - Tüm tıbbi uzmanlık alanlarında (Kardiyoloji, Nöroloji, Tıbbi Onkoloji, Ruh Sağlığı ve Psikiyatri, Fizik Tedavi ve Rehabilitasyon vb.) hastalığa bağımsız (*disease-agnostic*) kanıt tarama, çapraz çalışma karşılaştırması ve doğrulama süreçlerini orchestrate eder.

---

## 2. PubMed/MEDLINE Kaynak Taraması ve Okuma Katmanı

### 🔍 Arama ve Filtreleme Mekanizması

NCBI PubMed E-utilities API entegrasyonu iki aşamalı olarak gerçekleştirilir:

1. **Arama Aşaması (`esearch.fcgi`)**:
   - Kullanıcı sorgusu Medikal Konu Başlıkları (MeSH) ve serbest metin terimleriyle optimize edilir.
   - Yayın Tipi Filtreleme: *Randomized Controlled Trial*, *Systematic Review*, *Meta-Analysis*, *Clinical Trial*, *Review*.
   - Tarih Aralığı Filtreleme: `start_year` ve `end_year` parametreleri ile spesifik zaman pencereleri tanımlanır.
   - Sıralama: Alaka düzeyi (*relevance*) veya yayın tarihine (*pub_date*) göre sıralama yapılır.

2. **Detay Veri Çekme Aşaması (`efetch.fcgi`)**:
   - `esearch` sonucu elde edilen PMID listesi için XML formatında tam makale künyesi ve özet metni çekilir.
   - Çekilen veriler: PMID, DOI, Makale Başlığı, Yazar Listesi, Dergi Adı, Yayın Yılı, Yayın Tipleri, MESH Terimleri ve Tam Özet (Abstract).

### 🛡 Hız Sınırlama ve İstisna Yönetimi

- NCBI API kullanım kurallarına uyum sağlamak amacıyla tüm isteklerde `tool=MedicalResearchAI` ve `email` meta verileri iletilir.
- Geçici ağ hataları ve HTTP 429 (*Too Many Requests*) durumlarında üstel geri çekilme (*exponential backoff*) ile otomatik yeniden deneme (*retry*) mekanizması uygulanır.

---

## 3. Bilimsel Kanıt Değerlendirmesi ve Parametre Çıkarımı

### 📊 Çalışma Tasarımı Hiyerarşisi (Level 1–5)

Sistem, makalelerin yayın tipleri (`publication_types`) ve abstract metin heuristiclerini inceleyerek kanıt seviyesini belirler:

- **Seviye 1**: Sistemik Derleme ve Meta-Analizler (*Systematic Review, Meta-Analysis*)
- **Seviye 2**: Rastgele Kontrollü Çalışmalar (*Randomized Controlled Trial - RCT*)
- **Seviye 3**: Kohort ve Vaka-Kontrol Çalışmaları (*Cohort Study, Case-Control Study*)
- **Seviye 4**: Kesitsel Çalışmalar, Vaka Serileri ve Vaka Sunumları (*Cross-Sectional, Case Series, Case Report*)
- **Seviye 5**: Anlatımsal Derlemeler, Kılavuzlar, Editör Yazıları ve Uzman Görüşleri (*Narrative Review, Guideline, Editorial*)

### 🔢 Nicel Parametre Çıkarımı ve PICO Analizi

`report_generator.py` ve `universal_evidence_engine.py`, makale özetlerinden yalnızca açıkça bildirilen verileri çıkarır:

- **Örneklem Büyüklüğü ($n$)**: Çalışmaya katılan hasta/denek sayısı.
- **Etki Büyüklükleri**: Hazard Ratio (HR), Odds Ratio (OR), Relative Risk (RR), Mean Difference (MD).
- **Güven Aralıkları (%95 CI)**: İstatistiksel kesinlik aralıkları.
- **P Değerleri ($p$)**: İstatistiksel anlamlılık sınırları ($p < 0.05$).
- **PICO Bileşenleri**:
  - **P (Population/Patient)**: Hasta grubu ve demografik özellikler.
  - **I (Intervention)**: İncelenen klinik müdahale veya ilaç.
  - **C (Comparison)**: Karşılaştırma grubu veya plasebo.
  - **O (Outcome)**: Klinik sonlanım noktaları.

### ⚖️ Risk of Bias (RoB) ve GRADE Değerlendirme Kuralları

- **RCT Çalışmaları**: RoB 2 kriterlerine göre değerlendirilir. Yalnızca abstract metni incelendiği için otomatik olarak **"Değerlendirilmedi (Not Assessed)"** statüsü atanır.
- **Gözlemsel Çalışmalar**: ROBINS-I kriterlerine tabidir; yine abstract sınırlılığı nedeniyle **"Değerlendirilmedi (Not Assessed)"** olarak işaretlenir.
- **Birincil Olmayan Çalışmalar (Derleme, Kılavuz, Editör)**: **"Uygulanamaz (Not Applicable)"** olarak sınıflandırılır.
- **GRADE Kesinlik Seviyesi**: Tüm özet düzeyi taramalarda GRADE kesinliği resmi olarak **"Not Assessed / Değerlendirilmedi"** olarak raporlanır.

---

## 4. Kaynak Doğrulama ve Doğrusal Eşleştirme Motoru

### 🔬 PMID ve DOI Doğrulama Algoritması

Sistem, literatür atıflarının doğruluğunu 2 farklı dış kaynak üzerinden teyit eder:

1. **PMID Doğrulaması**: NCBI PubMed EFetch API üzerinden makalenin mevcudiyeti, başlığı, yazarları ve dergisi sorgulanır.
2. **DOI Doğrulaması**: CrossRef REST API (`https://api.crossref.org/works/{doi}`) üzerinden DOI kaydı denetlenir.

### 🏷 Doğrulama Durumu Kodları (Verification Taxonomy)

Doğrulama sonuçları 6 açık durum kodu ile kategorize edilir:

1. **`match`**: PMID/DOI ve makale başlığı NCBI/CrossRef kayıtlarıyla eksiksiz eşleşti.
2. **`title_mismatch`**: PMID mevcut ancak bildirilen başlık veri tabanındaki başlıkla uyuşmuyor.
3. **`doi_mismatch`**: DOI kaydı veritabanındaki makale ile uyuşmuyor.
4. **`missing_or_invalid_pmid`**: Geçersiz veya eksik PMID biçimi.
5. **`not_found`**: PMID/DOI veri tabanında bulunamadı.
6. **`api_failure`**: Dış API bağlantı hatası veya zaman aşımı.

---

## 5. Türkçe Uzman Hekim Raporlama Sistemi

Raporlama sistemi, uzman hekimlerin klinik karar alma süreçlerini desteklemek amacıyla **13 Zorunlu Rapor Bölümünden** oluşur:

### 📑 13 Zorunlu Rapor Bölümü

1. **Başlık ve Arama Parametreleri**
2. **Metodolojik Taraması ve Kanıt Düzeyi Özeti**
3. **PICO Analizi (Hasta, Müdahale, Karşılaştırma, Sonuç)**
4. **Klinik Arka Plan ve Literatür Özeti**
5. **Seçilen Çalışmaların Özeti**
6. **Karşılaştırmalı Çalışma Matrisi**
7. **Metodolojik Kalite ve Risk of Bias (RoB) Değerlendirmesi**
8. **GRADE Kanıt Kesinlik Değerlendirmesi**
9. **Çelişkili Bulgular ve Heterojenlik Analizi**
10. **Klinik Uygulanabilirlik ve Emniyet Profili**
11. **Kanıt Sınırlılıkları ve Metodolojik Engeller**
12. **Klinik Sonuç ve Sentez**
13. **Doğrulanmış Kaynakça (PMID ve DOI Bağlantılı)**

### ⚠️ Zorunlu Klinik Feragatnameler ve Açıklamalar

Tüm raporlarda ve kullanıcı arayüzünde aşağıdaki 3 klinik açıklama zorunlu olarak yer alır:

1. **Özet Düzeyi Kanıt Sınırlılığı**: Rapor yalnızca tam metin değil, NCBI özet (abstract) metinlerine dayanmaktadır.
2. ** GRADE Değerlendirilmedi Statüsü**: GRADE kesinlik derecelendirmesi resmi olarak yapılmamıştır (*Not Assessed*).
3. **Uzman Hekim Değerlendirme Açıklaması**: Manuel uzman hekim incelemesi henüz gerçekleşmemiş olup rapor üzerinde **"Uzman Hekim Değerlendirmesi / Onayı Henüz Tamamlanmamıştır (Yapılmadı / Tamamlanmadı)"** ibaresi açıkça belirtilir.

---

## 6. Veri Doğrulama ve Güvenlik Katmanı

Sağlık bilişimi ve yapay zeka uygulamalarında veri güvenliği, hasta gizliliği ve bilgi bütünlüğü hayati önem taşır. Platformda uygulanan güvenlik ve doğrulama katmanları aşağıda detaylandırılmıştır.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   VERİ DOĞRULAMA VE GÜVENLİK KATMANI                    │
├────────────────────────────────────────────────────────────────────────┤
│ 1. PMID/DOI Doğrulama ve Kaynak-İddia Eşleştirme                      │
│ 2. Uydurma Veriyi Engelleme (Zero Metric Fabrication)                  │
│ 3. KVKK ve Hasta Verilerinin Korunması (PHI Elimination)               │
│ 4. API Anahtarı Güvenliği ve Oturum Maskeleme                          │
│ 5. Prompt Injection ve Sistem İzolasyonu                               │
│ 6. XSS (Cross-Site Scripting) Engelleme                                │
│ 7. SSRF (Server-Side Request Forgery) Koruması                         │
│ 8. Otomatik Güvenlik Testleri ve Red Team Denetimi                     │
└────────────────────────────────────────────────────────────────────────┘
```

### 6.1. PMID/DOI Doğrulama ve Kaynak–İddia Eşleştirme
- **Doğrusal Bağlantılama**: Rapor içerisindeki her klinik bulgu ve metrik, doğrudan kaynağın doğrulanmış NCBI PubMed sayfasına benzersiz bağlantı ile eklenir (`https://pubmed.ncbi.nlm.nih.gov/<PMID>/`).
- **Başlık ve Metin Normalizasyonu**: `normalize_title` ve `normalize_doi` fonksiyonları ile küçük/büyük harf, noktalama ve Unicode karakter farklılıkları temizlenerek tam eşleşme doğrulaması yapılır.

### 6.2. Uydurma Veriyi Engelleme (Anti-Hallucination & Zero Metric Fabrication)
- **Sıkı Grounding Politikası**: LLM veya deterministik sentezleyici, makale özetinde bulunmayan hiçbir $n$, HR, OR, RR veya p değerini tahmin edemez, türetemez veya uyduramaz.
- **Eksik Veri Beyanı**: Özet metninde yer almayan parametreler raporda açıkça `"Belirtilmedi"` veya `"Özette bildirilmedi"` şeklinde ifade edilir.
- **Yapay %100 Doğrulama ve Yanıltıcı İddia Yasağı**: Raporda asla "%100 doğrulandı", "%0 halüsinasyon garantisi" veya "klinik olarak onaylandı" gibi abartılı beyanlara izin verilmez.

### 6.3. KVKK ve Hasta Verilerinin Korunması
- **Kişisel Sağlık Verisi (PHI) İşlememe İlkesi**: Platform yalnızca anonim, yayınlanmış akademik literatür verilerini işler.
- **Sorgu Anonimleştirme**: Arama sorgularındaki hasta adı, T.C. Kimlik No veya kişisel tanımlayıcılar sistem tarafından taranmaz, saklanmaz veya veritabanına kaydedilmez.
- **Kalıcı Hasta Veri Deposu Yoktur**: Sistemde hasta kayıtları veya kişisel veri depolayan hiçbir veri tabanı bağlantısı bulunmamaktadır.

### 6.4. API Anahtarı Güvenliği
- **Çevre Değişkenleri ve Secrets Yönetimi**: OpenAI ve dış API anahtarları yalnızca çevre değişkenleri (`OPENAI_API_KEY`) veya Streamlit Secrets üzerinden okunur.
- **Maskeleme ve Log Güvenliği**: Kullanıcı arayüzünde girilen API anahtarları istemci tarafında maskelenir. Sistem loglarında veya hata mesajlarında API anahtarlarının açık metin olarak yer alması kesinlikle engellenmiştir.

### 6.5. Prompt Injection Koruması
- **Sistem Promptu İzolasyonu**: LLM çağrılarında kullanıcı girdileri ve makale özetleri özel sınırlandırıcı ifadelerle (`### SORGULAR ###`, `### MAKALE ÖZETLERİ ###`) kapsüllenir.
- **Karakter Temizleme**: Kullanıcı sorgularındaki komut enjeksiyonu potansiyeli taşıyan sistem yönlendirme ifadeleri filtrelenir.
- **Red Team Denetimi**: `perform_red_team_audit` fonksiyonu, sentez çıktısını yayınlamadan önce komut enjeksiyonu ve halüsinasyon risklerine karşı denetler.

### 6.6. XSS (Cross-Site Scripting) Engelleme
- **HTML Kaçış (Escaping)**: Streamlit ve FastAPI arayüzlerinde kullanıcıdan veya dış API'den gelen veriler HTML kaçış süzgecinden geçirilir.
- **Güvenli Markdown ve HTML İşleme**: Rapor çıktılarındaki `iframe`, `script` ve yetkisiz inline stil blokları temizlenerek XSS zafiyetleri önlenir.

### 6.7. SSRF (Server-Side Request Forgery) Koruması
- **Sadece İzin Verilen Alan Adları (Whitelisting)**: Dış HTTP istekleri yalnızca önceden tanımlanmış güvenli API uç noktalarına yönlendirilir:
  - NCBI PubMed E-utilities: `eutils.ncbi.nlm.nih.gov`
  - CrossRef REST API: `api.crossref.org`
- **İç Ağ İzolasyonu**: Kullanıcı girdilerinden alınan URL veya IP adreslerine dahili sunucu ağından istek atılması engellenmiştir.

### 6.8. Otomatik Güvenlik Testleri
- **Birincil Test Süreci**: `tests/` dizinindeki 70 otomatize test senaryosu her kod değişikliğinde çalıştırılır.
- **Canlı NCBI Validation**: `live_ncbi_validation.py` betiği ve GitHub Actions iş akışı (`.github/workflows/live-ncbi-validation.yml`) aracılığıyla canlı NCBI sunucuları üzerinde düzenli güvenlik ve doğrulama denetimi sağlanır.

---

## 7. Tıbbi Branş ve Uzmanlık Matrisi

Depo kök dizininde yer alan `all_specialty_matrix.json` dosyası, platformun evrensel tıp kapsayıcılığını sağlayan 88 tıbbi uzmanlık alanını içerir.

### 📋 Matris Özellikleri
- **Toplam Branş Sayısı**: Exactly 88 araştırma ve uzmanlık alanı.
- **Özel Ayrı Branş Kayıtları**:
  - **Ruh Sağlığı ve Psikiyatri** (`ruh_sagligi_ve_psikiyatri`)
  - **Fizik Tedavi ve Rehabilitasyon** (`fizik_tedavi_ve_rehabilitasyon`)
- **Alt Odak Alanı Sayısı**: Bütün 88 branş kaydının her birinde **14 özel alt odak alanı** (`sub_focus_areas`) tanımlanmıştır.
- **Zorunlu Alanlar**: `id`, `specialty_name`, `specialty_name_en`, `category`, `description`, `sub_focus_areas`, `search_keywords`.

---
*Doküman Sonu - Medical Research AI Sistem Mimarisi*

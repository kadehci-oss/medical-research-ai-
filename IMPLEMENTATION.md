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

**Medical Research AI**, canlı NCBI PubMed kayıtları ve mevcut özetler üzerinde çalışan bir klinik araştırma prototipidir. Arama ve rapor üretimi sezgiseldir; sistematik tarama, uzman hekim doğrulaması veya halüsinasyonsuzluk garantisi sağlamaz. PMID/DOI eşleşmesi kaynak kaydının kimliğini doğrular, rapordaki her klinik iddianın kaynakça tarafından desteklendiğini kanıtlamaz.

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
   - Çalışma tasarımını sınıflandırır. Tasarım adından kanıt düzeyi üretmez.
   - Kural tabanlı deterministik sentezleyici ve OpenAI LLM sentezleyicisi ile 13 zorunlu bölümden oluşan Türkçe klinik rapor üretir.

5. **`universal_evidence_engine.py` (Evrensel Klinik Kanıt Motoru)**:
   - 88 yapılandırılmış uzmanlık etiketi için anahtar sözcük tabanlı eşleşme ve bazı güvenli kısaltmalar için sınırlı sorgu genişletmesi uygular; bu, her branş veya klinik sorunun kapsandığı anlamına gelmez.
   - PubMed kayıtları ve özetleri üzerinde ön araştırma/sentez yapar. Tam metin taraması, sistematik derleme protokolü veya uzman hekim doğrulaması sağlamaz.

---

## 2. PubMed/MEDLINE Kaynak Taraması ve Okuma Katmanı

### 🔍 Arama ve Filtreleme Mekanizması

NCBI PubMed E-utilities API entegrasyonu iki aşamalı olarak gerçekleştirilir:

1. **Arama Aşaması (`esearch.fcgi`)**:
   - Kullanıcının sorgusu PubMed'e gönderilir. Sadece algılanan uzmanlık ve belirli kısaltmalarda sınırlı eş anlamlı genişletmesi yapılır; kapsamlı MeSH/PICO arama stratejisi oluşturulmaz.
   - Yayın Tipi Filtreleme: *Randomized Controlled Trial*, *Systematic Review*, *Meta-Analysis*, *Clinical Trial*, *Review*.
   - Tarih Aralığı Filtreleme: `start_year` ve `end_year` parametreleri ile spesifik zaman pencereleri tanımlanır.
   - Sıralama: Alaka düzeyi (*relevance*) veya yayın tarihine (*pub_date*) göre sıralama yapılır.

2. **Detay Veri Çekme Aşaması (`efetch.fcgi`)**:
   - `esearch` sonucu elde edilen PMID listesi için XML formatında makale künyesi ve mevcutsa özet metni çekilir; makalenin tam metni alınmaz.
   - Çekilen veriler: PMID, DOI, makale başlığı, yazar listesi, dergi adı, yayın yılı, yayın tipleri ve mevcut özet.

### 🛡 Yeniden Deneme ve İstisna Yönetimi

- İsteklerde `tool` ve `email` meta verileri, yapılandırılmışsa `api_key` iletilir.
- Geçici ağ hataları ve HTTP 429 (*Too Many Requests*) durumlarında sınırlı bekleme/yeniden deneme uygulanır. Süreçler arası ortak hız sınırlayıcı yoktur; API'de kimlik doğrulama ve rate limit de yoktur.

---

## 3. Bilimsel Kanıt Değerlendirmesi ve Parametre Çıkarımı

### 📊 Çalışma Tasarımı

Sistem, NLM yayın türü ile başlık ve özetteki tasarım ifadesini kullanarak tasarımı ayırır. Ayrım bir kanıt düzeyi değildir; `level` alanı `Değerlendirilemedi` kalır.

- Rastgele kontrollü çalışma (RCT)
- Kohort
- Vaka-kontrol
- Kesitsel çalışma
- Olgu sunumu
- Olgu serisi
- Sistematik derleme
- Meta-analiz
- Klinik kılavuz

Resmi GRADE değerlendirmesi veya kesinlik derecesi üretilmez. Özetten çıkarılan sınırlı, kural tabanlı metin sinyalleri sonlanım cümlesine bağlanabilir; bunlar tek bir makale için toplam puana veya çalışmalar arası kanıt bütünü değerlendirmesine dönüştürülmez. Sonlanım veya alan eksikse `değerlendirilemedi` yazılır. RoB 2, ROBINS-I, ROBIS, AXIS, JBI, AGREE II veya QUADAS-2 tasarıma göre seçilebilir; tam yöntem değerlendirmesi yapılmadan araç sonucu veya risk derecesi verildiği iddia edilmez. Hasta grubu, örneklem, müdahale, karşılaştırıcı, sonlanım ve istatistik, kaynak cümle ve PMID ile gösterilir.

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
│ 1. PMID/DOI Kayıt Kimliği Kontrolü                                     │
│ 2. Kaynak Metriklerinin Sezgisel Çıkarımı                              │
│ 3. LLM Veri Aktarımı İçin Açık Kullanıcı Onayı                         │
│ 4. API Anahtarı İşleme ve Hata Mesajı Maskeleme                        │
│ 5. Prompt Injection Riskini Azaltmaya Yönelik Talimatlar               │
│ 6. XSS (Cross-Site Scripting) Engelleme                                │
│ 7. SSRF (Server-Side Request Forgery) Koruması                         │
│ 8. Otomatik Testler ve Sezgisel Çıktı Denetimi                         │
└────────────────────────────────────────────────────────────────────────┘
```

### 6.1. PMID/DOI Doğrulama ve Kaynak–İddia Eşleştirme
- **Kayıt Kimliği Kontrolü**: Verilen PMID PubMed'den yeniden alınır; sağlanmış başlık ve DOI alanları normalize edilerek karşılaştırılır. Bu, kaynak kaydının kimliğini kontrol eder; rapordaki her klinik iddianın o kaynak tarafından desteklendiğini kanıtlamaz.
- **Kaynak Bağlantıları**: Raporlar kaynak kayıtlarına PubMed bağlantısı verebilir; klinik iddia-kaynak eşleştirmesi sezgisel olup uzman tarafından denetlenmelidir.
- **Başlık ve Metin Normalizasyonu**: `normalize_title` ve `normalize_doi` fonksiyonları küçük/büyük harf, noktalama ve DOI öneklerindeki bazı farklılıkları karşılaştırma öncesinde normalleştirir; bu yöntem bağımsız bilimsel doğrulama değildir.

### 6.2. Kaynağa Dayalı Raporlama Hedefi ve Sınırları
- **Kısıtlayıcı İstem ve Kural Tabanlı Çıkarım**: LLM istemi ile metrik çıkarıcılar, kaynakta olmayan sayıların eklenmesini azaltmayı hedefler; halüsinasyonsuzluk veya her metriğin doğru ayrıştırıldığı garanti edilmez.
- **Eksik Veri Beyanı**: Çıkarıcıların bulamadığı parametreler çoğu yerde `"Belirtilmedi"` veya `"Özette bildirilmedi"` olarak sunulur; otomatik çıkarım hatalı veya eksik olabilir.
- **Uzman İncelemesi**: Rapordaki klinik çıkarımlar, güvenlik değerlendirmeleri ve kaynak desteği hekim tarafından gözden geçirilmeden klinik karar için kullanılmamalıdır.

### 6.3. Kişisel Sağlık Verisi: Kullanım Sınırları
- **Amaçlanan Kullanım**: Sistem yayınlanmış araştırma literatürünü sorgulamak içindir; hasta kayıtlarını veya tanımlanabilir sağlık verilerini girmeyin.
- **Otomatik PHI Tespiti Yoktur**: Sorgular hasta adı, T.C. Kimlik No veya başka kişisel tanımlayıcılar için taranmaz ya da anonimleştirilmez. Kalıcı hasta veritabanı bulunmaması, girilen verinin başka hizmetlere aktarılmayacağı anlamına gelmez.
- **LLM Veri Aktarımı**: OpenAI sentezi varsayılan olarak kapalıdır. Kullanıcı açık onay verdiğinde sorgu, PubMed makale üstverisi ve özetleri OpenAI'ye gönderilir; onay, verinin gerçekten kimliksiz olduğunun teknik doğrulaması değildir.

### 6.4. API Anahtarı İşleme
- **Anahtar Kaynakları**: Streamlit `OPENAI_API_KEY` çevre değişkenini kullanabilir; FastAPI rapor isteği ayrıca API anahtarını gövdesinde kabul eder. API servisi kimlik doğrulaması ve hız sınırlaması sağlamaz; herkese açık ağa doğrudan açılmamalıdır.
- **Hata Mesajları**: PubMed ve OpenAI rapor hataları kullanıcıya genel mesajlarla döndürülür; canlı NCBI artifact'ine ham istisna metni yazılmaz. Bu korumalar, uygulamayı her çalışma ortamında gizli bilgi sızıntısına karşı garanti etmez.

### 6.5. Prompt Injection Riskini Azaltma
- **İstem Uyarıları**: LLM sistem istemi kullanıcı sorgusu ve makale başlık/özetlerini güvenilmeyen veri olarak tanımlamaya çalışır; bu, prompt injection'ı kesin biçimde engellemez.
- **Otomatik Denetim**: `perform_red_team_audit` rapora yönelik kural tabanlı kontroller sağlar. Bağımsız red-team testi değildir ve klinik doğruluk ya da halüsinasyonsuzluk garantisi vermez.

### 6.6. XSS (Cross-Site Scripting) Engelleme
- **HTML Kaçış (Escaping)**: Streamlit ve FastAPI arayüzlerinde kullanıcıdan veya dış API'den gelen veriler HTML kaçış süzgecinden geçirilir.
- **Güvenli Markdown ve HTML İşleme**: Rapor oluşturucusu Markdown içeriğini HTML olarak kaçırır ve yalnızca izin verilen bağlantıları üretmeye çalışır; bu, bütün olası XSS yollarının bağımsız güvenlik testiyle doğrulandığı anlamına gelmez.

### 6.7. SSRF Saldırı Yüzeyini Sınırlama
- **Sabit Kaynak Uç Noktaları**: PubMed ve CrossRef istemcileri kodda tanımlı uç noktalara istek gönderir; kullanıcıdan serbest URL alınmaz. OpenAI istemcisi ayrıca ortam yapılandırmasını kullanabilir; uygulama seviyesinde genel bir ağ çıkış allowlist'i yoktur:
  - NCBI PubMed E-utilities: `eutils.ncbi.nlm.nih.gov`
  - CrossRef REST API: `api.crossref.org`
- **Kapsam Sınırı**: Kullanıcı girdilerinden doğrudan URL/IP fetch edilmez; bu, dağıtım katmanındaki ağ yalıtımı veya tüm SSRF risklerinin bağımsız denetimi yerine geçmez.

### 6.8. Otomatik Testler ve Canlı NCBI Kontrolü
- **Otomatik Testler**: `tests/` içindeki pytest paketi `.github/workflows/ci.yml` ile `main`/`master` push ve pull request'lerinde Python 3.12 üzerinde çalıştırılır. Bu testler tek başına klinik doğrulama değildir.
- **Canlı NCBI Kontrolü**: `live_ncbi_validation.py`, sınırlı ESearch/EFetch ve kayıt kimliği smoke testidir; güvenlik denetimi veya klinik doğrulama değildir. GitHub Actions iş akışı haftalık ve elle çalıştırılır, sonuç JSON'unu run artifact'i olarak yükler; depodaki JSON otomatik güncellenmez. İş akışı Python 3.12 kullanır ve bağımlılıkları `requirements.lock` dosyasından kurar. `NCBI_EMAIL` depo sırrı **Settings > Secrets and variables > Actions** altında tanımlanabilir; sır yoksa iş `::warning::` yazar.

---

## 7. Tıbbi Branş ve Uzmanlık Matrisi

Depo kök dizinindeki `all_specialty_matrix.json`, 88 uzmanlık etiketi ve anahtar sözcük içerir. Bu yapılandırılmış liste tıbbın tamamını veya her klinik soruyu kapsamaz; uzmanlık eşleştirmesi sezgiseldir ve kapsam/klinik doğruluk garantisi vermez.

### 📋 Matris Özellikleri
- **Toplam Branş Sayısı**: Exactly 88 araştırma ve uzmanlık alanı.
- **Özel Ayrı Branş Kayıtları**:
  - **Ruh Sağlığı ve Psikiyatri** (`ruh_sagligi_ve_psikiyatri`)
  - **Fizik Tedavi ve Rehabilitasyon** (`fizik_tedavi_ve_rehabilitasyon`)
- **Alt Odak Alanı Sayısı**: Bütün 88 branş kaydının her birinde **14 özel alt odak alanı** (`sub_focus_areas`) tanımlanmıştır.
- **Zorunlu Alanlar**: `id`, `specialty_name`, `specialty_name_en`, `category`, `description`, `sub_focus_areas`, `search_keywords`.

---
*Doküman Sonu - Medical Research AI Sistem Mimarisi*

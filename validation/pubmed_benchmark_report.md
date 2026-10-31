# Çok Branşlı PubMed Klinik Kanıt Benchmark Raporu

Bu rapor, sekiz önceden belirlenmiş PubMed kaydında abstract düzeyindeki çıkarımı kaynak cümleleriyle karşılaştırır. Bu bir hekim adjudikasyonu, tam metin incelemesi, GRADE değerlendirmesi veya yanlılık riski değerlendirmesi değildir.

## Sonuç özeti

- PubMed kimliği doğrulanan kayıt: **8/8**.
- Önceden belirlenmiş referans alanı eşleşmesi: **62/82** (75.6%).
- Eksiksiz makale çıkarımı: **3/8** (37.5%).
- Kaynak cümlesi eşleşmesi: **71/71** (100.0%); bu yalnızca cümlenin kaynak abstract'ta yer aldığını ölçer, anlamsal doğruluğu tek başına kanıtlamaz.
- Yanlış/unsupported çıkarım bayrakları: **0/91** (0.0%); kaynak cümlesi, sayısal değer ve metrik türü kontrollerinde başarısız alanlar sayılır.
- Yanlış nedensellik koruma bayrağı: **0**.

## En sık kaçan referans alanları ve güvenli sonraki işler

Sıra, kaçan alan sayısı ile kaynak/ölçüt bütünlüğü önceliğini birleştirir; klinik risk sıralaması veya hekim adjudikasyonu değildir.
1. **P1 — sonuç değeri — outcome_estimate: 11/16 eşleşti; 5 kaçan.** Yalnızca abstract'ta açıkça yazılı sonuç değerleri için dar kapsamlı çıkarım kalıpları ekle.
2. **P1 — ölçüt türü — outcome_metric: 11/16 eşleşti; 5 kaçan.** HR, OR, oran ve tanısal ölçüt türlerini birbirine karıştırmadan ayır.
3. **P1 — kaynak bağlantısı — outcome_source_sentence: 11/16 eşleşti; 5 kaçan.** Sonuç değerlerini kaynak cümlesine daha güvenilir bağla; eşleşmeyi genişletirken kaynak dışı iddia üretme.
4. **P1 — tahmin belirsizliği — outcome_confidence_interval: 6/7 eşleşti; 1 kaçan.** GA'yı eşleşen tahmine bağla; etiketsiz parantezlerden güven aralığı çıkarma.
5. **P2 — kol paydaları — arm_participant_n: 2/5 eşleşti; 3 kaçan.** Açıkça tahsis edilmiş tedavi kollarının N değerini çalışma toplamı ve sonuç paydasından ayır; karşılaştırmalı kol olmayan grupları zorla eşleme.
6. **P2 — sonuç sayımları — outcome_event_count: 4/5 eşleşti; 1 kaçan.** Olay sayısını aynı sonuç cümlesinde ve doğru kola bağlı olarak karşılaştır.

Not: Bu referans kümesinde [cerrahi vaka serisindeki 51/56 tedavi edilmiş hasta](https://pubmed.ncbi.nlm.nih.gov/39071203/) ve [MRI teknik grupları (29/19)](https://pubmed.ncbi.nlm.nih.gov/31732398/) karşılaştırmalı tahsis kolları değildir; eksikleri yapay kola dönüştürmek uygun değildir.

## Üç ayrı doğrulama kategorisi

1. **Yazılım birim/entegrasyon testleri:** `python -m pytest -q` — PASS; 395 passed, 5 skipped, 17 subtests passed in 132.68s (0:02:12).
2. **Gerçek PubMed kaynak doğrulaması:** 8/8 kayıt PMID ve sağlanan DOI/başlıkla yeniden alındı/eşleşti; **klinik iddialar bağımsız doğrulanmış sayılmaz**.
3. **Bağımsız klinik veri doğrulaması:** **NOT_PERFORMED** — Bu benchmark çalıştırmasında bağımsız klinik adjudikasyon yapılmadı; PMID/DOI/başlık kimliği ve abstract kaynak cümlesi kontrolleri klinik doğruluk doğrulaması değildir.

## Branş ve tasarım bazında sonuçlar

| Branş | PMID | Beklenen tasarım | Motor tasarımı | N (referans / motor) | Alan eşleşmesi | Kaynak cümlesi | Nedensellik bayrağı |
|---|---:|---|---|---:|---:|---|---|
| Kardiyoloji | 34449189 | rct | rct | 5988 / 5988 | 18/18 | 100% | yok |
| Onkoloji | 39416390 | meta_analysis | systematic_review_and_meta_analysis | 2833 / 2833 | 14/14 | 100% | yok |
| Nöroloji | 32113113 | cohort | cohort | 302 / 302 | 2/9 | 100% | yok |
| Enfeksiyon hastalıkları | 17540675 | case_control | case_control | 903 / 903 | 9/10 | 100% | yok |
| Endokrinoloji | 10218744 | systematic_review | systematic_review | — / belirtilmedi | 1/7 | yok | yok |
| Pediatri | 37461867 | diagnostic_accuracy | diagnostic_accuracy | 126 / 126 | 8/8 | 100% | yok |
| Cerrahi | 39071203 | case_series | case_series | 56 / 56 | 2/6 | 100% | yok |
| Radyoloji | 31732398 | diagnostic_accuracy | diagnostic_accuracy | 48 / 48 | 8/10 | 100% | yok |

## Yorum ve sınırlar

Eksiksiz çıkarım, yalnızca referans tablosunda açıkça verilmiş alanların tamamının eşleşmesi olarak tanımlanmıştır; desteklenmeyen alanlar tahminle doldurulmamıştır. Kaynak eşleşme oranı, çıkarılmış değerin doğru klinik yorumlandığını değil, bağlanan kaynak cümlenin PubMed abstract'ında bulunduğunu gösterir. Referans tablosu kısıtlı sayıda makale içerir ve bütün klinik çeşitliliği temsil etmez.

Nedensellik bayrağı; gözlemsel, tanısal, olgu serisi ve derleme/meta-analiz kayıtlarının model durum alanındaki korumayı kontrol eder. Bu, oluşturulmuş her Türkçe cümlenin bağımsız hekim tarafından doğrulanmış olduğu anlamına gelmez.

Model sürümü: `1.0`. PubMed referans kaynağı ve her makalenin bağlantısı [önceden belirlenmiş referans tablosunda](pubmed_reference_cases.json) yer alır.

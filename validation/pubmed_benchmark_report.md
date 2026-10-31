# Çok Branşlı PubMed Klinik Kanıt Benchmark Raporu

Bu rapor, sekiz önceden belirlenmiş PubMed kaydında abstract düzeyindeki çıkarımı kaynak cümleleriyle karşılaştırır. Bu bir hekim adjudikasyonu, tam metin incelemesi, GRADE değerlendirmesi veya yanlılık riski değerlendirmesi değildir.

## Sonuç özeti

- PubMed kimliği doğrulanan kayıt: **8/8**.
- Önceden belirlenmiş referans alanı eşleşmesi: **46/82** (56.1%).
- Eksiksiz makale çıkarımı: **1/8** (12.5%).
- Kaynak cümlesi eşleşmesi: **53/53** (100.0%); bu yalnızca cümlenin kaynak abstract'ta yer aldığını ölçer, anlamsal doğruluğu tek başına kanıtlamaz.
- Yanlış/unsupported çıkarım bayrakları: **0/67** (0.0%); kaynak cümlesi, sayısal değer ve metrik türü kontrollerinde başarısız alanlar sayılır.
- Yanlış nedensellik koruma bayrağı: **0**.

## Üç ayrı doğrulama kategorisi

1. **Yazılım birim/entegrasyon testleri:** `python -m pytest -q` — PASS; 389 passed, 5 skipped, 17 subtests passed in 146.70s (0:02:26).
2. **Gerçek PubMed kaynak doğrulaması:** 8/8 kayıt PMID ve sağlanan DOI/başlıkla yeniden alındı/eşleşti; **klinik iddialar bağımsız doğrulanmış sayılmaz**.
3. **Bağımsız klinik veri doğrulaması:** **NOT_PERFORMED** — Bağımsız hekim değerlendirmeli veri kümesi veya tam metin çıkarımı sağlanmadı; PubMed kayıt kimliği ve özet cümlesi eşleşmesi klinik doğrulama değildir.

## Branş ve tasarım bazında sonuçlar

| Branş | PMID | Beklenen tasarım | Motor tasarımı | N (referans / motor) | Alan eşleşmesi | Kaynak cümlesi | Nedensellik bayrağı |
|---|---:|---|---|---:|---:|---|---|
| Kardiyoloji | 34449189 | rct | rct | 5988 / 5988 | 14/18 | 100% | yok |
| Onkoloji | 39416390 | meta_analysis | systematic_review_and_meta_analysis | 2833 / 2833 | 8/14 | 100% | yok |
| Nöroloji | 32113113 | cohort | cohort | 302 / 302 | 2/9 | 100% | yok |
| Enfeksiyon hastalıkları | 17540675 | case_control | case_control | 903 / 903 | 9/10 | 100% | yok |
| Endokrinoloji | 10218744 | systematic_review | systematic_review | — / belirtilmedi | 1/7 | yok | yok |
| Pediatri | 37461867 | diagnostic_accuracy | diagnostic_accuracy | 126 / 126 | 8/8 | 100% | yok |
| Cerrahi | 39071203 | case_series | case_series | 56 / 56 | 2/6 | 100% | yok |
| Radyoloji | 31732398 | diagnostic_accuracy | diagnostic_accuracy | 48 / 48 | 2/10 | 100% | yok |

## Yorum ve sınırlar

Eksiksiz çıkarım, yalnızca referans tablosunda açıkça verilmiş alanların tamamının eşleşmesi olarak tanımlanmıştır; desteklenmeyen alanlar tahminle doldurulmamıştır. Kaynak eşleşme oranı, çıkarılmış değerin doğru klinik yorumlandığını değil, bağlanan kaynak cümlenin PubMed abstract'ında bulunduğunu gösterir. Referans tablosu kısıtlı sayıda makale içerir ve bütün klinik çeşitliliği temsil etmez.

Nedensellik bayrağı; gözlemsel, tanısal, olgu serisi ve derleme/meta-analiz kayıtlarının model durum alanındaki korumayı kontrol eder. Bu, oluşturulmuş her Türkçe cümlenin bağımsız hekim tarafından doğrulanmış olduğu anlamına gelmez.

Model sürümü: `1.0`. PubMed referans kaynağı ve her makalenin bağlantısı [önceden belirlenmiş referans tablosunda](pubmed_reference_cases.json) yer alır.

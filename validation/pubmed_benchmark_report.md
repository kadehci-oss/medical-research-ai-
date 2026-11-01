# Çok Branşlı PubMed Kaynaklı Alan Benchmark Raporu

Bu rapor, sekiz önceden belirlenmiş PubMed kaydında abstract düzeyindeki yazılım çıkarımını kaynak cümleleri ve referans alanlarıyla karşılaştırır. Bu çalışma bağımsız klinik adjudikasyon, tam metin incelemesi, GRADE veya yanlılık riski değerlendirmesi değildir.

## Sonuç özeti

- Yeniden alınarak PMID/başlık/DOI ile doğrulanan kayıt: **8/8**.
- Önceden belirlenmiş referans alanı eşleşmesi: **79/79** (100.0%).
- Eksiksiz referans alanı: **8/8**.
- Bağlı kaynak cümlesi bulunan alan: **142/142** (100.0%); bu, klinik doğruluğu değil cümlenin kaynak abstract'ta bulunduğunu ölçer.
- Desteklenmeyen kaynak/değer/metrik bayrağı: **0/164**.
- Nedensellik koruma kuralı ihlali: **0**.

## Referans alanı boşlukları

Aşağıdaki öncelik, yalnızca sınırlı benchmark referansındaki eşleşmeyen alan sayısını gösterir; klinik risk veya klinik adjudikasyon sıralaması değildir.
- Bu sınırlı referans kümesinde eşleşmeyen alan yok.

## Kayıt bazında sonuçlar

| Branş | PMID | Tasarım (beklenen / model) | N (beklenen / model) | Alan eşleşmesi | Kaynak cümlesi | Model alan kontrolü |
|---|---:|---|---:|---:|---:|---|
| Kardiyoloji | 34449189 | rct / rct | 5988 / 5988 | 18/18 | 27/27 | structurally_valid |
| Onkoloji | 39416390 | meta_analysis / systematic_review_and_meta_analysis | 2833 / 2833 | 14/14 | 70/70 | structurally_valid |
| Nöroloji | 32113113 | cohort / cohort | 302 / 302 | 9/9 | 6/6 | structurally_valid |
| Enfeksiyon hastalıkları | 17540675 | case_control / case_control | 903 / 903 | 10/10 | 14/14 | structurally_valid |
| Endokrinoloji | 10218744 | systematic_review / systematic_review | — / belirtilmedi | 7/7 | 4/4 | structurally_valid |
| Pediatri | 37461867 | diagnostic_accuracy / diagnostic_accuracy | 126 / 126 | 8/8 | 6/6 | structurally_valid |
| Cerrahi | 39071203 | case_series / case_series | 56 / 56 | 5/5 | 4/4 | structurally_valid |
| Radyoloji | 31732398 | diagnostic_accuracy / diagnostic_accuracy | 48 / 48 | 8/8 | 11/11 | structurally_valid |

## Doğrulama sınırları

PubMed kimlik kontrolü kaynak kaydının yeniden bulunması ve verilen kimlik alanlarının eşleşmesi içindir. Kaynak cümlesi kontrolü cümlenin abstract/başlıkta bulunmasına bakar; alanın klinik anlamda doğru yorumlandığını kanıtlamaz. Benchmark referans kümesi sınırlıdır ve bütün klinik çeşitliliği temsil etmez.

Bağımsız klinik doğrulama: **YAPILMADI**. GRADE ve yanlılık riski: **değerlendirilmedi**.

Kanonik model sürümü: `1.0.0`. Referans verisi: `pubmed_reference_cases.json` (sürüm 1.1).

# Çok Branşlı PubMed Kaynaklı Alan Benchmark Raporu

Bu rapor, sekiz önceden belirlenmiş PubMed kaydında abstract düzeyindeki yazılım çıkarımını kaynak cümleleri ve referans alanlarıyla karşılaştırır. Bu çalışma bağımsız klinik adjudikasyon, tam metin incelemesi, GRADE veya yanlılık riski değerlendirmesi değildir.

## Sonuç özeti

- Yeniden alınarak PMID/başlık/DOI ile doğrulanan kayıt: **8/8**.
- Önceden belirlenmiş referans alanı eşleşmesi: **79/79 (100.0%)**.
- Eksiksiz referans alanı: **8/8**.
- Önceden belirlenmiş kaynak alıntısı metninin canlı PubMed kaydında bulunması: **23/23**.
- Model alanlarının kaynak metninin canlı abstract/başlık içinde bulunması: **130/130 (100.0%)**; bu tam cümle eşitliği veya klinik doğruluk değildir.
- Desteklenmeyen literal değer/ölçüt kaynak dizesi kontrolleri: **0/148**; kaynaktan türetilmiş değerlerde literal sayı kontrolü yapılmayan kaynak: **0**.
- Kanonik renderer’ın yapılandırılmış iddia cümlelerinde phrase-scan ile desteklenmeyen nedensel dil: **0/26**.

## Referans alanı boşlukları

Aşağıdaki öncelik, yalnızca sınırlı benchmark referansındaki eşleşmeyen alan sayısını gösterir; klinik risk veya klinik adjudikasyon sıralaması değildir.
- Bu sınırlı referans kümesinde eşleşmeyen alan yok.

## Kayıt bazında sonuçlar

| Branş | PMID | Tasarım (beklenen / model) | N (beklenen / model) | Alan eşleşmesi | Kaynak metni | Model alan kontrolü |
|---|---:|---|---:|---:|---:|---|
| Kardiyoloji | 34449189 | rct / rct | 5988 / 5988 | 18/18 | 27/27 | structurally_valid |
| Onkoloji | 39416390 | meta_analysis / systematic_review_and_meta_analysis | 2833 / 2833 | 14/14 | 55/55 | structurally_valid |
| Nöroloji | 32113113 | cohort / cohort | 302 / 302 | 9/9 | 6/6 | structurally_valid |
| Enfeksiyon hastalıkları | 17540675 | case_control / case_control | 903 / 903 | 10/10 | 17/17 | structurally_valid |
| Endokrinoloji | 10218744 | systematic_review / systematic_review | — / belirtilmedi | 7/7 | 4/4 | structurally_valid |
| Pediatri | 37461867 | diagnostic_accuracy / diagnostic_accuracy | 126 / 126 | 8/8 | 6/6 | structurally_valid |
| Cerrahi | 39071203 | case_series / case_series | 56 / 56 | 5/5 | 4/4 | structurally_valid |
| Radyoloji | 31732398 | diagnostic_accuracy / diagnostic_accuracy | 48 / 48 | 8/8 | 11/11 | structurally_valid |

## Doğrulama sınırları

PubMed kimlik kontrolü kaynak kaydının yeniden bulunması ve verilen kimlik alanlarının eşleşmesi içindir. Kaynak metni kontrolü normalize edilmiş alıntı metninin canlı abstract/başlık içinde yer almasını denetler; tam cümle eşitliği veya alanın klinik anlamda doğru yorumlandığını kanıtlamaz. Nedensel dil phrase-scan’i yalnızca kanonik renderer’ın yapılandırılmış iddia cümlelerini tarar; semantik veya hekim değerlendirmesi değildir. Benchmark referans kümesi sınırlıdır ve bütün klinik çeşitliliği temsil etmez.

Bağımsız klinik doğrulama: **YAPILMADI**. GRADE ve yanlılık riski: **değerlendirilmedi**.

Kanonik model sürümü: `1.1.0`. Referans verisi: `pubmed_reference_cases.json` (sürüm 1.1).

## Çalıştırma izi

UTC zamanı: `2026-11-01T15:06:15.366247+00:00`; Python: `3.12.3`; çalıştırıcı SHA-256: `69e0488ff4dc9dd39a162a0490f927416643f923b460ff39d0a7fce57a7cb9e0`; referans verisi SHA-256: `246793d61354b5fcc5a724d733b2fcd76c5af1292d9c9a5611b497289ccb4fe3`; çalıştırma anındaki Git HEAD: `bb844dc9b454b6d1f5fe96fb97eb02ea1be188c3`.
Canlı abstract SHA-256 özeti her doğrulanan kayıt için JSON raporunda saklanır. Kimliği doğrulanamayan kayıtlar bu metriklerin paydasına dahil edilmez; değerlendirilmedikleri ayrıca sayılır.

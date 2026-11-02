# Bağımsız uzman hekim değerlendirme protokolü — henüz onay verilmedi

İnceleme malzemesi üretmek için `python generate_review_packet.py --output review_packet --pause 2` çalıştırılabilir. Betik PubMed'den taslak rapor ve boş `puanlama.csv` yazar. Puanları doldurmaz, imza toplamaz ve bu protokolün uygulandığını göstermez.

## Şartlar
- En az iki bağımsız, ilgili branştan uzman hekim; geliştirici ve test verilerini hazırlayan kişilerden bağımsız.
- Önceden belirlenmiş 30 klinik soru: anti-HMGCR/statin miyopatisi (10), kalp yetersizliği (10), enfeksiyon hastalıkları/antibiyotik stewardship (10). Gerçek hasta kimliği içermeyen, sentetik veya anonim klinik sorular.
- Bu 30 soruluk örneklem yalnızca üç klinik alan için pilot değerlendirmedir; tüm branşları, soru türlerini veya tüm kullanıcı gruplarını doğruladığı ileri sürülemez. Projenin tüm branş hedefi için daha geniş, önceden belirlenmiş bir örneklem ve ilgili uzmanlık alanlarından değerlendiriciler gerekir.
- Her soru için önceden dondurulmuş referans cevap: makale PMID/DOI, tam metin veya özet kaynağı, kılavuz tarihi, PICO, temel bulgular, uygulanabilirlik, sakıncalar.
- Uzmanlara araç adı/modeli gizlenerek, rastgele sırayla rapor çıktıları sunulmalı; başlangıçta bağımsız değerlendirme, ardından uyuşmazlıklarda üçüncü uzman.

## Puanlama formu (her vaka için)
Vaka ID: ____    İnceleyen uzman kodu: ____    Tarih: ____

| Alan | 0: Kabul edilemez | 1: Kısmen doğru | 2: Doğru | Puan |
|---|---|---|---|---|
| Klinik soru ve PICO | Yanlış popülasyon/müdahale | Eksik ama zararsız | Doğru ve uygun | ___ |
| Kaynak kimliği | Yanlış/uydurma PMID veya DOI | Kısmi eksik | Doğru | ___ |
| İddia-kaynak uyumu | Desteklenmeyen klinik sonuç | Çekinceler eksik | Tam izlenebilir | ___ |
| Çalışma tasarımı/kanıt | Derlemeyi RCT sayıyor | Kısmen doğru | Doğru | ___ |
| Güvenlik/uygulanabilirlik | Zararlı veya mutlak öneri | Önemli çekince eksik | Güvenli ve bağlama uygun | ___ |
| Belirsizlik ve sınırlar | Yapay kesinlik | Kısmi sınırlar | Yeterli sınırlar | ___ |

Kritik hata var mı? (Uydurma kaynak, yanlış tedavi önerisi, kontrendikasyon atlama, hatalı doz, popülasyon dışı kesin çıkarım): Evet / Hayır
Kritik hatanın açıklaması ve referansı: ____
Uzman değerlendirmesi: Onay / Düzeltmeyle koşullu kabul / Ret
Uzman adı, kurum, uzmanlık alanı, imza: ____

## Önceden belirlenmiş kabul ölçütü (protokol önerisi; klinik standart iddiası değil)
- Sıfır kritik güvenlik hatası, 30 vakanın her birinde.
- Her iki değerlendiricinin her vaka için tüm alanlarda >=1 vermesi.
- Toplam alan puanlarının en az %90'ında 2 puan.
- Uyuşmazlık ve düzeltmelerin sürüm bazında kaydedilmesi.
- Canlı API ve üretimden alınmış raporların test sırasında değişmeden arşivlenmesi.

**Bu form boş bir protokoldür. Bağımsız hekim incelemesi veya onayı yapılmış değildir.**

## Değer düzeyinde doğrulama kiti (test kategorisi 3)

`validation/clinician_verification/` klasörü, motorun 75 PubMed özetinden (10 branş) çıkardığı her değer için bir satır içerir: tasarım, toplam n, kol büyüklükleri, olay sayıları, her etki tahmini (değer, GA, p, sonlanım) ve nedensel dil izni. Her satırda PMID, PubMed bağlantısı ve kaynak cümle vardır.

1. `degerlendirici_A.csv` ve `degerlendirici_B.csv` aynı satırları farklı rastgele sırada içerir; iki hekim birbirinden bağımsız doldurur.
2. `karar` sütununa yalnızca şu değerlerden biri yazılır: `dogru`, `yanlis`, `eksik_veya_belirsiz`, `kaynakta_yok`. Yanlışsa `dogru_deger` sütununa kaynaktaki değer yazılır.
3. `python validation/clinician_verification/score_sheets.py` hata oranlarını, ham uyumu ve Cohen kappa değerini hesaplar; uyuşmayan satırları hakem kararına listeler.

Karar sütunları depoda boştur ve boş kalırken puanlayıcı `NOT_PERFORMED` döndürür. Bu kit bir doğrulama sonucu değildir; sonuç ancak hekimler doldurduktan sonra oluşur. Kit motor değiştikçe `build_sheet.py` ile yeniden üretilmelidir.

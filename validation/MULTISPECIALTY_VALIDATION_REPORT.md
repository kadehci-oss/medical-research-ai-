# Çok Branşlı Doğrulama Raporu

Oluşturulma: 2026-11-01 · Yazılım: `v1.5.0` · Kanıt veri modeli: `1.0.0`

Bu rapor `python validation/run_multispecialty_validation.py` ile üretilir; elle düzenlenmez.

## Özet

- Geliştirme kümesi motor ayarlanırken kullanıldı; sonuçları **iyimserdir**, doğruluk tahmini değildir.
- **Ayrılmış küme 1** ve **ayrılmış küme 2** için referans değerler motor bu kayıtlarda hiç çalıştırılmadan yazıldı;
  ilk çalıştırmalar `validation/holdout_first_run_results.json` ve `validation/holdout2_first_run_results.json` içinde donduruldu.
  Küme 2, küme 1'in ortaya çıkardığı hatalar düzeltildikten sonra kuruldu: düzeltmelerin genellenip genellenmediğini ölçer.
- **Gerçekçi beklenti, iki bağımsız ilk çalıştırmadır** (aşağıda kalın). Sonraki düzeltmeler bu kümeleri de görmüş olduğundan
  güncel sonuçları bağımsız değildir.

| Ölçüt | Geliştirme kümesi (ayarlı) | **Ayrılmış küme 1, ilk çalıştırma (bağımsız)** | **Ayrılmış küme 2, ilk çalıştırma (bağımsız)** | Küme 1 + 2, düzeltme sonrası (bağımsız değil) |
|---|---|---|---|---|
| Eksiksiz çıkarım oranı | %100.0 (153/153) | **%77.9 (53/68)** | **%78.8 (52/66)** | %100.0 (68/68) / %93.9 (62/66) |
| Yanlış çıkarım oranı | %0.0 (0/153) | **%8.6 (5/58)** | **%11.9 (7/59)** | %0.0 (0/68) / %1.6 (1/63) |
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (210/210) | **%100.0 (62/62)** | **%100.0 (73/73)** | %100.0 (92/92) / %100.0 (87/87) |
| Kaynak eşleşme doğruluğu (sayısal değer) | %100.0 (160/160) | **%100.0 (52/52)** | **%100.0 (48/48)** | %100.0 (67/67) / %100.0 (63/63) |
| Yanlış nedensellik iddiası | 0 | **0** | **0** | 0 / 0 |
| Soru çerçevesi seçimi | 18/18 | **9/10** | **8/8** | 10/10 / 8/8 |

- Yayın sayısı: geliştirme 35, ayrılmış küme 1 16, ayrılmış küme 2 17; toplam **68 gerçek PubMed yayını**.
- **Sınırlılık:** Referans tabloları bir yapay zekâ asistanı hazırladı; bağımsız uzman hekim kontrolü yapılmadı. Yalnızca özetler kullanıldı. Kümeler küçük olduğu için oranların belirsizliği yüksektir.

### Ayrılmış küme 1: ilk çalıştırmada bulunan hatalar

- **PMID 31535829:** EKSİK: 31535829 eşlik eden tedavi '' (beklenen ['recommended therapy'])
- **PMID 41020486:** EKSİK: 41020486 HR 0.81 [0.68, 0.96]
- **PMID 41439471:** BAĞLANMADI: 41439471 HR 0.7 [0.65, 0.76] sonlanım adı yok
- **PMID 41468680:** YANLIŞ: 41468680 örneklem 1627 (beklenen 465)
- **PMID 41317018:** YANLIŞ: 41317018 örneklem 22189 (beklenen 170198); EKSİK: 41317018 OR 2.32 [1.85, 2.91]
- **PMID 39652885:** EKSİK: 39652885 müdahale '' (beklenen ['pct', 'procalcitonin']); EKSİK: 39652885 karşılaştırıcı '' (beklenen ['standard care', 'crp'])
- **PMID 38864155:** YANLIŞ BAĞLAMA: 38864155 OR 0.91 [0.81, 1.01] → 'assigned intermittent infusion'; YANLIŞ BAĞLAMA: 38864155 RD -1.9 [-4.9, 1.1] → 'assigned intermittent infusion'; EKSİK: 38864155 müdahale '' (beklenen ['continuous']); EKSİK: 38864155 karşılaştırıcı '' (beklenen ['intermittent'])
- **PMID 41454243:** EKSİK: 41454243 örneklem None (beklenen 973); EKSİK: 41454243 sensitivity 96.8 None
- **PMID 40937188:** EKSİK: 40937188 örneklem None (beklenen 5)
- **PMID 40697501:** EKSİK: 40697501 örneklem None (beklenen 3)
- **PMID 40996213:** BAĞLANMADI: 40996213 HR 0.8 [0.47, 1.4] sonlanım adı yok; BAĞLANMADI: 40996213 HR 0.6 [0.36, 1.14] sonlanım adı yok; EKSİK: 40996213 müdahale '' (beklenen ['wedge', '4b/5', 'segment']); EKSİK: 40996213 karşılaştırıcı '' (beklenen ['wedge', '4b/5', 'segment']); YANLIŞ: 40996213 birincil çalışma yanlışlıkla 'updated_analysis' sayıldı

### Ayrılmış küme 2: ilk çalıştırmada bulunan hatalar

- **PMID 41631724:** YANLIŞ BAĞLAMA: 41631724 HR 1.337 [1.043, 1.713] → 'non-inferiority'; YANLIŞ BAĞLAMA: 41631724 HR 0.657 [0.455, 0.949] → 'non-inferiority'
- **PMID 41667319:** EKSİK: 41667319 örneklem None (beklenen 736)
- **PMID 41449806:** EKSİK: 41449806 örneklem None (beklenen 9988)
- **PMID 41269206:** YANLIŞ: 41269206 müdahale '44 days' (beklenen ['stenting', 'endarterectomy']); YANLIŞ: 41269206 karşılaştırıcı 'ipsilateral ischemic stroke' (beklenen ['medical'])
- **PMID 41406444:** YANLIŞ: 41406444 örneklem 6586 (beklenen 13299); EKSİK: 41406444 HR 0.92 [0.83, 1.01]
- **PMID 41675637:** EKSİK: 41675637 örneklem None (beklenen 24463)
- **PMID 42065095:** EKSİK: 42065095 örneklem None (beklenen 356904)
- **PMID 41092331:** EKSİK: 41092331 örneklem None (beklenen 149090); YANLIŞ: 41092331 karşılaştırıcı 'azithromycin four times a year' (beklenen ['placebo'])
- **PMID 41051743:** BAĞLANMADI: 41051743 OR 0.12 [0.06, 0.26] sonlanım adı yok
- **PMID 41552219:** EKSİK: 41552219 örneklem None (beklenen 235)
- **PMID 41167592:** EKSİK: 41167592 örneklem None (beklenen 198); YANLIŞ BAĞLAMA: 41167592 OR 1.94 None → 'diabetes mellitus'
- **PMID 41410574:** EKSİK: 41410574 accuracy 78.6 None
- **PMID 41354041:** EKSİK: 41354041 örneklem None (beklenen 8094)

## Dış referans: PR #64'ün sekiz PubMed vakası

Referans tablosu (`validation/reference_external_pr64.json`) PR #64'te başka bir yapay zekâ ajanı tarafından, bu motor
bu kayıtları görmeden yazıldı ve buraya değiştirilmeden kopyalandı. Sekiz branşın her birinden bir yayın içerir.
Puanlama `python validation/run_external_reference_check.py` ile yapılır ve yalnızca sayısal alanları kapsar
(tasarım, toplam n, kol n, etki tahmini, GA, p, olay sayısı); niteliksel alanlar ayrıca listelenir.
Ölçüt tanımları yukarıdaki kümelerden farklıdır; oranlar doğrudan karşılaştırılamaz.

| Ölçüt | **İlk çalıştırma (bağımsız)** | Düzeltme sonrası (bağımsız değil) |
|---|---|---|
| Doğru alan | **%67.4 (31/46)** | %97.7 (42/43) |
| Yanlış alan | **%8.7 (4/46)** | %0.0 (0/43) |
| Eksik alan | **11/46** | 1/43 |
| Eksiksiz makale | **3/8** | 7/8 |

### Dış referans: ilk çalıştırmada bulunan hatalar

- **PMID 34449189** (Kardiyoloji, rct): eksik arm_n:empagliflozin (beklenen 2997, bulunan None); eksik arm_n:placebo (beklenen 2991, bulunan None); eksik events:407 (total number of hospitalizatio) (beklenen 407, bulunan [415, 511, 2997, 2991]); eksik events:541 (total number of hospitalizatio) (beklenen 541, bulunan [415, 511, 2997, 2991]); yanlış olay sayısı olarak hasta sayısı: 2997 (beklenen olay değil, bulunan 2997); yanlış olay sayısı olarak hasta sayısı: 2991 (beklenen olay değil, bulunan 2991)
- **PMID 39416390** (Onkoloji, meta_analysis): yanlış total_n (beklenen 2833, bulunan 5); eksik estimate:proportion 71.8% (12-month overall survival for combined a) (beklenen 71.8%, bulunan None); eksik ci:proportion 71.8% (12-month overall survival for combined a) (beklenen ['67.6%', '76.2%'], bulunan None); eksik estimate:proportion 35.1% (12-month progression-free survival for c) (beklenen 35.1%, bulunan None); eksik ci:proportion 35.1% (12-month progression-free survival for c) (beklenen ['30.5%', '40.4%'], bulunan None)
- **PMID 32113113** (Nöroloji, cohort): eksik total_n (beklenen 302, bulunan None)
- **PMID 17540675** (Enfeksiyon hastalıkları, case_control): eksik total_n (beklenen 903, bulunan None)
- **PMID 31732398** (Radyoloji, diagnostic_accuracy): eksik total_n (beklenen 48, bulunan None); yanlış olay sayısı olarak hasta sayısı: 48 (beklenen olay değil, bulunan 48)

## Geliştirme kümesi ayrıntıları

### Kapsam ve yöntem

- **35 gerçek PubMed yayını**, **8 branş**: Cerrahi, Endokrinoloji, Enfeksiyon, Kardiyoloji, Nöroloji, Onkoloji, Pediatri, Radyoloji.
- Kayıtlar PubMed'den alındı (PMID, DOI, başlık, özet, yayın türü) ve `validation/` altındaki JSON dosyalarında değiştirilmeden saklandı.
- Referans tablo özetler elle okunarak, motor çıktısına bakılmadan yazıldı.
- **Sınırlılık:** Referans tabloyu bir yapay zekâ asistanı hazırladı. Bağımsız uzman hekim kontrolü henüz yapılmadı. Yalnızca özetler kullanıldı; tam metin okunmadı.

### Ölçüt tanımları

- **Eksiksiz çıkarım oranı:** Referansta bildirilen öğelerden (tasarım, örneklem, ana etki tahmini + GA, müdahale, karşılaştırıcı, eşlik eden tedavi, yayın ilişkisi) motorun doğru çıkardıklarının oranı.
- **Yanlış çıkarım oranı:** Motorun ileri sürdüğü öğelerden referansla çelişenlerin oranı (yanlış sonlanım bağlama, olay/kol sayısının örneklem sanılması, eksik değere değer atama dahil).
- **Kaynak eşleşme doğruluğu:** Her yapılandırılmış öğenin kaynak cümlesinin aynı PMID'nin özetinde birebir bulunma oranı; ayrıca her sayısal değerin o cümlede geçme oranı.
- **Yanlış nedensellik iddiası:** Randomize olmayan çalışmalara bağlı rapor satırlarında (alıntılar hariç) nedensel/üstünlük ifadesi sayısı + nedensel çıkarıma yanlışlıkla izin verilen çalışma sayısı.

### Genel sonuçlar

| Ölçüt | Değer |
|---|---|
| Eksiksiz çıkarım oranı | %100.0 (153/153) |
| Yanlış çıkarım oranı | %0.0 (0/153) |
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (210/210) |
| Kaynak eşleşme doğruluğu (sayısal değer) | %100.0 (160/160) |
| Yanlış nedensellik iddiası | 0 |
| Örneklem yerine olay/kol sayısı | 0 |
| Eşlik eden tedavinin müdahale sanılması | 0 |
| Bağımsız kanıt sayımı hatası | 0 |
| Soru çerçevesi seçimi | 18/18 |
| Sonlanım bağlama (doğru / adsız / yanlış) | 31 / 0 / 0 |

### Branşlara göre

| Branş | Yayın | Tasarımlar | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|---|
| Cerrahi | 4 | Kohort, Mektup (özet yok), RCT | %100.0 (15/15) | %0.0 (0/15) |
| Endokrinoloji | 4 | Kohort, Meta-analiz, RCT | %100.0 (16/16) | %0.0 (0/16) |
| Enfeksiyon | 5 | Olgu serisi, RCT, Tanısal doğruluk | %100.0 (16/16) | %0.0 (0/16) |
| Kardiyoloji | 5 | Meta-analiz, RCT, Sistematik derleme | %100.0 (30/30) | %0.0 (0/30) |
| Nöroloji | 5 | Kohort, Meta-analiz, Protokol (sonuç yok), RCT | %100.0 (21/21) | %0.0 (0/21) |
| Onkoloji | 6 | Olgu serisi, RCT, Vaka-kontrol | %100.0 (25/25) | %0.0 (0/25) |
| Pediatri | 3 | Kohort, RCT | %100.0 (15/15) | %0.0 (0/15) |
| Radyoloji | 3 | Meta-analiz, Tanısal doğruluk | %100.0 (15/15) | %0.0 (0/15) |

### Araştırma türüne göre

| Tasarım | Yayın | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|
| Vaka-kontrol | 2 | %100.0 (5/5) | %0.0 (0/5) |
| Olgu serisi | 4 | %100.0 (8/8) | %0.0 (0/8) |
| Kohort | 7 | %100.0 (22/22) | %0.0 (0/22) |
| Tanısal doğruluk | 3 | %100.0 (11/11) | %0.0 (0/11) |
| Mektup (özet yok) | 1 | %100.0 (3/3) | %0.0 (0/3) |
| Meta-analiz | 6 | %100.0 (32/32) | %0.0 (0/32) |
| Protokol (sonuç yok) | 1 | %100.0 (1/1) | %0.0 (0/1) |
| RCT | 10 | %100.0 (66/66) | %0.0 (0/66) |
| Sistematik derleme | 1 | %100.0 (5/5) | %0.0 (0/5) |

### Çalışma ilişkileri (mükerrer kanıt kontrolü)

- Bağımsız birincil kanıt birimi: 24
- Aynı çalışma kümesi: PMID 34449189, 36129693
- Aynı çalışma kümesi: PMID 37272513, 39288781
- Aynı çalışma kümesi: PMID 33017106, 34694761
- PMID 36041474 (kanıt sentezi), PMID 34449189, 36129693 ile aynı katılımcıları içeriyor; bu katılımcılar bağımsız kanıt toplamına iki kez eklenmedi.

### Rapor doğrulama durumu (branş başına tam Türkçe rapor)

| Branş | Durum | Alıntı kontrolü | Kümede olmayan PMID | RoB/GRADE derece iddiası |
|---|---|---|---|---|
| Kardiyoloji | Doğrulandı | 78/78 | 0 | 0 |
| Onkoloji | Doğrulandı | 80/80 | 0 | 0 |
| Nöroloji | Doğrulandı | 64/64 | 0 | 0 |
| Enfeksiyon | Doğrulandı | 40/40 | 0 | 0 |
| Endokrinoloji | Doğrulandı | 57/57 | 0 | 0 |
| Pediatri | Doğrulandı | 51/51 | 0 | 0 |
| Cerrahi | Doğrulandı | 46/46 | 0 | 0 |
| Radyoloji | Doğrulandı | 34/34 | 0 | 0 |

### Soru çerçevesi seçimi

| Branş | Soru | Beklenen | Motor |
|---|---|---|---|
| Kardiyoloji | Empagliflozin versus placebo in heart failure with preserved ejection fraction | therapy | therapy ✓ |
| Kardiyoloji | Sensitivity and specificity of automated blood pressure devices for detecting atrial fibrillation | diagnosis | diagnosis ✓ |
| Onkoloji | Oral contraceptive use and risk of colorectal cancer | etiology | etiology ✓ |
| Onkoloji | Low-dose CT screening for lung cancer mortality | screening | screening ✓ |
| Nöroloji | Prognosis of post-stroke epilepsy and seizure recurrence | prognosis | prognosis ✓ |
| Nöroloji | Optic nerve sheath diameter ultrasound diagnostic accuracy for raised intracranial pressure | diagnosis | diagnosis ✓ |
| Enfeksiyon | Dexamethasone for hospitalized COVID-19 patients mortality | therapy | therapy ✓ |
| Enfeksiyon | Prevalence of Toscana virus meningitis in Austria | epidemiology | epidemiology ✓ |
| Endokrinoloji | Tirzepatide adverse events and safety in obesity | safety | safety ✓ |
| Endokrinoloji | Metformin use and cancer risk in type 2 diabetes cohort | etiology | etiology ✓ |
| Pediatri | Ondansetron for children with gastroenteritis vomiting | therapy | therapy ✓ |
| Pediatri | Long-term prognosis of children with recurrent febrile seizures | prognosis | prognosis ✓ |
| Cerrahi | Antibiotics versus appendectomy for acute appendicitis | surgery | surgery ✓ |
| Cerrahi | Laparoscopic versus open cholecystectomy postoperative complications | surgery | surgery ✓ |
| Radyoloji | Diagnostic accuracy of MRCP versus ultrasonography in obstructive jaundice | diagnosis | diagnosis ✓ |
| Radyoloji | Cost-effectiveness of teleradiology services in rural hospitals | health_services | health_services ✓ |
| Kardiyoloji | Kalp yetmezliğinde SGLT2 inhibitörlerinin mortaliteye etkisi | therapy | therapy ✓ |
| Radyoloji | Beyin kanamasında konik ışınlı BT tanısal doğruluğu duyarlılık özgüllük | diagnosis | diagnosis ✓ |

### Eksik ve yanlış öğeler (çalışma bazında)


### Test kategorileri

1. **Yazılım birim ve entegrasyon testleri:** `tests/test_evidence_model.py` (rapor doğrulama testleri dahil), `tests/test_question_framework.py` ve mevcut test paketi.
2. **Gerçek PubMed kaynak doğrulaması:** `tests/test_pubmed_source_verification.py` (kayıtlı PubMed kayıtlarının bütünlüğü; `RUN_LIVE_PUBMED=1` ile canlı NCBI karşılaştırması).
3. **Bağımsız klinik veri doğrulaması:** `tests/test_clinical_reference_validation.py` (bu raporun ölçütleri; eşik altına düşerse test başarısız olur).


## Ayrılmış küme 1, güncel çalıştırma ayrıntıları

### Kapsam ve yöntem

- **16 gerçek PubMed yayını**, **8 branş**: Cerrahi, Endokrinoloji, Enfeksiyon, Kardiyoloji, Nöroloji, Onkoloji, Pediatri, Radyoloji.
- Kayıtlar PubMed'den alındı (PMID, DOI, başlık, özet, yayın türü) ve `validation/` altındaki JSON dosyalarında değiştirilmeden saklandı.
- Referans tablo özetler elle okunarak, motor çıktısına bakılmadan yazıldı.
- **Sınırlılık:** Referans tabloyu bir yapay zekâ asistanı hazırladı. Bağımsız uzman hekim kontrolü henüz yapılmadı. Yalnızca özetler kullanıldı; tam metin okunmadı.

### Ölçüt tanımları

- **Eksiksiz çıkarım oranı:** Referansta bildirilen öğelerden (tasarım, örneklem, ana etki tahmini + GA, müdahale, karşılaştırıcı, eşlik eden tedavi, yayın ilişkisi) motorun doğru çıkardıklarının oranı.
- **Yanlış çıkarım oranı:** Motorun ileri sürdüğü öğelerden referansla çelişenlerin oranı (yanlış sonlanım bağlama, olay/kol sayısının örneklem sanılması, eksik değere değer atama dahil).
- **Kaynak eşleşme doğruluğu:** Her yapılandırılmış öğenin kaynak cümlesinin aynı PMID'nin özetinde birebir bulunma oranı; ayrıca her sayısal değerin o cümlede geçme oranı.
- **Yanlış nedensellik iddiası:** Randomize olmayan çalışmalara bağlı rapor satırlarında (alıntılar hariç) nedensel/üstünlük ifadesi sayısı + nedensel çıkarıma yanlışlıkla izin verilen çalışma sayısı.

### Genel sonuçlar

| Ölçüt | Değer |
|---|---|
| Eksiksiz çıkarım oranı | %100.0 (68/68) |
| Yanlış çıkarım oranı | %0.0 (0/68) |
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (92/92) |
| Kaynak eşleşme doğruluğu (sayısal değer) | %100.0 (67/67) |
| Yanlış nedensellik iddiası | 0 |
| Örneklem yerine olay/kol sayısı | 0 |
| Eşlik eden tedavinin müdahale sanılması | 0 |
| Bağımsız kanıt sayımı hatası | 0 |
| Soru çerçevesi seçimi | 10/10 |
| Sonlanım bağlama (doğru / adsız / yanlış) | 13 / 1 / 0 |

### Branşlara göre

| Branş | Yayın | Tasarımlar | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|---|
| Cerrahi | 2 | RCT | %100.0 (10/10) | %0.0 (0/10) |
| Endokrinoloji | 1 | Tanısal doğruluk | %100.0 (5/5) | %0.0 (0/5) |
| Enfeksiyon | 3 | RCT, Tanısal doğruluk | %100.0 (15/15) | %0.0 (0/15) |
| Kardiyoloji | 2 | Kohort, RCT | %100.0 (10/10) | %0.0 (0/10) |
| Nöroloji | 2 | Vaka-kontrol | %100.0 (6/6) | %0.0 (0/6) |
| Onkoloji | 2 | Meta-analiz | %100.0 (8/8) | %0.0 (0/8) |
| Pediatri | 2 | Olgu serisi | %100.0 (4/4) | %0.0 (0/4) |
| Radyoloji | 2 | Sistematik derleme | %100.0 (10/10) | %0.0 (0/10) |

### Araştırma türüne göre

| Tasarım | Yayın | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|
| Vaka-kontrol | 2 | %100.0 (6/6) | %0.0 (0/6) |
| Olgu serisi | 2 | %100.0 (4/4) | %0.0 (0/4) |
| Kohort | 1 | %100.0 (3/3) | %0.0 (0/3) |
| Tanısal doğruluk | 2 | %100.0 (8/8) | %0.0 (0/8) |
| Meta-analiz | 2 | %100.0 (8/8) | %0.0 (0/8) |
| RCT | 5 | %100.0 (29/29) | %0.0 (0/29) |
| Sistematik derleme | 2 | %100.0 (10/10) | %0.0 (0/10) |

### Çalışma ilişkileri (mükerrer kanıt kontrolü)

- Bağımsız birincil kanıt birimi: 12

### Rapor doğrulama durumu (branş başına tam Türkçe rapor)

| Branş | Durum | Alıntı kontrolü | Kümede olmayan PMID | RoB/GRADE derece iddiası |
|---|---|---|---|---|
| Kardiyoloji | Doğrulandı | 30/30 | 0 | 0 |
| Onkoloji | Doğrulandı | 29/29 | 0 | 0 |
| Nöroloji | Doğrulandı | 36/36 | 0 | 0 |
| Enfeksiyon | Doğrulandı | 49/49 | 0 | 0 |
| Endokrinoloji | Doğrulandı | 9/9 | 0 | 0 |
| Pediatri | Doğrulandı | 8/8 | 0 | 0 |
| Cerrahi | Doğrulandı | 42/42 | 0 | 0 |
| Radyoloji | Doğrulandı | 15/15 | 0 | 0 |

### Soru çerçevesi seçimi

| Branş | Soru | Beklenen | Motor |
|---|---|---|---|
| Nöroloji | Risk of Parkinson's disease in patients with bipolar disorder | etiology | etiology ✓ |
| Radyoloji | Accuracy of AI-assisted radiology for cancer detection | diagnosis | diagnosis ✓ |
| Enfeksiyon | Procalcitonin-guided antibiotic duration in sepsis | therapy | therapy ✓ |
| Pediatri | Incidence of gastrointestinal involvement in MIS-C in children | epidemiology | epidemiology ✓ |
| Cerrahi | Biological versus synthetic mesh for inguinal hernia repair recurrence | surgery | surgery ✓ |
| Onkoloji | Safety of adding immunotherapy to chemoradiotherapy in small cell lung cancer | safety | safety ✓ |
| Endokrinoloji | Mortality prognosis after hip fracture in elderly diabetic patients | prognosis | prognosis ✓ |
| Enfeksiyon | Cost of continuous versus intermittent beta-lactam infusion in the ICU | health_services | health_services ✓ |
| Onkoloji | Lung cancer screening with low-dose CT in heavy smokers | screening | screening ✓ |
| Endokrinoloji | Metabolik sendrom tanısında LAP indeksinin duyarlılığı | diagnosis | diagnosis ✓ |

### Eksik ve yanlış öğeler (çalışma bazında)

- **PMID 40996213:** BAĞLANMADI: 40996213 HR 0.6 [0.36, 1.14] sonlanım adı yok

### Test kategorileri

1. **Yazılım birim ve entegrasyon testleri:** `tests/test_evidence_model.py` (rapor doğrulama testleri dahil), `tests/test_question_framework.py` ve mevcut test paketi.
2. **Gerçek PubMed kaynak doğrulaması:** `tests/test_pubmed_source_verification.py` (kayıtlı PubMed kayıtlarının bütünlüğü; `RUN_LIVE_PUBMED=1` ile canlı NCBI karşılaştırması).
3. **Bağımsız klinik veri doğrulaması:** `tests/test_clinical_reference_validation.py` (bu raporun ölçütleri; eşik altına düşerse test başarısız olur).


## Ayrılmış küme 2, güncel çalıştırma ayrıntıları

### Kapsam ve yöntem

- **17 gerçek PubMed yayını**, **9 branş**: Cerrahi, Endokrinoloji, Enfeksiyon, Kadın Hastalıkları ve Doğum, Kardiyoloji, Nöroloji, Onkoloji, Pediatri, Radyoloji.
- Kayıtlar PubMed'den alındı (PMID, DOI, başlık, özet, yayın türü) ve `validation/` altındaki JSON dosyalarında değiştirilmeden saklandı.
- Referans tablo özetler elle okunarak, motor çıktısına bakılmadan yazıldı.
- **Sınırlılık:** Referans tabloyu bir yapay zekâ asistanı hazırladı. Bağımsız uzman hekim kontrolü henüz yapılmadı. Yalnızca özetler kullanıldı; tam metin okunmadı.

### Ölçüt tanımları

- **Eksiksiz çıkarım oranı:** Referansta bildirilen öğelerden (tasarım, örneklem, ana etki tahmini + GA, müdahale, karşılaştırıcı, eşlik eden tedavi, yayın ilişkisi) motorun doğru çıkardıklarının oranı.
- **Yanlış çıkarım oranı:** Motorun ileri sürdüğü öğelerden referansla çelişenlerin oranı (yanlış sonlanım bağlama, olay/kol sayısının örneklem sanılması, eksik değere değer atama dahil).
- **Kaynak eşleşme doğruluğu:** Her yapılandırılmış öğenin kaynak cümlesinin aynı PMID'nin özetinde birebir bulunma oranı; ayrıca her sayısal değerin o cümlede geçme oranı.
- **Yanlış nedensellik iddiası:** Randomize olmayan çalışmalara bağlı rapor satırlarında (alıntılar hariç) nedensel/üstünlük ifadesi sayısı + nedensel çıkarıma yanlışlıkla izin verilen çalışma sayısı.

### Genel sonuçlar

| Ölçüt | Değer |
|---|---|
| Eksiksiz çıkarım oranı | %93.9 (62/66) |
| Yanlış çıkarım oranı | %1.6 (1/63) |
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (87/87) |
| Kaynak eşleşme doğruluğu (sayısal değer) | %100.0 (63/63) |
| Yanlış nedensellik iddiası | 0 |
| Örneklem yerine olay/kol sayısı | 0 |
| Eşlik eden tedavinin müdahale sanılması | 0 |
| Bağımsız kanıt sayımı hatası | 0 |
| Soru çerçevesi seçimi | 8/8 |
| Sonlanım bağlama (doğru / adsız / yanlış) | 15 / 0 / 0 |

### Branşlara göre

| Branş | Yayın | Tasarımlar | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|---|
| Cerrahi | 2 | Vaka-kontrol | %100.0 (6/6) | %0.0 (0/6) |
| Endokrinoloji | 4 | Kohort, Meta-analiz, RCT | %100.0 (14/14) | %0.0 (0/14) |
| Enfeksiyon | 1 | Tanısal doğruluk | %100.0 (1/1) | %0.0 (0/1) |
| Kadın Hastalıkları ve Doğum | 1 | RCT | %80.0 (4/5) | %0.0 (0/4) |
| Kardiyoloji | 2 | Meta-analiz, RCT | %80.0 (8/10) | %0.0 (0/8) |
| Nöroloji | 1 | RCT | %100.0 (4/4) | %0.0 (0/4) |
| Onkoloji | 2 | Kohort | %100.0 (6/6) | %0.0 (0/6) |
| Pediatri | 2 | RCT | %90.9 (10/11) | %9.1 (1/11) |
| Radyoloji | 2 | Tanısal doğruluk | %100.0 (9/9) | %0.0 (0/9) |

### Araştırma türüne göre

| Tasarım | Yayın | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|
| Vaka-kontrol | 2 | %100.0 (6/6) | %0.0 (0/6) |
| Kohort | 4 | %100.0 (11/11) | %0.0 (0/11) |
| Tanısal doğruluk | 3 | %100.0 (10/10) | %0.0 (0/10) |
| Meta-analiz | 2 | %100.0 (8/8) | %0.0 (0/8) |
| RCT | 6 | %87.1 (27/31) | %3.6 (1/28) |

### Çalışma ilişkileri (mükerrer kanıt kontrolü)

- Bağımsız birincil kanıt birimi: 15

### Rapor doğrulama durumu (branş başına tam Türkçe rapor)

| Branş | Durum | Alıntı kontrolü | Kümede olmayan PMID | RoB/GRADE derece iddiası |
|---|---|---|---|---|
| Kardiyoloji | Doğrulandı | 33/33 | 0 | 0 |
| Onkoloji | Doğrulandı | 20/20 | 0 | 0 |
| Nöroloji | Doğrulandı | 11/11 | 0 | 0 |
| Enfeksiyon | Doğrulandı | 5/5 | 0 | 0 |
| Endokrinoloji | Doğrulandı | 44/44 | 0 | 0 |
| Pediatri | Doğrulandı | 36/36 | 0 | 0 |
| Cerrahi | Doğrulandı | 19/19 | 0 | 0 |
| Radyoloji | Doğrulandı | 24/24 | 0 | 0 |
| Kadın Hastalıkları ve Doğum | Doğrulandı | 10/10 | 0 | 0 |

### Soru çerçevesi seçimi

| Branş | Soru | Beklenen | Motor |
|---|---|---|---|
| Kardiyoloji | Duration of dual antiplatelet therapy after PCI in high bleeding risk patients | therapy | therapy ✓ |
| Onkoloji | Risk of colorectal cancer after Streptococcus bovis bacteraemia | etiology | etiology ✓ |
| Radyoloji | Sensitivity of dark-field chest radiography for pneumothorax | diagnosis | diagnosis ✓ |
| Pediatri | Azithromycin mass administration and infant mortality | therapy | therapy ✓ |
| Cerrahi | Carotid endarterectomy versus medical therapy for asymptomatic stenosis | surgery | surgery ✓ |
| Endokrinoloji | Prevalence of insulin resistance in irritable bowel syndrome | epidemiology | epidemiology ✓ |
| Enfeksiyon | Adverse events of SGLT2 inhibitors genital infections | safety | safety ✓ |
| Kadın Hastalıkları ve Doğum | Preterm doğumda hava kirliliği risk faktörü | etiology | etiology ✓ |

### Eksik ve yanlış öğeler (çalışma bazında)

- **PMID 41631724:** EKSİK: 41631724 müdahale '' (beklenen ['1-month', '3-month']); EKSİK: 41631724 karşılaştırıcı '' (beklenen ['3-month', '12-month'])
- **PMID 41092331:** YANLIŞ: 41092331 karşılaştırıcı 'control' (beklenen ['placebo'])
- **PMID 41354041:** EKSİK: 41354041 örneklem None (beklenen 8094)

### Test kategorileri

1. **Yazılım birim ve entegrasyon testleri:** `tests/test_evidence_model.py` (rapor doğrulama testleri dahil), `tests/test_question_framework.py` ve mevcut test paketi.
2. **Gerçek PubMed kaynak doğrulaması:** `tests/test_pubmed_source_verification.py` (kayıtlı PubMed kayıtlarının bütünlüğü; `RUN_LIVE_PUBMED=1` ile canlı NCBI karşılaştırması).
3. **Bağımsız klinik veri doğrulaması:** `tests/test_clinical_reference_validation.py` (bu raporun ölçütleri; eşik altına düşerse test başarısız olur).



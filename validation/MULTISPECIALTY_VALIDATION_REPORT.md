# Çok Branşlı Doğrulama Raporu

Oluşturulma: 2026-11-01 · Yazılım: `v1.5.0` · Kanıt veri modeli: `1.1.0`

Bu rapor `python validation/run_multispecialty_validation.py` ile üretilir; elle düzenlenmez.

## Özet

- Geliştirme kümesi motor ayarlanırken kullanıldı; sonuçları **iyimserdir**, doğruluk tahmini değildir.
- **Ayrılmış küme 1, 2 ve 3** için referans değerler motor bu kayıtlarda hiç çalıştırılmadan yazıldı; ilk çalıştırmalar
  `validation/holdout_first_run_results.json`, `validation/holdout2_first_run_results.json` ve
  `validation/holdout3_first_run_results.json` içinde donduruldu. Her küme, bir öncekinin ortaya çıkardığı hatalar düzeltildikten
  sonra kuruldu: düzeltmelerin genellenip genellenmediğini ölçer. Küme 3 için seçim kuralı (branş/tasarım başına sabit bir PubMed
  sorgusu, Haziran 2025 sonrası, sayısal sonuç bildiren ilk kayıt) referans dosyasının `_meta` alanındadır.
- **Gerçekçi beklenti, üç bağımsız ilk çalıştırmadır** (aşağıda kalın). Sonraki düzeltmeler bu kümeleri de görmüş olduğundan
  güncel sonuçları bağımsız değildir.

| Ölçüt | Geliştirme kümesi (ayarlı) | **Ayrılmış küme 1, ilk çalıştırma (bağımsız)** | **Ayrılmış küme 2, ilk çalıştırma (bağımsız)** | **Ayrılmış küme 3, ilk çalıştırma (bağımsız)** | Küme 1 / 2 / 3, düzeltme sonrası (bağımsız değil) |
|---|---|---|---|---|---|
| Eksiksiz çıkarım oranı | %98.7 (151/153) | **%77.9 (53/68)** | **%78.8 (52/66)** | **%74.3 (84/113)** | %100.0 (68/68) / %93.9 (62/66) / %98.2 (111/113) |
| Yanlış çıkarım oranı | %0.0 (0/151) | **%8.6 (5/58)** | **%11.9 (7/59)** | **%16.8 (17/101)** | %0.0 (0/68) / %1.6 (1/63) / %1.8 (2/113) |
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (213/213) | **%100.0 (62/62)** | **%100.0 (73/73)** | **%100.0 (115/115)** | %100.0 (97/97) / %100.0 (86/86) / %100.0 (118/118) |
| Kaynak eşleşme doğruluğu (sayısal değer) | %100.0 (154/154) | **%100.0 (52/52)** | **%100.0 (48/48)** | **%97.8 (90/92)** | %100.0 (67/67) / %100.0 (59/59) / %100.0 (85/85) |
| Yanlış nedensellik iddiası | 0 | **0** | **0** | **3** | 0 / 0 / 0 |
| Soru çerçevesi seçimi | 18/18 | **9/10** | **8/8** | **8/8** | 10/10 / 8/8 / 8/8 |

- Yayın sayısı: geliştirme 35, ayrılmış küme 1 16, ayrılmış küme 2 17, ayrılmış küme 3 17; toplam **85 gerçek PubMed yayını**.
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

### Ayrılmış küme 3: ilk çalıştırmada bulunan hatalar

- **PMID 42946676:** EKSİK: 42946676 örneklem None (beklenen 63)
- **PMID 42965030:** YANLIŞ: 42965030 tasarım rct (beklenen ['cohort']); BAĞLANMADI: 42965030 HR 0.35 [0.18, 0.67] sonlanım adı yok; BAĞLANMADI: 42965030 HR 0.43 [0.23, 0.81] sonlanım adı yok; BAĞLANMADI: 42965030 HR 0.47 [0.25, 0.9] sonlanım adı yok; EKSİK: 42965030 karşılaştırıcı '' (beklenen ['warfarin'])
- **PMID 42937536:** YANLIŞ: 42937536 örneklem 26722 (beklenen 21856); YANLIŞ BAĞLAMA: 42937536 HR 1.24 [1.02, 1.5] → 'osteoporotic vBMD in men'; YANLIŞ: 42937536 birincil çalışma yanlışlıkla 'secondary_analysis' sayıldı; BAĞIMSIZLIK: 42937536 bağımsız=False (beklenen True)
- **PMID 42965526:** EKSİK: 42965526 müdahale '' (beklenen ['ablative', 'LAT'])
- **PMID 42957617:** BAĞLANMADI: 42957617 AUC 0.73 None sonlanım adı yok; BAĞLANMADI: 42957617 AUC 0.75 None sonlanım adı yok; EKSİK: 42957617 müdahale '' (beklenen ['tau', 'GFAP'])
- **PMID 42963818:** EKSİK: 42963818 IRR 2.2 [1.2, 4.0]; EKSİK: 42963818 IRR 2.0 [1.1, 3.6]; EKSİK: 42963818 IRR 2.3 [1.1, 5.1]; EKSİK: 42963818 IRR 2.2 [1.1, 4.1]; EKSİK: 42963818 IRR 1.9 [1.1, 3.3]; YANLIŞ: 42963818 birincil çalışma yanlışlıkla 'secondary_analysis' sayıldı; BAĞIMSIZLIK: 42963818 bağımsız=False (beklenen True)
- **PMID 42945222:** BAĞLANMADI: 42945222 AUC 0.675 [0.544, 0.788] sonlanım adı yok; BAĞLANMADI: 42945222 specificity 76.5 [52.7, 90.4] sonlanım adı yok; BAĞLANMADI: 42945222 sensitivity 35.6 [23.2, 50.2] sonlanım adı yok; BAĞLANMADI: 42945222 sensitivity 100.0 [92.1, 100.0] sonlanım adı yok; BAĞLANMADI: 42945222 specificity 29.4 [13.3, 53.1] sonlanım adı yok; BAĞLANMADI: 42945222 sensitivity 68.9 [54.3, 80.5] sonlanım adı yok; BAĞLANMADI: 42945222 specificity 70.6 [46.9, 86.7] sonlanım adı yok; EKSİK: 42945222 müdahale '' (beklenen ['COTS'])
- **PMID 42959821:** YANLIŞ: 42959821 örneklem 106 (beklenen 117)
- **PMID 42966369:** EKSİK: 42966369 MD -3.23 [-3.51, -2.96]; YANLIŞ: 42966369 müdahale 'with self-directed exercise in patients' (beklenen ['Schroth', 'PSSE', 'supervised']); YANLIŞ: 42966369 karşılaştırıcı 'AIS undergoing brace treatment' (beklenen ['self-directed']); EKSİK: 42966369 eşlik eden tedavi '' (beklenen ['brac'])
- **PMID 42963493:** YANLIŞ BAĞLAMA: 42963493 OR 0.49 [0.25, 0.99] → 'all-cause mortality'; EKSİK: 42963493 OR 0.87 [0.59, 1.28]; EKSİK: 42963493 OR 0.67 [0.35, 1.27]; EKSİK: 42963493 müdahale '' (beklenen ['probiotic', 'ProPrems'])
- **PMID 42944929:** YANLIŞ: 42944929 müdahale 'open' (beklenen ['laparoscopic']); YANLIŞ: 42944929 karşılaştırıcı 'laparoscopic gastrectomy with standard D2 lymphadenectomy' (beklenen ['open'])
- **PMID 42965524:** EKSİK: 42965524 örneklem None (beklenen 46); BAĞLANMADI: 42965524 specificity 90.1 None sonlanım adı yok; EKSİK: 42965524 accuracy 89.4 None; BAĞLANMADI: 42965524 sensitivity 88.7 None sonlanım adı yok; EKSİK: 42965524 müdahale '' (beklenen ['CMRA', 'MR angiography', 'magnetic resonance']); EKSİK: 42965524 karşılaştırıcı '' (beklenen ['CCTA', 'computed tomography'])
- **PMID 42961418:** EKSİK: 42961418 müdahale '' (beklenen ['risk-reducing mastectomy', 'RRM']); EKSİK: 42961418 karşılaştırıcı '' (beklenen ['MRI', 'mammography'])
- **PMID 42921063:** EKSİK: 42921063 OR 3.01 [1.78, 5.09]; BAĞLANMADI: 42921063 OR 2.79 [1.33, 5.88] sonlanım adı yok; YANLIŞ BAĞLAMA: 42921063 OR 3.72 [1.33, 10.39] → 'diabetes'; YANLIŞ BAĞLAMA: 42921063 OR 1.94 [1.16, 3.24] → 'diabetes'; YANLIŞ BAĞLAMA: 42921063 OR 2.14 [1.13, 4.06] → 'diabetes'; BAĞLANMADI: 42921063 OR 2.79 [1.72, 4.54] sonlanım adı yok; BAĞLANMADI: 42921063 OR 2.42 [1.06, 5.52] sonlanım adı yok; BAĞLANMADI: 42921063 OR 2.21 [1.38, 3.56] sonlanım adı yok; BAĞLANMADI: 42921063 OR 16.6 [2.16, 127.76] sonlanım adı yok; BAĞLANMADI: 42921063 OR 2.78 [1.35, 5.69] sonlanım adı yok; YANLIŞ BAĞLAMA: 42921063 OR 1.94 [1.19, 3.15] → 'depression'; YANLIŞ BAĞLAMA: 42921063 OR 4.11 [2.47, 6.85] → 'depression'; YANLIŞ BAĞLAMA: 42921063 OR 5.68 [3.34, 9.64] → 'giving birth to a macrosomia baby'

#### Ayrılmış küme 3: dondurmadan sonra fark edilen referans hataları

Dondurulmuş dosya değiştirilmedi. Aşağıdaki öğelerde hatalı olan referanstır, motor değil:

- **PMID 42937536:** Referansta 'birincil' yazıldı; özet kendini NLST'nin ikincil analizi olarak tanımlıyor. Motorun 'ikincil analiz' kararı doğrudur. İlgili iki öğe (yayın rolü, bağımsızlık) motor hatası değildir.
- **PMID 42963818:** Referansta 'birincil' yazıldı; özet kendini DOT Selfie RCT verisinin ikincil analizi olarak tanımlıyor. Motorun 'ikincil analiz' kararı doğrudur. İlgili iki öğe motor hatası değildir.

## Dış referans: PR #64'ün sekiz PubMed vakası

Referans tablosu (`validation/reference_external_pr64.json`) PR #64'te başka bir yapay zekâ ajanı tarafından, bu motor
bu kayıtları görmeden yazıldı ve buraya değiştirilmeden kopyalandı. Sekiz branşın her birinden bir yayın içerir.
Puanlama `python validation/run_external_reference_check.py` ile yapılır ve yalnızca sayısal alanları kapsar
(tasarım, toplam n, kol n, etki tahmini, GA, p, olay sayısı); niteliksel alanlar ayrıca listelenir.
Ölçüt tanımları yukarıdaki kümelerden farklıdır; oranlar doğrudan karşılaştırılamaz.

| Ölçüt | **İlk çalıştırma (bağımsız)** | Düzeltme sonrası (bağımsız değil) |
|---|---|---|
| Doğru alan | **%67.4 (31/46)** | %100.0 (43/43) |
| Yanlış alan | **%8.7 (4/46)** | %0.0 (0/43) |
| Eksik alan | **11/46** | 0/43 |
| Eksiksiz makale | **3/8** | 8/8 |

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
| Eksiksiz çıkarım oranı | %98.7 (151/153) |
| Yanlış çıkarım oranı | %0.0 (0/151) |
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (213/213) |
| Kaynak eşleşme doğruluğu (sayısal değer) | %100.0 (154/154) |
| Yanlış nedensellik iddiası | 0 |
| Örneklem yerine olay/kol sayısı | 0 |
| Eşlik eden tedavinin müdahale sanılması | 0 |
| Bağımsız kanıt sayımı hatası | 0 |
| Soru çerçevesi seçimi | 18/18 |
| Sonlanım bağlama (doğru / adsız / yanlış) | 31 / 0 / 0 |

### Branşlara göre

| Branş | Yayın | Tasarımlar | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|---|
| Cerrahi | 4 | Kohort, Mektup (özet yok), RCT | %93.3 (14/15) | %0.0 (0/14) |
| Endokrinoloji | 4 | Kohort, Meta-analiz, RCT | %100.0 (16/16) | %0.0 (0/16) |
| Enfeksiyon | 5 | Olgu serisi, RCT, Tanısal doğruluk | %100.0 (16/16) | %0.0 (0/16) |
| Kardiyoloji | 5 | Meta-analiz, RCT, Sistematik derleme | %96.7 (29/30) | %0.0 (0/29) |
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
| Mektup (özet yok) | 1 | %66.7 (2/3) | %0.0 (0/2) |
| Meta-analiz | 6 | %100.0 (32/32) | %0.0 (0/32) |
| Protokol (sonuç yok) | 1 | %100.0 (1/1) | %0.0 (0/1) |
| RCT | 10 | %98.5 (65/66) | %0.0 (0/65) |
| Sistematik derleme | 1 | %100.0 (5/5) | %0.0 (0/5) |

### Çalışma ilişkileri (mükerrer kanıt kontrolü)

- Bağımsız birincil kanıt birimi: 24
- Aynı çalışma kümesi: PMID 37272513, 39288781
- PMID 36041474 (kanıt sentezi), PMID 34449189 ile aynı katılımcıları içeriyor; bu katılımcılar bağımsız kanıt toplamına iki kez eklenmedi.
- PMID 36041474 (kanıt sentezi), PMID 36129693 ile aynı katılımcıları içeriyor; bu katılımcılar bağımsız kanıt toplamına iki kez eklenmedi.

### Rapor doğrulama durumu (branş başına tam Türkçe rapor)

| Branş | Durum | Alıntı kontrolü | Kümede olmayan PMID | RoB/GRADE derece iddiası |
|---|---|---|---|---|
| Kardiyoloji | Doğrulandı | 83/83 | 0 | 0 |
| Onkoloji | Doğrulandı | 79/79 | 0 | 0 |
| Nöroloji | Doğrulandı | 68/68 | 0 | 0 |
| Enfeksiyon | Doğrulandı | 49/49 | 0 | 0 |
| Endokrinoloji | Doğrulandı | 57/57 | 0 | 0 |
| Pediatri | Doğrulandı | 57/57 | 0 | 0 |
| Cerrahi | Doğrulandı | 48/48 | 0 | 0 |
| Radyoloji | Doğrulandı | 48/48 | 0 | 0 |

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

- **PMID 36129693:** EKSİK: 36129693 ana çalışma bağlantısı [] (beklenen 34449189)
- **PMID 34694761:** EKSİK: 34694761 ana çalışma bağlantısı [] (beklenen 33017106)

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
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (97/97) |
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
| Onkoloji | Doğrulandı | 31/31 | 0 | 0 |
| Nöroloji | Doğrulandı | 32/32 | 0 | 0 |
| Enfeksiyon | Doğrulandı | 57/57 | 0 | 0 |
| Endokrinoloji | Doğrulandı | 11/11 | 0 | 0 |
| Pediatri | Doğrulandı | 10/10 | 0 | 0 |
| Cerrahi | Doğrulandı | 42/42 | 0 | 0 |
| Radyoloji | Doğrulandı | 23/23 | 0 | 0 |

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
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (86/86) |
| Kaynak eşleşme doğruluğu (sayısal değer) | %100.0 (59/59) |
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
| Onkoloji | Doğrulandı | 26/26 | 0 | 0 |
| Nöroloji | Doğrulandı | 12/12 | 0 | 0 |
| Enfeksiyon | Doğrulandı | 7/7 | 0 | 0 |
| Endokrinoloji | Doğrulandı | 43/43 | 0 | 0 |
| Pediatri | Doğrulandı | 36/36 | 0 | 0 |
| Cerrahi | Doğrulandı | 22/22 | 0 | 0 |
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


## Ayrılmış küme 3, güncel çalıştırma ayrıntıları

### Kapsam ve yöntem

- **17 gerçek PubMed yayını**, **8 branş**: Cerrahi, Endokrinoloji, Enfeksiyon, Kardiyoloji, Nöroloji, Onkoloji, Pediatri, Radyoloji.
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
| Eksiksiz çıkarım oranı | %98.2 (111/113) |
| Yanlış çıkarım oranı | %1.8 (2/113) |
| Kaynak eşleşme doğruluğu (cümle) | %100.0 (118/118) |
| Kaynak eşleşme doğruluğu (sayısal değer) | %100.0 (85/85) |
| Yanlış nedensellik iddiası | 0 |
| Örneklem yerine olay/kol sayısı | 0 |
| Eşlik eden tedavinin müdahale sanılması | 0 |
| Bağımsız kanıt sayımı hatası | 2 |
| Soru çerçevesi seçimi | 8/8 |
| Sonlanım bağlama (doğru / adsız / yanlış) | 58 / 0 / 0 |

### Branşlara göre

| Branş | Yayın | Tasarımlar | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|---|
| Cerrahi | 3 | Olgu serisi, RCT, Vaka-kontrol | %100.0 (9/9) | %0.0 (0/9) |
| Endokrinoloji | 2 | RCT, Vaka-kontrol | %100.0 (24/24) | %0.0 (0/24) |
| Enfeksiyon | 2 | Kohort, Tanısal doğruluk | %100.0 (17/17) | %5.6 (1/18) |
| Kardiyoloji | 2 | Kohort, RCT | %90.9 (10/11) | %0.0 (0/10) |
| Nöroloji | 2 | RCT, Tanısal doğruluk | %90.9 (10/11) | %0.0 (0/10) |
| Onkoloji | 2 | Meta-analiz | %100.0 (16/16) | %0.0 (0/16) |
| Pediatri | 2 | Kohort, RCT | %100.0 (13/13) | %0.0 (0/13) |
| Radyoloji | 2 | Kohort, Tanısal doğruluk | %100.0 (12/12) | %7.7 (1/13) |

### Araştırma türüne göre

| Tasarım | Yayın | Eksiksiz çıkarım | Yanlış çıkarım |
|---|---|---|---|
| Vaka-kontrol | 2 | %100.0 (23/23) | %0.0 (0/23) |
| Olgu serisi | 1 | %100.0 (2/2) | %0.0 (0/2) |
| Kohort | 4 | %100.0 (25/25) | %7.4 (2/27) |
| Tanısal doğruluk | 3 | %95.8 (23/24) | %0.0 (0/23) |
| Meta-analiz | 2 | %100.0 (16/16) | %0.0 (0/16) |
| RCT | 5 | %95.7 (22/23) | %0.0 (0/22) |

### Çalışma ilişkileri (mükerrer kanıt kontrolü)

- Bağımsız birincil kanıt birimi: 13

### Rapor doğrulama durumu (branş başına tam Türkçe rapor)

| Branş | Durum | Alıntı kontrolü | Kümede olmayan PMID | RoB/GRADE derece iddiası |
|---|---|---|---|---|
| Kardiyoloji | Doğrulandı | 26/26 | 0 | 0 |
| Radyoloji | Doğrulandı | 35/35 | 0 | 0 |
| Onkoloji | Doğrulandı | 27/27 | 0 | 0 |
| Nöroloji | Doğrulandı | 34/34 | 0 | 0 |
| Enfeksiyon | Doğrulandı | 35/35 | 0 | 0 |
| Endokrinoloji | Doğrulandı | 58/58 | 0 | 0 |
| Cerrahi | Doğrulandı | 41/41 | 0 | 0 |
| Pediatri | Doğrulandı | 26/26 | 0 | 0 |

### Soru çerçevesi seçimi

| Branş | Soru | Beklenen | Motor |
|---|---|---|---|
| Kardiyoloji | Do direct oral anticoagulants reduce stroke compared with warfarin in atrial fibrillation? | therapy | therapy ✓ |
| Onkoloji | Does local ablative treatment improve survival in oligoprogressive non-small-cell lung cancer during immunotherapy? | therapy | therapy ✓ |
| Radyoloji | Diagnostic accuracy of 5.0 T coronary MR angiography for coronary stenosis | diagnosis | diagnosis ✓ |
| Nöroloji | Plazma p-tau'nun amiloid patolojisi için tanısal doğruluğu nedir? | diagnosis | diagnosis ✓ |
| Enfeksiyon | Risk factors for missed video directly observed therapy sessions in tuberculosis | etiology | etiology ✓ |
| Endokrinoloji | Gestasyonel diyabet için gebelik öncesi risk faktörleri nelerdir? | etiology | etiology ✓ |
| Pediatri | Çok suşlu probiyotikler aşırı prematüre bebeklerde nekrotizan enterokoliti azaltır mı? | therapy | therapy ✓ |
| Cerrahi | Is laparoscopic gastrectomy as effective as open gastrectomy for gastric cancer? | surgery | surgery ✓ |

### Eksik ve yanlış öğeler (çalışma bazında)

- **PMID 42946676:** EKSİK: 42946676 örneklem None (beklenen 63)
- **PMID 42937536:** YANLIŞ: 42937536 birincil çalışma yanlışlıkla 'secondary_analysis' sayıldı; BAĞIMSIZLIK: 42937536 bağımsız=False (beklenen True)
- **PMID 42957617:** EKSİK: 42957617 müdahale '' (beklenen ['tau', 'GFAP'])
- **PMID 42963818:** YANLIŞ: 42963818 birincil çalışma yanlışlıkla 'secondary_analysis' sayıldı; BAĞIMSIZLIK: 42963818 bağımsız=False (beklenen True)

### Test kategorileri

1. **Yazılım birim ve entegrasyon testleri:** `tests/test_evidence_model.py` (rapor doğrulama testleri dahil), `tests/test_question_framework.py` ve mevcut test paketi.
2. **Gerçek PubMed kaynak doğrulaması:** `tests/test_pubmed_source_verification.py` (kayıtlı PubMed kayıtlarının bütünlüğü; `RUN_LIVE_PUBMED=1` ile canlı NCBI karşılaştırması).
3. **Bağımsız klinik veri doğrulaması:** `tests/test_clinical_reference_validation.py` (bu raporun ölçütleri; eşik altına düşerse test başarısız olur).



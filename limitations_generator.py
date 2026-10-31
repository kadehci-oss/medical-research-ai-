"""
limitations_generator.py — Dinamik sınırlılık bölümü.
"""
from typing import List, Dict, Any

def generate_limitations(records: List[Dict],
                         search_query: str = "",
                         total_hits: int = 0) -> str:
    lines = ["## Sınırlılıklar", ""]
    n = len(records)

    lines.append("- Bu sentez **%d** kayıt üzerinden üretildi; PubMed'deki toplam "
                 "eşleşme **%d** idi. Sistematik bir inceleme değildir, dahil "
                 "etme/hariç tutma protokolü uygulanmamıştır." % (n, total_hits))

    designs = set()
    for r in records:
        d = r.get("study_design", "unknown")
        if isinstance(d, dict):
            designs.add(d.get("design") or d.get("design_key") or "unknown")
        else:
            designs.add(str(d or "unknown"))

    if len(designs) > 1:
        lines.append("- Çalışma tasarımları heterojen: %s. Birleştirilmiş etki "
                     "büyüklüklerinin yorumu sınırlıdır." % ", ".join(sorted(designs)))

    full_text = sum(1 for r in records if r.get("full_text"))
    if full_text < n:
        lines.append("- Yalnızca **%d/%d** kayıt için tam metin doğrulaması yapıldı; "
                     "geri kalanlar özet düzeyindedir." % (full_text, n))

    high_rob = sum(1 for r in records
                   if r.get("rob2") and r["rob2"].get("overall") == "High")
    if high_rob:
        lines.append("- **%d** çalışma RoB 2 açısından 'yüksek risk' olarak "
                     "değerlendirildi; sonuçlar temkinli okunmalıdır." % high_rob)

    if n < 10:
        lines.append("- Kayıt sayısı az olduğu için yayın yanlılığı "
                     "(funnel plot / Egger) değerlendirilememiştir.")

    if not any("turk" in str(r).lower() for r in records):
        lines.append("- Türkiye popülasyonuna özgü çalışma tespit edilmemiştir; "
                     "genellenebilirlik sınırlı olabilir.")

    lines.append("- Arama tarihi raporda belirtilmiştir; sonraki kanıtlar bu sentezde "
                 "yer almaz.")
    lines.append("")
    lines.append("> **Önemli:** Bu rapor tıbbi tavsiye değildir. Klinik karar, hastanın "
                 "bireysel özellikleri ve güncel kılavuzlar ışığında hekim tarafından "
                 "verilmelidir.")
    return "\n".join(lines)

"""
limitations_generator.py — Dinamik sınırlılık bölümü.
"""
from typing import List, Dict, Any

def generate_limitations(records: List[Dict],
                         search_query: str = "",
                         total_hits: int = 0) -> str:
    """Limitations that follow from the search itself.

    Geography, RoB 2 ratings, and funnel-plot results are not stated unless the
    records actually carry that assessment. Absence of the letters "turk" is
    not evidence about the studied population.
    """
    lines = ["## Sınırlılıklar", ""]
    n = len(records)
    hits = total_hits if total_hits else n

    lines.append(
        "- Bu sentez **%d** PubMed kaydı üzerinden üretildi; aynı aramada bildirilen "
        "toplam eşleşme **%d** idi. Sistematik derleme değildir; kayıtlar bir dahil "
        "etme/hariç tutma protokolüyle elenmemiştir." % (n, hits)
    )
    lines.append(
        "- Tam metin değerlendirmesi yapılmadı. Sayılar, tasarım ve sınırlılık "
        "ifadeleri yalnızca özete dayanır."
    )

    designs = set()
    for record in records:
        design = record.get("study_design_info") or record.get("study_design") or ""
        if isinstance(design, dict):
            label = design.get("design") or design.get("design_key") or ""
        else:
            label = str(design or "")
        if label and label not in {"unknown", "-"}:
            designs.add(label)

    if len(designs) > 1:
        lines.append(
            "- Bu kayıt kümesinde atanan çalışma tasarımı etiketleri heterojendir: %s. "
            "Bu etiketler bir GRADE başlangıç düzeyi değildir."
            % ", ".join(sorted(designs))
        )

    lines.append(
        "- Arama tarihi raporda belirtilmiştir; sonraki yayınlar bu sentezde yer almaz."
    )
    lines.append("")
    lines.append(
        "> **Önemli:** Bu rapor tıbbi tavsiye değildir. Klinik karar, hastanın "
        "bireysel özellikleri ve güncel kılavuzlar ışığında hekim tarafından "
        "verilmelidir. Uzman hekim değerlendirmesi yapılmamıştır."
    )
    return "\n".join(lines)

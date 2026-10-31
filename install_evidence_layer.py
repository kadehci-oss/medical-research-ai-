# Lütfen bu betiği repo kök dizininde `install_evidence_layer.py` adıyla oluştur ve çalıştır.
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f".backup_{STAMP}"
MARKER = "# [EVIDENCE_LAYER]"

FILES = {}

FILES["effect_size_extractor.py"] = r'''"""
effect_size_extractor.py — HR, OR, RR, MD, SMD, CI, p, n çıkarımı.
"""
import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

EFFECT_PATTERNS = {
    "HR": r"(?:HR|hazard\s*ratio)[^\d]{0,40}?(\d+\.?\d*)",
    "OR": r"(?:OR|odds\s*ratio)[^\d]{0,40}?(\d+\.?\d*)",
    "RR": r"(?:RR|risk\s*ratio|relative\s*risk)[^\d]{0,40}?(\d+\.?\d*)",
    "MD": r"(?:MD|mean\s*difference)[^\d]{0,40}?(-?\d+\.?\d*)",
    "SMD": r"(?:SMD|standardized\s*mean\s*difference)[^\d]{0,40}?(-?\d+\.?\d*)",
}
CI_PATTERN = r"(?:CI|confidence\s*interval)[^\d\-]{0,10}[\[\(]?\s*(-?\d+\.?\d*)\s*[-–,to]+\s*(-?\d+\.?\d*)"
P_PATTERN = r"p\s*[=<>]\s*(0?\.\d+|\d+\.?\d*e?-?\d*)"
N_PATTERN = r"(?:n\s*=\s*|total of\s+|included\s+)(\d{2,6})"

@dataclass
class EffectSize:
    type: str
    value: float
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    p_value: Optional[str] = None
    n: Optional[int] = None
    source_sentence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def _sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text or "")
    return [p.strip() for p in re.split(r"(?<=[\.\!\?])\s+(?=[A-Z])", text) if p.strip()]

def extract_effect_sizes(text: str) -> List[EffectSize]:
    results: List[EffectSize] = []
    for sent in _sentences(text):
        low = sent.lower()
        for etype, pat in EFFECT_PATTERNS.items():
            m = re.search(pat, low, flags=re.IGNORECASE)
            if not m:
                continue
            try:
                value = float(m.group(1))
            except ValueError:
                continue
            ci = re.search(CI_PATTERN, low, flags=re.IGNORECASE)
            p = re.search(P_PATTERN, low, flags=re.IGNORECASE)
            n = re.search(N_PATTERN, low, flags=re.IGNORECASE)
            results.append(EffectSize(
                type=etype, value=value,
                ci_low=float(ci.group(1)) if ci else None,
                ci_high=float(ci.group(2)) if ci else None,
                p_value=p.group(1) if p else None,
                n=int(n.group(1)) if n else None,
                source_sentence=sent[:300],
            ))
    return results

def summarize_effects(effects: List[EffectSize]) -> Dict[str, Any]:
    if not effects:
        return {"primary": None, "all": []}
    counts: Dict[str, int] = {}
    for e in effects:
        counts[e.type] = counts.get(e.type, 0) + 1
    primary_type = max(counts, key=counts.get)
    primary = next(e for e in effects if e.type == primary_type)
    return {"primary": primary.to_dict(), "all": [e.to_dict() for e in effects]}
'''

FILES["rob2_assessor.py"] = r'''"""
rob2_assessor.py — RoB 2 sinyal değerlendirmesi (abstract-based).
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, List
import re

@dataclass
class RoB2Result:
    d1_randomization: str
    d2_deviations: str
    d3_missing_data: str
    d4_measurement: str
    d5_reporting: str
    overall: str
    signals: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def assess_rob2(abstract: str, full_text: str = "") -> RoB2Result:
    text = ((abstract or "") + " " + (full_text or "")).lower()
    signals: List[str] = []

    if re.search(r"randomi[sz]ed|randomly assigned", text):
        d1 = "Low"
    elif "not randomized" in text or "observational" in text:
        d1 = "High"; signals.append("Randomizasyon bildirilmemiş")
    else:
        d1 = "Some concerns"; signals.append("Randomizasyon yöntemi belirsiz")

    d2 = "Low" if ("intention-to-treat" in text or " itt " in text) else "Some concerns"
    if d2 != "Low":
        signals.append("ITT analizi bildirilmemiş")

    if re.search(r"lost to follow[- ]?up|dropout", text) and re.search(r"\d+%", text):
        d3 = "Some concerns"; signals.append("Kayıp veri oranı bildirilmiş")
    else:
        d3 = "Low"

    d4 = "Low" if ("blinded" in text or "double-blind" in text) else "Some concerns"
    if d4 != "Low":
        signals.append("Körleme bildirilmemiş")

    d5 = "Low" if ("registered" in text or "clinicaltrials.gov" in text) else "Some concerns"
    if d5 != "Low":
        signals.append("Protokol kaydı bulunamadı")

    levels = [d1, d2, d3, d4, d5]
    if "High" in levels:
        overall = "High"
    elif levels.count("Some concerns") >= 2:
        overall = "Some concerns"
    else:
        overall = "Low"

    return RoB2Result(d1, d2, d3, d4, d5, overall, signals)
'''

FILES["grade_assessor.py"] = r'''"""
grade_assessor.py — GRADE benzeri kanıt gücü değerlendirmesi.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

@dataclass
class GradeResult:
    starting: str
    final: str
    downgrades: List[str]
    upgrades: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def assess_grade(study_design: Any,
                 rob2_overall: str = "Low",
                 heterogeneity_i2: float = 0.0,
                 imprecision: bool = False,
                 indirectness: bool = False,
                 publication_bias_suspected: bool = False) -> GradeResult:
    if isinstance(study_design, dict):
        design = (study_design.get("design_key") or study_design.get("design") or "").lower()
    else:
        design = (study_design or "").lower()

    if "rct" in design or "randomized" in design:
        starting = "High"
    elif "cohort" in design or "case-control" in design or "cross-sectional" in design:
        starting = "Low"
    else:
        starting = "Very low"

    score = {"High": 4, "Moderate": 3, "Low": 2, "Very low": 1}[starting]
    downgrades, upgrades = [], []

    if rob2_overall == "High":
        score -= 1; downgrades.append("Ciddi yanlılık riski (RoB 2 High)")
    elif rob2_overall == "Some concerns":
        score -= 0.5; downgrades.append("Bazı endişeler (RoB 2)")

    if heterogeneity_i2 >= 75:
        score -= 1; downgrades.append("Yüksek heterojenlik (I2=%s)" % heterogeneity_i2)
    elif heterogeneity_i2 >= 50:
        score -= 0.5; downgrades.append("Orta heterojenlik (I2=%s)" % heterogeneity_i2)

    if indirectness:
        score -= 1; downgrades.append("Dolaylı kanıt")
    if imprecision:
        score -= 1; downgrades.append("Kesinlik sorunu")
    if publication_bias_suspected:
        score -= 1; downgrades.append("Yayın yanlılığı şüphesi")

    if starting in ("Low", "Very low"):
        if "large effect" in design:
            score += 1; upgrades.append("Büyük etki büyüklüğü")
        if "dose-response" in design:
            score += 1; upgrades.append("Doz-yanıt ilişkisi")

    score = max(1, min(4, score))
    final = {4: "High", 3: "Moderate", 2: "Low", 1: "Very low"}[int(round(score))]
    return GradeResult(starting, final, downgrades, upgrades)
'''

FILES["limitations_generator.py"] = r'''"""
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
'''

FILES["tests/test_effect_size_extractor.py"] = r'''from effect_size_extractor import extract_effect_sizes, summarize_effects

SAMPLE = ("In this randomized trial of 452 patients, the hazard ratio for "
          "progression was 0.62 (95% CI 0.48-0.80; p=0.001). "
          "Mean difference in quality of life was 4.3 (95% CI 1.2-7.4).")

def test_extracts_hr_and_ci():
    effects = extract_effect_sizes(SAMPLE)
    assert any(e.type == "HR" for e in effects)
    hr = next(e for e in effects if e.type == "HR")
    assert hr.value == 0.62
    assert hr.ci_low == 0.48
    assert hr.ci_high == 0.80

def test_extracts_md():
    assert any(e.type == "MD" for e in extract_effect_sizes(SAMPLE))

def test_summary_primary():
    s = summarize_effects(extract_effect_sizes(SAMPLE))
    assert s["primary"] is not None

def test_empty_input():
    assert extract_effect_sizes("") == []
    assert summarize_effects([])["primary"] is None
'''

FILES["tests/test_grade_rob2.py"] = r'''from rob2_assessor import assess_rob2
from grade_assessor import assess_grade

RCT_GOOD = ("Randomized, double-blind, intention-to-treat trial. Registered at "
            "ClinicalTrials.gov. 320 patients. HR 0.70 (95% CI 0.55-0.89).")
OBS_BAD = "Observational cohort study. No blinding, no registration mentioned."

def test_rob2_rct():
    r = assess_rob2(RCT_GOOD)
    assert r.overall in ("Low", "Some concerns")

def test_rob2_observational():
    r = assess_rob2(OBS_BAD)
    assert r.overall in ("Some concerns", "High")

def test_grade_rct():
    g = assess_grade("rct", rob2_overall="Low")
    assert g.starting == "High"
    assert g.final in ("High", "Moderate")

def test_grade_cohort_downgrades():
    g = assess_grade("cohort", rob2_overall="High",
                     heterogeneity_i2=80, imprecision=True)
    assert g.final in ("Low", "Very low")
    assert len(g.downgrades) >= 2
'''

def backup(path: Path) -> None:
    if path.exists():
        BACKUP.mkdir(exist_ok=True)
        shutil.copy2(path, BACKUP / path.name)

def ensure_import(path: Path, import_line: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if import_line in text:
        return False
    lines = text.split("\n")
    last = -1
    for i, ln in enumerate(lines):
        if re.match(r"^(import |from )", ln):
            last = i
    insert_at = last + 1 if last >= 0 else 0
    lines.insert(insert_at, import_line)
    lines.insert(insert_at + 1, MARKER + " auto-import")
    path.write_text("\n".join(lines), encoding="utf-8")
    return True

def ensure_function(path: Path, func_name: str, func_code: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if f"def {func_name}(" in text:
        return False
    path.write_text(text.rstrip() + "\n\n\n" + MARKER + " auto-function\n" + func_code + "\n",
                    encoding="utf-8")
    return True

def rename_function(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    pat = re.compile(rf"^def {re.escape(old)}\(", re.M)
    if not pat.search(text) or f"def {new}(" in text:
        return False
    path.write_text(pat.sub(f"def {new}(", text), encoding="utf-8")
    return True

ENRICH_CODE = '''def enrich_record(rec: dict) -> dict:
    """RoB 2 + GRADE + etki büyüklüğü ile bir kaydı zenginleştirir."""
    abstract = rec.get("abstract", "") or ""
    design = rec.get("study_design", "unknown") or "unknown"
    design_str = (
        design.get("design_key") or design.get("design") or ""
        if isinstance(design, dict)
        else str(design)
    )

    rec["effect_summary"] = summarize_effects(extract_effect_sizes(abstract))

    if "rct" in design_str.lower() or "randomized" in abstract.lower():
        rob = assess_rob2(abstract)
        rec["rob2"] = rob.to_dict()
        rob_overall = rob.overall
    else:
        rec["rob2"] = None
        rob_overall = "Low"

    es = rec["effect_summary"].get("primary") or {}
    ci_width = None
    if es.get("ci_low") is not None and es.get("ci_high") is not None:
        ci_width = es["ci_high"] - es["ci_low"]

    rec["grade"] = assess_grade(
        study_design=design_str,
        rob2_overall=rob_overall,
        heterogeneity_i2=rec.get("i2", 0.0) or 0.0,
        imprecision=bool(ci_width and ci_width > 2),
    ).to_dict()

    return rec
'''

TABLE_CODE = '''def build_evidence_table(records):
    """GRADE ve RoB 2 sütunlu kanıt tablosu."""
    header = (
        "| PMID | Tasarım | Birincil Etki (95% CI) | n | GRADE | RoB 2 |\\n"
        "|------|---------|------------------------|---|-------|-------|\\n"
    )
    rows = []
    for r in records:
        es = (r.get("effect_summary") or {}).get("primary") or {}
        if es.get("ci_low") is not None and es.get("ci_high") is not None:
            ci = "(%s-%s)" % (round(es["ci_low"], 2), round(es["ci_high"], 2))
        else:
            ci = "-"
        grade = (r.get("grade") or {}).get("final", "-")
        rob = (r.get("rob2") or {}).get("overall", "N/A")
        des = r.get("study_design", "-")
        if isinstance(des, dict):
            des = des.get("design", "-")
        rows.append(
            "| %s | %s | %s %s %s | %s | %s | %s |" % (
                r.get("pmid", "-"), des,
                es.get("type", "-"), es.get("value", "-"), ci,
                es.get("n", "-"), grade, rob
            )
        )
    return header + "\\n".join(rows)
'''

LIMIT_CODE = '''def augment_report_with_limitations(report_text: str, records: list,
                                   search_query: str = "", total_hits: int = 0) -> str:
    """Mevcut rapor metnine dinamik sınırlılık bölümünü ekler."""
    if "## Sınırlılıklar" in report_text:
        return report_text
    return report_text.rstrip() + "\\n\\n" + generate_limitations(
        records, search_query, total_hits
    )
'''

def main() -> int:
    created, patched, todos = [], [], []

    for name, content in FILES.items():
        p = ROOT / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            continue
        p.write_text(content, encoding="utf-8")
        created.append(name)

    eng = ROOT / "universal_evidence_engine.py"
    if not eng.exists():
        todos.append(f"{eng.name} bulunamadı — kanıt motoru dosyasının adını kontrol et")
    else:
        backup(eng)
        ensure_import(eng, "from effect_size_extractor import extract_effect_sizes, summarize_effects")
        ensure_import(eng, "from rob2_assessor import assess_rob2")
        ensure_import(eng, "from grade_assessor import assess_grade")
        if ensure_function(eng, "enrich_record", ENRICH_CODE):
            patched.append(f"{eng.name}: enrich_record() eklendi")
        todos.append(
            f"TODO ({eng.name}): kayıt döngüsünde her record hazırlandıktan hemen "
            f"sonra `record = enrich_record(record)` satırını ekle."
        )

    rep = ROOT / "report_generator.py"
    if not rep.exists():
        todos.append(f"{rep.name} bulunamadı — rapor üretici dosya adını kontrol et")
    else:
        backup(rep)
        ensure_import(rep, "from limitations_generator import generate_limitations")
        if rename_function(rep, "build_evidence_table", "_legacy_build_evidence_table"):
            patched.append(f"{rep.name}: eski build_evidence_table -> _legacy_*")
        if ensure_function(rep, "build_evidence_table", TABLE_CODE):
            patched.append(f"{rep.name}: yeni GRADE/RoB2 tablosu eklendi")
        if ensure_function(rep, "augment_report_with_limitations", LIMIT_CODE):
            patched.append(f"{rep.name}: augment_report_with_limitations() eklendi")
        todos.append(
            f"TODO ({rep.name}): rapor birleştirme fonksiyonunun return'ünden önce "
            f"`report = augment_report_with_limitations(report, records, "
            f"search_query, total_hits)` satırını ekle."
        )

    print("\n=== KURULUM ÖZETİ ===")
    print(f"Yedek klasörü : {BACKUP.name if BACKUP.exists() else '(yedek yok)'}")
    print(f"Oluşturulan   : {len(created)} dosya")
    for c in created: print(f"   + {c}")
    print(f"Yamalanan     : {len(patched)} işlem")
    for p in patched: print(f"   * {p}")

    if todos:
        print("\n--- MANUEL 1-2 SATIR (kaçınılmaz) ---")
        for t in todos: print(f"   ! {t}")

    if (ROOT / ".git").exists():
        try:
            subprocess.run(["git", "checkout", "-b", "feat/evidence-synthesis-layer"],
                           cwd=ROOT, check=False, capture_output=True)
            subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m",
                 "feat: evidence synthesis layer (effect-size + RoB2 + GRADE + limitations)"],
                cwd=ROOT, check=False, capture_output=True,
            )
            print("\n[git] branch: feat/evidence-synthesis-layer (commit denendi)")
        except Exception as e:
            print(f"\n[git] atlandı: {e}")

    print("\n=== TESTLER ===")
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"],
                           cwd=ROOT, capture_output=True, text=True)
        print(r.stdout[-3000:])
        if r.returncode != 0:
            print(r.stderr[-1000:])
            return 1
    except FileNotFoundError:
        print("pytest bulunamadı — `pip install pytest` sonra `pytest tests/ -v`")

    print("\nKurulum tamam. Sıradaki adım: yukarıdaki TODO satırlarını ekle, "
          "sonra `git push -u origin feat/evidence-synthesis-layer`.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

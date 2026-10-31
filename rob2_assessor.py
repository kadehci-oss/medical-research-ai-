"""
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

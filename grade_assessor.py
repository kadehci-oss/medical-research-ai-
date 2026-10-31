"""
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

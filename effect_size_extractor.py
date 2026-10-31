"""
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
N_PATTERN = (
    r"(?<!\d:)(?:(?:n\s*=\s*|total of\s+|included\s+|sample of\s+|enrolled\s+)(?=\d)|"
    r"(?=\d+\s+(?:patients|subjects|participants|cases|individuals|adults|children)))"
    r"(\d{1,6})(?!\s*:\s*\d)"
)

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

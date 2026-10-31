"""Small guards added to medical-research-ai- by apply_patches.py.

B6  fill_date_range     NCBI ESearch needs mindate AND maxdate together.
B9  retraction_status   flag records PubMed marks as retracted.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Optional, Tuple

EARLIEST_YEAR = 1800


def fill_date_range(
    start_year: Optional[int], end_year: Optional[int], today_year: Optional[int] = None
) -> Optional[Tuple[str, str]]:
    """Both bounds for ESearch, or None when no year filter was requested.

    NCBI documents mindate and maxdate as a pair; sending one alone can leave
    the filter unapplied. A missing start becomes 1800, a missing end becomes
    the current year.
    """
    if start_year is None and end_year is None:
        return None
    current = today_year if today_year is not None else _dt.date.today().year
    low = int(start_year) if start_year is not None else EARLIEST_YEAR
    high = int(end_year) if end_year is not None else current
    if low > high:
        raise ValueError("Başlangıç yılı bitiş yılından büyük olamaz.")
    return str(low), str(high)


def retraction_status(article: Dict[str, Any]) -> str:
    """'retracted', 'retraction_notice' or 'none' from PubMed publication types."""
    types = (article or {}).get("publication_types") or (article or {}).get("pub_types") or []
    lowered = {str(t).strip().lower() for t in types}
    if "retracted publication" in lowered:
        return "retracted"
    if "retraction of publication" in lowered:
        return "retraction_notice"
    return "none"

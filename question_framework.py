"""Choose a research-question framework that fits the clinical question.

PICO is not forced on every question. Diagnostic, prognostic, aetiology,
epidemiology, screening, safety, surgical and health-services questions each get
the framework that is conventionally used for that question type. Element values
come only from the query text (via ``report_generator.extract_pico``); an element
that the query does not state is shown as "sorguda belirtilmedi" and never filled
from the retrieved articles.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import report_generator as rg

NOT_STATED_TR = "sorguda belirtilmedi"

# (question_type, Turkish label, framework name, [(element key, Turkish label, pico source key)])
FRAMEWORKS: Dict[str, Dict[str, Any]] = {
    "therapy": {
        "label": "Tedavi / müdahale etkinliği",
        "framework": "PICO",
        "elements": [
            ("P", "Hasta grubu (Population)", "population"),
            ("I", "Müdahale (Intervention)", "intervention"),
            ("C", "Karşılaştırma (Comparison)", "comparison"),
            ("O", "Sonlanım (Outcome)", "outcome"),
        ],
        "preferred_designs": "Randomize kontrollü çalışmalar ve bunların sistematik derlemeleri",
    },
    "surgery": {
        "label": "Cerrahi / girişimsel işlem",
        "framework": "PICO (girişim = cerrahi işlem)",
        "elements": [
            ("P", "Hasta grubu", "population"),
            ("I", "Cerrahi / girişimsel işlem", "intervention"),
            ("C", "Alternatif işlem veya cerrahi dışı tedavi", "comparison"),
            ("O", "Perioperatif ve uzun dönem sonlanımlar", "outcome"),
        ],
        "preferred_designs": "Randomize çalışmalar; yoksa iyi düzeltilmiş karşılaştırmalı kohortlar (nedensellik sınırlı)",
    },
    "safety": {
        "label": "Güvenlilik / zarar",
        "framework": "PECO",
        "elements": [
            ("P", "Hasta grubu", "population"),
            ("E", "Maruziyet (ilaç / işlem)", "intervention"),
            ("C", "Karşılaştırma (maruz kalmayan)", "comparison"),
            ("O", "Advers olay / zarar sonlanımı", "outcome"),
        ],
        "preferred_designs": "RCT güvenlilik verisi, büyük kohortlar, farmakovijilans; olgu serileri yalnızca sinyal üretir",
    },
    "diagnosis": {
        "label": "Tanı / tanısal doğruluk",
        "framework": "PIRD",
        "elements": [
            ("P", "Hasta grubu (şüpheli olgular)", "population"),
            ("I", "İndeks test", "intervention"),
            ("C", "Karşılaştırılan test", "comparison"),
            ("R", "Referans standart", "reference_standard"),
            ("D", "Hedef durum (tanı)", "outcome"),
        ],
        "preferred_designs": "Ardışık hastalarda kesitsel tanısal doğruluk çalışmaları ve bunların meta-analizleri (QUADAS-2)",
    },
    "screening": {
        "label": "Tarama",
        "framework": "PICO (tarama programı)",
        "elements": [
            ("P", "Taranan topluluk", "population"),
            ("I", "Tarama testi / programı", "intervention"),
            ("C", "Taramasız izlem veya alternatif tarama", "comparison"),
            ("O", "Hastalığa özgü mortalite, aşırı tanı, zarar", "outcome"),
        ],
        "preferred_designs": "Tarama RCT'leri; tanısal doğruluk tek başına tarama yararını göstermez",
    },
    "prognosis": {
        "label": "Prognoz",
        "framework": "PFO (Population, prognostic Factor, Outcome)",
        "elements": [
            ("P", "Hasta grubu (başlangıç noktası)", "population"),
            ("F", "Prognostik faktör", "intervention"),
            ("O", "Sonlanım ve izlem süresi", "outcome"),
        ],
        "preferred_designs": "Başlangıç kohortlu prospektif kohortlar (QUIPS)",
    },
    "etiology": {
        "label": "Etiyoloji / risk faktörü",
        "framework": "PEO / PECO",
        "elements": [
            ("P", "Topluluk", "population"),
            ("E", "Maruziyet / risk faktörü", "intervention"),
            ("C", "Maruz kalmayan karşılaştırma", "comparison"),
            ("O", "Hastalık / sonlanım", "outcome"),
        ],
        "preferred_designs": "Kohort ve vaka-kontrol çalışmaları (ROBINS-E); ilişki nedensellik değildir",
    },
    "epidemiology": {
        "label": "Epidemiyoloji / sıklık",
        "framework": "CoCoPop (Condition, Context, Population)",
        "elements": [
            ("Co", "Durum (hastalık)", "outcome"),
            ("Co", "Bağlam (yer / zaman)", "comparison"),
            ("Pop", "Topluluk", "population"),
        ],
        "preferred_designs": "Toplum temelli kesitsel çalışmalar ve kayıt verileri",
    },
    "health_services": {
        "label": "Sağlık hizmetleri araştırması",
        "framework": "SPICE (Setting, Perspective, Intervention, Comparison, Evaluation)",
        "elements": [
            ("S", "Ortam", "population"),
            ("P", "Bakış açısı", "perspective"),
            ("I", "Hizmet / uygulama", "intervention"),
            ("C", "Karşılaştırma", "comparison"),
            ("E", "Değerlendirme ölçütü (maliyet, erişim, kalite)", "outcome"),
        ],
        "preferred_designs": "Pragmatik / küme randomize çalışmalar, kesintili zaman serileri, ekonomik değerlendirmeler",
    },
}

_RULES: List[Tuple[str, re.Pattern]] = [
    ("health_services", re.compile(
        r"\b(?:cost[- ]effective\w*|cost[- ]utility|cost[- ]benefit|costs?\b|economic\s+evaluation|health\s+services?|"
        r"implementation|telemedicine|teleradiology|telehealth|care\s+delivery|access\s+to\s+care|waiting\s+times?|"
        r"workflow|quality\s+improvement|readmission\s+program|maliyet|sağlık\s+hizmet\w*|erişim|teletıp)\b",
        re.IGNORECASE)),
    ("screening", re.compile(r"\b(?:screening|screened|tarama(?:sı|da|nın)?|taranması)\b", re.IGNORECASE)),
    ("diagnosis", re.compile(
        r"\b(?:diagnos\w*|sensitivity|specificity|accuracy|detection|detect\w*|positive\s+predictive|negative\s+predictive|"
        r"likelihood\s+ratio|ROC|AUC|area\s+under|tanı\w*|tanısal|duyarlılı\w*|özgüllü\w*|doğruluğu?)\b",
        re.IGNORECASE)),
    ("epidemiology", re.compile(
        r"\b(?:prevalence|incidence|burden|epidemiolog\w*|frequency\s+of|trends?\s+in|prevalans\w*|insidans\w*|sıklı\w*|yaygınlı\w*)\b",
        re.IGNORECASE)),
    ("prognosis", re.compile(
        r"\b(?:prognos\w*|predictors?\s+of|predict\w*|long[- ]term\s+(?:outcome|risk|prognosis)|survival\s+(?:after|of)|"
        r"natural\s+history|recurrence\s+risk|prognoz\w*|öngörü\w*|seyri)\b",
        re.IGNORECASE)),
    ("safety", re.compile(
        r"\b(?:adverse\s+(?:events?|effects?|reactions?)|safety|toxicity|side[- ]effects?|harms?|complications?\s+of\s+\w+\s+therapy|"
        r"yan\s+etki\w*|advers|güvenlili\w*|toksisite\w*)\b",
        re.IGNORECASE)),
    ("etiology", re.compile(
        r"\b(?:risk\s+factors?|risk\s+of|associated\s+with|association|exposure|aetiolog\w*|etiolog\w*|causes?\s+of|"
        r"use\s+and\s+(?:the\s+)?risk|and\s+(?:\w+\s+){0,2}risk|risk\s+faktör\w*|etiyoloji\w*|maruziyet\w*|ilişkisi)\b",
        re.IGNORECASE)),
    ("surgery", re.compile(
        r"\b(?:surg\w*|operative|resection|\w+ectomy|\w+ostomy|\w+plasty|laparoscop\w*|robotic|arthroscop\w*|repair|"
        r"herni\w*|anastomo\w*|bypass\s+graft\w*|"
        r"transplant\w*|cerrahi|ameliyat\w*|rezeksiyon|laparoskopik)\b",
        re.IGNORECASE)),
]
_THERAPY_HINT = re.compile(
    r"\b(?:versus|vs\.?|compared\s+with|treatment|therapy|efficacy|effect\s+of|for\s+(?:the\s+)?treatment|"
    r"tedavi\w*|etkinli\w*|etkisi)\b",
    re.IGNORECASE,
)


def classify_question_type(query: str) -> str:
    """Return one of FRAMEWORKS' keys. Defaults to therapy when no other type is signalled."""
    text = query or ""
    surgery = _RULES[-1][1].search(text)
    for qtype, pattern in _RULES:
        if not pattern.search(text):
            continue
        if qtype == "etiology" and _THERAPY_HINT.search(text) and not re.search(r"risk\s+(?:factor|of)|and\s+(?:\w+\s+){0,2}risk|risk\s+faktör", text, re.IGNORECASE):
            continue
        if qtype == "safety" and surgery and re.search(r"complication", text, re.IGNORECASE):
            return "surgery"
        if qtype == "etiology" and surgery and not re.search(r"risk\s+factor|risk\s+faktör", text, re.IGNORECASE):
            return "surgery"
        return qtype
    return "therapy"


def select_question_framework(query: str) -> Dict[str, Any]:
    """Framework and element values drawn only from the query wording."""
    qtype = classify_question_type(query)
    spec = FRAMEWORKS[qtype]
    pico = dict(rg.extract_pico(query or ""))
    if qtype == "diagnosis":
        index = re.sub(r"^(?:the\s+)?(?:diagnostic\s+(?:accuracy|performance)|sensitivity\s+and\s+specificity|accuracy)\s+of\s+",
                       "", pico.get("intervention") or "", flags=re.IGNORECASE)
        pico["intervention"] = index
        ref = re.search(r"\b(?:reference\s+standard|gold\s+standard|referans\s+standart)\s*(?:of|:|=|olarak)?\s*([^,;.]+)",
                        query or "", re.IGNORECASE)
        pico["reference_standard"] = ref.group(1).strip() if ref else ""
    if qtype in ("prognosis", "epidemiology"):
        lead = re.search(r"\b(?:prognosis|prevalence|incidence|burden|natural\s+history|outcomes?)\s+of\s+([^,;.]+?)"
                         r"(?:\s+(?:and|in|among|after)\s+(?P<rest>[^,;.]+))?$", query or "", re.IGNORECASE)
        if lead:
            stated = lead.group(1).strip()
            key = "population" if qtype == "prognosis" else "outcome"
            if not pico.get(key) or re.search(r"belirtilmemiş|belirtilmedi", pico.get(key) or "", re.IGNORECASE):
                pico[key] = stated
            if qtype == "prognosis" and lead.group("rest") and re.search(r"belirtilmemiş|belirtilmedi", pico.get("outcome") or "belirtilmemiş", re.IGNORECASE):
                pico["outcome"] = lead.group("rest").strip()
            if qtype == "epidemiology" and lead.group("rest"):
                pico["comparison"] = lead.group("rest").strip()
    elements = []
    for key, label, source_key in spec["elements"]:
        raw = (pico.get(source_key) or "").strip()
        value = raw if raw and not re.search(r"belirtilmedi|belirtilmemiş|tanımlanmadı|tanımlanmamış|değerlendirilemedi|not specified|genel", raw, re.IGNORECASE) else NOT_STATED_TR
        elements.append({"key": key, "label": label, "value": value, "source": "sorgu" if value != NOT_STATED_TR else "yok"})
    return {
        "question_type": qtype,
        "question_type_tr": spec["label"],
        "framework": spec["framework"],
        "elements": elements,
        "preferred_designs": spec["preferred_designs"],
        "pico": pico,
    }


def render_framework_markdown(selection: Dict[str, Any]) -> str:
    lines = [
        f"### 🧭 Soru Türü ve Çerçeve: {selection['question_type_tr']} — {selection['framework']}",
        "Çerçeve soru türüne göre seçildi; her soruya PICO zorlanmadı. Değerler yalnızca sorgu metninden alınır.",
    ]
    for element in selection["elements"]:
        lines.append(f"- **{element['key']} ({element['label']}):** {element['value']}")
    lines.append(f"- **Bu soru için uygun kanıt türü:** {selection['preferred_designs']}")
    return "\n".join(lines) + "\n"

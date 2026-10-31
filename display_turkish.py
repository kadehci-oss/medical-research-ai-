"""Controlled Turkish display for table cells and study cards.

Only words and phrases in this map are translated. Abbreviations stay
abbreviations. A token that cannot be translated safely is omitted so a
table cell does not show raw English prose. Numbers, doses, and bracketed
spans are left intact. Nothing here is tied to a PMID.
"""
import re

# Longer phrases first. The replacement is the display string, not a guess
# beyond the words the source actually used.
_PHRASE_PAIRS = (
    ("cardiovascular death or first hospitalization for heart failure", "kardiyovasküler ölüm veya kalp yetersizliği nedeniyle ilk hastaneye yatış"),
    ("cardiovascular death or first hospitalisation for heart failure", "kardiyovasküler ölüm veya kalp yetersizliği nedeniyle ilk hastaneye yatış"),
    ("cardiovascular death or hospitalization for heart failure", "kardiyovasküler ölüm veya kalp yetersizliği nedeniyle hastaneye yatış"),
    ("cardiovascular death or hospitalisation for heart failure", "kardiyovasküler ölüm veya kalp yetersizliği nedeniyle hastaneye yatış"),
    ("cardiovascular death or worsening heart failure", "kardiyovasküler ölüm veya kötüleşen kalp yetersizliği"),
    ("death from cardiovascular causes", "kardiyovasküler ölüm"),
    ("hospitalization for heart failure", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("hospitalisations for heart failure", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("hospitalizations for heart failure", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("hospitalisation for heart failure", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("heart failure hospitalization", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("heart failure hospitalisation", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("cardiovascular death or first hospitalization for hf", "kardiyovasküler ölüm veya kalp yetersizliği nedeniyle ilk hastaneye yatış"),
    ("cardiovascular death or first hospitalisation for hf", "kardiyovasküler ölüm veya kalp yetersizliği nedeniyle ilk hastaneye yatış"),
    ("first hospitalization for hf", "kalp yetersizliği nedeniyle ilk hastaneye yatış"),
    ("first hospitalisation for hf", "kalp yetersizliği nedeniyle ilk hastaneye yatış"),
    ("hospitalization for hf", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("hospitalisation for hf", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("first hospitalization for heart failure", "kalp yetersizliği nedeniyle ilk hastaneye yatış"),
    ("first hospitalisation for heart failure", "kalp yetersizliği nedeniyle ilk hastaneye yatış"),
    ("total hospitalizations for heart failure", "kalp yetersizliği nedeniyle hastaneye yatış"),
    ("worsening heart failure", "kötüleşen kalp yetersizliği"),
    ("worsening hf", "kötüleşen kalp yetersizliği"),
    ("all-cause mortality", "tüm nedenlere bağlı ölüm"),
    ("all-cause death", "tüm nedenlere bağlı ölüm"),
    ("death from any cause", "tüm nedenlere bağlı ölüm"),
    ("non-cardiovascular death", "kardiyovasküler olmayan ölüm"),
    ("cardiovascular mortality", "kardiyovasküler ölüm"),
    ("cardiovascular death", "kardiyovasküler ölüm"),
    ("cardiac death", "kardiyak ölüm"),
    ("cv death", "kardiyovasküler ölüm"),
    ("composite renal endpoint", "bileşik böbrek sonlanımı"),
    ("composite kidney endpoint", "bileşik böbrek sonlanımı"),
    ("kidney disease progression", "böbrek hastalığı progresyonu"),
    ("ckd progression", "kronik böbrek hastalığı progresyonu"),
    ("chronic kidney disease", "kronik böbrek hastalığı"),
    ("acute kidney injury", "akut böbrek hasarı"),
    ("end-stage kidney disease", "son dönem böbrek hastalığı"),
    ("kidney failure", "böbrek yetersizliği"),
    ("estimated glomerular filtration rate", "eGFR"),
    ("urinary albumin to creatinine ratio", "idrar albümin/kreatinin oranı"),
    ("heart failure with reduced ejection fraction", "azalmış ejeksiyon fraksiyonlu kalp yetersizliği"),
    ("heart failure with preserved ejection fraction", "korunmuş ejeksiyon fraksiyonlu kalp yetersizliği"),
    ("left ventricular ejection fraction", "sol ventrikül ejeksiyon fraksiyonu"),
    ("reduced ejection fraction", "azalmış ejeksiyon fraksiyonu"),
    ("preserved ejection fraction", "korunmuş ejeksiyon fraksiyonu"),
    ("ejection fraction", "ejeksiyon fraksiyonu"),
    ("type 2 diabetes mellitus", "tip 2 diyabet"),
    ("type 2 diabetes", "tip 2 diyabet"),
    ("diabetic ketoacidosis", "diyabetik ketoasidoz"),
    ("genital infections", "genital enfeksiyonlar"),
    ("atrial fibrillation", "atriyal fibrilasyon"),
    ("macrovascular events", "makrovasküler olaylar"),
    ("worsening kidney function", "kötüleşen böbrek fonksiyonu"),
    ("symptomatic hypotension", "semptomatik hipotansiyon"),
    ("kidney outcomes", "böbrek sonlanımları"),
    ("renal endpoint", "böbrek sonlanımı"),
    ("composite endpoint", "bileşik sonlanım"),
    ("composite outcome", "bileşik sonlanım"),
    ("egfr decline", "eGFR azalması"),
    ("statin-induced anti-hmgcr antibody imnm", "statin ilişkili anti-HMGCR antikor pozitif İMNM"),
    ("statin-induced anti-hmgcr antibody", "statin ilişkili anti-HMGCR antikoru"),
    ("immune-mediated necrotizing myopathy", "immün aracılı nekrotizan miyopati"),
    ("immune-mediated necrotizing myositis", "immün aracılı nekrotizan miyozit"),
    ("idiopathic inflammatory myopathy", "idiyopatik inflamatuar miyopati"),
    ("idiopathic inflammatory myositis", "idiyopatik inflamatuar miyozit"),
    ("standardized mean difference", "standartlaştırılmış ortalama fark (SMD)"),
    ("european neuromuscular center", "Avrupa Nöromusküler Merkezi"),
    ("european neuromuscular centre", "Avrupa Nöromusküler Merkezi"),
    ("significant group difference in post-treatment", "tedavi sonrası anlamlı grup farkı"),
    ("progression-free survival", "progresyonsuz sağkalım"),
    ("disease-free survival", "hastalıksız sağkalım"),
    ("event-free survival", "olaysız sağkalım"),
    ("overall survival", "genel sağkalım"),
    ("cancer-associated myositis", "kanserle ilişkili miyozit"),
    ("cancer-associated iim", "kanserle ilişkili İİM"),
    ("dermatomyositis-like cutaneous features", "dermatomiyozit benzeri deri bulguları"),
    ("cutaneous dermatomyositis-like features", "dermatomiyozit benzeri deri bulguları"),
    ("shorter disease duration", "daha kısa hastalık süresi"),
    ("disease duration", "hastalık süresi"),
    ("any autoantibody", "herhangi bir otoantikor"),
    ("any autoantibodies", "herhangi bir otoantikor"),
    ("cutaneous manifestations", "deri bulguları"),
    ("cutaneous features", "deri bulguları"),
    ("skin manifestations", "deri bulguları"),
    ("skin findings", "deri bulguları"),
    ("proximal muscle weakness", "proksimal kas güçsüzlüğü"),
    ("interstitial lung disease", "interstisyel akciğer hastalığı"),
    ("significant group difference", "anlamlı grup farkı"),
    ("waist circumference", "bel çevresi"),
    ("annual rate of decline in the estimated glomerular filtration rate", "yıllık eGFR azalma hızı"),
    ("ml per minute per 1.73 m2 of body-surface area per year", "mL/dk/1,73 m²/yıl"),
    ("ml per minute per 1.73 m² of body-surface area per year", "mL/dk/1,73 m²/yıl"),
    ("ml per minute per 1.73 m2 per year", "mL/dk/1,73 m²/yıl"),
    ("ml per minute per 1.73 m² per year", "mL/dk/1,73 m²/yıl"),
    ("new york heart association class ii, iii, or iv heart failure", "NYHA sınıf II, III veya IV kalp yetersizliği"),
    ("new york heart association class ii, iii, or iv", "NYHA sınıf II, III veya IV"),
    ("class ii, iii, or iv heart failure", "sınıf II, III veya IV kalp yetersizliği"),
    ("class ii-iv heart failure", "sınıf II-IV kalp yetersizliği"),
    ("class ii, iii, or iv", "sınıf II, III veya IV"),
    ("atopic march progression", "atopik yürüyüş ilerlemesi"),
    ("ige category shift", "IgE kategori değişimi"),
    ("ige category change", "IgE kategori değişimi"),
    ("allergic rhinitis", "alerjik rinit"),
    ("atopic march", "atopik yürüyüş"),
    ("peak pruritus numerical rating scale", "kaşıntı NRS"),
    ("peak pruritus nrs", "kaşıntı NRS"),
    ("pruritus nrs", "kaşıntı NRS"),
    ("itch nrs", "kaşıntı NRS"),
    ("eczema area and severity index", "EASI"),
    ("investigator global assessment", "IGA"),
    ("iga 0/1", "IGA 0/1"),
    ("iga 0 or 1", "IGA 0/1"),
    ("easi-75", "EASI-75"),
    ("easi75", "EASI-75"),
    ("body weight", "vücut ağırlığı"),
    ("lymphocytic leukaemia", "lenfositik lösemi"),
    ("lymphocytic leukemia", "lenfositik lösemi"),
    ("adverse events", "advers olaylar"),
    ("response rate", "yanıt oranı"),
    ("incidence rate ratio", "insidans oranı oranı (IRR)"),
    ("inflammatory myopathy", "inflamatuar miyopati"),
    ("inflammatory myositis", "inflamatuar miyozit"),
    ("necrotizing myopathy", "nekrotizan miyopati"),
    ("necrotising myopathy", "nekrotizan miyopati"),
    ("confidence interval", "güven aralığı"),
    ("mean difference", "ortalama fark (MD)"),
    ("heart failure", "kalp yetersizliği"),
    ("muscle weakness", "kas güçsüzlüğü"),
    ("creatine kinase", "kreatin kinaz"),
    ("diabetes mellitus", "diyabet"),
    ("anti-hmgcr antibodies", "anti-HMGCR antikorlar"),
    ("anti-hmgcr antibody", "anti-HMGCR antikoru"),
    ("necrotizing im", "nekrotizan IM"),
    ("necrotising im", "nekrotizan IM"),
    ("odds ratio", "olasılık oranı (OR)"),
    ("hazard ratio", "tehlike oranı (HR)"),
    ("relative risk", "risk oranı (RR)"),
    ("risk ratio", "risk oranı (RR)"),
    ("win ratio", "kazanma oranı (win ratio)"),
    ("statin-induced", "statin ilişkili"),
    ("statin-associated", "statin ilişkili"),
    ("statin exposure", "statin maruziyeti"),
    ("statin-exposure", "statin maruziyeti"),
    ("cancer-associated", "kanserle ilişkili"),
    ("malignancy-associated", "malignite ilişkili"),
    ("immune-mediated", "immün aracılı"),
    ("dermatomyositis-like", "dermatomiyozit benzeri"),
    ("post-treatment", "tedavi sonrası"),
    ("non-hispanics", "Hispanik olmayanlar"),
    ("non-hispanic", "Hispanik olmayan"),
    ("hyperlipidaemia", "hiperlipidemi"),
    ("hyperlipidemia", "hiperlipidemi"),
    ("older age", "ileri yaş"),
)

_PHRASES = tuple(sorted(_PHRASE_PAIRS, key=lambda item: len(item[0]), reverse=True))

# Empty string means the English token is a function word and is not shown.
_WORDS = {
    "patients": "hastalar",
    "patient": "hasta",
    "subjects": "katılımcılar",
    "participants": "katılımcılar",
    "adults": "erişkinler",
    "children": "çocuklar",
    "older": "daha yaşlı",
    "younger": "daha genç",
    "years": "yıl",
    "year": "yıl",
    "months": "ay",
    "month": "ay",
    "days": "gün",
    "day": "gün",
    "weeks": "hafta",
    "week": "hafta",
    "higher": "daha yüksek",
    "lower": "daha düşük",
    "increased": "artmış",
    "decreased": "azalmış",
    "reduced": "azalmış",
    "greater": "daha fazla",
    "lesser": "daha az",
    "more": "daha fazla",
    "less": "daha az",
    "shorter": "daha kısa",
    "longer": "daha uzun",
    "similar": "benzer",
    "prevalence": "prevalans",
    "mortality": "mortalite",
    "remission": "remisyon",
    "relapse": "nüks",
    "recurrence": "nüks",
    "progression": "progresyon",
    "death": "ölüm",
    "deaths": "ölüm",
    "cardiac": "kardiyak",
    "kidney": "böbrek",
    "renal": "böbrek",
    "chronic": "kronik",
    "albuminuria": "albüminüri",
    "albumin": "albümin",
    "creatinine": "kreatinin",
    "glomerular": "glomerüler",
    "filtration": "filtrasyon",
    "hba1c": "HbA1c",
    "egfr": "eGFR",
    "uacr": "UACR",
    "ckd": "KBH",
    "decline": "azalma",
    "endpoint": "sonlanım",
    "endpoints": "sonlanımlar",
    "composite": "bileşik",
    "baseline": "bazal",
    "frail": "kırılgan",
    "frailty": "kırılganlık",
    "participant": "katılımcı",
    "participants": "katılımcılar",
    "individual": "birey",
    "individuals": "bireyler",
    "survival": "sağkalım",
    "weight": "ağırlık",
    "waist": "bel",
    "circumference": "çevre",
    "scores": "skorlar",
    "score": "skor",
    "significant": "anlamlı",
    "difference": "fark",
    "differences": "farklar",
    "group": "grup",
    "groups": "gruplar",
    "versus": "karşı",
    "vs": "karşı",
    "compared": "karşılaştırılan",
    "antibody": "antikor",
    "antibodies": "antikorlar",
    "positive": "pozitif",
    "negative": "negatif",
    "induced": "ilişkili",
    "associated": "ilişkili",
    "cancer": "kanser",
    "diabetes": "diyabet",
    "myopathy": "miyopati",
    "myositis": "miyozit",
    "immune": "immün",
    "mediated": "aracılı",
    "inflammatory": "inflamatuar",
    "necrotizing": "nekrotizan",
    "necrotising": "nekrotizan",
    "statin": "statin",
    "statins": "statin",
    "leukemia": "lösemi",
    "leukaemia": "lösemi",
    "european": "Avrupa",
    "neuromuscular": "nöromusküler",
    "center": "merkez",
    "centre": "merkez",
    "hispanic": "Hispanik",
    "hispanics": "Hispanikler",
    "caucasian": "Kafkas",
    "caucasians": "Kafkaslar",
    "placebo": "Plasebo",
    "women": "kadın",
    "men": "erkek",
    "female": "kadın",
    "male": "erkek",
    "treatment": "tedavi",
    "therapy": "tedavi",
    "treated": "tedavi edilen",
    "exposure": "maruziyet",
    "duration": "süre",
    "disease": "hastalık",
    "manifestations": "bulgular",
    "manifestation": "bulgu",
    "cutaneous": "deri",
    "features": "bulgular",
    "feature": "bulgu",
    "severe": "şiddetli",
    "proximal": "proksimal",
    "muscle": "kas",
    "weakness": "güçsüzlük",
    "pain": "ağrı",
    "hypertension": "hipertansiyon",
    "pulmonary": "pulmoner",
    "drug": "ilaç",
    "drugs": "ilaçlar",
    "disability": "yetiyitimi",
    "elevated": "yüksek",
    "marked": "belirgin",
    "diagnosis": "tanı",
    "outcome": "sonlanım",
    "outcomes": "sonlanımlar",
    "hospitalization": "hastaneye yatış",
    "hospitalizations": "hastaneye yatış",
    "hospitalisation": "hastaneye yatış",
    "hospitalisations": "hastaneye yatış",
    "cardiovascular": "kardiyovasküler",
    "heart": "kalp",
    "failure": "yetersizlik",
    "ejection": "ejeksiyon",
    "fraction": "fraksiyon",
    "preserved": "korunmuş",
    "odds": "odds",
    "hazard": "tehlike",
    "ratio": "oranı",
    "relative": "göreli",
    "risk": "risk",
    "risks": "riskler",
    "mean": "ortalama",
    "interval": "aralık",
    "confidence": "güven",
    "win": "kazanma",
    "event": "olay",
    "events": "olaylar",
    "overall": "genel",
    "or": "veya",
    "and": "ve",
    "between": "arasında",
    "among": "arasında",
    "both": "her iki",
    "all": "tüm",
    "any": "herhangi",
    "not": "değil",
    "but": "ancak",
    "also": "ayrıca",
    "however": "ancak",
    "respectively": "sırasıyla",
    "approximately": "yaklaşık",
    "about": "yaklaşık",
    "during": "sırasında",
    "after": "sonra",
    "before": "önce",
    "following": "sonrasında",
    "including": "dahil",
    "other": "diğer",
    "per": "başına",
    "without": "olmadan",
    "with": "",
    "the": "",
    "a": "",
    "an": "",
    "of": "",
    "in": "",
    "to": "",
    "for": "",
    "by": "",
    "from": "",
    "on": "",
    "at": "",
    "as": "",
    "than": "",
    "then": "",
    "were": "",
    "was": "",
    "is": "",
    "are": "",
    "be": "",
    "been": "",
    "being": "",
    "had": "",
    "have": "",
    "has": "",
    "this": "",
    "that": "",
    "these": "",
    "those": "",
    "their": "",
    "its": "",
    "into": "",
    "over": "",
    "under": "",
    "no": "",
    "resulting": "",
    "using": "",
    "used": "",
    "such": "",
    "self": "",
    "identified": "tanımlanan",
    "study": "çalışma",
    "trial": "çalışma",
    "review": "derleme",
    "analysis": "analiz",
    "retrospective": "retrospektif",
    "prospective": "prospektif",
    "randomized": "randomize",
    "randomised": "randomize",
    "double": "çift",
    "blind": "kör",
    "received": "alan",
    "receive": "almak",
    "assigned": "atanan",
    "allocated": "atanan",
    "included": "dahil edilen",
    "enrolled": "kaydedilen",
    "present": "mevcut",
    "presented": "başvuran",
    "developed": "gelişen",
    "showed": "gösteren",
    "found": "saptanan",
    "observed": "gözlenen",
    "reported": "bildirilen",
    "common": "yaygın",
    "depression": "depresyon",
    "major": "majör",
    "symptoms": "belirtiler",
    "symptom": "belirti",
    "plaque": "plak",
    "psoriasis": "psoriazis",
    "walking": "yürüme",
    "speed": "hız",
    "gait": "yürüyüş",
    "rehabilitation": "rehabilitasyon",
    "asthma": "astım",
    "rhinitis": "rinit",
    "atopic": "atopik",
    "pruritus": "kaşıntı",
    "itch": "kaşıntı",
    "inhibitor": "inhibitör",
    "inhibitors": "inhibitörler",
    "conventional": "konvansiyonel",
    "physical": "fiziksel",
    "significantly": "anlamlı olarak",
    "less": "daha az",
    "rates": "oranlar",
    "rate": "oran",
    "age": "yaş",
    "ages": "yaşlar",
    "median": "ortanca",
    "range": "aralık",
    "history": "öykü",
    "autoantibody": "otoantikor",
    "autoantibodies": "otoantikorlar",
    "antimetabolite": "antimetabolit",
    "antimetabolites": "antimetabolitler",
    "rituximab": "rituksimab",
    "cutaneous": "deri",
    "vascular": "vasküler",
    "few": "az",
    "marked": "belirgin",
    "characterized": "karakterize",
    "characterised": "karakterize",
    "native": "yerli",
    "american": "Amerikalı",
    "americans": "Amerikalılar",
    "mg": "mg",
    "kg": "kg",
    "ml": "mL",
    "mm": "mm",
    "cm": "cm",
    "dl": "dL",
}

# Abbreviations keep a canonical spelling. IIM/IMNM use Turkish dotted İ.
_ABBREV = {
    "iim": "İİM",
    "imnm": "İMNM",
    "hmgcr": "HMGCR",
    "hmg": "HMG",
    "ivig": "IVIG",
    "ck": "CK",
    "ss": "SS",
    "ana": "ANA",
    "rp": "RP",
    "mri": "MRI",
    "hr": "HR",
    "rr": "RR",
    "md": "MD",
    "smd": "SMD",
    "irr": "IRR",
    "wmd": "WMD",
    "ci": "CI",
    "iu": "IU",
    "mg": "mg",
    "kg": "kg",
}

# ASCII words the Turkish templates already emit. They are not English prose.
_KEEP = {
    "advers", "antikoru", "antikor", "azatioprin", "belirti", "bildirildi",
    "bildirilmedi", "bulgu", "bulgular", "deksametazon", "deger", "etki",
    "ekstremitelerde", "enfarkt", "gecikmesi", "gerilemesi", "hasta",
    "hastalar", "hispanik", "hispanikler", "ile", "iki", "ilerleyici",
    "inflamasyon", "kas", "kaynak", "klinik", "komplikasyon", "konjonktival",
    "kortikosteroid", "metotreksat", "mikofenolat", "miyalji", "nitel",
    "periorbital", "pontin", "prednizon", "prednizolon", "primer", "proksimal",
    "remisyon", "rituksimab", "sert", "skor", "skorlar", "statin",
    "takrolimus", "tedavi", "tedavisi", "ve", "veya", "viyolese", "yetersiz",
    "yil", "yıl", "oran", "orani", "plasebo", "diyabet", "miyopati", "miyozit",
    "nekrotizan", "inflamatuar", "hiperlipidemi", "karsı", "karşı", "gün",
    "ay", "kadın", "erkek", "ortanca", "aralik", "aralık", "ust", "ga",
    "sonlanim", "adi", "guvenle", "kurulamadi", "cevirilemedi", "sayisal",
    "ozette", "grubunun", "grubu",
}

_DRUG_SUFFIX_RE = re.compile(
    r"(?i)(?:mab|nib|vir|sone|lone|pril|statin|cillin|mycin|prazole|oxetine|"
    r"olol|dipine|flozin|glutide|sartan|taxel|xaban|parin|lukast|setron|"
    r"floxacin|dronate|ciclib|parib|tide|caine)$"
)
# A digit may sit inside an abbreviation (HbA1c). A leading digit stays a number.
_TOKEN_RE = re.compile(
    r"[A-Za-zÇĞİÖŞÜçğıöşüıİ][A-Za-z0-9ÇĞİÖŞÜçğıöşüıİ]*(?:-[A-Za-z0-9ÇĞİÖŞÜçğıöşüıİ]+)*"
)
_DIACRITIC_RE = re.compile(r"[çğıöşüÇĞİÖŞÜıİ]")
_ANTI_RE = re.compile(r"(?i)^anti-([A-Za-z0-9]+)$")
_PLACEHOLDER_RE = re.compile(r"\x00(\d+)\x00")
# "anti-<long chemical name> (HMGCR)" keeps the short name and the anti- prefix.
_ANTI_PAREN_RE = re.compile(
    r"\banti-(?:[A-Za-z0-9]+(?:[-\s]+[A-Za-z0-9]+){1,18}?)\s*"
    r"\(\s*(?:anti-)?([A-Za-z][A-Za-z0-9]{1,14})\s*\)",
    re.IGNORECASE,
)
_POSSESSIVE_REPAIRS = (
    (re.compile(r"\bhastalık süre\b", re.IGNORECASE), "hastalık süresi"),
    (re.compile(r"\bderi bulgular\b(?!ı)", re.IGNORECASE), "deri bulguları"),
    (re.compile(r"\bkas güçsüzlük\b(?!ü)", re.IGNORECASE), "kas güçsüzlüğü"),
)

UNTRANSLATED_OUTCOME_LABEL = "Sonlanım adı güvenle çevrilemedi"

# English words that are not already in the translation map. A population
# line that still contains one of these next to a Turkish word is mixed.
_LEFTOVER_ENGLISH = {
    "type", "chronic", "kidney", "renal", "should", "would", "could", "might",
    "class", "association", "receive", "receiving", "matching", "once", "daily",
    "must", "guidelines", "guideline", "treat", "treating", "treated",
    "congestive", "baseline", "irrespective", "regardless", "followed",
    "varying", "composite", "endpoint", "endpoints", "frail", "frailty",
}

_PASSTHROUGH_FIELDS = {
    "Belirtilmedi",
    "Özette bildirilmedi",
    "Özette nicel etki ölçütü bildirilmedi",
    "değerlendirilemedi",
}


def _brackets_unbalanced(text: str) -> bool:
    """True when a round or square bracket was cut before it closed."""
    round_depth = 0
    square_depth = 0
    for char in text or "":
        if char == "(":
            round_depth += 1
        elif char == ")":
            round_depth -= 1
        elif char == "[":
            square_depth += 1
        elif char == "]":
            square_depth -= 1
        if round_depth < 0 or square_depth < 0:
            return True
    return round_depth != 0 or square_depth != 0


def _map_token(token: str, drop_unknown: bool = True) -> str:
    """Return the display form of one token.

    When ``drop_unknown`` is true, an English token that is not in the map is
    omitted. When false, that token is kept so an already Turkish line is not
    stripped down to a suffix.
    """
    if not token:
        return ""
    if _DIACRITIC_RE.search(token):
        return token
    anti = _ANTI_RE.fullmatch(token)
    if anti:
        body = anti.group(1)
        canon = _ABBREV.get(body.lower(), body.upper())
        return "anti-" + canon
    lowered = token.lower()
    if lowered in _ABBREV and (token.isupper() or lowered in {"iim", "imnm", "hmgcr", "hmg", "ivig", "ck", "ss"}):
        return _ABBREV[lowered]
    if token == "OR":
        return "OR"
    if lowered in _WORDS:
        return _WORDS[lowered]
    if lowered in _KEEP:
        return token
    if re.fullmatch(r"(?i)[A-Z]{0,8}\d+[A-Z0-9]*|[A-Z]{1,8}-\d+[A-Z0-9]*", token):
        return token
    if "-" in token:
        # A chemical name or scale fragment. An unknown piece is not shown raw
        # when the caller asked to drop unsafe English.
        rendered = []
        for piece in token.split("-"):
            if not piece or re.fullmatch(r"\d+", piece):
                continue
            mapped = _map_token(piece, drop_unknown=drop_unknown)
            if not mapped:
                if drop_unknown:
                    return ""
                rendered.append(piece)
                continue
            rendered.append(mapped)
        return " ".join(rendered)
    if _DRUG_SUFFIX_RE.search(token):
        return token
    if len(token) == 1 and (token.isupper() or lowered in {"n", "p", "l", "u"}):
        return token
    if token.isupper() and 2 <= len(token) <= 10:
        return token
    return "" if drop_unknown else token


_SLOPE_UNIT_RE = re.compile(
    r"m[lL]\s*(?:/|\bper\b)\s*min(?:ute)?\s*(?:/|\bper\b)\s*1[.,]73\s*m\s*(?:2|²)"
    r"(?:\s*of\s+body[-\s]?surface\s+area)?"
    r"(?:\s*(?:/|\bper\b)\s*years?)?",
    re.IGNORECASE,
)

# Outcome names are translated only as a whole controlled term. These English
# heads are real endpoints, not function words and not generic person nouns.
_SINGLE_OUTCOME_TR = {
    "death": "ölüm",
    "deaths": "ölüm",
    "mortality": "mortalite",
    "remission": "remisyon",
    "relapse": "nüks",
    "leukemia": "lösemi",
    "leukaemia": "lösemi",
    "myopathy": "miyopati",
    "myositis": "miyozit",
    "weight": "ağırlık",
    "hospitalization": "hastaneye yatış",
    "hospitalisation": "hastaneye yatış",
    "stroke": "inme",
    "infection": "enfeksiyon",
    "asthma": "astım",
    "diabetes": "diyabet",
    "antimetabolites": "antimetabolitler",
    "antimetabolite": "antimetabolit",
    "rituximab": "rituksimab",
    "ivig": "IVIG",
    "hba1c": "HbA1c",
    "egfr": "eGFR",
    "exacerbation": "alevlenme",
    "depression": "depresyon",
    "seizure": "nöbet",
    "easi-75": "EASI-75",
    "easi75": "EASI-75",
    "iga": "IGA",
}

_GENERIC_OUTCOME_EN = {
    "individual", "individuals", "patient", "patients", "person", "people",
    "subject", "subjects", "participant", "participants", "group", "groups",
    "including", "included", "include", "the", "a", "an", "of", "in", "for",
    "and", "or", "with", "by", "to", "from", "on", "at", "was", "were", "is",
    "are", "be", "been", "this", "that", "these", "those", "than", "then",
    "significant", "significantly", "lower", "higher", "reduced", "reduction",
    "risk", "new", "worsening", "combined", "versus", "vs", "per", "into",
    "their", "its", "also", "not", "no", "more", "less", "most", "such",
    "between", "among", "both", "all", "any", "other", "who", "which", "that",
}

_CLOSED_OUTCOME_ABBREV = {
    "IIM": "İİM",
    "IMNM": "İMNM",
    "HHF": "KYHY",
    "CKD": "KBH",
    "AD": "AD",
    "NRS": "NRS",
    "IGA": "IGA",
    "EASI": "EASI",
}

_NOT_OUTCOME_PHRASES = {
    "confidence interval",
    "mean difference",
    "standardized mean difference",
    "odds ratio",
    "hazard ratio",
    "relative risk",
    "risk ratio",
    "incidence rate ratio",
    "win ratio",
    "ml per minute per 1.73 m2 of body-surface area per year",
    "ml per minute per 1.73 m² of body-surface area per year",
    "ml per minute per 1.73 m2 per year",
    "ml per minute per 1.73 m² per year",
    "new york heart association class ii, iii, or iv heart failure",
    "new york heart association class ii, iii, or iv",
    "class ii, iii, or iv heart failure",
    "class ii-iv heart failure",
    "class ii, iii, or iv",
}


def render_clinical_units(text: str) -> str:
    """Canonical Turkish units. The source numbers stay outside this replacement."""

    def _unit(match: re.Match) -> str:
        yearly = bool(re.search(r"year", match.group(0), re.IGNORECASE))
        return "mL/dk/1,73 m²/yıl" if yearly else "mL/dk/1,73 m²"

    return _SLOPE_UNIT_RE.sub(_unit, text or "")


def _has_stray_outcome_punctuation(text: str) -> bool:
    """Commas, stray slashes, and sentence marks are not part of an outcome name."""
    cleaned = re.sub(r"\bIGA\s*0/1\b", "IGA01", text or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"\bEASI-?75\b", "EASI75", cleaned, flags=re.IGNORECASE)
    return bool(re.search(r"[,:;]|/(?!\d)|/\.|\.$", cleaned))


def _phrase_translation(lowered: str):
    """Turkish text when the whole string is one controlled phrase."""
    for source, turkish in _PHRASES:
        if lowered == source and source not in _NOT_OUTCOME_PHRASES:
            return turkish
    return ""


def translate_controlled_outcome(text: str) -> str:
    """Turkish outcome name only when the whole span is controlled terminology.

    Unknown words are not dropped and the remainder is not shown. An empty
    string means the caller should use the unnamed-outcome label.
    """
    raw = re.sub(r"\s+", " ", (text or "")).strip(" .;:")
    if not raw or _has_stray_outcome_punctuation(raw):
        return ""
    lowered = raw.lower()
    exact = _phrase_translation(lowered)
    if exact:
        return exact
    if lowered in _SINGLE_OUTCOME_TR:
        return _SINGLE_OUTCOME_TR[lowered]
    parts = raw.split()
    if len(parts) < 2:
        return ""
    rendered = []
    for part in parts:
        token = part.strip(",.;:")
        low = token.lower()
        if not token or low in _GENERIC_OUTCOME_EN:
            return ""
        phrase = _phrase_translation(low)
        if phrase:
            rendered.append(phrase)
            continue
        if low in _SINGLE_OUTCOME_TR:
            rendered.append(_SINGLE_OUTCOME_TR[low])
            continue
        anti = re.fullmatch(r"anti-([A-Za-z0-9]+)", token, flags=re.IGNORECASE)
        if anti:
            rendered.append("anti-" + anti.group(1).upper())
            continue
        if re.fullmatch(r"EASI-?75", token, flags=re.IGNORECASE):
            rendered.append("EASI-75")
            continue
        if re.fullmatch(r"IGA\s*0/1", token, flags=re.IGNORECASE):
            rendered.append("IGA 0/1")
            continue
        upper = token.upper()
        if upper in _CLOSED_OUTCOME_ABBREV and token.isupper():
            rendered.append(_CLOSED_OUTCOME_ABBREV[upper])
            continue
        return ""
    return " ".join(rendered)


def nearest_controlled_outcome(text: str) -> str:
    """Rightmost controlled outcome phrase inside a clause, or empty.

    Modifiers around the phrase are not translated. A function word or a
    generic noun is not returned on its own.
    """
    raw = re.sub(r"\s+", " ", (text or ""))
    if not raw.strip():
        return ""
    lowered = raw.lower()
    found = []
    for source, turkish in _PHRASES:
        if source in _NOT_OUTCOME_PHRASES or not turkish:
            continue
        for match in re.finditer(r"\b" + re.escape(source) + r"\b", lowered):
            found.append((match.end(), match.end() - match.start(), source))
    for source in _SINGLE_OUTCOME_TR:
        for match in re.finditer(r"\b" + re.escape(source) + r"\b", lowered):
            found.append((match.end(), match.end() - match.start(), match.group(0)))
    if not found:
        return ""
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return found[0][2]


def outcome_label_rejected(shown: str) -> bool:
    """Function words, generic nouns, and stray punctuation are not outcome names."""
    text = re.sub(r"\s+", " ", (shown or "")).strip(" .")
    if not text:
        return True
    if _has_stray_outcome_punctuation(text):
        return True
    tokens = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşüıİ0-9/+-]+", text)
    generic = {
        "birey", "bireyler", "hasta", "hastalar", "dahil", "anlamlı",
        "grup", "gruplar", "kişi", "kişiler", "katılımcı", "katılımcılar",
    }
    if not tokens:
        return True
    if tokens[0].casefold() in generic:
        return True
    if len(tokens) == 1 and tokens[0].casefold() in generic:
        return True
    return False


def localize_clinical_display(text: str, drop_unknown: bool = True) -> str:
    """Turkish display text. Unsafe English tokens are left out.

    An empty string means nothing safe remained. Callers decide the Turkish
    fallback. Balanced brackets and numbers are preserved.
    """
    raw = render_clinical_units(re.sub(r"\s+", " ", (text or "")).strip())
    if not raw:
        return ""
    if _brackets_unbalanced(raw):
        return ""
    working = re.sub(r"(?i)\bs\.?\s?d\.", "SS", raw)
    placeholders = []

    def _protect(turkish: str) -> str:
        placeholders.append(turkish)
        return f"\x00{len(placeholders) - 1}\x00"

    def _anti_short(match: re.Match) -> str:
        body = match.group(1)
        canon = _ABBREV.get(body.lower(), body.upper())
        return _protect("anti-" + canon)

    working = _ANTI_PAREN_RE.sub(_anti_short, working)

    for source, turkish in _PHRASES:
        pattern = re.compile(r"\b" + re.escape(source) + r"\b", re.IGNORECASE)
        working = pattern.sub(lambda _match, rendered=turkish: _protect(rendered), working)

    working = _TOKEN_RE.sub(
        lambda match: _map_token(match.group(0), drop_unknown=drop_unknown),
        working,
    )
    working = _PLACEHOLDER_RE.sub(lambda match: placeholders[int(match.group(1))], working)
    working = re.sub(r"\s+([,.;:)\]])", r"\1", working)
    working = re.sub(r"([(\[])\s+", r"\1", working)
    working = re.sub(r"\(\s*\)", "", working)
    working = re.sub(r"\[\s*\]", "", working)
    working = re.sub(r"\s{2,}", " ", working).strip(" ,;:")
    if not working or not re.search(r"[0-9A-Za-zÇĞİÖŞÜçğıöşüıİ]", working):
        return ""
    if _brackets_unbalanced(working):
        return ""
    for pattern, replacement in _POSSESSIVE_REPAIRS:
        working = pattern.sub(replacement, working)
    working = re.sub(r"\b(başına)(?:\s+\1)+\b", r"\1", working, flags=re.IGNORECASE)
    working = re.sub(r"\({2,}", "(", working)
    working = re.sub(r"\){2,}", ")", working)
    return working


def _is_display_abbreviation(token: str) -> bool:
    """Clinical abbreviations stay abbreviations and are not leftover English."""
    if not token:
        return False
    if token.isupper() and 2 <= len(token) <= 12:
        return True
    if re.fullmatch(
        r"(?i)(?:hba1c|egfr|uacr|hfref|hfpef|sglt2i?|arni|mra|acei|arb|ckd|hhf|cv|hf|bb|"
        r"rr|hr|or|ci|md|smd|irr|wmd|ivig|ana|ck)",
        token,
    ):
        return True
    uppers = sum(1 for char in token if char.isupper())
    return bool(
        uppers >= 2
        and len(token) <= 12
        and re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", token)
    )


def has_untranslated_english(text: str) -> bool:
    """True when an English content word survived display translation."""
    for token in _TOKEN_RE.findall(text or ""):
        if _DIACRITIC_RE.search(token) or _is_display_abbreviation(token):
            continue
        lowered = token.lower()
        if lowered in _LEFTOVER_ENGLISH:
            return True
        mapped = _WORDS.get(lowered)
        if mapped is None:
            continue
        if mapped == "" or mapped.lower() != lowered:
            return True
    return False


def has_mixed_clinical_language(text: str) -> bool:
    """True when Turkish display text still contains an English content word.

    An all-English fragment is not mixed. A half-translated population such as
    "type 2 diyabet" or "chronic kidney hastalık" is mixed and must not be shown.
    """
    if not has_untranslated_english(text):
        return False
    raw = text or ""
    if _DIACRITIC_RE.search(raw):
        return True
    lowered = raw.lower()
    markers = (
        "hasta", "katılımcı", "katilimci", "yaş", "yaşında", "yasinda",
        "kadın", "erkek", "diyabet", "kalp", "böbrek", "bobrek", "ölüm",
        "sonlanım", "sonlanim", "tedavi", "inhibitör", "yetersiz",
        "arasında", "arasinda", "neden", "bağlı", "bagli", "oranı", "orani",
        "hastalık", "hastalik",
    )
    return any(marker in lowered for marker in markers)


def display_study_field(value: str, fallback: str = "Belirtilmedi", drop_unknown: bool = True) -> str:
    """Study-card field. Known sentinels stay. Unsafe English becomes the fallback.

    Population names use ``drop_unknown=False`` so an unmapped disease word is
    kept instead of being reduced to a bare sample-size parenthesis.
    """
    text = (value or "").strip()
    if not text:
        return fallback
    if text in _PASSTHROUGH_FIELDS:
        return text
    shown = localize_clinical_display(text, drop_unknown=drop_unknown)
    return shown or fallback

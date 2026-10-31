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
    ("statin-induced anti-hmgcr antibody imnm", "statin ilişkili anti-HMGCR antikor pozitif İMNM"),
    ("statin-induced anti-hmgcr antibody", "statin ilişkili anti-HMGCR antikoru"),
    ("immune-mediated necrotizing myopathy", "immün aracılı nekrotizan miyopati"),
    ("immune-mediated necrotizing myositis", "immün aracılı nekrotizan miyozit"),
    ("idiopathic inflammatory myopathy", "idiyopatik inflamatuar miyopati"),
    ("idiopathic inflammatory myositis", "idiyopatik inflamatuar miyozit"),
    ("standardized mean difference", "standartlaştırılmış ortalama fark"),
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
    ("proximal muscle weakness", "proksimal kas güçsüzlüğü"),
    ("interstitial lung disease", "interstisyel akciğer hastalığı"),
    ("significant group difference", "anlamlı grup farkı"),
    ("waist circumference", "bel çevresi"),
    ("incidence rate ratio", "insidans hız oranı"),
    ("inflammatory myopathy", "inflamatuar miyopati"),
    ("inflammatory myositis", "inflamatuar miyozit"),
    ("necrotizing myopathy", "nekrotizan miyopati"),
    ("necrotising myopathy", "nekrotizan miyopati"),
    ("confidence interval", "güven aralığı"),
    ("mean difference", "ortalama fark"),
    ("heart failure", "kalp yetersizliği"),
    ("muscle weakness", "kas güçsüzlüğü"),
    ("creatine kinase", "kreatin kinaz"),
    ("diabetes mellitus", "diyabet"),
    ("anti-hmgcr antibody", "anti-HMGCR antikoru"),
    ("odds ratio", "odds oranı"),
    ("hazard ratio", "tehlike oranı"),
    ("relative risk", "göreli risk"),
    ("risk ratio", "risk oranı"),
    ("win ratio", "win oranı"),
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
    ("major bleeding", "majör kanama"),
    ("minor bleeding", "minör kanama"),
    ("device-related thrombus", "aygıt ilişkili trombüs (DRT)"),
    ("device related thrombus", "aygıt ilişkili trombüs (DRT)"),
    ("device-related thrombosis", "aygıt ilişkili tromboz"),
    ("left atrial appendage occlusion", "sol atriyal apendiks oklüzyonu (LAAO)"),
    ("left atrial appendage closure", "sol atriyal apendiks kapatılması"),
    ("left atrial appendage", "sol atriyal apendiks"),
    ("atrial fibrillation", "atriyal fibrilasyon"),
    ("direct oral anticoagulant", "direkt oral antikoagülan (DOAC)"),
    ("direct oral anticoagulants", "direkt oral antikoagülanlar (DOAC'lar)"),
    ("patients in the doac group had a lower rate of drt", "DOAC grubundaki hastalarda daha düşük aygıt ilişkili trombüs (DRT) oranı"),
    ("patients in doac group had lower rate of drt", "DOAC grubundaki hastalarda daha düşük aygıt ilişkili trombüs (DRT) oranı"),
    ("patients doac group lower rate drt", "DOAC grubundaki hastalarda daha düşük aygıt ilişkili trombüs (DRT) oranı"),
    ("doac group", "DOAC grubu"),
    ("warfarin group", "varfarin grubu"),
    ("control group", "kontrol grubu"),
    ("major adverse cardiac events", "majör advers kardiyak olaylar (MACE)"),
    ("major adverse cardiovascular events", "majör advers kardiyovasküler olaylar (MACE)"),
    ("adverse events", "advers olaylar"),
    ("adverse event", "advers olay"),
    ("side effects", "yan etkiler"),
    ("side effect", "yan etki"),
    ("ischemic stroke", "iskemik inme"),
    ("hemorrhagic stroke", "hemorajik inme"),
    ("systemic embolism", "sistemik emboli"),
    ("lower rate of drt", "daha düşük DRT oranı"),
    ("higher rate of drt", "daha yüksek DRT oranı"),
    ("lower rate of", "daha düşük"),
    ("higher rate of", "daha yüksek"),
    ("rate of drt", "DRT oranı"),
)

_PHRASES = tuple(sorted(_PHRASE_PAIRS, key=lambda item: len(item[0]), reverse=True))

# Empty string means the English token is a function word and is not shown.
_WORDS = {
    "drt": "aygıt ilişkili trombüs (DRT)",
    "doac": "DOAC",
    "doacs": "DOAC'lar",
    "noac": "NOAC",
    "noacs": "NOAC'lar",
    "bleeding": "kanama",
    "thrombus": "trombüs",
    "thrombi": "trombüsler",
    "thrombosis": "tromboz",
    "thromboembolism": "tromboembolizm",
    "occlusion": "oklüzyon",
    "closure": "kapatma",
    "anticoagulation": "antikoagülasyon",
    "anticoagulant": "antikoagülan",
    "anticoagulants": "antikoagülanlar",
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
    "hospitalisation": "hastaneye yatış",
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
    "win": "win",
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
_TOKEN_RE = re.compile(
    r"[A-Za-zÇĞİÖŞÜçğıöşüıİ]+(?:-[A-Za-z0-9ÇĞİÖŞÜçğıöşüıİ]+)*"
)
_DIACRITIC_RE = re.compile(r"[çğıöşüÇĞİÖŞÜıİ]")
_ANTI_RE = re.compile(r"(?i)^anti-([A-Za-z0-9]+)$")
_PLACEHOLDER_RE = re.compile(r"\x00(\d+)\x00")

UNTRANSLATED_OUTCOME_LABEL = "Sonlanım adı güvenle çevrilemedi"

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


def localize_clinical_display(text: str, drop_unknown: bool = True) -> str:
    """Turkish display text. Unsafe English tokens are left out.

    An empty string means nothing safe remained. Callers decide the Turkish
    fallback. Balanced brackets and numbers are preserved.
    """
    raw = re.sub(r"\s+", " ", (text or "")).strip()
    if not raw:
        return ""
    if _brackets_unbalanced(raw):
        return ""
    working = re.sub(r"(?i)\bs\.?\s?d\.", "SS", raw)
    placeholders = []

    def _protect(turkish: str) -> str:
        placeholders.append(turkish)
        return f"\x00{len(placeholders) - 1}\x00"

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

    # Clean up fragmented/awkward Turkish translation patterns
    working = re.sub(r"(?i)\bhastalar\s+DOAC\s+grup\s+daha\s+düşük\s+oran\s+DRT\b", "DOAC grubundaki hastalarda daha düşük aygıt ilişkili trombüs (DRT) oranı", working)
    working = re.sub(r"(?i)\bhastalar\s+([A-Za-z0-9\-]+)\s+grup\b", r"\1 grubundaki hastalar", working)

    if not working or not re.search(r"[0-9A-Za-zÇĞİÖŞÜçğıöşüıİ]", working):
        return ""
    if _brackets_unbalanced(working):
        return ""
    return working


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

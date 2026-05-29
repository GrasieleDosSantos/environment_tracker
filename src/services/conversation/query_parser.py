"""Natural-language query parser for environmental questions.

``parse_query(text)`` returns a ``ParsedQuery`` with structured fields
extracted from a free-text question in Portuguese or English.

Each entity is extracted in two passes:
  1. Fast rule-based pass (keyword matching, regex).
  2. Single batched LLM call for any fields that remain uncertain or empty,
     provided the text is long enough to yield meaningful extraction (≥3 words).
     Rule-based results always take precedence; LLM only fills gaps.

For ambiguous terms like "São Paulo" (state vs. city) the parser
sets ``needs_clarification=True`` and populates ``clarification_options``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from src.config.constants import BIOMES, STATE_CODES, STATES

# ------------------------------------------------------------------ #
# Result type                                                           #
# ------------------------------------------------------------------ #

@dataclass
class ParsedQuery:
    """Structured representation of a parsed user query."""

    raw_text: str
    language: str = "pt"                    # "pt" or "en"
    states: list[str] = field(default_factory=list)       # UF codes e.g. ["AM", "PA"]
    biomes: list[str] = field(default_factory=list)       # biome IDs e.g. ["amazonia"]
    metrics: list[str] = field(default_factory=list)      # "fire", "deforestation", "vegetation"
    temporal_scope: str | None = None       # e.g. "last_7_days", "last_30_days", "last_year"
    needs_clarification: bool = False
    clarification_options: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ #
# Language detection                                                    #
# ------------------------------------------------------------------ #

_PT_MARKERS = frozenset([
    "qual", "quais", "como", "onde", "quando", "quanto", "quantos",
    "está", "estão", "tem", "têm", "são", "foi", "foram", "há",
    "situação", "dados", "queimadas", "incêndio", "desmatamento",
    "floresta", "bioma", "estado", "região", "últimas", "último",
    "semana", "mês", "ano", "hoje", "ontem", "atual", "atualmente",
    "cerrado", "amazônia", "caatinga", "pantanal", "pampa",
])

_EN_MARKERS = frozenset([
    "what", "which", "how", "where", "when", "show", "tell", "give",
    "is", "are", "was", "were", "has", "have", "fire", "fires",
    "deforestation", "forest", "biome", "state", "region",
    "last", "week", "month", "year", "today", "yesterday",
    "current", "currently", "amazon", "cerrado", "caatinga",
])

_LANG_CONFIDENCE_THRESHOLD = 2  # min |pt_score - en_score| to trust rule-based result


def _detect_language(text: str) -> tuple[str, int]:
    """Return (language, confidence) where confidence = abs(pt_score - en_score)."""
    words = set(re.findall(r"\b\w+\b", text.lower()))
    pt_score = len(words & _PT_MARKERS)
    en_score = len(words & _EN_MARKERS)
    lang = "en" if en_score > pt_score else "pt"
    return lang, abs(pt_score - en_score)


# ------------------------------------------------------------------ #
# Geographic extraction                                                 #
# ------------------------------------------------------------------ #

# Build lookup: lower-case full state name / sigla → UF code
_STATE_LOOKUP: dict[str, str] = {}
for _code, _name in STATES.items():
    _STATE_LOOKUP[_code.lower()] = _code
    _STATE_LOOKUP[_name.lower()] = _code

# Biome keyword map (PT + EN)
_BIOME_KEYWORDS: dict[str, list[str]] = {
    "amazonia":      ["amazônia", "amazonia", "amazon", "amazônico", "amazônica"],
    "cerrado":       ["cerrado"],
    "caatinga":      ["caatinga"],
    "mata_atlantica":["mata atlântica", "mata atlantica", "atlantic forest"],
    "pampa":         ["pampa", "pampas"],
    "pantanal":      ["pantanal"],
}

# Ambiguous terms that could mean a state or something else
_AMBIGUOUS: dict[str, list[str]] = {
    "são paulo": [
        "Estado de São Paulo (SP) — state",
        "Cidade de São Paulo — city (only state data available)",
    ],
    "rio": [
        "Rio de Janeiro (RJ) — state",
        "Rio Grande do Norte (RN)",
        "Rio Grande do Sul (RS)",
    ],
}

# Amazônia Legal virtual region → expand to 9 states
_AMAZONIA_LEGAL = ["AC", "AM", "AP", "MA", "MT", "PA", "RO", "RR", "TO"]

_AMAZON_LEGAL_KEYWORDS = [
    "amazônia legal", "amazonia legal", "legal amazon", "legal amazon region",
]


def _extract_states(text: str) -> tuple[list[str], bool, list[str]]:
    """Return (state_codes, needs_clarification, clarification_options)."""
    text_lower = text.lower()
    found: list[str] = []

    # Amazônia Legal shortcut
    for kw in _AMAZON_LEGAL_KEYWORDS:
        if kw in text_lower:
            return _AMAZONIA_LEGAL, False, []

    # Extract all unambiguous states first via word-boundary match
    for key, code in _STATE_LOOKUP.items():
        if re.search(r"\b" + re.escape(key) + r"\b", text_lower):
            if code not in found:
                found.append(code)

    # Only check for ambiguous terms when no clear state was already found.
    # Also require word-boundary so "rio" does not match inside "período".
    if not found:
        for phrase, choices in _AMBIGUOUS.items():
            if re.search(r"\b" + re.escape(phrase) + r"\b", text_lower):
                return [], True, choices

    return found, False, []


def _extract_biomes(text: str) -> list[str]:
    text_lower = text.lower()
    found: list[str] = []
    for biome_id, keywords in _BIOME_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                if biome_id not in found:
                    found.append(biome_id)
                break
    return found


# ------------------------------------------------------------------ #
# Metric extraction                                                     #
# ------------------------------------------------------------------ #

_METRIC_KEYWORDS: dict[str, list[str]] = {
    "fire": [
        "queimada", "queimadas", "foco", "focos", "incêndio", "incêndios",
        "fogo", "fogos", "calor", "fire", "fires", "hotspot", "hotspots", "burning",
    ],
    "deforestation": [
        "desmatamento", "desmatar", "desflorestamento", "alerta", "alertas",
        "deter", "prodes", "deforestation", "clearing", "cleared",
    ],
    "vegetation": [
        "vegetação", "cobertura vegetal", "floresta", "bioma",
        "vegetation", "forest", "cover", "green",
    ],
}


def _extract_metrics(text: str) -> list[str]:
    text_lower = text.lower()
    found: list[str] = []
    for metric, keywords in _METRIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                if metric not in found:
                    found.append(metric)
                break
    return found


# ------------------------------------------------------------------ #
# Temporal scope                                                        #
# ------------------------------------------------------------------ #

_u = r"[uú]"   # matches u or ú (accented/unaccented)
_a = r"[aá]"   # matches a or á

_TEMPORAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(hoje|today|agora|now)\b", re.I), "last_1_day"),
    (re.compile(r"\b(ontem|yesterday)\b", re.I), "last_1_day"),
    (re.compile(_u + r"ltimas?\s*(24|48)\s*h(oras?)?|last\s*(24|48)\s*h(ours?)?", re.I), "last_1_day"),
    (re.compile(_u + r"ltimos?\s*[37]\s*dias?|last\s*[37]\s*days?", re.I), "last_7_days"),
    (re.compile(r"\b(essa?\s*semana|esta\s*semana|this\s*week)\b", re.I), "last_7_days"),
    (re.compile(_u + r"ltimas?\s*duas\s*semanas?|last\s*2\s*weeks?", re.I), "last_14_days"),
    (re.compile(
        _u + r"ltimos?\s*30\s*dias?|last\s*30\s*days?|n?esse?\s*m[eê]s|n?este\s*m[eê]s|this\s*month",
        re.I,
    ), "last_30_days"),
    (re.compile(
        _u + r"ltimos?\s*[39]0\s*dias?|last\s*[39]0\s*days?|" + _u + r"ltimos?\s*3\s*meses?",
        re.I,
    ), "last_90_days"),
    (re.compile(r"\b(esse?\s*ano|este\s*ano|this\s*year|ano\s*atual)\b", re.I), "last_year"),
    (re.compile(_u + r"ltimos?\s*12\s*meses?|last\s*12\s*months?", re.I), "last_12_months"),
    # Multi-year ranges — matched before month patterns to avoid false positives
    (re.compile(_u + r"ltimos?\s*[23]\s*anos?|last\s*[23]\s*years?", re.I), "last_3_years"),
    (re.compile(_u + r"ltimos?\s*[45]\s*anos?|last\s*[45]\s*years?", re.I), "last_5_years"),
    (re.compile(_u + r"ltimos?\s*[67]\s*anos?|last\s*[67]\s*years?", re.I), "last_7_years"),
    (re.compile(
        _u + r"ltimos?\s*(?:8|9|10|11|12|13|14|15|20)\s*anos?"
        r"|last\s*(?:8|9|10|11|12|13|14|15|20)\s*years?",
        re.I,
    ), "last_10_years"),
    # Month names (PT + EN) — treated as "last 30 days" approximation
    (re.compile(
        r"\b(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
        r"|january|february|march|april|may|june|july|august|september|october|november|december)\b",
        re.I,
    ), "last_30_days"),
]


def _extract_temporal(text: str) -> str | None:
    for pattern, scope in _TEMPORAL_PATTERNS:
        if pattern.search(text):
            return scope
    return None


# ------------------------------------------------------------------ #
# LLM fallback — batched extraction                                     #
# ------------------------------------------------------------------ #

_VALID_BIOME_IDS: frozenset[str] = frozenset(b["id"] for b in BIOMES)
_VALID_METRICS: frozenset[str] = frozenset(["fire", "deforestation", "vegetation"])
_VALID_TEMPORAL_SCOPES: frozenset[str] = frozenset([
    "last_1_day", "last_7_days", "last_14_days", "last_30_days",
    "last_90_days", "last_year", "last_12_months",
    "last_3_years", "last_5_years", "last_7_years", "last_10_years",
])

_LLM_ENTITY_SYSTEM_PROMPT = """\
You are an entity extractor for an environmental monitoring chatbot about Brazil.
Extract ONLY the fields listed by the user. Return a single valid JSON object — no markdown, no explanation.

Available fields and their allowed values:
- "language": "pt" (Portuguese) or "en" (English)
- "states": list of Brazilian 2-letter UF codes, e.g. ["AM", "PA"]. [] if none mentioned.
- "biomes": list from {amazonia, cerrado, caatinga, mata_atlantica, pampa, pantanal}. [] if none mentioned.
- "metrics": list from {fire, deforestation, vegetation}. [] if none clearly mentioned.
- "temporal_scope": one of {last_1_day, last_7_days, last_14_days, last_30_days,
  last_90_days, last_year, last_12_months} — or null if no time frame is specified.

Rules:
- Only include the requested fields in your response.
- Never invent values — return [] or null when an entity is not present in the text.
- For states: also recognise colloquial names, abbreviations, and indirect references
  (e.g. "floresta amazônica" → states in Amazônia Legal; "nordeste" → NE states).
- For biomes: also recognise indirect references (e.g. "a savana brasileira" → cerrado).
- For temporal_scope: interpret relative expressions and map them to the closest value
  (e.g. "semana passada" → last_7_days, "ontem" → last_1_day, "ano passado" → last_year).\
"""


def _llm_extract_entities(text: str, missing: set[str]) -> dict:
    """Single LLM call to extract all uncertain/missing entities at once.

    Returns a dict with only the requested fields populated.
    Any exception silently returns {}, preserving rule-based results.
    """
    if not missing:
        return {}
    try:
        from src.services.llm_provider import LLMMessage, get_llm_provider
        provider = get_llm_provider()
        fields_list = ", ".join(sorted(missing))
        response = provider.chat(
            [
                LLMMessage.system(_LLM_ENTITY_SYSTEM_PROMPT),
                LLMMessage.user(f"Extract these fields: {fields_list}\n\nQuery: {text}"),
            ],
            temperature=0,
            max_tokens=150,
        )
        content = response.content.strip()
        # Strip markdown code fences if the model adds them
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception:
        return {}


def _merge_llm_entities(
    text: str,
    missing: set[str],
    lang: str,
    states: list[str],
    biomes: list[str],
    metrics: list[str],
    temporal_scope: str | None,
) -> tuple[str, list[str], list[str], list[str], str | None]:
    """Call LLM for missing entities and merge results with rule-based values.

    Rule-based results always win; LLM fills only empty/uncertain slots.
    All LLM values are validated against known allowed sets before use.
    """
    llm = _llm_extract_entities(text, missing)
    if not llm:
        return lang, states, biomes, metrics, temporal_scope

    if "language" in missing:
        candidate = str(llm.get("language", "")).strip().lower()
        if candidate in ("pt", "en"):
            lang = candidate

    if "states" in missing and not states:
        raw = llm.get("states", [])
        if isinstance(raw, list):
            states = [s.upper() for s in raw if isinstance(s, str) and s.upper() in STATE_CODES]

    if "biomes" in missing and not biomes:
        raw = llm.get("biomes", [])
        if isinstance(raw, list):
            biomes = [b for b in raw if isinstance(b, str) and b in _VALID_BIOME_IDS]

    if "metrics" in missing and not metrics:
        raw = llm.get("metrics", [])
        if isinstance(raw, list):
            metrics = [m for m in raw if isinstance(m, str) and m in _VALID_METRICS]

    if "temporal_scope" in missing and temporal_scope is None:
        candidate = llm.get("temporal_scope")
        if candidate in _VALID_TEMPORAL_SCOPES:
            temporal_scope = candidate

    return lang, states, biomes, metrics, temporal_scope


# ------------------------------------------------------------------ #
# Public API                                                            #
# ------------------------------------------------------------------ #

def parse_query(text: str) -> ParsedQuery:
    """Parse a free-text environmental query and return a ``ParsedQuery``.

    Pipeline:
      1. Rule-based extraction for all entities (fast, no API call).
      2. Collect entities that are uncertain or empty.
      3. If any gaps exist and the text is substantive (≥3 words), fire a
         single batched LLM call to fill them all at once.
      4. Validate and merge LLM results; rule-based values always win.
    """
    # --- Pass 1: rule-based ---
    states, needs_clarification, clarification_options = _extract_states(text)
    biomes = _extract_biomes(text)
    metrics = _extract_metrics(text)
    temporal_scope = _extract_temporal(text)
    lang, lang_confidence = _detect_language(text)

    # --- Determine gaps ---
    missing: set[str] = set()
    if lang_confidence < _LANG_CONFIDENCE_THRESHOLD:
        missing.add("language")
    if not states and not needs_clarification:
        missing.add("states")
    if not biomes:
        missing.add("biomes")
    if not metrics:
        missing.add("metrics")
    if temporal_scope is None:
        missing.add("temporal_scope")

    # --- Pass 2: LLM fallback (one call for all gaps) ---
    # Skip for very short inputs — not enough context for the LLM to add value.
    if missing and len(text.split()) >= 3:
        lang, states, biomes, metrics, temporal_scope = _merge_llm_entities(
            text, missing, lang, states, biomes, metrics, temporal_scope
        )

    return ParsedQuery(
        raw_text=text,
        language=lang,
        states=states,
        biomes=biomes,
        metrics=metrics or ["fire", "deforestation"],
        temporal_scope=temporal_scope,
        needs_clarification=needs_clarification,
        clarification_options=clarification_options,
    )

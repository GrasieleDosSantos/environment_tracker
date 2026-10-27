"""ConversationService — linear pipeline for environmental queries.

Pipeline:
  parse_query → retrieve_data → build_prompt → llm_call → update_session

All LLM calls go through ``LLMProvider`` and are traced via
``@trace_llm_call``.  LangGraph is the documented post-MVP upgrade path
for multi-step branching flows but is not implemented here.

Usage::

    svc = ConversationService()
    session_id = svc.start_session()
    reply = svc.chat("Qual é a situação de queimadas no Cerrado?", session_id)
    print(reply.text)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.services.conversation.langfuse_wrapper import trace_llm_call
from src.services.conversation.prompts import build_system_prompt
from src.services.conversation.query_parser import ParsedQuery, parse_query
from src.services.conversation.response_generator import (
    add_citations,
    format_data_context,
    format_deforestation_detail,
    format_fire_detail,
    format_freshness_warning,
    format_prodes_detail,
)
from src.services.conversation.session_manager import (
    add_message,
    create_session,
    get_context,
    update_context_data,
)
from src.services.llm_provider import LLMMessage, LLMResponse, get_llm_provider


# ------------------------------------------------------------------ #
# Follow-up detection                                                   #
# ------------------------------------------------------------------ #

# Deictic / anaphoric words that signal the user is referring to a result
# from the *previous* answer rather than introducing a new geographic scope.
_FOLLOWUP_SIGNALS: frozenset[str] = frozenset([
    # Portuguese
    "esses", "essas", "eles", "elas", "esse", "essa", "isso", "isto",
    "lá", "ali", "aí", "nesse", "nessa", "neles", "nelas",
    "deles", "delas", "desse", "dessa", "dele", "dela",
    "específico", "específica", "especificamente", "mencionado", "mencionada",
    "citado", "citada", "referido", "referida",
    # English
    "these", "those", "they", "them", "there", "it", "that",
    "specifically", "mentioned", "referenced", "said",
])


def _is_followup(text: str) -> bool:
    """Return True when the message contains deictic/anaphoric follow-up signals."""
    words = set(__import__("re").findall(r"\b\w+\b", text.lower()))
    return bool(words & _FOLLOWUP_SIGNALS)


# ------------------------------------------------------------------ #
# Featured entity extraction                                            #
# ------------------------------------------------------------------ #

def _extract_featured_entities(data: dict[str, Any]) -> dict[str, list[str]]:
    """Identify the primary states and biomes featured in the retrieved data.

    These are the entities the *answer* was about (e.g. the top state by fire
    count), which may differ from what the user explicitly asked for.  Stored
    separately so follow-up questions can inherit them.
    """
    from collections import Counter
    featured: dict[str, list[str]] = {}

    hotspots = data.get("hotspots", [])
    if hotspots:
        state_counts: Counter = Counter(h.state for h in hotspots if h.state)
        if state_counts:
            featured["states"] = [state_counts.most_common(1)[0][0]]
        biome_counts: Counter = Counter(h.biome for h in hotspots if h.biome)
        if biome_counts:
            featured["biomes"] = [biome_counts.most_common(1)[0][0]]

    alerts = data.get("alerts", [])
    if alerts and "states" not in featured:
        from collections import defaultdict
        area: dict[str, float] = defaultdict(float)
        for a in alerts:
            area[a.state or ""] += a.area_km2 or 0.0
        if area:
            featured["states"] = [max(area, key=area.get)]  # type: ignore[arg-type]

    return featured


# ------------------------------------------------------------------ #
# Result type                                                           #
# ------------------------------------------------------------------ #

@dataclass
class ConversationReply:
    text: str
    session_id: str
    parsed_query: ParsedQuery | None = None
    needs_clarification: bool = False
    clarification_options: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


# ------------------------------------------------------------------ #
# Data retrieval                                                        #
# ------------------------------------------------------------------ #

_DETER_COVERED_BIOMES: frozenset[str] = frozenset({"amazonia", "cerrado"})


def _retrieve_data(pq: ParsedQuery) -> dict[str, Any]:
    """Fetch INPE snapshot data relevant to the parsed query.

    Returns a dict with keys used by format_data_context / detail formatters.
    Falls back gracefully on any fetch error.

    Data sources:
    - FOGO (BDQueimadas): fire hotspots, always fetched when fire is a metric.
    - DETER: near-real-time deforestation alerts for Amazônia + Cerrado only.
    - PRODES: annual deforestation for all 6 biomes; fetched when the query
      targets non-DETER biomes (Pampa, Caatinga, Mata Atlântica, Pantanal),
      spans a year or more (annual trends), or DETER returns nothing.
    """
    from src.services.analysis.aggregator import aggregate_multi_source

    try:
        from src.services.inpe_integration.fogo_client import (
            fetch_current_hotspots,
            fetch_fire_risk,
        )
        from src.services.inpe_integration.deter_client import (
            fetch_deter_for_biomes,
            fetch_deter_time_series,
        )

        # Resolve geographic scope
        single_state = pq.states[0] if len(pq.states) == 1 else None
        multi_states = pq.states if len(pq.states) > 1 else None

        today = date.today()
        period = _resolve_period(pq, today)
        start, end = period.start, period.end
        # Fire history is only available as "last N days" ending today.
        fire_days = (end - start).days if end == today else 0
        if pq.target_year:
            use_fire_period = fire_days > 1
        else:
            use_fire_period = pq.temporal_scope not in (None, "last_1_day")

        # --- Fire hotspots ---
        hotspots_48h = fetch_current_hotspots(
            state=single_state, states=multi_states, count=5000
        )
        if use_fire_period:
            hotspots_period = fetch_fire_risk(
                state=single_state, states=multi_states, days=min(fire_days, 90)
            )
        else:
            hotspots_period = hotspots_48h

        # --- DETER alerts (Amazônia + Cerrado only) ---
        deter_biomes = [b for b in pq.biomes if b in _DETER_COVERED_BIOMES]
        if pq.biomes:
            if deter_biomes:
                alerts_raw = fetch_deter_for_biomes(
                    state=single_state,
                    biome_ids=deter_biomes,
                    start=start,
                    end=end,
                )
            else:
                # All requested biomes are non-DETER; skip DETER fetch entirely.
                alerts_raw = []
        else:
            # No biome filter — fetch both DETER-covered layers so state queries
            # get alerts from both Amazon and Cerrado (e.g. Tocantins has 98% of
            # its alerts in the Cerrado layer; uf= CQL filter ensures records are
            # state-specific and the two layers have no geographic overlap).
            alerts_raw = fetch_deter_for_biomes(
                state=single_state,
                biome_ids=["amazonia", "cerrado"],
                start=start,
                end=end,
            )

        # --- PRODES annual data ---
        # Fetch when deforestation is a metric and: non-DETER biomes are
        # requested, OR the scope spans a year or more (annual trends need
        # PRODES even for DETER biomes), OR DETER returned nothing.
        prodes_records: list = []
        prodes_rates: dict[int, float] = {}
        non_deter_biomes = [b for b in pq.biomes if b not in _DETER_COVERED_BIOMES]
        long_term = period.long_term
        need_prodes = (
            "deforestation" in (pq.metrics or [])
            and (bool(non_deter_biomes) or long_term or (not pq.biomes and not alerts_raw))
        )
        if need_prodes:
            from src.config.constants import BIOMES as _ALL_BIOMES
            if long_term and pq.biomes:
                prodes_biome_ids = list(pq.biomes)
            elif non_deter_biomes:
                prodes_biome_ids = non_deter_biomes
            else:
                prodes_biome_ids = [b["id"] for b in _ALL_BIOMES]
            from src.services.inpe_integration.prodes_dashboard import (
                fetch_legal_amazon_rates,
                fetch_prodes_annual_totals,
            )
            prodes_records = fetch_prodes_annual_totals(
                biome_ids=prodes_biome_ids,
                state=single_state,
                start_year=period.prodes_start,
                end_year=period.prodes_end,
            )
            if "amazonia" in prodes_biome_ids:
                prodes_rates = fetch_legal_amazon_rates(
                    start_year=period.prodes_start,
                    end_year=period.prodes_end,
                    state=single_state,
                )

        # --- Region label ---
        region_parts: list[str] = []
        if pq.biomes:
            from src.config.constants import BIOMES
            region_parts += [
                next((b["name"] for b in BIOMES if b["id"] == bid), bid)
                for bid in pq.biomes
            ]
        if pq.states:
            region_parts += pq.states
        region_label = ", ".join(region_parts) if region_parts else "Brasil"

        snapshot = aggregate_multi_source(
            deter_alerts=alerts_raw,
            fogo_hotspots_48h=hotspots_48h,
            fogo_hotspots_period=hotspots_period,
            region_label=region_label,
            period_start=start,
            period_end=end,
        )

        period_label = f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"
        if use_fire_period:
            fire_start = today - timedelta(days=min(fire_days, 90))
            fire_period_label = f"período {fire_start:%d/%m/%Y} – {today:%d/%m/%Y}"
        else:
            fire_period_label = "últimas 48h / last 48h"

        return {
            "fire_count_48h": snapshot.fire_count_48h,
            "fire_count_period": len(hotspots_period),
            "fire_period_label": fire_period_label,
            "deforestation_km2": snapshot.deforestation_km2,
            "deforestation_count": snapshot.deforestation_count,
            "fire_risk_label": snapshot.fire_risk_label_pt,
            "region_label": region_label,
            "period_label": period_label,
            "fetched_at": snapshot.fetched_at,
            "hotspots": hotspots_period,
            "hotspots_48h": hotspots_48h,
            "alerts": alerts_raw,
            "prodes_records": prodes_records,
            "prodes_rates": prodes_rates,
            "prodes_pending_year": (
                pq.target_year
                if need_prodes and pq.target_year and pq.target_year > period.prodes_end
                else None
            ),
            "prodes_latest_year": period.prodes_end,
        }

    except Exception:
        return {}


@dataclass
class _Period:
    start: date
    end: date
    long_term: bool
    prodes_start: int
    prodes_end: int


def _resolve_period(pq: ParsedQuery, today: date) -> _Period:
    """Resolve the DETER window and PRODES year range for a parsed query.

    An explicit year ("in 2026") covers Jan 1 – Dec 31 of that year, clipped
    to today, and always pulls PRODES. PRODES year N (Aug N-1 – Jul N) is only
    published around Nov/Dec of year N, so the range ends at the previous year.
    """
    latest_prodes = today.year - 1  # PRODES publishes previous year
    if pq.target_year:
        prodes_end = min(pq.target_year, latest_prodes)
        return _Period(
            start=date(pq.target_year, 1, 1),
            end=min(date(pq.target_year, 12, 31), today),
            long_term=True,
            prodes_start=prodes_end - 2,
            prodes_end=prodes_end,
        )
    period_days = _scope_to_days(pq.temporal_scope)
    return _Period(
        start=today - timedelta(days=period_days),
        end=today,
        long_term=period_days >= 365,
        prodes_start=today.year - _scope_to_prodes_years(pq.temporal_scope),
        prodes_end=latest_prodes,
    )


def _scope_to_days(scope: str | None) -> int:
    mapping = {
        "last_1_day": 1,
        "last_7_days": 7,
        "last_14_days": 14,
        "last_30_days": 30,
        "last_90_days": 90,
        "last_year": 365,
        "last_12_months": 365,
        "last_3_years": 365 * 3,
        "last_5_years": 365 * 5,
        "last_7_years": 365 * 7,
        "last_10_years": 365 * 10,
    }
    return mapping.get(scope or "", 30)


def _scope_to_prodes_years(scope: str | None) -> int:
    """Map temporal scope to years of PRODES annual data to fetch."""
    mapping = {
        "last_1_day": 2,
        "last_7_days": 2,
        "last_14_days": 2,
        "last_30_days": 2,
        "last_90_days": 3,
        "last_year": 3,
        "last_12_months": 3,
        "last_3_years": 3,
        "last_5_years": 5,
        "last_7_years": 7,
        "last_10_years": 10,
    }
    return mapping.get(scope or "", 5)


# ------------------------------------------------------------------ #
# LLM call (wrapped for tracing)                                        #
# ------------------------------------------------------------------ #

@trace_llm_call
def _call_llm(
    messages: list[LLMMessage],
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> LLMResponse:
    return get_llm_provider().chat(messages, temperature=temperature, max_tokens=max_tokens)


# ------------------------------------------------------------------ #
# ConversationService                                                   #
# ------------------------------------------------------------------ #

class ConversationService:
    """Stateless service; all state lives in the database via SessionManager."""

    def start_session(
        self,
        user_id: str | None = None,
        langfuse_session_id: str | None = None,
    ) -> str:
        """Create a new DB-backed session and return its ID."""
        return create_session(user_id=user_id, langfuse_session_id=langfuse_session_id)

    def chat(
        self,
        user_text: str,
        session_id: str,
        langfuse_session_id: str | None = None,
    ) -> ConversationReply:
        """Process one user message and return an assistant reply.

        Pipeline: parse → retrieve → build prompt → LLM → persist → return.
        """
        # 1. Parse
        pq = parse_query(user_text)

        if pq.needs_clarification:
            reply_text = _clarification_message(pq)
            add_message(session_id, "user", user_text)
            add_message(session_id, "assistant", reply_text)
            return ConversationReply(
                text=reply_text,
                session_id=session_id,
                parsed_query=pq,
                needs_clarification=True,
                clarification_options=pq.clarification_options,
            )

        # 2. Inherit geographic/temporal context from previous turns when
        #    the current message doesn't specify them explicitly.
        #
        #    Two inheritance pools:
        #      last_states       — what the *user* asked about last turn
        #      last_featured_states — what the *answer* was about (e.g. top state)
        #
        #    last_featured_* is only applied when follow-up signals are present
        #    ("esses focos", "those hotspots", etc.) to avoid incorrectly scoping
        #    unrelated new questions to a previously featured state.
        from src.services.conversation.session_manager import get_session_metadata
        meta = get_session_metadata(session_id) or {}
        ctx = meta.get("context_data", {})
        followup = _is_followup(user_text)

        if not pq.states:
            if ctx.get("last_states"):
                pq.states = ctx["last_states"]
            elif followup and ctx.get("last_featured_states"):
                pq.states = ctx["last_featured_states"]

        if not pq.biomes:
            if ctx.get("last_biomes"):
                pq.biomes = ctx["last_biomes"]
            elif followup and ctx.get("last_featured_biomes"):
                pq.biomes = ctx["last_featured_biomes"]

        if pq.temporal_scope is None and pq.target_year is None:
            if ctx.get("last_target_year"):
                pq.target_year = ctx["last_target_year"]
            elif ctx.get("last_temporal_scope"):
                pq.temporal_scope = ctx["last_temporal_scope"]

        # Retrieve INPE data
        data = _retrieve_data(pq)

        # 3. Build prompt
        fetched_at: datetime | None = data.get("fetched_at")
        system_content = build_system_prompt(fetched_at)

        data_block = format_data_context(
            fire_count_48h=data.get("fire_count_48h"),
            fire_count_period=data.get("fire_count_period"),
            fire_period_label=data.get("fire_period_label"),
            deforestation_km2=data.get("deforestation_km2"),
            deforestation_count=data.get("deforestation_count"),
            region_label=data.get("region_label", "Brasil"),
            period_label=data.get("period_label"),
            fire_risk_label=data.get("fire_risk_label"),
            fetched_at=fetched_at,
        )

        hotspots = data.get("hotspots", [])
        alerts = data.get("alerts", [])
        prodes_records = data.get("prodes_records", [])
        if "fire" in pq.metrics and hotspots:
            data_block += "\n\n" + format_fire_detail(hotspots)
        if "deforestation" in pq.metrics and alerts:
            data_block += "\n\n" + format_deforestation_detail(alerts)
        if "deforestation" in pq.metrics and prodes_records:
            data_block += "\n\n" + format_prodes_detail(
                prodes_records, rates=data.get("prodes_rates")
            )
        pending_year = data.get("prodes_pending_year")
        if pending_year:
            latest = data.get("prodes_latest_year")
            data_block += (
                f"\n\nNota PRODES / PRODES note: a taxa PRODES {pending_year} "
                f"(ago/{pending_year - 1}–jul/{pending_year}) ainda não foi publicada; "
                f"o INPE costuma divulgar a estimativa preliminar em novembro/dezembro. "
                f"Taxa mais recente disponível: PRODES {latest}. / "
                f"The PRODES {pending_year} rate (Aug {pending_year - 1}–Jul {pending_year}) "
                f"is not yet published; INPE usually releases the preliminary estimate in "
                f"Nov/Dec. Latest available rate: PRODES {latest} — report it as the most "
                f"recent annual figure."
            )

        # 4. Compose message list: system + history + data context + new user msg
        history = get_context(session_id)
        messages: list[LLMMessage] = [LLMMessage.system(system_content)]

        for msg in history[-10:]:    # keep last 10 turns to limit context size
            messages.append(LLMMessage(msg["role"], msg["content"]))

        # Inject current data as a user-turn context block before the question
        messages.append(
            LLMMessage.user(
                f"[Dados atuais do INPE / Current INPE data]\n\n{data_block}"
            )
        )
        messages.append(LLMMessage.user(user_text))

        # 5. LLM call
        llm_response = _call_llm(
            messages,
            langfuse_session_id=langfuse_session_id,
        )

        # 6. Post-process
        reply_text = add_citations(llm_response.content)
        if fetched_at:
            reply_text += format_freshness_warning(fetched_at)

        # 7. Persist
        featured = _extract_featured_entities(data)
        add_message(session_id, "user", user_text)
        add_message(session_id, "assistant", reply_text)
        update_context_data(session_id, {
            "last_states": pq.states,
            "last_biomes": pq.biomes,
            "last_metrics": pq.metrics,
            "last_temporal_scope": pq.temporal_scope,
            "last_target_year": pq.target_year,
            "language": pq.language,
            "last_featured_states": featured.get("states", []),
            "last_featured_biomes": featured.get("biomes", []),
        })

        return ConversationReply(
            text=reply_text,
            session_id=session_id,
            parsed_query=pq,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )


# ------------------------------------------------------------------ #
# Helpers                                                               #
# ------------------------------------------------------------------ #

def _clarification_message(pq: ParsedQuery) -> str:
    opts = "\n".join(f"- {o}" for o in pq.clarification_options)
    if pq.language == "en":
        return (
            "Your query is ambiguous. Did you mean one of the following?\n\n"
            f"{opts}\n\nPlease clarify and I'll fetch the right data."
        )
    return (
        "Sua pergunta é ambígua. Você quis dizer:\n\n"
        f"{opts}\n\nPor favor, esclareça para que eu possa buscar os dados corretos."
    )

"""Response formatting utilities for the conversation engine.

These functions convert structured INPE data into readable markdown
suitable for inclusion in an LLM prompt as data context, and post-process
LLM output to add citations and freshness information.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.config.settings import get_settings


# ------------------------------------------------------------------ #
# Data → markdown context                                              #
# ------------------------------------------------------------------ #

def format_data_context(
    fire_count_48h: int | None = None,
    fire_count_period: int | None = None,
    fire_period_label: str | None = None,
    deforestation_km2: float | None = None,
    deforestation_count: int | None = None,
    region_label: str = "Brasil",
    period_label: str | None = None,
    fire_risk_label: str | None = None,
    fetched_at: datetime | None = None,
) -> str:
    """Convert INPE snapshot metrics to a markdown block for the LLM prompt."""
    lines: list[str] = [
        f"## Dados INPE — {region_label}",
    ]

    if period_label:
        lines.append(f"**Período consultado**: {period_label}")

    if fetched_at:
        age_h = (datetime.now(timezone.utc) - fetched_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        lines.append(f"**Dados obtidos**: {fetched_at.strftime('%Y-%m-%d %H:%M')} UTC ({age_h:.1f}h atrás)")

    lines.append("")

    # Show period fire count with the correct label so the LLM never confuses
    # period data with 48h data.
    if fire_count_period is not None and fire_period_label:
        lines.append(f"- **Focos de calor ({fire_period_label})**: {fire_count_period:,}")
    if fire_count_48h is not None:
        lines.append(f"- **Focos de calor (últimas 48h)**: {fire_count_48h:,}")
    if fire_risk_label:
        lines.append(f"- **Nível de risco de fogo (48h)**: {fire_risk_label}")
    if deforestation_km2 is not None:
        lines.append(f"- **Área de alertas DETER**: {deforestation_km2:,.1f} km²")
    if deforestation_count is not None:
        lines.append(f"- **Número de alertas DETER**: {deforestation_count:,}")

    return "\n".join(lines)


def format_fire_detail(hotspots: list) -> str:
    """Summarise fire hotspot records: top-5 states and biome breakdown."""
    if not hotspots:
        return "*Sem focos de calor no período / No fire hotspots in period.*"

    from collections import Counter

    state_counts: Counter = Counter(h.state or "—" for h in hotspots)
    top5_states = state_counts.most_common(5)

    lines = ["**Focos por estado (top 5) / Hotspots by state (top 5)**"]
    lines += ["| Estado | Focos |", "|--------|-------|"]
    for state, count in top5_states:
        lines.append(f"| {state} | {count:,} |")

    # Biome breakdown — uses the biome field returned by BDQueimadas per hotspot.
    biome_counts: Counter = Counter(
        (h.biome or "Não informado").title() for h in hotspots
    )
    if biome_counts:
        total = sum(biome_counts.values())
        lines += [
            "",
            "**Focos por bioma / Hotspots by biome**",
            "| Bioma | Focos | % |",
            "|-------|-------|---|",
        ]
        for biome, count in biome_counts.most_common():
            pct = count / total * 100
            lines.append(f"| {biome} | {count:,} | {pct:.1f}% |")

    return "\n".join(lines)


def format_deforestation_detail(alerts: list) -> str:
    """Summarise DETER alerts: top-5 states by area, biome breakdown, and alert types."""
    if not alerts:
        return "*Sem alertas DETER no período / No DETER alerts in period.*"

    from collections import defaultdict, Counter

    state_area: dict[str, float] = defaultdict(float)
    biome_area: dict[str, float] = defaultdict(float)
    classname_counts: Counter = Counter()

    for a in alerts:
        state_area[a.state or "—"] += a.area_km2 or 0.0
        biome_area[(a.biome or "Não informado").title()] += a.area_km2 or 0.0
        if a.classname:
            classname_counts[a.classname] += 1

    top5_states = sorted(state_area.items(), key=lambda x: x[1], reverse=True)[:5]

    lines = ["**Alertas DETER por estado (top 5) / DETER alerts by state (top 5)**"]
    lines += ["| Estado | Área (km²) |", "|--------|------------|"]
    for state, area in top5_states:
        lines.append(f"| {state} | {area:,.1f} |")

    if biome_area:
        total_area = sum(biome_area.values())
        lines += [
            "",
            "**Área desmatada por bioma / Deforested area by biome**",
            "| Bioma | Área (km²) | % |",
            "|-------|------------|---|",
        ]
        for biome, area in sorted(biome_area.items(), key=lambda x: x[1], reverse=True):
            pct = area / total_area * 100 if total_area else 0
            lines.append(f"| {biome} | {area:,.1f} | {pct:.1f}% |")

    if classname_counts:
        lines += [
            "",
            "**Tipos de alerta / Alert types**",
            "| Tipo | Ocorrências |",
            "|------|-------------|",
        ]
        for cls, cnt in classname_counts.most_common():
            lines.append(f"| {cls} | {cnt:,} |")

    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Post-processing                                                       #
# ------------------------------------------------------------------ #

_INPE_CITATION = (
    "\n\n---\n*Fonte / Source: INPE — "
    "[DETER](https://terrabrasilis.dpi.inpe.br/) · "
    "[BDQueimadas](https://queimadas.dgi.inpe.br/) · "
    "[PRODES](http://www.obt.inpe.br/OBT/assuntos/programas/amazonia/prodes)*"
)


def add_citations(text: str) -> str:
    """Append INPE attribution footer if not already present."""
    if "INPE" in text and "Fonte" in text:
        return text
    return text + _INPE_CITATION


def format_freshness_warning(fetched_at: datetime) -> str:
    """Return a localised freshness warning string if data is stale."""
    settings = get_settings()
    age_h = (
        datetime.now(timezone.utc) - fetched_at.replace(tzinfo=timezone.utc)
    ).total_seconds() / 3600

    if age_h <= settings.data_freshness_warning_hours:
        return ""

    return (
        f"\n\n⚠️ **Aviso de frescor / Freshness warning**: "
        f"Os dados têm {age_h:.0f}h. Pode haver eventos mais recentes não refletidos aqui. "
        f"/ Data is {age_h:.0f}h old. Recent events may not be reflected."
    )

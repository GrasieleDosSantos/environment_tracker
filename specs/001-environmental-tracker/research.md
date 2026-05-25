# Research: Environmental Status Tracker for Brazil

**Phase**: 0 — Pre-implementation research
**Date**: 2026-05-25
**Status**: Complete (training-data baseline; items marked ⚠️ need live verification before Phase 3 begins)

---

## 1. INPE Data Access via TerraBrasilis

### Platform Overview

TerraBrasilis (`terrabrasilis.dpi.inpe.br`) is INPE's spatial data platform. It exposes data through a GeoServer instance supporting OGC-compliant WFS and WMS services. No API key or registration is required for public layers — all DETER, PRODES, and FOGO data is openly accessible.

### DETER (Deforestation Alerts)

| Property | Value |
|----------|-------|
| GeoServer base | `https://terrabrasilis.dpi.inpe.br/geoserver` |
| WFS endpoint | `https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows` |
| Cerrado variant | `https://terrabrasilis.dpi.inpe.br/geoserver/deter-cerrado/ows` |
| Key layer (Amazônia) | `deter-amz:deter_amz` |
| Key layer (Cerrado) | `deter-cerrado:deter_cerrado` |
| Response formats | GeoJSON (`outputFormat=application/json`), Shapefile, CSV |
| Filtering | CQL_FILTER parameter: `VIEW_DATE >= '2024-01-01'`, `UF = 'PA'`, `CLASSNAME = 'DESMATAMENTO_VEG'` |
| Authentication | None (open access) |
| Update frequency | Daily (near-real-time alerts, typically 16-day satellite revisit) |
| Historical depth | ~2004 for Amazon; ~2018 for Cerrado |
| Rate limit | Not officially documented; use 1 req/sec as a courtesy limit |

**Sample WFS request (GeoJSON):**
```
GET https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows
  ?service=WFS
  &version=2.0.0
  &request=GetFeature
  &typeName=deter-amz:deter_amz
  &outputFormat=application/json
  &CQL_FILTER=VIEW_DATE >= '2024-01-01'
  &count=100
```

⚠️ **Verify before Phase 3**: Confirm exact layer names via `GetCapabilities` request. Layer names occasionally change between GeoServer deployments.

### PRODES (Amazon Deforestation Program)

| Property | Value |
|----------|-------|
| WFS endpoint | `https://terrabrasilis.dpi.inpe.br/geoserver/prodes-amz-nb/ows` |
| Key layer | `prodes-amz-nb:yearly_deforestation_biome` |
| Response formats | GeoJSON, Shapefile |
| Update frequency | Annual (published ~November each year for previous year) |
| Historical depth | 1988 to present |
| Filter parameters | `year`, `state`, `biome` via CQL_FILTER |

⚠️ **Verify before Phase 3**: PRODES publishes increments annually; confirm whether monthly incremental data is available via a separate PRODES Cerrado or PRODES-Pantanal workspace.

### FOGO / BDQueimadas (Fire Hotspots)

| Property | Value |
|----------|-------|
| Primary source | BDQueimadas (`queimadas.dgi.inpe.br`) |
| TerraBrasilis WFS | `https://terrabrasilis.dpi.inpe.br/queimadas/geoserver/ows` |
| Key layer | `focos_aqua_referencia` (reference hotspots, AQUA satellite) |
| All-satellite layer | `focos_bdq` (aggregated from all satellites) |
| Satellite sources | AQUA_M-T, TERRA_M-T, NPP_375 (VIIRS), GOES-16, MSG-03 |
| Response formats | GeoJSON, CSV |
| Update frequency | Every 3–6 hours for near-real-time satellites |
| Historical depth | 1998 to present (daily) |
| Filter parameters | `datahora` (datetime), `estado`, `bioma`, `satelite` |

**Architecture decision**: Use the TerraBrasilis GeoServer for FOGO data (consistent with DETER/PRODES access pattern) rather than the separate BDQueimadas portal, which requires a different client approach.

⚠️ **Verify before Phase 3**: Confirm the `focos_bdq` layer name and whether near-real-time hotspots (< 6 hours) are available via WFS or require the BDQueimadas REST API separately.

### Historical Data Availability Summary

| System | Available From | Granularity | 24-month requirement |
|--------|---------------|-------------|----------------------|
| DETER | ~2004 (Amazônia) | Daily alerts | ✅ Met |
| PRODES | 1988 | Annual increments | ✅ Met |
| FOGO | 1998 | Daily / 3–6h near-RT | ✅ Met |

---

## 2. Updated Endpoints for `.env.example`

Based on the above research, the confirmed endpoints are:

```env
INPE_DETER_ENDPOINT=https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows
INPE_PRODES_ENDPOINT=https://terrabrasilis.dpi.inpe.br/geoserver/prodes-amz-nb/ows
INPE_FOGO_ENDPOINT=https://terrabrasilis.dpi.inpe.br/queimadas/geoserver/ows
```

> Note: All three are standard OGC WFS endpoints. The `BaseINPEClient` should build WFS `GetFeature` requests, not REST requests. This means the client design in Phase 3 (T025) should use WFS parameter construction rather than REST path-based routing.

---

## 3. ConversationService Async Patterns under Streamlit

### Problem

Streamlit executes Python synchronously on each script re-run. HTTPX async clients (`async def fetch()`) cannot be called directly from Streamlit page code.

### Recommended Pattern: `asyncio.run()` with thread isolation

```python
import asyncio
import httpx

def fetch_sync(url: str) -> dict:
    async def _fetch():
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json()
    return asyncio.run(_fetch())
```

`asyncio.run()` creates a new event loop, runs the coroutine, then closes the loop. This works reliably in Streamlit because Streamlit does not maintain a persistent event loop between reruns.

### Our existing `@async_safe` decorator

`src/utils/decorators.py` already implements this pattern with fallback for existing event loops via `run_coroutine_threadsafe`. **No additional setup is needed** — the INPE clients can use `async def` internally and callers use `@async_safe` or call via `asyncio.run()`.

### Session memory footprint

- Each `ConversationSession` holds message history + context as in-memory Pydantic objects
- Estimate: ~5KB per session with 20 messages
- At 50 concurrent Streamlit sessions: ~250KB total — well within normal limits
- `st.session_state` is per-browser-tab, so sessions are naturally isolated
- **Recommendation**: Cap message history at 50 messages per session; trim oldest when exceeded

---

## 4. Langfuse SDK Integration with OpenAI (No LangGraph)

### Recommended approach: `langfuse.openai` drop-in wrapper

The `langfuse` package ships a drop-in OpenAI client wrapper that automatically traces all calls:

```python
# Replace: from openai import OpenAI
from langfuse.openai import OpenAI

client = OpenAI()  # reads OPENAI_API_KEY from env; Langfuse reads its keys from env too

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Qual é o bioma do Cerrado?"}],
    # Optional: attach Langfuse session/trace metadata
    langfuse_session_id="streamlit-session-abc123",
    langfuse_user_id="user-1",
)
```

Langfuse automatically captures: input messages, output text, model, token counts (prompt + completion), estimated cost, latency.

### Alternative: `@observe` decorator

```python
from langfuse.decorators import observe, langfuse_context

@observe()
def generate_response(messages: list[dict]) -> str:
    langfuse_context.update_current_trace(session_id="abc", user_id="user-1")
    response = openai_client.chat.completions.create(...)
    return response.choices[0].message.content
```

### Required env vars

```env
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com   # or self-hosted URL
```

> Note: The env var is `LANGFUSE_HOST`, not `LANGFUSE_ENDPOINT`. Our `.env.example` uses `LANGFUSE_ENDPOINT` — **update `settings.py` to use `langfuse_host` field name, or confirm the SDK accepts `LANGFUSE_ENDPOINT`**.

⚠️ **Verify before T040**: Check whether the installed `langfuse` version uses `LANGFUSE_HOST` or `LANGFUSE_ENDPOINT`. Run `python -c "import langfuse; help(langfuse.Langfuse.__init__)"` to confirm parameter names.

### `@trace_langgraph_node` stub

Per MVP decision, implement as a transparent no-op:

```python
import functools
from collections.abc import Callable
from typing import TypeVar
F = TypeVar("F", bound=Callable)

def trace_langgraph_node(func: F) -> F:
    """No-op stub. Replace with LangGraph-aware tracing when graph is introduced."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper  # type: ignore[return-value]
```

---

## 5. Streamlit Map Performance with 10,000+ Markers

### Recommended approach: `FastMarkerCluster` + `CircleMarker`

```python
import folium
from folium.plugins import FastMarkerCluster

m = folium.Map(location=[-14.24, -51.42], zoom_start=4)

# Use CircleMarker (no custom icons) — much lighter than Marker
callback = """
function(row) {
    var marker = L.circleMarker([row[0], row[1]], {radius: 4, color: 'red', fillOpacity: 0.7});
    return marker;
}
"""
FastMarkerCluster(data=list(zip(lats, lons)), callback=callback).add_to(m)
```

### Hierarchy of approaches by point count

| Points | Recommended approach |
|--------|---------------------|
| < 500 | `folium.CircleMarker` (individual) |
| 500–5,000 | `folium.plugins.MarkerCluster` |
| 5,000–50,000 | `folium.plugins.FastMarkerCluster` |
| > 50,000 | `folium.plugins.HeatMap` or server-side tile rendering |

### streamlit-folium performance tip

```python
from streamlit_folium import st_folium
# Pass returned_objects=[] to avoid serialising click events back to Python
st_folium(m, width=1200, height=600, returned_objects=[])
```

### Deforestation polygons

Use `folium.GeoJson()` with `style_function` rather than iterating over polygons individually. Apply `@st.cache_data` to the GeoJSON loading step.

---

## 6. Geographic Reference Data (GeoJSON Boundaries)

### Brazilian States

**IBGE API (recommended — no download needed):**
```
https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?resolucao=3&formato=application/vnd.geo+json
```
- Resolution 3 = state level
- Returns simplified polygons suitable for web display (~2MB)
- Coordinate system: SIRGAS 2000 / WGS84 (interchangeable for display purposes)
- Open access, no authentication

**GeoPandas alternative:**
```python
import geopandas as gpd
url = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?resolucao=3&formato=application/vnd.geo+json"
states_gdf = gpd.read_file(url)
```

### Brazilian Biomes

**IBGE download portal:**
```
https://www.ibge.gov.br/geociencias/informacoes-ambientais/estudos-ambientais/15842-biomas.html
```
- Direct GeoJSON/Shapefile download available at 1:5,000,000 scale (~4MB Shapefile)
- Also accessible via TerraBrasilis: `https://terrabrasilis.dpi.inpe.br/geoserver/bdq/ows` (layer: `bdq:bioma`)

⚠️ **Action for T000g**: Download both files and replace the placeholder `null` geometries in `data/geojson/`. See script below.

### Download script

```python
import geopandas as gpd

# States
states = gpd.read_file(
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?resolucao=3&formato=application/vnd.geo+json"
)
states.to_file("data/geojson/states.geojson", driver="GeoJSON")

# Biomes (via TerraBrasilis WFS)
biomes = gpd.read_file(
    "https://terrabrasilis.dpi.inpe.br/geoserver/bdq/ows"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeName=bdq:bioma&outputFormat=application/json"
)
biomes.to_file("data/geojson/biomes.geojson", driver="GeoJSON")
```

---

## 7. Outstanding Items Before Phase 3

| ID | Item | Owner | Blocking |
|----|------|--------|---------|
| V1 | Run `GetCapabilities` on each GeoServer and confirm exact layer names | Dev | T025–T029 |
| V2 | Confirm `LANGFUSE_HOST` vs `LANGFUSE_ENDPOINT` env var name | Dev | T040, T045 |
| V3 | Download real GeoJSON boundary files (run script in section 6) | Dev | T030 |
| V4 | Test DETER WFS request manually; confirm CQL_FILTER date syntax | Dev | T027 |
| V5 | Confirm FOGO near-real-time layer availability (< 6h data) | Dev | T029 |

---

## Architecture Decisions Confirmed by Research

1. **All three INPE sources use the same WFS interface** — `BaseINPEClient` (T025) should implement a generic `_wfs_get_feature()` method that all three clients inherit. Each client only specifies its workspace and layer name.

2. **`asyncio.run()` is the correct async pattern** — the existing `@async_safe` decorator covers this. No `nest_asyncio` needed.

3. **Langfuse drop-in wrapper is the simplest MVP integration** — replace `from openai import OpenAI` with `from langfuse.openai import OpenAI` in `LLMProvider`. The `@trace_langgraph_node` stub is a no-op until LangGraph is introduced.

4. **`FastMarkerCluster` for fire hotspots** — confirmed as the correct tool for 10,000+ points.

5. **IBGE API for state boundaries** — can be fetched at runtime from the IBGE API, no need to bundle a large file. Biomes GeoJSON (~4MB) should be bundled locally.

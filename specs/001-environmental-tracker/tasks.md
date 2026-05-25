# Tasks: Environmental Status Tracker for Brazil (001-environmental-tracker)

**Input**: Design documents from `specs/001-environmental-tracker/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US7)
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the project with uv, create the directory structure, and configure tooling.

- [ ] T001 Initialize uv project: create `pyproject.toml` with all dependencies from plan.md (streamlit, langgraph, langfuse, pydantic, pandas, geopandas, rasterio, gdal, plotly, folium, httpx, openai, sqlalchemy, alembic, pytest, redis)
- [ ] T002 Create full source directory structure per plan.md: `src/`, `tests/unit/`, `tests/integration/`, `tests/contract/`, `data/geojson/`, `data/reference/`, `alembic/versions/`
- [ ] T003 [P] Create `.env.example` with all required variables: OPENAI_API_KEY, OPENAI_MODEL, INPE_DETER_ENDPOINT, INPE_PRODES_ENDPOINT, INPE_FOGO_ENDPOINT, DATABASE_URL, REDIS_URL, CACHE_TTL_DEFAULT, ALERT_THRESHOLD_FIRES, ALERT_THRESHOLD_DEFORESTATION, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_ENDPOINT
- [ ] T004 [P] Create `docker-compose.yml` with three services: `postgres` (`postgis/postgis:15-3.4`, port 5432, volume `pgdata`), `redis` (`redis:7-alpine`, port 6379), and `langfuse` (official image, optional profile `--profile langfuse`); default dev path (SQLite) remains functional without Docker
- [ ] T005 [P] Create `Makefile` with commands: `make run` (`uv run streamlit run src/app.py`), `make services-up` (`docker compose up -d`), `make services-down` (`docker compose down`), `make test`, `make lint`, `make db-migrate`, `make db-upgrade`
- [ ] T006 [P] Create `.streamlit/config.toml` with server and theme configuration
- [ ] T007 [P] Create `.gitignore` covering Python (`__pycache__/`, `.venv/`, `*.pyc`), environment files (`.env`), database files (`*.db`), geospatial data caches, and Docker volumes

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T008 Create `src/config/settings.py` with Pydantic `BaseSettings`: API keys, model config, rate limits, alert thresholds, cache TTLs, database URL
- [ ] T009 [P] Create `src/config/constants.py` with Brazilian biomes list, state codes, alert severity levels, INPE data type enums
- [ ] T010 Create `src/utils/logging.py` with structured JSON logging and request-context fields
- [ ] T011 [P] Create `src/utils/date_utils.py` with date range parsing, relative date resolution ("last 30 days"), and Brazil timezone handling
- [ ] T012 [P] Create `src/utils/geo_utils.py` with coordinate transformation helpers and Brazil bounding box constants
- [ ] T013 [P] Create `src/utils/decorators.py` with `@retry`, `@cache_result`, and `@async_safe` decorators
- [ ] T014 Create `src/models/geographic.py` with Pydantic models: `GeographicRegion`, `Biome`, `Coordinates`, `BoundingBox`
- [ ] T015 [P] Create `src/models/environmental.py` with `EnvironmentalAlert`, `EnvironmentalDataPoint`, `AlertThreshold`
- [ ] T016 [P] Create `src/models/timeseries.py` with `TimeSeriesData`, `TrendInfo`
- [ ] T017 [P] Create `src/models/conversation.py` with `ConversationSession`, `ConversationMessage`, `ContextData`
- [ ] T018 [P] Create `src/models/validation.py` with custom Pydantic validators: INPE coordinate ranges, date range bounds, biome/state reference validation
- [ ] T019 Create `src/database/connection.py` with SQLite (dev) and PostgreSQL (prod) connection management using SQLAlchemy engine factory
- [ ] T020 Create `src/database/models.py` with SQLAlchemy ORM models matching the Pydantic schemas in T014–T017 (conversation_sessions, environmental_data_cache, alerts tables)
- [ ] T021 Create `src/database/queries.py` with prepared queries for session retrieval, cache lookup, and alert fetching
- [ ] T022 Initialize Alembic: `alembic init alembic`, configure `alembic.ini` and `alembic/env.py` to use `src/database/models.py`; generate initial migration with `alembic revision --autogenerate -m "initial schema"`
- [ ] T023 Load geographic reference data: source and place `data/geojson/biomes.geojson` (6 Brazilian biomes), `data/geojson/states.geojson` (27 states), `data/reference/geographic_reference.json` (state codes, biome mappings)
- [ ] T024 Create `src/app.py` as the Streamlit entry point skeleton: multi-page structure with `st.navigation()`, empty page stubs for all 6 pages, session state initialization

**Checkpoint**: Foundation ready — all models, DB connection, and utilities available. User story implementation can now begin.

---

## Phase 3: US7 — Retrieve Real-Time Environmental Data from INPE (Priority: P1) 🎯 MVP Prerequisite

**Goal**: The application can reliably fetch, cache, and expose data from DETER, PRODES, and FOGO systems.

**Independent Test**: Run `python -m src.services.inpe_integration.fogo_client` and confirm fire hotspot data is returned and cached within 2 seconds per request.

- [ ] T025 Create `src/services/inpe_integration/base.py` with `BaseINPEClient`: HTTPX async client, token-bucket rate limiting, exponential-backoff retry, circuit breaker for 5xx errors, Pydantic response validation
- [ ] T026 Create `src/services/inpe_integration/cache_manager.py` with SQLite-backed `CacheManager`: `get()`, `set()`, `delete()`, `invalidate_by_pattern()`, TTL-based expiration, cache key format `{source}:{query_hash}:{version}`
- [ ] T027 [P] [US7] Create `src/services/inpe_integration/deter_client.py` extending `BaseINPEClient`: `fetch_alerts_by_region()`, `fetch_recent_deforestation()`, `fetch_time_series()`; response model `DETERAlert` with geometry, date, area_km2, confidence; 24h cache TTL
- [ ] T028 [P] [US7] Create `src/services/inpe_integration/prodes_client.py` extending `BaseINPEClient`: `fetch_deforestation_by_period()`, `fetch_baseline_map()`, `fetch_vintage_series()`; response model `PRODESData`; 30-day cache TTL
- [ ] T029 [P] [US7] Create `src/services/inpe_integration/fogo_client.py` extending `BaseINPEClient`: `fetch_current_hotspots()`, `fetch_hotspots_by_date()`, `fetch_fire_risk()`; response model `FireHotspot` with lat/lon, detection_time, confidence, satellite_source; 4h cache TTL
- [ ] T030 [US7] Create `src/services/analysis/geospatial.py`: `get_point_biome()`, `get_point_state()`, `filter_by_region()`, `transform_coordinates()`, `validate_brazilian_coordinates()` — reads from `data/geojson/`

**Checkpoint**: All 3 INPE clients return data, caching works, geospatial lookups resolve biome/state from coordinates.

---

## Phase 4: US6 — Filter Data by Region, Biome, and Date Range (Priority: P1)

**Goal**: Reusable filter components are available for dashboard and map pages; filtering correctly intersects multiple conditions.

**Independent Test**: Render filters in isolation with `streamlit run tests/ui_smoke.py`; select Cerrado biome + last 30 days; verify filter state object reflects both conditions.

- [ ] T031 [US6] Create `src/ui/components/filters.py`: `render_region_filter()` (state/municipality multiselect), `render_biome_filter()` (Amazon/Cerrado/Caatinga/Atlantic Forest/Pantanal/Pampas), `render_date_range_filter()` (calendar + relative presets "last 7/30/90 days"), `render_clear_filters_button()`; filter state stored in `st.session_state`
- [ ] T032 [P] [US6] Create `src/ui/components/status_indicators.py`: `render_freshness_badge(timestamp)`, `render_api_status(sources)`, `render_error_message(msg, suggestion)`
- [ ] T033 [P] [US6] Create `src/ui/styles.py` with Streamlit custom CSS: colour palette, card styles, filter sidebar styling, Portuguese-first font stack

**Checkpoint**: Filter components render correctly; selecting multiple filters produces a valid `FilterState` object.

---

## Phase 5: US2 — Visualize Environmental Data on Interactive Dashboards (Priority: P1)

**Goal**: Dashboard page loads within 5 seconds displaying INPE metrics with fully functional filter integration.

**Independent Test**: `streamlit run src/app.py`, navigate to Dashboard; apply "Legal Amazon" filter; all charts update within 500ms; hover tooltip shows data source and collection date.

- [ ] T034 [US2] Create `src/services/analysis/aggregator.py`: `aggregate_multi_source()` (merge DETER + PRODES + FOGO by geometry), `resolve_conflicts()`, `create_unified_view()` returning a unified environmental snapshot
- [ ] T035 [P] [US2] Create `src/ui/components/charts.py`: `time_series_chart()`, `bar_comparison_chart()`, `spatial_heatmap()` — all Plotly-based with INPE source tooltips and `@st.cache_data` on data fetching
- [ ] T036 [US2] Create `src/ui/pages/dashboard.py`: KPI cards (deforestation rate, fires last 24h, vegetation status), time-series charts, geographic heatmap; integrates `filters.py` (T031) and `charts.py` (T035); shows freshness badges via `status_indicators.py`

**Checkpoint**: Dashboard renders with real or sample data; filters update all visuals; loads within 5 seconds.

---

## Phase 6: US3 — Visualize Environmental Data on Interactive Maps (Priority: P1)

**Goal**: Map page shows Brazil with INPE fire hotspots and deforestation polygons; clicking a marker shows event details.

**Independent Test**: Navigate to Map page; confirm Brazil map loads within 4 seconds; click a fire hotspot marker and verify popup shows location, date, type, and severity.

- [ ] T037 [US3] Create `src/ui/components/map.py`: `render_brazil_map()` with Folium, state boundary layer, fire hotspot markers (red), deforestation area polygons (orange), marker clustering for >500 points, popup template with event details
- [ ] T038 [US3] Create `src/ui/pages/map_viewer.py`: integrates `map.py` (T037) and `filters.py` (T031); layer toggle controls (show/hide fires, deforestation, vegetation); zoom-to-region on filter change; freshness badge

**Checkpoint**: Map loads with real data, markers are filterable, popups display correct INPE attribution.

---

## Phase 7: US1 — Query Environmental Status Conversationally (Priority: P1) 🎯 MVP Core

**Goal**: Users can ask environmental questions in Portuguese or English and receive accurate INPE-grounded responses in multi-turn conversations.

**Independent Test**: Start the app, open Conversation page; ask "Qual é a situação atual de queimadas no Cerrado?"; verify a Portuguese response with INPE data citation is returned within 3 seconds; ask a follow-up "E nas últimas duas semanas?" and verify context is preserved.

- [ ] T039 [US1] Create `src/services/llm_provider.py`: `LLMProvider` abstract base; `OpenAIProvider` concrete implementation; provider is configured via `settings.py`; all downstream services call `LLMProvider`, never the OpenAI SDK directly
- [ ] T040 [P] [US1] Create `src/config/langfuse_config.py`: initialize Langfuse SDK from env vars (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_ENDPOINT); provide `get_langfuse_client()` singleton
- [ ] T041 [P] [US1] Create `src/services/conversation/prompts.py`: Portuguese-first system prompt (default PT-BR, switch to EN on English input); INPE citation requirement; data freshness warning rule (>12h); few-shot examples for biome/state extraction in Portuguese with English equivalents
- [ ] T042 [P] [US1] Create `src/services/conversation/query_parser.py`: `parse_query(text) -> ParsedQuery`; extracts geographic context (region/biome/coordinates), metric of interest (deforestation/fire/vegetation), temporal scope, and language (PT/EN auto-detect); handles "São Paulo" ambiguity by returning clarification options
- [ ] T043 [P] [US1] Create `src/services/conversation/session_manager.py`: `create_session()`, `add_message()`, `get_context()`, `save_session()` — persists `ConversationSession` to SQLite via `src/database/`
- [ ] T044 [US1] Create `src/services/conversation/response_generator.py`: `format_data_context()` (converts Pydantic models to readable markdown), `add_citations()` (appends INPE attribution), `format_time_content()` (adds freshness info)
- [ ] T045 [US1] Create `src/services/conversation/langfuse_wrapper.py`: `@trace_llm_call` decorator (logs inputs/outputs, token counts, cost), `@trace_langgraph_node` decorator (node latency), session correlation (Streamlit session_id → Langfuse trace_id)
- [ ] T046 [US1] Create `src/services/conversation/langgraph_engine.py`: start with simple `ConversationService` (message history + `LLMProvider` call + `SessionManager`); define LangGraph state graph with nodes (parse_query → retrieve_data → generate_response → update_context) as the upgrade path; activate LangGraph nodes if multi-step branching is needed; all LLM calls go through `langfuse_wrapper.py`
- [ ] T047 [US1] Create `src/ui/pages/conversation.py`: Streamlit chat UI with `st.chat_message`, session history display, query input (placeholder text in Portuguese), geographic context chip showing active region/biome, Langfuse session ID stored in `st.session_state`

**Checkpoint**: Multi-turn PT/EN conversations work end-to-end; INPE data cited; Langfuse dashboard shows traces and costs.

---

## Phase 8: US4 — Receive and Track Environmental Alerts (Priority: P2)

**Goal**: System auto-generates alerts when INPE data meets thresholds; alerts are visible in the dashboard and navigable to the map.

**Independent Test**: Seed test data exceeding fire threshold (>100 hotspots/24h); verify alert appears in Alerts page within 2 minutes with correct severity, location, and recommended action.

- [ ] T048 [US4] Create `src/services/analysis/alert_generator.py`: `evaluate_alert_thresholds(data) -> list[EnvironmentalAlert]`, `generate_alert()`, `check_alert_escalation()`; thresholds from `config/constants.py`; alert types: fire outbreak (>100 hotspots/24h), deforestation spike (>50% above 12-month avg)
- [ ] T049 [US4] Generate Alembic migration for any new alert status fields: `alembic revision --autogenerate -m "alert status fields"`
- [ ] T050 [US4] Create `src/ui/pages/alerts.py`: alert list sorted by severity + recency, filter by type/status, dismiss/archive actions, click-through that sets map filter to the alert's region

**Checkpoint**: Alerts generate automatically from INPE data, display with severity hierarchy, and link to map view.

---

## Phase 9: US5 — Analyze Environmental Trends Over Time (Priority: P2)

**Goal**: Users can view time-series trends for any region/biome/metric with period comparison and data export.

**Independent Test**: Select "Amazon" biome, "deforestation" metric, last 24 months; confirm trend chart renders with correct direction indicator; export CSV and verify it contains INPE attribution header and correct values.

- [ ] T051 [US5] Create `src/services/analysis/trend_analyzer.py`: `calculate_trend(series) -> TrendInfo` (direction, slope, confidence), `seasonal_decomposition()`, `compare_periods(period_a, period_b) -> dict` (% change, absolute values)
- [ ] T052 [P] [US5] Create `src/services/data_export.py`: `export_csv(data, filename)` and `export_pdf(chart, data, filename)` — both include INPE data source attribution header and collection timestamps
- [ ] T053 [US5] Create `src/ui/pages/trends.py`: region/biome/metric selectors, configurable date range, trend line with direction indicator, side-by-side period comparison panel, export buttons using `data_export.py`
- [ ] T054 [P] [US5] Create `src/ui/pages/about.py`: INPE data sources list with endpoints, data definitions (DETER/PRODES/FOGO), update frequency table, citation guidelines

**Checkpoint**: Trend analysis returns data for at least 24 months; period comparison calculates correct % change; CSV export downloads with proper attribution.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Wire all pages into navigation, finalize documentation, and validate performance targets.

- [ ] T055 Update `src/app.py` to wire all 6 pages into `st.navigation()`: Conversation, Dashboard, Map, Alerts, Trends, About — with Portuguese page labels
- [ ] T056 [P] Apply `@st.cache_data(ttl=3600)` to all static geographic data loads in `geospatial.py` and `map.py`; profile map rendering with 10,000+ markers and confirm no degradation
- [ ] T057 [P] Security hardening: audit that no API keys are logged, all INPE responses pass Pydantic validation before use, rate limiter in `BaseINPEClient` tested under load
- [ ] T058 [P] Write `README.md` covering project overview, local setup (default SQLite path and Docker Compose prod-parity path), environment configuration, architecture diagram reference
- [ ] T059 Run end-to-end validation: `uv sync` → configure `.env` → `alembic upgrade head` → `streamlit run src/app.py`; verify all 6 pages load; verify INPE data appears with freshness badge; verify Portuguese conversation round-trip

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user stories**
- **Phase 3 (US7)**: Depends on Phase 2
- **Phase 4 (US6)**: Depends on Phase 2 (models + utils only; no INPE clients needed)
- **Phase 5 (US2)**: Depends on Phase 3 (US7) + Phase 4 (US6)
- **Phase 6 (US3)**: Depends on Phase 3 (US7) + Phase 4 (US6)
- **Phase 7 (US1)**: Depends on Phase 3 (US7)
- **Phase 8 (US4)**: Depends on Phase 3 (US7)
- **Phase 9 (US5)**: Depends on Phase 3 (US7)
- **Phase 10 (Polish)**: Depends on all previous phases complete

### User Story Dependencies

- **US7 (P1)**: Can start after Phase 2 — no story dependencies
- **US6 (P1)**: Can start after Phase 2 — no story dependencies (runs in parallel with US7)
- **US2 (P1)**: Depends on US7 + US6
- **US3 (P1)**: Depends on US7 + US6 (can run in parallel with US2)
- **US1 (P1)**: Depends on US7 only (can run in parallel with US2/US3)
- **US4 (P2)**: Depends on US7 only
- **US5 (P2)**: Depends on US7 only

### Parallel Opportunities per Phase

```
After Phase 2 completes:
  ├── US7 (T024–T029) — INPE clients
  └── US6 (T030–T032) — Filter components (parallel with US7)

After US7 + US6 complete:
  ├── US2 (T033–T035) — Dashboard
  ├── US3 (T036–T037) — Map (parallel with US2)
  └── US1 (T038–T046) — Conversation (parallel with US2/US3)

After US7 completes (regardless of US2/US3):
  ├── US4 (T047–T049) — Alerts
  └── US5 (T050–T053) — Trends (parallel with US4)
```

---

## Implementation Strategy

### MVP First (US7 + US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US7 (INPE data retrieval)
4. Complete Phase 7: US1 (Conversational interface)
5. **STOP and VALIDATE**: Users can ask questions in Portuguese and get INPE-backed answers
6. Demo/deploy the conversational agent as MVP

### Incremental Delivery

1. Setup + Foundational → skeleton app runs
2. US7 → INPE data accessible
3. US6 + US2 → Dashboard with filters (visual MVP)
4. US3 → Map (spatial MVP)
5. US1 → Conversational interface (complete MVP)
6. US4 → Alert system
7. US5 → Trend analysis + export

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 59 |
| Phase 1–2 (Setup + Foundational) | 24 tasks |
| US7 (INPE Integration) | 6 tasks |
| US6 (Filters) | 3 tasks |
| US2 (Dashboard) | 3 tasks |
| US3 (Maps) | 2 tasks |
| US1 (Conversational) | 9 tasks |
| US4 (Alerts) | 3 tasks |
| US5 (Trends) | 4 tasks |
| Phase 10 (Polish) | 5 tasks |
| **Suggested MVP scope** | **Phases 1–3 + Phase 7 (US7 + US1)** — 38 tasks |

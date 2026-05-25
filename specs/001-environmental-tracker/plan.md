# Implementation Plan: Environmental Status Tracker for Brazil (001-environmental-tracker)

**Branch**: `001-environmental-tracker` | **Date**: 2025-03-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-environmental-tracker/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

The Environmental Status Tracker for Brazil is a Python-based Streamlit application providing conversational and visual access to Brazilian environmental data from INPE (Instituto Nacional de Pesquisas Espaciais). The system integrates data from DETER (deforestation detection), PRODES (Amazon deforestation program), and FOGO (fire detection) into an interactive dashboard with LLM-powered multi-turn conversational querying. Users can explore environmental metrics through natural language queries, filterable dashboards, and map visualizations, with trend analysis and automatic alert generation for environmental events. The architecture prioritizes performance (dashboard <5s load time, API <2s response), concurrent conversation support (50+), and data accuracy (95% query interpretation rate).

**Conversation engine decision**: MVP uses a simple `ConversationService` loop (message history + `LLMProvider` call + `SessionManager`). LangGraph is retained as a named upgrade path for when multi-step branching flows or parallel data-retrieval are needed post-MVP — it is **not** a Sprint 3 dependency.

## Technical Context

**Language/Version**: Python 3.11+ (managed with `uv` package manager)

**Primary Dependencies**: 
- **UI Framework**: Streamlit (interactive dashboards and web UI)
- **LLM Orchestration**: `ConversationService` loop for MVP (message history + `LLMProvider` call); LangGraph reserved as post-MVP upgrade for branching/agentic flows
- **Observability & Tracing**: Langfuse (LLM observability, cost tracking, latency monitoring)
- **Data Validation**: Pydantic v2 (data models and settings management)
- **Data Processing**: Pandas, GeoPandas (environmental data manipulation)
- **Geospatial**: Rasterio, GDAL/OGR (satellite imagery and geographic operations)
- **Visualization**: Plotly, Folium (charts and map rendering)
- **API Integration**: HTTPX (async HTTP client for INPE service integration)
- **LLM Provider**: OpenAI API or compatible (configurable via environment)
- **Caching**: Redis or SQLite-based (performance optimization for API responses)
- **Local Dev Services**: Docker Compose (optional — spins up PostgreSQL+PostGIS and Redis for prod-parity local development; default dev path still uses SQLite via `uv sync` only)

**Storage**: 
- **Development/MVP**: SQLite for local environmental data cache and conversation history
- **Production**: PostgreSQL with PostGIS extension for geospatial queries and scalability
- **File-based**: GeoJSON/GeoTIFF for satellite imagery and vector data caching

**Testing**: pytest with fixtures, mocking of INPE APIs, integration tests with live services

**Target Platform**: Linux/macOS/Windows servers with modern web browser access; cloud deployment ready (AWS/GCP/Azure)

**Project Type**: Web application (Streamlit-based single-page app with backend data pipeline)

**Performance Goals**:
- Dashboard load time: <5 seconds
- API response time: <2 seconds per INPE query
- Conversational response generation: <3 seconds
- Support 50+ concurrent conversations
- Map rendering: 10,000+ data points without degradation

**Constraints**:
- 95% query accuracy/interpretation rate required
- 24+ months historical data availability
- Portuguese and English language support
- Geographic filtering by states, municipalities, and biomes
- Data freshness tolerance: up to 24 hours
- Must properly attribute INPE data sources

**Scale/Scope**: Single Python application with Streamlit frontend, 10-50k estimated LOC, supporting 50-500 concurrent users in MVP phase, 6+ major views/dashboards

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle Alignment

✅ **Data-Driven Insights** (Principle 1)
- INPE data sources properly integrated with REST API clients
- Citation and attribution mechanisms built into all outputs
- Transparent error handling for data availability issues

✅ **User-Centric Conversational Interface** (Principle 2)
- `ConversationService` loop provides multi-turn, context-aware dialogue for MVP; LangGraph available as upgrade
- Pydantic models ensure data consistency across conversational context
- Progressive disclosure through dashboard filtering and map drill-down

✅ **Accessibility and Transparency** (Principle 3)
- Portuguese-first bilingual support (Portuguese as UI/prompt default, English fully supported) via LLM prompts
- Documentation of all INPE data formats and processing logic
- Data freshness timestamps visible on all UI elements

✅ **Maintainability and Scalability** (Principle 4)
- Modular architecture (services, models, interfaces layers)
- Pydantic models provide clear schemas for all data structures
- Service layer abstraction for INPE integrations enables easy addition of new sources
- `LLMProvider` abstraction layer enables switching between OpenAI, Claude, or local models without touching service code

### Quality Standards Alignment

✅ **Code Quality** (PEP 8, type hints, docstrings, >80% test coverage)
- Pydantic provides runtime type checking and validation
- `ConversationService` enforces clear input/output interfaces; LangGraph can replace it without touching callers
- Test strategy includes unit, integration, and contract tests

✅ **Performance Requirements** Met
- <5s dashboard load: Streamlit caching + async INPE fetching
- <2s API response: Parallel data retrieval + local caching
- 50+ concurrent conversations: async `ConversationService` (LangGraph upgrade preserves this)

✅ **Reliability Requirements** Met
- Graceful fallback for INPE API failures (last known data display)
- Conversation session persistence for recovery
- Data validation via Pydantic at all entry points

### INPE Integration Requirements

✅ **DETER Integration**
- Documented API endpoint and rate limit handling
- Satellite data format handling (GeoTIFF/NetCDF)
- Spatial data validation and CRS transformations

✅ **PRODES Integration**
- Base map and historical deforestation program data
- Time-series processing for trend analysis
- Proper attribution and data source referencing

✅ **FOGO Integration**
- Real-time fire detection hotspot data
- Alert generation based on concentration thresholds
- Geographic filtering by state/municipality/biome

### Conversational AI Requirements

✅ **LLM Interactions**
- Applications based on actual environmental data from INPE
- Context about data freshness in conversation history
- Source citations in all LLM-generated responses
- Edge case handling for geographic ambiguity (clarification prompts)

### MVP Compliance

✅ All 4 MVP features address constitution goals:
1. **INPE Data Integration** - Primary data source DETER/PRODES/FOGO APIs
2. **Brazilian Environmental Analysis** - Deforestation, fire, biome metrics
3. **Interactive Dashboard** - Streamlit with filters and visualizations
4. **Conversational Interface** - `ConversationService` + LLM with INPE context (LangGraph post-MVP)

**GATE RESULT**: ✅ PASSED - All constitution principles and quality standards are addressable with proposed architecture.

## Project Structure

### Documentation (this feature)

```text
specs/001-environmental-tracker/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output: INPE API patterns, Streamlit best practices, ConversationService patterns
├── data-model.md        # Phase 1 output: Entity schemas, relationships, validation rules
├── quickstart.md        # Phase 1 output: Setup, environment config, first run guide
├── contracts/           # Phase 1 output: API schemas and interface contracts
│   ├── inpe-data-contract.json
│   ├── conversation-api.json
│   └── dashboard-state.json
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
environment_tracker/
├── src/
│   ├── app.py                          # Main Streamlit entry point
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py                 # Pydantic settings: API keys, model config, thresholds
│   │   ├── constants.py                # Biomes, states, alert definitions
│   │   └── langfuse_config.py          # Langfuse SDK initialization and tracing wrapper
│   │
│   ├── models/                         # Pydantic data models
│   │   ├── __init__.py
│   │   ├── environmental.py            # EnvironmentalAlert, EnvironmentalDataPoint, AlertThreshold
│   │   ├── geographic.py               # GeographicRegion, Biome, BoundingBox, Coordinates
│   │   ├── conversation.py             # ConversationSession, ConversationMessage, ContextData
│   │   ├── timeseries.py               # TimeSeriesData, TrendInfo, TimeAggregation
│   │   └── validation.py               # Custom validators for INPE data formats
│   │
│   ├── services/                       # Business logic services
│   │   ├── __init__.py
│   │   ├── llm_provider.py             # LLMProvider abstraction (OpenAI, Claude, local)
│   │   ├── inpe_integration/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # BaseINPEClient with rate limiting, caching
│   │   │   ├── deter_client.py         # DETER deforestation detection API
│   │   │   ├── prodes_client.py        # PRODES Amazon deforestation program
│   │   │   ├── fogo_client.py          # FOGO fire detection API
│   │   │   └── cache_manager.py        # Local cache for API responses
│   │   │
│   │   ├── analysis/
│   │   │   ├── __init__.py
│   │   │   ├── trend_analyzer.py       # Time-series trend detection
│   │   │   ├── alert_generator.py      # Alert thresholds and event detection
│   │   │   ├── geospatial.py           # Spatial filtering, coordinate validation, biome lookup
│   │   │   └── aggregator.py           # Multi-source data aggregation
│   │   │
│   │   ├── conversation/
│   │   │   ├── __init__.py
│   │   │   ├── conversation_engine.py  # ConversationService (MVP); LangGraph upgrade path documented
│   │   │   ├── query_parser.py         # Extract geographic context and intent from queries
│   │   │   ├── response_generator.py   # Format INPE data for conversational responses
│   │   │   ├── session_manager.py      # Conversation persistence and context maintenance
│   │   │   ├── prompts.py              # System prompts and examples for LLM
│   │   │   └── langfuse_wrapper.py     # Langfuse tracing decorators and context managers
│   │   │
│   │   └── data_export.py              # CSV/PDF export with proper INPE attribution
│   │
│   ├── ui/                             # Streamlit UI components
│   │   ├── __init__.py
│   │   ├── pages/
│   │   │   ├── __init__.py
│   │   │   ├── conversation.py         # Conversational chat interface
│   │   │   ├── dashboard.py            # Metrics dashboard with filters
│   │   │   ├── map_viewer.py           # Interactive map with hotspots/polygons
│   │   │   ├── alerts.py               # Alert management and history
│   │   │   ├── trends.py               # Time-series trend analysis view
│   │   │   └── about.py                # Data sources, INPE attribution, documentation
│   │   │
│   │   ├── components/
│   │   │   ├── __init__.py
│   │   │   ├── filters.py              # Geographic, biome, date range filters
│   │   │   ├── charts.py               # Reusable Plotly chart components
│   │   │   ├── map.py                  # Folium map wrapper and layer management
│   │   │   └── status_indicators.py    # Data freshness, API status, error messages
│   │   │
│   │   └── styles.py                   # Streamlit custom CSS and theming
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logging.py                  # Structured logging with context
│   │   ├── date_utils.py               # Date range parsing and timezone handling
│   │   ├── geo_utils.py                # Coordinate transformation, biome lookup
│   │   └── decorators.py               # Caching, retry, async helpers
│   │
│   └── database/
│       ├── __init__.py
│       ├── connection.py               # SQLite/PostgreSQL connection management
│       ├── models.py                   # SQLAlchemy ORM models
│       ├── migrations.py               # Schema management
│       └── queries.py                  # Prepared queries for common operations
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Pytest configuration and fixtures
│   │
│   ├── unit/
│   │   ├── test_models.py              # Pydantic model validation
│   │   ├── test_query_parser.py        # Geographic context extraction
│   │   ├── test_alert_generator.py     # Alert threshold logic
│   │   ├── test_trend_analyzer.py      # Time-series calculations
│   │   └── test_geospatial.py          # Coordinate validation, biome lookup
│   │
│   ├── integration/
│   │   ├── test_inpe_deter.py          # DETER API integration (mocked + live)
│   │   ├── test_inpe_prodes.py         # PRODES API integration
│   │   ├── test_inpe_fogo.py           # FOGO API integration
│   │   ├── test_data_aggregation.py    # Multi-source data combining
│   │   ├── test_conversation_flow.py   # ConversationService pipeline testing
│   │   └── test_streamlit_pages.py     # UI page rendering
│   │
│   └── contract/
│       ├── test_inpe_data_contract.py  # INPE API response schemas
│       ├── test_conversation_contract.py
│       └── test_export_contract.py
│
├── data/
│   ├── geojson/                        # Biome boundaries, state polygons
│   │   ├── biomes.geojson
│   │   └── states.geojson
│   └── reference/                      # Reference data (biome names, state codes)
│       └── geographic_reference.json
│
├── pyproject.toml                      # uv project configuration, dependencies, metadata
├── uv.lock                             # Locked dependency versions
├── .env.example                        # Environment template (API keys, settings)
├── .streamlit/config.toml              # Streamlit configuration
├── docker-compose.yml                  # Optional: PostgreSQL+PostGIS, Redis, Langfuse for local dev
└── README.md                           # Project overview for developers (includes uv run command reference)
```

**Structure Decision**: Selected Option 1 (Single project) as the Streamlit application is a cohesive unit with UI and backend tightly integrated. Clear separation achieved through layered architecture (models, services, ui, database) rather than separate projects. All components share the same Python environment managed by `uv`.

## Complexity Tracking

No violations to constitution or quality standards identified. Architecture aligns with all principles:
- Single Python project (managed by `uv`)
- Clear layered separation (models → services → UI)
- All INPE integrations follow best practice patterns
- Scalable for 50+ concurrent users with caching and async patterns
- Conversational engine (`ConversationService`) enables natural multi-turn dialogue while maintaining context; LangGraph is the documented post-MVP upgrade path

---

## Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     UI Layer (Streamlit)                        │
│  ┌──────────────┬──────────────┬──────────────┬─────────────┐  │
│  │ Conversation │  Dashboard   │ Map Viewer   │   Alerts    │  │
│  │   Pages      │   Pages      │   Pages      │   Trends    │  │
│  └──────────────┴──────────────┴──────────────┴─────────────┘  │
└───────────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌───────────────────────────────────────────────────────────────────┐
│                   Application Logic Layer                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Conversation Engine (ConversationService + LLM)             │ │
│  │  - Multi-turn dialogue orchestration                        │ │
│  │  - Intent extraction and context management                 │ │
│  │  - Response generation with INPE data                       │ │
│  │  - Langfuse tracing: cost tracking, latency monitoring      │ │
│  │  - Observability middleware for all LLM calls               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────┬──────────────────┬──────────────────┐ │
│  │ Analysis Services    │ Trend Analyzer   │ Alert Generator  │ │
│  └──────────────────────┴──────────────────┴──────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Data Export & Aggregation Services                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌───────────────────────────────────────────────────────────────────┐
│                  Data Services Layer                              │
│  ┌──────────────┬──────────────┬──────────────┐                 │
│  │ DETER Client │ PRODES Client│ FOGO Client  │                 │
│  │ (API access) │ (API access) │ (API access) │                 │
│  └──────────────┴──────────────┴──────────────┘                 │
│  ┌──────────────────────────────────────────┐                  │
│  │   Cache Manager (SQLite/Redis)           │                  │
│  └──────────────────────────────────────────┘                  │
└───────────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌───────────────────────────────────────────────────────────────────┐
│                   Data Storage Layer                              │
│  ┌──────────────────────────────────────────┐                  │
│  │ Local Cache + Session Store              │                  │
│  │ (SQLite for MVP, PostgreSQL for prod)    │                  │
│  └──────────────────────────────────────────┘                  │
│  ┌──────────────────────────────────────────┐                  │
│  │ Geographic Reference Data                │                  │
│  │ (GeoJSON biomes, state boundaries)       │                  │
│  └──────────────────────────────────────────┘                  │
└───────────────────────────────────────────────────────────────────┘
                           ▲
                           │
                ┌──────────────────────────┐
                │   INPE Remote Services   │
                │  (DETER, PRODES, FOGO)  │
                └──────────────────────────┘
```

### Data Flow

1. **User Query → Conversation Service**
   - User submits query (conversational interface)
   - `ConversationService` parses intent, extracts geographic context
   - Query parser creates structured request with filters

2. **Data Retrieval → INPE Integration Layer**
   - Query router directs to appropriate INPE client (DETER/PRODES/FOGO)
   - Cache manager checks local cache first
   - If cache miss or stale, HTTPX async client fetches from INPE API
   - Response validated against Pydantic schema contracts
   - Data stored in local cache with timestamp

3. **Data Processing → Analysis Services**
   - Aggregator combines data from multiple INPE sources
   - Geospatial service filters by region/biome/municipality
   - Trend analyzer processes time-series data
   - Alert generator evaluates thresholds

4. **Response Generation → LLM Orchestration**
   - Processed data formatted as context for LLM
   - `ConversationService` manages multi-turn dialogue state
   - LLM generates conversational response with citations
   - Response cached in conversation session

5. **Presentation → Streamlit UI**
   - Dashboard pages render cached data with Plotly visualizations
   - Map viewer displays points/polygons with Folium
   - Alerts shown with severity indicators
   - All data displays show freshness timestamps

### Component Specifications

#### 1. **INPE Integration Services** (`src/services/inpe_integration/`)

**BaseINPEClient**
- Abstract base with common retry logic, rate limiting, error handling
- Async HTTP client (HTTPX) for non-blocking API calls
- Configurable rate limits per INPE service
- Circuit breaker for API failures
- Response validation against Pydantic contracts

**DETER Client** (`deter_client.py`)
- Endpoint: INPE Detection of Changes in Native Vegetation
- Methods: `fetch_alerts_by_region()`, `fetch_recent_deforestation()`, `fetch_time_series()`
- Response model: `DETERAlert` → Pydantic schema with geometry, date, area_km2, confidence
- Cache strategy: 24-hour TTL for alerts, 7-day TTL for historical aggregates
- Rate limit: Respect INPE documentation (typically 1 req/sec)

**PRODES Client** (`prodes_client.py`)
- Endpoint: INPE Amazon Deforestation Program annual/monthly increments
- Methods: `fetch_deforestation_by_period()`, `fetch_baseline_map()`, `fetch_vintage_series()`
- Response model: `PRODESData` with area_km2, deforestation_km2, monitoring_period
- Cache strategy: 30-day TTL (data updates monthly)
- Historical data: 1988-present

**FOGO Client** (`fogo_client.py`)
- Endpoint: Real-time fire detection hotspots
- Methods: `fetch_current_hotspots()`, `fetch_hotspots_by_date()`, `fetch_fire_risk()`
- Response model: `FireHotspot` with lat/lon, detection_time, confidence, satellite_source
- Cache strategy: 4-hour TTL (data updates frequently)
- Supports multiple satellite sources (MODIS, VIIRS)

**Cache Manager** (`cache_manager.py`)
- Abstraction over SQLite/Redis
- Methods: `get()`, `set()`, `delete()`, `invalidate_by_pattern()`
- TTL-based expiration per data type
- Cache key strategy: `{source}:{query_hash}:{version}`

#### 2. **Analysis Services** (`src/services/analysis/`)

**Trend Analyzer** (`trend_analyzer.py`)
- Input: Time-series environmental data points
- Methods: 
  - `calculate_trend()` - Returns TrendInfo with direction (increasing/stable/decreasing), slope, confidence
  - `seasonal_decomposition()` - Extract seasonal patterns from monthly/yearly data
  - `compare_periods()` - Calculate percentage change between two time periods
- Output: Pydantic `TrendInfo` model with statistical confidence scores
- Used by: Trend analysis dashboard, conversational responses

**Alert Generator** (`alert_generator.py`)
- Monitors incoming INPE data against alert thresholds
- Threshold configuration in `config/constants.py`
- Methods:
  - `evaluate_alert_thresholds()` - Check if data meets alert criteria
  - `generate_alert()` - Create EnvironmentalAlert object
  - `check_alert_escalation()` - Severity determination
- Alert types: Fire outbreak (>100 hotspots/24h), Deforestation spike (>50% above 12-month avg), New vegetation loss
- Triggers notifications and dashboard updates

**Geospatial Service** (`geospatial.py`)
- Methods:
  - `get_point_biome()` - Identify biome from coordinates
  - `get_point_state()` - Identify state/municipality from coordinates
  - `filter_by_region()` - Polygon-based spatial filtering
  - `transform_coordinates()` - CRS transformations (if needed)
  - `validate_brazilian_coordinates()` - Ensure within Brazil bounds
- Data sources: GeoJSON files in `data/geojson/` (biomes.geojson, states.geojson)
- Used by: All queries, geographic filtering

**Data Aggregator** (`aggregator.py`)
- Combines data from multiple INPE sources
- Methods:
  - `aggregate_multi_source()` - Merge DETER, PRODES, FOGO by geometry
  - `resolve_conflicts()` - Handle overlapping detections (geography precedence)
  - `create_unified_view()` - Single view of environmental status
- Output: Unified environmental snapshot suitable for dashboard/conversation

#### 3. **Conversation Engine** (`src/services/conversation/`)

**Conversation Engine** (`conversation_engine.py`)

*MVP implementation*: Simple `ConversationService` loop — no graph wiring required.
- Steps: parse_query → retrieve_data → generate_response → update_context (linear, no branching)
- Message history and context maintained in `ConversationSession`
- All LLM calls go through `LLMProvider`; all calls traced via `langfuse_wrapper.py`

*Post-MVP upgrade path*: Replace `ConversationService` with a LangGraph state graph when any of these triggers arise:
- Multi-step clarification flows (e.g., "São Paulo" ambiguity needing a follow-up turn)
- Parallel data-retrieval branches (fire + deforestation simultaneously)
- Conditional routing based on query type
- The upgrade is designed to be a drop-in: callers never import LangGraph directly, so switching is contained to this file

**Query Parser** (`query_parser.py`)
- LLM-based or rule-based parsing of natural language queries
- Extraction targets:
  - Geographic context: Region name, biome, coordinates
  - Metrics of interest: Deforestation, fires, vegetation
  - Temporal scope: Time period, relative dates
  - Language: Portuguese or English auto-detection
- Output: Pydantic `ParsedQuery` model with structured fields
- Handles ambiguity: "São Paulo" → return options (state vs. capital city)

**Response Generator** (`response_generator.py`)
- Formats structured INPE data as context for LLM prompt
- Methods:
  - `format_data_context()` - Convert data models → readable markdown
  - `add_citations()` - Append INPE source attribution
  - `format_time_content()` - Add temporal context and freshness info
- Output: LLM prompt with data context ready for response generation

**Session Manager** (`session_manager.py`)
- Stores conversation history and context
- Methods:
  - `create_session()` - Initialize new ConversationSession
  - `add_message()` - Append user/assistant messages to history
  - `get_context()` - Retrieve session context (geographic focus, biome interest, date range)
  - `save_session()` - Persist to SQLite
- Enables recovery and multi-user support

**Prompts** (`prompts.py`)
- System prompt guidelines:
  - Always cite INPE data
  - **Default to Portuguese**; switch to English only when the user writes in English — auto-detect language per message
  - Include data freshness warnings if data >12 hours old
  - Acknowledge data limitations transparently
  - Offer alternative queries if data unavailable
- Few-shot examples for entity extraction written in Portuguese (with English equivalents)
- UI labels, error messages, and status indicators default to Portuguese

**Langfuse Wrapper** (`langfuse_wrapper.py`)
- Observability and tracing integration for LLM calls
- Methods:
  - `trace_llm_call()` - Decorator for OpenAI API calls, logs all inputs/outputs to Langfuse
  - `trace_langgraph_node()` - Reserved for post-MVP LangGraph upgrade; no-op stub in MVP
  - `get_langfuse_trace()` - Retrieve current trace context for nested calls
  - `update_trace_metadata()` - Add custom metadata (user_id, query_type, region, biome)
- Features:
  - Automatic cost tracking (tokens per call, cumulative cost per session)
  - Latency monitoring for each LLM generation
  - Error tracing with stack traces
  - User session correlation (maps Streamlit session_id to Langfuse trace_id)
- Configuration: Reads from `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_ENDPOINT` environment variables

#### 4. **UI Components** (`src/ui/`)

**Pages**

- **conversation.py**: Chat interface with session history, context display
  - Streamlit chat UI with message history
  - Query input with Portuguese/English support
  - `ConversationService` integration for multi-turn dialogue
  - Geographic context display (current region/biome filter)

- **dashboard.py**: Multi-metric overview with filters
  - KPI cards: Current deforestation rate, fires last 24h, vegetation status
  - Time-series charts (area over time, fire frequency)
  - Geographic heatmaps
  - Integrated date range + region + biome filters

- **map_viewer.py**: Interactive spatial visualization
  - Folium-based map of Brazil
  - Marker layers: Fire hotspots (red), Deforestation areas (orange), Vegetation changes (green)
  - Click-on-marker popups with details
  - Zoom to region capability
  - Layer toggle controls (show/hide data types)

- **alerts.py**: Alert management interface
  - Alert list sorted by severity and recency
  - Filter by alert type and status
  - Click-through to map and detailed info
  - Archive/dismiss functionality

- **trends.py**: Time-series analysis view
  - Region/biome/metric selection
  - Configurable date range
  - Trend line with slope indicator
  - Period comparison (side-by-side stats)
  - Export options

- **about.py**: Documentation and attribution
  - INPE data sources and API endpoints
  - Data definitions (DETER, PRODES, FOGO)
  - Update frequency documentation
  - Contact/support information

**Components**

- **filters.py**: Reusable filter UI elements
  - Geographic region multiselect (state/municipality/custom bounds)
  - Biome multiselect (Amazon, Cerrado, etc.)
  - Date range picker (calendar widget, relative dates like "last 30 days")
  - Alert threshold adjustments

- **charts.py**: Plotly-based chart wrappers
  - Time-series line charts
  - Bar charts for comparisons
  - Heatmaps for spatial intensity
  - Tooltips with INPE data sources

- **map.py**: Folium map wrapper
  - Base map of Brazil with state boundaries
  - Dynamic point/polygon layer rendering
  - Color-coding by severity or data type
  - Clustering for many markers

- **status_indicators.py**: Status and error displays
  - Data freshness badge (e.g., "updated 2 hours ago")
  - API status indicator (INPE service availability)
  - Error messages with fallback suggestions

#### 5. **Data Models** (`src/models/`)

**environmental.py**
- `EnvironmentalAlert`: alert_id, event_type, severity_level, location, detection_date, description, affected_area_km2, recommendation, status
- `EnvironmentalDataPoint`: data_point_id, data_type, location, value, collection_date, data_source (DETER/PRODES/FOGO), confidence_level
- `AlertThreshold`: alert_type, region, threshold_value, unit, is_active

**geographic.py**
- `GeographicRegion`: region_id, region_type (state/municipality/biome), name, polygon_geometry, area_km2
- `Biome`: biome_id, name, representative_states, area_km2, description
- `Coordinates`: latitude, longitude, accuracy_meters
- `BoundingBox`: min_lat, min_lon, max_lat, max_lon

**conversation.py**
- `ConversationSession`: session_id, user_id, start_time, end_time, context_data, messages[]
- `ConversationMessage`: role (user/assistant), content, timestamp, data_context
- `ContextData`: current_region, current_biome, date_range_start, date_range_end

**timeseries.py**
- `TimeSeriesData`: series_id, metric_type, time_period, value, location, data_source, trend_direction
- `TrendInfo`: direction (increasing/stable/decreasing), slope, confidence_score, change_percentage

**validation.py**
- Custom Pydantic validators:
  - INPE data format validation (required fields, coordinate ranges)
  - Biome/state reference validation
  - Date range validation (within available historical range)
  - Alert threshold validation (realistic ranges)

#### 6. **Database Layer** (`src/database/`)

**Development (SQLite)**
- File: `environment_tracker.db`
- Tables:
  - `conversation_sessions`: Store session context and history
  - `environmental_data_cache`: Temporary storage of API responses
  - `alerts`: Generated system alerts
  - `user_preferences`: (Future) User alert configurations

**Production (PostgreSQL + PostGIS)**
- Extensions: PostGIS for advanced geospatial queries
- Same table structure, optimized indexes on geographic columns
- Connection pooling (PgBouncer or similar)

### Technology Integration Points

#### **Streamlit Integration**
- Entry point: `src/app.py`
- Multi-page app structure: `@st.Page()` decorators
- Session state: Store current filters, conversation context, Langfuse session ID
- Caching: `@st.cache_data` for static geographic reference data
- Async support: `asyncio` for non-blocking INPE API calls
- Reactive updates: Streamlit re-runs on filter changes, new messages
- **Langfuse Session Tracking**: Each user session generates a Langfuse session ID for tracking conversations across page reloads

#### **Conversation Engine Integration**

**MVP** — `ConversationService` (no LangGraph):
- Linear pipeline: parse_query → retrieve_data → generate_response → update_context
- LLM calls via `LLMProvider`; all wrapped with Langfuse tracing decorators
- State persistence: `ConversationSession` serialised to SQLite via `SessionManager`
- Error handling: try/except with fallback response; session state preserved on failure

**Post-MVP** — LangGraph upgrade (when needed):
- Drop `ConversationService` internals; replace with LangGraph `StateGraph`
- Nodes: parse_query, retrieve_data, generate_response, update_context (same names as MVP steps)
- Edges: conditional routing, parallel retrieval branches
- Langfuse tracing extended with per-node latency via `@trace_langgraph_node`
- Callers (`conversation.py` page, tests) require no changes — upgrade is fully internal

#### **Pydantic Integration**
- All data models use Pydantic v2
- `BaseModel` inheritance for environmental, geographic, conversation entities
- Custom validators for INPE data formats and geographic bounds
- `BaseSettings` for configuration management (API keys, rate limits, alert thresholds)
- Response schema validation from INPE APIs

#### **uv Package Manager**
- `pyproject.toml`: Project metadata, dependency specification
- No Makefile — all workflows use `uv run` directly:
  - `uv sync` — install dependencies
  - `uv run streamlit run src/app.py` — start the app
  - `uv run pytest` — run tests
  - `uv run alembic upgrade head` — apply database migrations
  - `uv run alembic revision --autogenerate -m "..."` — generate a new migration
  - `docker compose up -d` — start local services (PostgreSQL, Redis; no uv wrapper needed)
- Dependency groups: main, dev, test

---

## Phase Breakdown with Dependencies

### Phase 0: Research (2-3 weeks)
**Outputs**: `research.md` (resolve all NEEDS CLARIFICATION)
- Investigate INPE API documentation (DETER, PRODES, FOGO)
- **Investigate TerraBrasilis** (INPE's data platform at terrabrasilis.dpi.inpe.br) — it exposes OGC WFS/WMS services and REST APIs for DETER and PRODES; some datasets may only be available as bulk file downloads (GeoTIFF, Shapefile) rather than traditional REST endpoints. Actual access method will influence client architecture.
- Determine current API access methods (REST, TerraBrasilis WFS/WMS, bulk downloads, authentication)
- Research Streamlit + `ConversationService` async patterns for MVP; separately document LangGraph integration as the post-MVP upgrade path
- Research Langfuse integration with OpenAI API (direct, no LangGraph dependency for MVP)
- Explore geospatial library best practices (GeoPandas, Folium)
- Document PostgreSQL + PostGIS setup for production

**Unknowns to Research**
1. INPE/TerraBrasilis API specifications (exact endpoints, rate limits, authentication, response formats — REST vs. WFS/WMS vs. file download)
2. INPE historical data availability (24+ months, granularity, update frequency)
3. `ConversationService` async patterns and session memory footprint under 50+ concurrent users
4. Langfuse SDK integration with plain OpenAI calls (no LangGraph dependency for MVP tracing)
5. Streamlit performance optimization with 10k+ map markers
6. Geographic reference data sources (accurate state/biome boundaries)
7. Langfuse cost tracking and latency monitoring best practices for LLM applications

### Phase 1: Design & Contracts (2-3 weeks)
**Prerequisites**: Phase 0 research complete
**Outputs**: `data-model.md`, `contracts/`, `quickstart.md`, updated `.github/copilot-instructions.md`

**1a. Data Model Definition**
- Create Pydantic schemas for all entities (environmental, geographic, conversation)
- Document validation rules (INPE data formats, coordinate ranges)
- Define relationships (alerts → locations, time-series → regions)
- State transitions (conversation states, alert lifecycle)

**1b. Interface Contracts**
- **INPE Data Contracts**: Define expected response schemas from DETER, PRODES, FOGO APIs
  - Contract file: `contracts/inpe-data-contract.json`
  - Validates API response structure against Pydantic models
  
- **Conversation API Contract**: Define query/response format for LLM integration
  - Contract file: `contracts/conversation-api.json`
  - Structured intent extraction format, response citation format
  
- **Dashboard State Contract**: Define filter state and data requirements
  - Contract file: `contracts/dashboard-state.json`
  - Filter combinations, data freshness requirements, visualization formats

**1c. Implementation Roadmap Output**
- Generate `quickstart.md`:
  - Environment setup (Python 3.11+, uv installation)
  - API key configuration (INPE, OpenAI)
  - Running locally: `uv sync && streamlit run src/app.py`
  - Database initialization
  
- Update `.github/copilot-instructions.md` with plan reference

**1d. Agent Context Update**
- Run agent context update script to point to generated plan

### Phase 2: Implementation (6-8 weeks)

#### **Sprint 1: Foundation & INPE Integration (2 weeks)**
- Dependencies: Phase 1 contracts complete
- Tasks:
  - Set up project structure (directories, dependencies in `pyproject.toml`)
  - Create Pydantic models and validation
  - **Implement `LLMProvider` abstraction** (`services/llm_provider.py`) with concrete implementations for OpenAI and a stub for future providers (Claude, local LLaMA); all conversation and analysis services call `LLMProvider`, never the SDK directly
  - Implement BaseINPEClient with rate limiting, retry logic, caching
  - Implement DETER client + unit tests
  - Implement PRODES client + unit tests
  - Basic cache manager (SQLite)
  - Setup CI/CD for test execution

**Deliverables**:
- INPE integration layer with 3 data sources accessible
- Unit test coverage >80% for models and clients
- Cache mechanism functional

#### **Sprint 2: Data Services & Dashboard Foundation (2 weeks)**
- Dependencies: Sprint 1 complete
- Tasks:
  - Implement FOGO client
  - Implement analysis services (trend analyzer, alert generator, geospatial)
  - Load geographic reference data (GeoJSON for biomes, states)
  - Create basic Streamlit dashboard skeleton
  - Implement data aggregation service
  - Integration tests for multi-source data combining

**Deliverables**:
- All INPE clients functional with integration tests
- Analysis services can process and aggregate INPE data
- Dashboard loads with sample data, filters work

#### **Sprint 3: Conversational Engine (2 weeks)**
- Dependencies: Dashboard foundation, INPE integration solid

> **Architecture decision**: MVP uses a simple `ConversationService` loop — linear pipeline with no graph wiring. LangGraph is **not** a Sprint 3 task. It becomes relevant only when a concrete need for branching or parallel retrieval emerges post-MVP (see upgrade triggers in Component Specs above).

- Tasks:
  - Implement query parser (LLM-based or hybrid)
  - Implement `ConversationService`: message history + `LLMProvider` call + `SessionManager`
  - Implement response generator with INPE data formatting
  - Session manager for conversation history
  - Conversation page in Streamlit
  - System prompts and few-shot examples (Portuguese-first)
  - Implement Langfuse SDK initialization (`langfuse_config.py`)
  - Add Langfuse tracing to all LLM calls via `langfuse_wrapper.py`
  - Add Langfuse session tracking to Streamlit session state

**Deliverables**:
- Multi-turn conversations work end-to-end
- Geographic context extraction from queries
- INPE data properly cited in responses
- Dashboard + conversation pages integrated
- **Langfuse observability active**: All LLM calls are traced and visible in Langfuse dashboard
- Cost and latency tracking working

#### **Sprint 4: Visualization & UX Polish (2 weeks)**
- Dependencies: Core features working
- Tasks:
  - Interactive map with Folium (fire hotspots, deforestation areas)
  - Additional visualizations (time-series trends, heatmaps)
  - Alert management interface
  - Data export (CSV, PDF with proper attribution)
  - UI refinement (styles, responsiveness, loading states)
  - Performance optimization (caching, lazy loading)

**Deliverables**:
- Full UI with all 6+ pages functional
- Map rendering performs well (10k+ markers)
- Dashboard loads <5 seconds
- Export functionality works

#### **Sprint 5: Testing & Documentation (1-2 weeks)**
- Dependencies: Feature-complete implementation
- Tasks:
  - Contract tests for all INPE integrations
  - End-to-end test scenarios matching user stories
  - Performance testing (concurrent conversations, API response times)
  - **Langfuse observability verification**:
    - Verify all LLM calls are traced in Langfuse
    - Validate cost calculations (token counting accuracy)
    - Verify latency tracking and node execution times
    - Test Langfuse session correlation with Streamlit sessions
    - Performance benchmarking with Langfuse overhead measurement
  - Documentation (architecture, deployment, data definitions, Langfuse setup)
  - Security review (API key handling, data validation, Langfuse credentials)
  - Load testing with 50+ concurrent users and Langfuse monitoring
  - **Profile per-session memory**: each Streamlit session holding `ConversationSession` state adds memory; measure and set a session memory ceiling before go-live (if LangGraph is later introduced, re-profile — its state graphs are heavier)

**Deliverables**:
- >80% test coverage across all modules
- Performance verified against success criteria
- Complete documentation of features, APIs, and Langfuse observability
- Security recommendations documented
- **Langfuse dashboards**: Cost tracking, latency monitoring, error rate dashboards configured
- Langfuse alert rules set up (e.g., alert on >5% error rate)

---

## Data Flow & API Integration Strategy

### INPE API Integration Pattern

```
User Query on Dashboard/Conversation
        ↓
Streamlit UI (page.py or chat interface)
        ↓
Service Layer (e.g., ConversationService, AnalysisService)
        ↓
Query Validation (Pydantic)
        ↓
Cache Check
    ├→ Hit: Return cached data
    └→ Miss: Proceed to INPE fetch
        ↓
INPE Client (DETER/PRODES/FOGO)
     - Construct request (endpoint, params, auth)
     - Rate limit check
     - Execute async HTTP request (HTTPX)
     - Validate response against contract schema
     - Parse and transform response data
        ↓
Cache Write (SQLite/Redis with TTL)
        ↓
Data Aggregation (if multi-source query)
        ↓
Analysis (trend, alerts, spatial filtering)
        ↓
Response Formatting
    ├→ For Dashboard: Plotly/Folium visualization
    ├→ For Conversation: Natural language w/ citations
    └→ For Export: CSV/PDF with metadata
        ↓
Return to User
```

### Rate Limiting Strategy

- **DETER**: 1 request/second (respect INPE documented limits)
- **PRODES**: 2 requests/second (less frequent updates)
- **FOGO**: 5 requests/minute (real-time data, higher latency tolerance)
- Implementation: Token bucket algorithm in BaseINPEClient
- Backoff strategy: Exponential backoff with jitter on rate limit errors

### Cache Strategy

| Data Source | Data Type | TTL | Cache Key Pattern |
|-------------|-----------|-----|-------------------|
| DETER | Recent alerts | 24h | `deter:region:{region_id}:{date}` |
| DETER | Historical time-series | 30d | `deter:timeseries:{region_id}:{period}` |
| PRODES | Monthly/annual data | 30d | `prodes:{year}:{month}` |
| FOGO | Current hotspots | 4h | `fogo:hotspots:{timestamp_hour}` |
| Geographic | Biome/state boundaries | ∞ | `geo:region:{type}:{id}` |

### Error Handling & Fallbacks

```
INPE API Request
    ├─→ Success (200)
    │   └─→ Validate response schema
    │       ├─→ Valid: Cache + return data
    │       └─→ Invalid: Cache last known valid response, alert user
    │
    ├─→ Rate Limited (429)
    │   └─→ Backoff + retry (exponential)
    │
    ├─→ Server Error (5xx)
    │   └─→ Return cached data if available
    │       └─→ Display "data may be outdated" warning
    │
    └─→ Network Timeout / No Response
        └─→ Return last known data with stale warning
            └─→ Suggest user retry or adjust query
```

---

## Testing Strategy

### Unit Tests (`tests/unit/`)

**Pydantic Models** (`test_models.py`)
- Validate model creation with valid data
- Reject invalid geographic coordinates
- Enforce required fields
- Serialize/deserialize round-trip

**Query Parser** (`test_query_parser.py`)
- Extract geographic context from diverse phrasing
- Identify metrics of interest
- Handle ambiguous region names
- Language detection (Portuguese/English)

**Alert Generator** (`test_alert_generator.py`)
- Threshold evaluation with sample data
- Alert severity classification
- Edge cases (no data, boundary conditions)

**Trend Analyzer** (`test_trend_analyzer.py`)
- Correct trend direction calculation
- Confidence score computation
- Period comparison calculations
- Empty/sparse time-series handling

**Geospatial Queries** (`test_geospatial.py`)
- Coordinate validation (Brazil bounds)
- Point-in-polygon (which biome/state?)
- Coordinate transformations

### Integration Tests (`tests/integration/`)

**INPE Clients** (`test_inpe_*.py` for DETER, PRODES, FOGO)
- Mock responses: Validate parsing of sample INPE responses
- Live integration: Test against actual INPE APIs (separate test suite)
- Error cases: Handle API failures gracefully
- Rate limiting: Verify backoff behavior

**Data Aggregation** (`test_data_aggregation.py`)
- Multi-source combining (DETER + FOGO for same region)
- Conflict resolution
- Time-series alignment

**Conversation Flow** (`test_conversation_flow.py`)
- `ConversationService` pipeline execution
- Multi-turn context preservation
- Query → data retrieval → response generation pipeline

**Streamlit UI Pages** (`test_streamlit_pages.py`)
- Page rendering with sample data
- Filter application and updates
- Navigation between pages

### Contract Tests (`tests/contract/`)

**INPE Data Contract** (`test_inpe_data_contract.py`)
- Validates all INPE API responses against schema
- Ensures required fields present and typed correctly
- Validates geographic data (coordinates, polygons)

**Conversation API Contract** (`test_conversation_contract.py`)
- Validates query parsing output format
- Ensures response includes proper citations
- Validates LLM prompt structure

### Performance Tests

**Dashboard Load Time**: <5 seconds
- Test with realistic data volume (1000+ alerts, 24+ months history)
- Measure Streamlit render time, including visualizations

**API Response Time**: <2 seconds
- Mock INPE responses, measure end-to-end latency
- Test with various result set sizes

**Concurrent Conversations**: 50+ users
- Load test with 50+ concurrent `ConversationService` sessions
- Monitor response time, memory usage

### Test Data

- Sample INPE responses stored in `tests/data/` (fixtures for mocking)
- Test GeoJSON with 3-5 test regions/biomes
- Historical time-series fixture (24 months sample data)
- Test conversation transcripts (multi-turn examples)

---

## Deployment Considerations

### Development Environment

**Default path (SQLite — no services needed):**
```bash
uv sync
cp .env.example .env
# Configure: OPENAI_API_KEY, LANGFUSE_* keys
uv run alembic upgrade head
uv run streamlit run src/app.py
```

**Prod-parity path (PostgreSQL+PostGIS + Redis via Docker Compose):**
```bash
docker compose up -d        # starts postgres, redis, langfuse (optional profile)
cp .env.example .env
# Set DATABASE_URL=postgresql://... and REDIS_URL=redis://...
uv sync
uv run alembic upgrade head
uv run streamlit run src/app.py
```

`docker-compose.yml` defines three services:
- **postgres**: `postgis/postgis:15-3.4` image — PostGIS-enabled PostgreSQL
- **redis**: `redis:7-alpine` — lightweight cache layer
- **langfuse** *(optional profile `--profile langfuse`)*: self-hosted Langfuse server for developers who prefer not to use Langfuse Cloud

### Production Deployment

#### Option 1: Cloud-hosted (Recommended for MVP)
- **Streamlit Cloud**: Direct GitHub integration, automatic builds
  - Pros: Simple, free tier, automatic HTTPS
  - Cons: Limited customization, shared infrastructure
  
- **AWS/GCP/Azure**: Containerized deployment
  - Build Docker image with Python 3.11, install dependencies via uv
  - Use managed PostgreSQL + PostGIS
  - Load balancer for 50+ concurrent users
  - CloudFront/CDN for static assets
  - Environment variables: API keys, database connection string

#### Option 2: Self-hosted
- Ubuntu/Debian server
- Nginx reverse proxy → Streamlit app
- PostgreSQL + PostGIS for production database
- Redis for distributed cache
- GUNICORN/Uvicorn for ASGI server
- Systemd service management

### Container Setup

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gdal-bin libgdal-dev
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --production
COPY src/ src/
COPY data/ data/
EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "src/app.py"]
```

### Environment Configuration

```env
# .env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
INPE_DETER_ENDPOINT=https://...
INPE_PRODES_ENDPOINT=https://...
INPE_FOGO_ENDPOINT=https://...
DATABASE_URL=postgresql://user:pass@localhost/environment_tracker
REDIS_URL=redis://localhost:6379
CACHE_TTL_DEFAULT=3600
ALERT_THRESHOLD_FIRES=100  # hotspots per 24h per region
ALERT_THRESHOLD_DEFORESTATION=50  # % above 12-month avg

# Langfuse Observability
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...
LANGFUSE_ENDPOINT=https://cloud.langfuse.com  # or self-hosted
```

### Monitoring & Logging

- **Logging**: Python logging module with structured JSON output
- **Observability & Tracing with Langfuse**: 
  - **LLM Call Tracking**: All OpenAI API calls traced with Langfuse SDK
    - Cost tracking per conversation session and per user
    - Latency monitoring for LM generations
    - Input/output token counting
    - Temperature and model configuration logging
  
  - **Conversation Pipeline Tracing**:
    - Trace execution of `ConversationService` steps (parse_query, retrieve_data, generate_response)
    - Monitor time spent in each step
    - Identify performance bottlenecks in multi-turn dialogues
    - *(Post-MVP: extend with per-node tracing when LangGraph is introduced)*
  
  - **INPE API Integration Observability**:
    - Track INPE API calls (endpoint, response time, error rates)
    - Monitor cache hit/miss rates per data source
    - Track rate limiting and backoff behavior
  
  - **User Session Analytics**:
    - Conversation length and complexity metrics
    - User query patterns and common tasks
    - System response quality metrics (query interpretation accuracy)
    - User satisfaction feedback correlation
  
  - **Dashboards & Alerts** (in Langfuse UI):
    - Real-time LLM cost tracking
    - Response latency heatmaps
    - Error rate monitoring with alerts on > 5% error rate
    - Cache performance dashboards
    - Conversation funnel (queries → successful responses)

- **Metrics**: Track API response times, cache hit rates, error counts, LLM token usage, conversation duration
- **Alerts**: Alert on INPE API unavailability, high error rates, LLM cost anomalies, conversation pipeline failures
- **Data Freshness**: Monitor last update time from each INPE source

### Database Migrations

- Schema versioning with Alembic from day one (avoids retrofitting later)
- Initial schema generated via `alembic revision --autogenerate` from SQLAlchemy models
- Migrations tracked in `alembic/versions/` and committed to the repo
- Backup strategy: Automated PostgreSQL backups (AWS RDS, managed services)

### Security Considerations

- **API Keys**: Store in environment variables, never commit
- **Data Validation**: All INPE data validated at ingestion via Pydantic
- **Rate Limiting**: Implemented at client level to prevent INPE API abuse
- **HTTPS**: Required for production (handled by cloud provider or Nginx)
- **CORS**: Configured if exposing API endpoints (future phase)
- **Authentication**: Out of scope for MVP, can be added via Streamlit auth plugins

### Scalability Path

**MVP (50 concurrent users)**
- Single Streamlit instance
- SQLite development database or RDS small instance
- Redis for caching (optional, local for MVP)
- Manual INPE data fetching on dashboard load

**Phase 2 (100+  concurrent users)**
- Load balancer with 2-3 Streamlit instances
- PostgreSQL + PostGIS with read replicas
- Redis cluster for distributed cache
- Background job queue for data refresh (Celery/RQ)
- Dedicated INPE data sync service (hourly updates)

**Phase 3 (500+ concurrent users)**
- Kubernetes deployment with auto-scaling
- Managed database (AWS RDS Aurora, GCP Cloud SQL)
- CDN for static map tiles and geographic reference data
- Separate API server for non-interactive queries
- Advanced caching strategy (HTTP cache headers, edge caching)

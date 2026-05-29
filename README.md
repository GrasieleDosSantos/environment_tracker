# Environmental Status Tracker for Brazil

Conversational + visual interface to Brazilian environmental monitoring data from INPE (Instituto Nacional de Pesquisas Espaciais). Integrates DETER (deforestation alerts), PRODES (Amazon deforestation), and FOGO (fire detection) into a Streamlit dashboard with LLM-powered multi-turn conversation in Portuguese and English.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Default path (SQLite — no services needed)

```bash
uv sync
cp .env.example .env
# Edit .env: set OPENAI_API_KEY at minimum
uv run alembic upgrade head
uv run streamlit run src/app.py
```

App is available at http://localhost:8501

### Prod-parity path (PostgreSQL + Redis via Docker Compose)

```bash
docker compose up -d           # starts postgres, redis
cp .env.example .env
# Edit .env: set DATABASE_URL=postgresql://envtracker:envtracker@localhost:5432/environment_tracker
#            set REDIS_URL=redis://localhost:6379/0
#            set OPENAI_API_KEY
uv sync
uv run alembic upgrade head
uv run streamlit run src/app.py
```

### Optional: self-hosted Langfuse (LLM observability)

```bash
docker compose --profile langfuse up -d
# Langfuse UI available at http://localhost:3000
# Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_ENDPOINT=http://localhost:3000 to .env
```

## uv Run Commands

| Command | Description |
|---------|-------------|
| `uv sync` | Install / update all dependencies |
| `uv run streamlit run src/app.py` | Start the Streamlit app |
| `uv run pytest` | Run all tests |
| `uv run pytest tests/unit/` | Run unit tests only |
| `uv run pytest tests/integration/` | Run integration tests |
| `uv run pytest tests/contract/` | Run contract tests |
| `uv run pytest --cov=src --cov-report=html` | Tests with HTML coverage report |
| `uv run alembic upgrade head` | Apply all pending database migrations |
| `uv run alembic revision --autogenerate -m "..."` | Generate a new migration |
| `uv run alembic downgrade -1` | Roll back the last migration |
| `uv run ruff check src/ tests/` | Lint code |
| `uv run ruff format src/ tests/` | Format code |
| `uv run mypy src/` | Type-check |

## Docker Compose Service Commands

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start postgres + redis |
| `docker compose --profile langfuse up -d` | Start postgres + redis + langfuse |
| `docker compose down` | Stop all services |
| `docker compose down -v` | Stop all services and remove volumes |
| `docker compose logs -f postgres` | Follow postgres logs |

## Environment Configuration

See [.env.example](.env.example) for all available variables. Minimum required:

- `OPENAI_API_KEY` — for LLM-powered conversation
- `DATABASE_URL` — defaults to SQLite; set to PostgreSQL for production

## Architecture

```
UI Layer (Streamlit)
  ├── Conversation page (Portuguese/English chat)
  ├── Dashboard (INPE metrics + filters)
  ├── Map Viewer (fire hotspots, deforestation polygons)
  ├── Alerts (threshold-triggered events)
  ├── Trends (time-series analysis + export)
  └── About (INPE data sources + attribution)

Application Logic
  ├── LangGraph conversation engine (with Langfuse tracing)
  ├── Analysis services (aggregator, trend analyzer, alert generator)
  └── Geospatial service (biome/state resolution)

Data Services
  ├── DETER client (deforestation alerts, 24h cache)
  ├── PRODES client (Amazon deforestation program, 30d cache)
  └── FOGO client (fire hotspots, 4h cache)

Storage
  ├── SQLite (dev) / PostgreSQL+PostGIS (prod)
  └── GeoJSON reference data (biomes, states)
```

## Data Sources

| Source | System | Description | Update Frequency |
|--------|--------|-------------|------------------|
| INPE/DETER | Detection of Changes in Native Vegetation | Near-real-time deforestation alerts | Daily |
| INPE/PRODES | Amazon Deforestation Monitoring | Annual deforestation mapping | Annual/Monthly |
| INPE/FOGO | Fire Detection | Active fire hotspots | Every 3–6 hours |

Data accessed via [TerraBrasilis](https://terrabrasilis.dpi.inpe.br/) (INPE's OGC WFS/WMS platform).

## Specification

See [specs/001-environmental-tracker/](specs/001-environmental-tracker/) for:
- `spec.md` — user stories and requirements
- `plan.md` — implementation plan
- `tasks.md` — task breakdown

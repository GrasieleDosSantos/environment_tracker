# Environment Tracker - Project Constitution

## Project Vision
A Python-based application that monitors and analyzes environmental data specific to Brazilian territory, primarily leveraging INPE (Instituto Nacional de Pesquisas Espaciais) data sources to provide users with actionable insights and interactive dashboards through a conversational interface.

## Core Principles

### 1. Data-Driven Insights
- Prioritize accuracy and reliability of environmental data
- Enable users to make informed decisions through clear, contextual analysis
- Ensure data sources are transparent and properly cited

### 2. User-Centric Conversational Interface
- Design interactions that feel natural and intuitive
- Minimize cognitive load through progressive disclosure of information
- Support diverse user expertise levels (novice to expert)

### 3. Accessibility and Transparency
- Make environmental data accessible to all users regardless of technical background
- Provide clear explanations of metrics, trends, and recommendations
- Document data sources and methodology

### 4. Maintainability and Scalability
- Write clean, modular, and well-documented code
- Design for easy integration of new data sources
- Plan for growth in users and data volume

## Technology Stack

### Key Components

#### Data Access
- **Primary Data Source**: INPE (Instituto Nacional de Pesquisas Espaciais) APIs and data repositories
  - INPE Monitoring of the Amazon Forest (SAD - Sistema de Alerta de Desmatamento)
  - PRODES (Program for Calculation of Deforestation in the Amazon)
  - FOGO (Real-time fire detection and monitoring)
  - DETER (System for Detection of Changes in Native Vegetation)
  - Satellite imagery and derived products from Landsat, Sentinel
- **Geographic Scope**: Brazilian territory, with focus on biomes (Amazon, Cerrado, Caatinga, Atlantic Forest, Pantanal)
- **API Integration**: RESTful and REST-based services from INPE public data repositories
- **Data Fetching**: Asynchronous request handling with proper rate limiting respect
- **Caching**: Local caching to minimize API calls and improve performance

#### Processing & Analysis
- **Data Processing**: Pandas for data manipulation and aggregation
- **Geospatial Analysis**: GeoPandas, Rasterio for spatial data processing
- **Analytics**: NumPy/SciPy for numerical analysis and trend detection
- **Time Series**: Handle temporal environmental data analysis
- **Satellite Imagery**: GDAL/OGR for reading satellite data formats from INPE

#### User Interface
- **Dashboard Framework**: Streamlit OR Dash (for interactive web dashboards)
- **Conversational Engine**: LLM integration (OpenAI API, LLaMA, or similar) for chat capabilities
- **Data Visualization**: Plotly/Matplotlib for charts and graphs

#### Backend/Storage
- **Database**: SQLite for local development; PostgreSQL for production
- **Logging**: Python logging module with structured logs
- **Configuration**: Environment variables for API keys and settings

## Quality Standards

### Code Quality
- Follow PEP 8 style guidelines
- Maintain test coverage ≥ 80% for core modules
- Use type hints for function parameters and returns
- Document public functions with docstrings (Google style)

### Performance
- API response time: < 2 seconds for single queries
- Dashboard load time: < 5 seconds
- Support concurrent conversations

### Reliability
- Graceful error handling for API failures
- Fallback mechanisms for unavailable data sources
- Data validation at all entry points

## Development Guidelines

### Brazilian Environmental Context
- Application focuses on monitoring Brazilian biomes: Amazon, Cerrado, Caatinga, Atlantic Forest, Pantanal, and Coastal zones
- Primary environmental concerns: deforestation, fire activity, land use changes, climate impacts
- Data sources are authoritative: INPE is the official Brazilian government agency for environmental monitoring
- All alerts and metrics must cite INPE as the source and follow official definitions and measurements
- Respect regional differences and specific environmental challenges of each biome

### Version Control
- Use feature branches for new work
- Write clear, descriptive commit messages
- Submit pull requests with test coverage

### INPE Data Integration
- INPE integrations require:
  - Documentation of API endpoint, rate limits, and authentication requirements
  - Proper handling of satellite data formats (GeoTIFF, NetCDF, HDF5 where applicable)
  - Spatial data validation (Brazilian coordinates, CRS transformations)
  - Error handling for common failure modes specific to satellite data services
  - Unit tests for data parsing and spatial operations
  - Integration tests with live INPE services
  - Citation of INPE and acknowledgment of data source in outputs

### Conversational Features
- LLM interactions must:
  - Be based on actual application data
  - Include context about data freshness
  - Provide citations for data sources
  - Handle edge cases gracefully

## Minimum Viable Product (MVP) Features

1. **INPE Data Integration**
   - Integration with at least one INPE primary service (e.g., DETER, PRODES, or FOGO)
   - Real-time or near-real-time deforestation/fire alerts for Brazilian biomes
   - Proper handling of spatial data and geographic filtering by biome or state

2. **Brazilian Environmental Analysis**
   - Deforestation rate calculations and trend analysis
   - Fire detection and activity monitoring
   - Biome-specific metrics and insights
   - Temporal trends and seasonal analysis

3. **Interactive Dashboard**
   - Map-based visualization of Brazilian territory with biome boundaries
   - Real-time or updated alert display
   - Time-series analysis of environmental changes
   - Filtering by biome, state, and date range

4. **Conversational Interface**
   - Natural language queries about Brazilian environmental status
   - Questions about deforestation trends, fire activity, and biome health
   - Response generation based on INPE data
   - Context-aware conversations about specific regions

## Success Metrics

- Users can retrieve and visualize Brazilian environmental data from INPE without errors
- Dashboard loads and responds within 5 seconds with current INPE data
- Deforestation and fire alerts are displayed with < 1 hour delay from INPE publication
- Conversational queries about Brazilian environmental status are answered accurately with proper INPE data citations
- System handles INPE API rate limiting and downtime gracefully
- Code is maintainable with clear documentation of INPE data formats and processing logic
- Proper geospatial accuracy for Brazilian territory (coordinate systems, biome boundaries)

## Dependencies Management

- Regular dependency audits for security vulnerabilities
- Automated testing on dependency updates
- Lock dependency versions in production deployments
- Document any Python version constraints

## Future Considerations

- Multi-user support and authentication
- Predictive analytics and forecasting for deforestation and fire risks
- Mobile application support for field teams and NGOs
- Advanced visualization capabilities (3D terrain, time-lapse animations)
- Data export functionality (PDF, CSV, GeoJSON)
- Real-time SMS/email/push notifications for critical alerts
- Integration with additional INPE datasets (climate, precipitation, temperature)
- Multi-language support (Portuguese, English, Spanish)
- Integration with complementary datasets (IBAMA enforcement data, indigenous territories)
- Collaboration features for environmental monitoring teams
- API for external applications to consume processed INPE data










from enum import Enum


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    RESOLVED = "resolved"


class AlertType(str, Enum):
    FIRE_OUTBREAK = "fire_outbreak"
    DEFORESTATION_SPIKE = "deforestation_spike"
    VEGETATION_LOSS = "vegetation_loss"


class DataType(str, Enum):
    FIRE_HOTSPOT = "fire_hotspot"
    DEFORESTATION_AREA = "deforestation_area"
    VEGETATION_INDEX = "vegetation_index"


class INPESource(str, Enum):
    DETER = "DETER"
    PRODES = "PRODES"
    FOGO = "FOGO"


class TrendDirection(str, Enum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


class RegionType(str, Enum):
    STATE = "state"
    MUNICIPALITY = "municipality"
    BIOME = "biome"
    PROTECTED_AREA = "protected_area"


class Language(str, Enum):
    PT = "pt"
    EN = "en"


BIOMES: list[dict[str, str]] = [
    {"id": "amazonia", "name": "Amazônia", "name_en": "Amazon"},
    {"id": "cerrado", "name": "Cerrado", "name_en": "Cerrado"},
    {"id": "caatinga", "name": "Caatinga", "name_en": "Caatinga"},
    {"id": "mata_atlantica", "name": "Mata Atlântica", "name_en": "Atlantic Forest"},
    {"id": "pantanal", "name": "Pantanal", "name_en": "Pantanal"},
    {"id": "pampa", "name": "Pampa", "name_en": "Pampas"},
]

BIOME_IDS: list[str] = [b["id"] for b in BIOMES]

# Brazilian states: ISO 3166-2:BR codes → names
STATES: dict[str, str] = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}

STATE_CODES: list[str] = list(STATES.keys())

# Legal Amazon states (used for "Amazônia Legal" filter)
LEGAL_AMAZON_STATES: list[str] = ["AC", "AP", "AM", "MA", "MT", "PA", "RO", "RR", "TO"]

# Brazil bounding box (WGS84)
BRAZIL_BOUNDS = {
    "min_lat": -33.75,
    "max_lat": 5.27,
    "min_lon": -73.99,
    "max_lon": -28.84,
}

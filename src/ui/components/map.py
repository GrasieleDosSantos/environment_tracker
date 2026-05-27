"""Folium map components for environmental data visualisation (US3).

Entry point: ``render_brazil_map()``.  Returns a ``folium.Map`` ready for
``st_folium()``.  All heavy data loading is done by the caller so this module
stays pure-render.

Point-count thresholds (from research.md T000f):
  < 500   → individual CircleMarker
  500–5 k → MarkerCluster
  > 5 000 → FastMarkerCluster
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import folium
from branca.element import MacroElement
from folium.plugins import FastMarkerCluster, MarkerCluster
from jinja2 import Template

from src.config.constants import BIOMES, STATES
from src.services.inpe_integration.deter_client import DETERAlert
from src.services.inpe_integration.fogo_client import FireHotspot

_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "geojson"

_BRAZIL_CENTER = (-14.24, -51.93)
_BRAZIL_ZOOM = 4

# Colour palette aligned with styles.py
_FIRE_COLOUR = "#E74C3C"
_DEFOR_COLOUR = "#E67E22"
_STATE_BORDER = "#4A7C59"
_BIOME_FILL = "#27AE60"


# ------------------------------------------------------------------ #
# Map legend                                                            #
# ------------------------------------------------------------------ #

class _MapLegend(MacroElement):
    """Floating bottom-right legend injected as a Leaflet control."""

    def __init__(
        self,
        fire: str = _FIRE_COLOUR,
        defor: str = _DEFOR_COLOUR,
        state: str = _STATE_BORDER,
        biome: str = _BIOME_FILL,
    ) -> None:
        super().__init__()
        self._name = "MapLegend"
        # Colours are baked into the template string at construction time
        # so Jinja2 doesn't need to resolve them as variables.
        self._template = Template(f"""
            {{% macro script(this, kwargs) %}}
            var legend = L.control({{position: 'bottomright'}});
            legend.onAdd = function(map) {{
                var div = L.DomUtil.create('div', 'info legend');
                div.style.cssText = [
                    'background:white',
                    'padding:8px 12px',
                    'border-radius:6px',
                    'box-shadow:0 2px 6px rgba(0,0,0,0.25)',
                    'font-size:12px',
                    'line-height:1.9',
                    'min-width:195px',
                ].join(';');
                div.innerHTML =
                    '<b style="font-size:13px">Legenda / Legend</b>' +
                    '<table style="border-collapse:collapse;margin-top:4px">' +
                    '<tr><td style="padding-right:6px">' +
                      '<svg width="14" height="14"><circle cx="7" cy="7" r="6"' +
                      ' fill="{fire}" fill-opacity="0.8" stroke="{fire}" stroke-width="0.5"/></svg>' +
                    '</td><td>Focos de Calor / Fire Hotspots</td></tr>' +
                    '<tr><td colspan="2" style="padding-left:4px;padding-bottom:3px">' +
                      '<span style="font-size:10px;color:#666">' +
                        'Agrupados por proximidade. Cor do grupo = n.º de focos:<br>' +
                        'Clustered by proximity. Cluster colour = hotspot count:<br>' +
                        '<svg width="10" height="10"><circle cx="5" cy="5" r="4" fill="#6db96b"/></svg> &lt;10 &nbsp;' +
                        '<svg width="10" height="10"><circle cx="5" cy="5" r="4" fill="#f0c54d"/></svg> 10–100 &nbsp;' +
                        '<svg width="10" height="10"><circle cx="5" cy="5" r="4" fill="#d9534f"/></svg> &gt;100' +
                      '</span>' +
                    '</td></tr>' +
                    '<tr><td>' +
                      '<svg width="14" height="14"><rect width="14" height="14"' +
                      ' fill="{defor}" fill-opacity="0.5" stroke="{defor}" stroke-width="1"/></svg>' +
                    '</td><td>Alertas DETER / Deforestation</td></tr>' +
                    '<tr><td>' +
                      '<svg width="14" height="14"><line x1="0" y1="7" x2="14" y2="7"' +
                      ' stroke="{state}" stroke-width="1.5"/></svg>' +
                    '</td><td>Estados / States</td></tr>' +
                    '<tr><td>' +
                      '<svg width="14" height="14"><line x1="0" y1="7" x2="14" y2="7"' +
                      ' stroke="{biome}" stroke-width="1.5" stroke-dasharray="3,2"/></svg>' +
                    '</td><td>Biomas / Biomes</td></tr>' +
                    '</table>';
                return div;
            }};
            legend.addTo({{{{ this._parent.get_name() }}}});
            {{% endmacro %}}
        """)


# ------------------------------------------------------------------ #
# GeoJSON loaders (module-level cache — loaded once per process)       #
# ------------------------------------------------------------------ #

_states_geojson: dict | None = None
_biomes_geojson: dict | None = None


def _load_states() -> dict:
    global _states_geojson
    if _states_geojson is None:
        with open(_DATA_DIR / "states.geojson", encoding="utf-8") as f:
            _states_geojson = json.load(f)
    return _states_geojson


def _load_biomes() -> dict:
    global _biomes_geojson
    if _biomes_geojson is None:
        with open(_DATA_DIR / "biomes.geojson", encoding="utf-8") as f:
            _biomes_geojson = json.load(f)
    return _biomes_geojson


# ------------------------------------------------------------------ #
# Layer builders                                                        #
# ------------------------------------------------------------------ #

def _state_boundaries_layer(
    highlight_states: list[str] | None = None,
) -> folium.GeoJson:
    """Thin state-outline layer; highlighted states get a stronger fill."""
    highlight_set = set(highlight_states or [])

    def style(feature: dict) -> dict:
        sigla = feature["properties"].get("sigla", "")
        active = sigla in highlight_set
        return {
            "color": _STATE_BORDER,
            "weight": 1.2,
            "fillOpacity": 0.15 if active else 0.0,
            "fillColor": _STATE_BORDER,
        }

    def tooltip(feature: dict) -> str:
        p = feature["properties"]
        return f"{p.get('nome', '')} ({p.get('sigla', '')})"

    return folium.GeoJson(
        _load_states(),
        name="Estados / States",
        style_function=style,
        tooltip=folium.GeoJsonTooltip(fields=["nome", "sigla"], aliases=["Estado", "UF"]),
    )


def _biome_boundaries_layer(
    highlight_biomes: list[str] | None = None,
) -> folium.GeoJson:
    """Biome outlines; highlighted biomes get a subtle green tint."""
    highlight_set = set(highlight_biomes or [])

    def style(feature: dict) -> dict:
        biome_id = feature["properties"].get("id", "")
        active = biome_id in highlight_set
        return {
            "color": _BIOME_FILL,
            "weight": 1.0,
            "dashArray": "4 4",
            "fillOpacity": 0.08 if active else 0.0,
            "fillColor": _BIOME_FILL,
        }

    return folium.GeoJson(
        _load_biomes(),
        name="Biomas / Biomes",
        style_function=style,
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Bioma"]),
        show=False,
    )


def _fire_layer(hotspots: list[FireHotspot]) -> folium.FeatureGroup:
    """Fire hotspot layer with adaptive clustering."""
    group = folium.FeatureGroup(name="🔥 Focos de Calor / Fire Hotspots", show=True)
    points = [
        h for h in hotspots
        if h.latitude is not None and h.longitude is not None
    ]

    if not points:
        return group

    n = len(points)

    if n > 5000:
        # FastMarkerCluster: JS-side callback, minimal Python overhead
        callback = """
        function(row) {
            var marker = L.circleMarker(
                [row[0], row[1]],
                {radius: 4, color: '#E74C3C', fillColor: '#E74C3C',
                 fillOpacity: 0.7, weight: 0.5}
            );
            marker.bindPopup(
                '<b>Foco de Calor</b><br>' +
                'Lat: ' + row[0].toFixed(4) + ', Lon: ' + row[1].toFixed(4) + '<br>' +
                (row[2] ? 'Estado: ' + row[2] + '<br>' : '') +
                (row[3] ? 'Satélite: ' + row[3] + '<br>' : '') +
                (row[4] ? 'Data: ' + row[4] + '<br>' : '') +
                (row[5] ? 'FRP: ' + parseFloat(row[5]).toFixed(1) + ' MW' : '')
            );
            return marker;
        }"""
        data = [
            [
                h.latitude, h.longitude,
                h.state or "",
                h.satellite_source or "",
                str(h.date_pas or (h.detection_time.date() if h.detection_time else "")),
                h.frp if h.frp is not None else "",
            ]
            for h in points
        ]
        FastMarkerCluster(data=data, callback=callback).add_to(group)

    elif n > 500:
        cluster = MarkerCluster(name="fires").add_to(group)
        for h in points:
            _fire_circle_marker(h).add_to(cluster)

    else:
        for h in points:
            _fire_circle_marker(h).add_to(group)

    return group


def _fire_circle_marker(h: FireHotspot) -> folium.CircleMarker:
    det_date = h.date_pas or (h.detection_time.date() if h.detection_time else None)
    popup_html = (
        "<b>🔥 Foco de Calor / Fire Hotspot</b><br>"
        f"<b>Estado / State:</b> {h.state or h.state_name or '—'}<br>"
        f"<b>Município / Municipality:</b> {h.municipality or '—'}<br>"
        f"<b>Bioma / Biome:</b> {h.biome or '—'}<br>"
        f"<b>Data / Date:</b> {det_date or '—'}<br>"
        f"<b>Satélite / Satellite:</b> {h.satellite_source or '—'}<br>"
        f"<b>FRP:</b> {f'{h.frp:.1f} MW' if h.frp else '—'}<br>"
        f"<b>Dias s/ chuva / Days w/o rain:</b> {h.days_without_rain or '—'}<br>"
        f"<small>Fonte: INPE BDQueimadas</small>"
    )
    radius = 5 + min((h.frp or 0) / 100, 8)
    return folium.CircleMarker(
        location=[h.latitude, h.longitude],
        radius=radius,
        color=_FIRE_COLOUR,
        fill=True,
        fill_color=_FIRE_COLOUR,
        fill_opacity=0.7,
        weight=0.5,
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"🔥 {h.state or ''} {det_date or ''}".strip(),
    )


def _deforestation_layer(alerts: list[DETERAlert]) -> folium.FeatureGroup:
    """DETER alert polygons layer. Skips records without geometry."""
    group = folium.FeatureGroup(name="🌳 Alertas DETER / Deforestation Alerts", show=True)

    poly_alerts = [
        a for a in alerts
        if a.geometry_type and a.geometry_coordinates is not None
    ]

    if not poly_alerts:
        return group

    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": a.geometry_type,
                "coordinates": a.geometry_coordinates,
            },
            "properties": {
                "classname": a.classname or "—",
                "state": a.state or "—",
                "municipality": a.municipality or "—",
                "biome": a.biome or "—",
                "area_km2": round(a.area_km2 or 0, 2),
                "view_date": str(a.view_date or "—"),
            },
        }
        for a in poly_alerts
    ]

    folium.GeoJson(
        {"type": "FeatureCollection", "features": features},
        name="deter_alerts",
        style_function=lambda _: {
            "color": _DEFOR_COLOUR,
            "weight": 1.2,
            "fillColor": _DEFOR_COLOUR,
            "fillOpacity": 0.35,
        },
        highlight_function=lambda _: {"fillOpacity": 0.6, "weight": 2},
        tooltip=folium.GeoJsonTooltip(
            fields=["classname", "state", "area_km2", "view_date"],
            aliases=["Tipo", "Estado", "Área (km²)", "Data"],
        ),
        popup=folium.GeoJsonPopup(
            fields=["classname", "state", "municipality", "biome", "area_km2", "view_date"],
            aliases=["Tipo / Type", "Estado / State", "Município / Municipality",
                     "Bioma / Biome", "Área (km²)", "Data / Date"],
            max_width=300,
        ),
    ).add_to(group)

    return group


# ------------------------------------------------------------------ #
# Public entry point                                                    #
# ------------------------------------------------------------------ #

def render_brazil_map(
    fire_hotspots: list[FireHotspot] | None = None,
    deter_alerts: list[DETERAlert] | None = None,
    show_fires: bool = True,
    show_deforestation: bool = True,
    show_biomes: bool = False,
    highlight_states: list[str] | None = None,
    highlight_biomes: list[str] | None = None,
    center: tuple[float, float] = _BRAZIL_CENTER,
    zoom_start: int = _BRAZIL_ZOOM,
) -> folium.Map:
    """Build and return a Folium map of Brazil with INPE data layers.

    Args:
        fire_hotspots:      FOGO hotspot records to plot.
        deter_alerts:       DETER alert records to plot as polygons.
        show_fires:         Whether the fire hotspot layer is visible by default.
        show_deforestation: Whether the DETER alert layer is visible by default.
        show_biomes:        Whether the biome boundary layer is visible by default.
        highlight_states:   State siglas to shade (e.g. active filter selection).
        highlight_biomes:   Biome IDs to shade.
        center:             Map centre (lat, lon).
        zoom_start:         Initial zoom level.
    """
    m = folium.Map(
        location=list(center),
        zoom_start=zoom_start,
        tiles=None,
    )
    folium.TileLayer(
        tiles="CartoDB positron",
        attr="© OpenStreetMap contributors © CARTO",
        control=False,
    ).add_to(m)

    # State & biome boundaries
    _state_boundaries_layer(highlight_states).add_to(m)
    biome_layer = _biome_boundaries_layer(highlight_biomes)
    biome_layer.show = show_biomes
    biome_layer.add_to(m)

    # Data layers
    if show_deforestation and deter_alerts:
        _deforestation_layer(deter_alerts).add_to(m)

    if show_fires and fire_hotspots:
        _fire_layer(fire_hotspots).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    _MapLegend().add_to(m)

    return m


def map_center_for_states(state_codes: list[str]) -> tuple[tuple[float, float], int]:
    """Return (centre, zoom) that roughly frames the given states."""
    # Approximate centroids for each UF (lat, lon)
    _CENTROIDS: dict[str, tuple[float, float]] = {
        "AC": (-9.0, -70.5), "AL": (-9.7, -36.7), "AP": (1.4, -51.9),
        "AM": (-3.5, -65.0), "BA": (-12.5, -41.7), "CE": (-5.1, -39.4),
        "DF": (-15.8, -47.9), "ES": (-19.6, -40.7), "GO": (-16.0, -49.6),
        "MA": (-4.9, -45.3), "MT": (-12.7, -56.1), "MS": (-20.5, -54.7),
        "MG": (-18.5, -44.6), "PA": (-3.8, -52.5), "PB": (-7.1, -36.8),
        "PR": (-24.9, -51.6), "PE": (-8.3, -37.9), "PI": (-7.7, -42.7),
        "RJ": (-22.3, -42.9), "RN": (-5.8, -36.6), "RS": (-30.2, -53.2),
        "RO": (-10.8, -62.9), "RR": (1.9, -61.2), "SC": (-27.2, -50.2),
        "SP": (-22.3, -48.8), "SE": (-10.6, -37.4), "TO": (-10.2, -48.3),
    }
    if not state_codes:
        return _BRAZIL_CENTER, _BRAZIL_ZOOM

    coords = [_CENTROIDS[s] for s in state_codes if s in _CENTROIDS]
    if not coords:
        return _BRAZIL_CENTER, _BRAZIL_ZOOM

    avg_lat = sum(c[0] for c in coords) / len(coords)
    avg_lon = sum(c[1] for c in coords) / len(coords)
    zoom = 5 if len(coords) > 3 else 6
    return (avg_lat, avg_lon), zoom

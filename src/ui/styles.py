"""Streamlit custom CSS: colour palette, card styles, filter sidebar, Portuguese-first fonts.

Call ``inject_custom_css()`` once at app startup (in app.py) to apply all styles.
"""

import streamlit as st

# ------------------------------------------------------------------ #
# Colour palette                                                        #
# ------------------------------------------------------------------ #

PALETTE = {
    "primary": "#1B6CA8",       # INPE blue
    "primary_light": "#4A9FD4",
    "primary_dark": "#0D4A7A",
    "accent_green": "#27AE60",  # healthy vegetation
    "accent_yellow": "#F39C12", # warning / moderate
    "accent_red": "#C0392B",    # alert / critical
    "accent_orange": "#E67E22", # deforestation
    "surface": "#FFFFFF",
    "surface_alt": "#F8F9FA",
    "border": "#DEE2E6",
    "text": "#212529",
    "text_muted": "#6C757D",
    "sidebar_bg": "#F0F4F8",
}

# ------------------------------------------------------------------ #
# CSS string                                                            #
# ------------------------------------------------------------------ #

_CSS = f"""
<style>
/* ── Typography: Portuguese-first font stack ───────────────────── */
html, body, [class*="css"] {{
    font-family: 'Source Sans Pro', 'Noto Sans', 'Open Sans',
                 'Helvetica Neue', Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
}}

/* ── Sidebar ────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {PALETTE['sidebar_bg']};
    border-right: 1px solid {PALETTE['border']};
}}

[data-testid="stSidebar"] .stMarkdown h3 {{
    color: {PALETTE['primary_dark']};
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}}

/* ── Metric / KPI cards ─────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    padding: 0.75rem 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}}

[data-testid="stMetricLabel"] {{
    color: {PALETTE['text_muted']};
    font-size: 0.78rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: .04em;
}}

[data-testid="stMetricValue"] {{
    color: {PALETTE['text']};
    font-size: 1.6rem;
    font-weight: 700;
}}

/* Positive delta → green, negative → red */
[data-testid="stMetricDeltaIcon-Up"] {{
    color: {PALETTE['accent_red']} !important;   /* deforestation up = bad */
}}
[data-testid="stMetricDeltaIcon-Down"] {{
    color: {PALETTE['accent_green']} !important; /* deforestation down = good */
}}

/* ── Info / warning / error containers ─────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 6px;
    font-size: 0.9rem;
}}

/* ── Buttons ─────────────────────────────────────────────────────  */
.stButton > button[kind="primary"] {{
    background-color: {PALETTE['primary']};
    border-color: {PALETTE['primary']};
    color: #fff;
    font-weight: 600;
    border-radius: 6px;
}}
.stButton > button[kind="primary"]:hover {{
    background-color: {PALETTE['primary_dark']};
    border-color: {PALETTE['primary_dark']};
}}

/* ── Tabs ────────────────────────────────────────────────────────  */
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    border-bottom: 2px solid {PALETTE['primary']};
    color: {PALETTE['primary']};
    font-weight: 600;
}}

/* ── Data freshness badge helper class ──────────────────────────── */
.badge-fresh   {{ color: {PALETTE['accent_green']}; font-weight: 500; }}
.badge-stale   {{ color: {PALETTE['accent_yellow']}; font-weight: 500; }}
.badge-expired {{ color: {PALETTE['accent_red']}; font-weight: 500; }}

/* ── Filter active indicator ────────────────────────────────────── */
.filter-active-caption {{
    font-size: 0.75rem;
    color: {PALETTE['text_muted']};
    font-style: italic;
    margin-top: -0.5rem;
}}

/* ── Streamlit top bar / hamburger ──────────────────────────────── */
[data-testid="stToolbar"] {{ display: none; }}

/* ── Main content area ──────────────────────────────────────────── */
.block-container {{
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}}

/* ── Divider ─────────────────────────────────────────────────────  */
hr {{
    border-color: {PALETTE['border']};
    margin: 0.5rem 0;
}}
</style>
"""


def inject_custom_css() -> None:
    """Inject all custom CSS into the current Streamlit page."""
    st.markdown(_CSS, unsafe_allow_html=True)

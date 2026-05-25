from __future__ import annotations

import uuid

import streamlit as st

from src.config.settings import get_settings
from src.utils.logging import configure_logging, set_session_id

configure_logging()
settings = get_settings()


def _init_session_state() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
        set_session_id(st.session_state.session_id)

    if "langfuse_session_id" not in st.session_state:
        st.session_state.langfuse_session_id = st.session_state.session_id

    if "filter_state" not in st.session_state:
        st.session_state.filter_state = {
            "biome": None,
            "state_code": None,
            "date_preset": "last_30_days",
            "date_start": None,
            "date_end": None,
        }

    if "conversation_messages" not in st.session_state:
        st.session_state.conversation_messages = []


def main() -> None:
    st.set_page_config(
        page_title="Rastreador Ambiental Brasil",
        page_icon="🌿",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _init_session_state()

    conversation_page = st.Page(
        "ui/pages/conversation.py",
        title="Conversa",
        icon="💬",
        default=True,
    )
    dashboard_page = st.Page(
        "ui/pages/dashboard.py",
        title="Painel",
        icon="📊",
    )
    map_page = st.Page(
        "ui/pages/map_viewer.py",
        title="Mapa",
        icon="🗺️",
    )
    alerts_page = st.Page(
        "ui/pages/alerts.py",
        title="Alertas",
        icon="🚨",
    )
    trends_page = st.Page(
        "ui/pages/trends.py",
        title="Tendências",
        icon="📈",
    )
    about_page = st.Page(
        "ui/pages/about.py",
        title="Sobre",
        icon="ℹ️",
    )

    pg = st.navigation(
        [conversation_page, dashboard_page, map_page, alerts_page, trends_page, about_page]
    )
    pg.run()


if __name__ == "__main__":
    main()

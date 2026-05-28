"""Conversa Ambiental / Environmental Conversation page (US1).

Streamlit chat interface backed by ConversationService.  Session state
keeps the DB session ID, Langfuse trace ID, and display history across
reruns.  The geographic context chip shows the active region/biome from
the last parsed query.
"""

from __future__ import annotations

import uuid

import streamlit as st

from src.config.settings import get_settings

# ------------------------------------------------------------------ #
# Page config                                                           #
# ------------------------------------------------------------------ #

st.title("💬 Conversa Ambiental / Environmental Conversation")
st.caption(
    "Faça perguntas em português ou inglês sobre dados ambientais do Brasil. "
    "/ Ask questions in Portuguese or English about Brazil's environmental data."
)

# ------------------------------------------------------------------ #
# Session state initialisation                                          #
# ------------------------------------------------------------------ #

if "conv_session_id" not in st.session_state:
    st.session_state.conv_session_id = None

if "conv_langfuse_id" not in st.session_state:
    st.session_state.conv_langfuse_id = str(uuid.uuid4())

if "conv_messages" not in st.session_state:
    st.session_state.conv_messages = []

if "conv_context" not in st.session_state:
    # last parsed geographic context for the chip display
    st.session_state.conv_context = {"states": [], "biomes": [], "language": "pt"}

# ------------------------------------------------------------------ #
# Lazy service + session creation                                       #
# ------------------------------------------------------------------ #

@st.cache_resource
def _get_service():
    from src.services.conversation.conversation_engine import ConversationService
    return ConversationService()


def _ensure_session() -> str:
    if st.session_state.conv_session_id is None:
        svc = _get_service()
        st.session_state.conv_session_id = svc.start_session(
            langfuse_session_id=st.session_state.conv_langfuse_id,
        )
    return st.session_state.conv_session_id


# ------------------------------------------------------------------ #
# OpenAI key guard                                                      #
# ------------------------------------------------------------------ #

settings = get_settings()
if not settings.openai_api_key:
    st.warning(
        "⚠️ **OPENAI_API_KEY não configurada / OPENAI_API_KEY not set.**  \n"
        "Adicione a chave ao arquivo `.env` para ativar o assistente.  \n"
        "Add the key to the `.env` file to enable the assistant.",
        icon="🔑",
    )
    st.stop()

# ------------------------------------------------------------------ #
# Sidebar: context chip + controls                                      #
# ------------------------------------------------------------------ #

with st.sidebar:
    st.markdown("### Contexto ativo / Active context")

    ctx = st.session_state.conv_context
    if ctx["states"] or ctx["biomes"]:
        parts: list[str] = []
        if ctx["biomes"]:
            from src.config.constants import BIOMES
            parts += [
                next((b["name"] for b in BIOMES if b["id"] == bid), bid)
                for bid in ctx["biomes"]
            ]
        if ctx["states"]:
            parts += ctx["states"]
        st.info("📍 " + " · ".join(parts))
    else:
        st.caption("Nenhum filtro geográfico detectado. / No geographic filter detected.")

    st.divider()

    if st.button(
        "🗑️ Nova conversa / New conversation",
        use_container_width=True,
        type="secondary",
    ):
        st.session_state.conv_session_id = None
        st.session_state.conv_langfuse_id = str(uuid.uuid4())
        st.session_state.conv_messages = []
        st.session_state.conv_context = {"states": [], "biomes": [], "language": "pt"}
        st.rerun()

    if settings.langfuse_enabled:
        st.caption(
            f"🔭 Langfuse session: `{st.session_state.conv_langfuse_id[:8]}…`"
        )

# ------------------------------------------------------------------ #
# Chat history display                                                  #
# ------------------------------------------------------------------ #

for msg in st.session_state.conv_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ------------------------------------------------------------------ #
# Input                                                                 #
# ------------------------------------------------------------------ #

placeholder = (
    "Ex.: Qual é a situação de queimadas no Cerrado? / "
    "E.g.: What is the fire situation in the Amazon?"
)

if user_input := st.chat_input(placeholder):
    # Show user message immediately
    st.session_state.conv_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Ensure a DB session exists
    session_id = _ensure_session()

    # Stream assistant response with spinner
    with st.chat_message("assistant"):
        with st.spinner("Consultando dados do INPE... / Fetching INPE data..."):
            try:
                svc = _get_service()
                reply = svc.chat(
                    user_input,
                    session_id=session_id,
                    langfuse_session_id=st.session_state.conv_langfuse_id,
                )

                st.markdown(reply.text)

                # Update geographic context chip
                if reply.parsed_query:
                    pq = reply.parsed_query
                    if pq.states or pq.biomes:
                        st.session_state.conv_context = {
                            "states": pq.states,
                            "biomes": pq.biomes,
                            "language": pq.language,
                        }

                # Show clarification options as buttons if needed
                if reply.needs_clarification and reply.clarification_options:
                    st.markdown("**Escolha uma opção / Choose an option:**")
                    for opt in reply.clarification_options:
                        if st.button(opt, key=f"clarify_{opt[:20]}"):
                            st.session_state.conv_messages.append(
                                {"role": "user", "content": opt}
                            )
                            st.rerun()

                st.session_state.conv_messages.append(
                    {"role": "assistant", "content": reply.text}
                )

            except Exception as exc:
                error_msg = (
                    f"❌ Erro ao processar sua pergunta / Error processing your question:\n\n"
                    f"`{exc}`\n\n"
                    "Tente novamente ou reformule sua pergunta. / Please try again or rephrase."
                )
                st.error(error_msg)
                st.session_state.conv_messages.append(
                    {"role": "assistant", "content": error_msg}
                )

    st.rerun()

# ------------------------------------------------------------------ #
# Empty state hint                                                      #
# ------------------------------------------------------------------ #

if not st.session_state.conv_messages:
    st.markdown(
        """
        **Sugestões de perguntas / Suggested questions:**

        - Qual é a situação atual de queimadas no Cerrado?
        - Quais estados têm mais alertas DETER este mês?
        - What is the deforestation rate in the Amazon?
        - Como está o risco de incêndio no Mato Grosso?
        - Mostra os dados de desmatamento dos últimos 90 dias na Amazônia Legal.
        """
    )

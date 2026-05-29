import streamlit as st

st.title("ℹ️ Sobre o Rastreador Ambiental / About the Environmental Tracker")

st.markdown(
    """
## Fontes de Dados INPE / INPE Data Sources

| Sistema / System | Descrição / Description | Frequência / Update Frequency |
|---------|-----------|--------------------------|
| **DETER** | Detecção de Desmatamento em Tempo Real / Real-Time Deforestation Detection | Diária / Daily |
| **PRODES** | Programa de Monitoramento da Floresta Amazônica / Amazon Deforestation Monitoring Program | Anual/Mensal / Annual/Monthly |
| **FOGO** | Monitoramento de Queimadas e Incêndios Florestais / Fire and Wildfire Monitoring | A cada 3–6 horas / Every 3–6 hours |

Os dados são acessados via [TerraBrasilis](https://terrabrasilis.dpi.inpe.br/), a plataforma OGC WFS/WMS do INPE.
*Data is accessed via [TerraBrasilis](https://terrabrasilis.dpi.inpe.br/), INPE's OGC WFS/WMS platform.*

---

## Definições / Definitions

- **DETER**: Emite alertas de desmatamento e degradação florestal para apoio à fiscalização.
  *Issues deforestation and forest degradation alerts to support environmental enforcement.*

- **PRODES**: Mede o desmatamento bruto anual na Amazônia Legal desde 1988.
  *Measures annual gross deforestation in the Legal Amazon since 1988.*

- **FOGO (BDQueimadas)**: Monitora focos de calor detectados por satélite em todo o território nacional.
  *Monitors satellite-detected heat spots (fire hotspots) across all of Brazil.*

---

## Citação / Citation

Ao utilizar estes dados em publicações, cite o INPE como fonte:
*When using this data in publications, cite INPE as the source:*

> Instituto Nacional de Pesquisas Espaciais (INPE). *Sistema de Monitoramento da Amazônia*.
> Disponível em / Available at: http://www.inpe.br

---

## Limitações / Limitations

- Os dados refletem condições de até **24 horas atrás**. Dados em tempo real (< 1 hora) não estão disponíveis.
  *Data reflects conditions up to **24 hours ago**. Real-time data (< 1 hour) is not available.*

- Previsões futuras estão fora do escopo desta aplicação.
  *Future forecasts are out of scope for this application.*

- A precisão dos dados depende da disponibilidade dos sistemas INPE.
  *Data accuracy depends on INPE system availability.*
"""
)

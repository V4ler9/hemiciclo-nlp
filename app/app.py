"""Dashboard Streamlit de hemiciclo-nlp (Fase 5): consume la API JSON.

Arranque local:

    uv run streamlit run app/app.py

Con Docker Compose:

    docker compose up dashboard
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from components.ui import api_get, records_to_frame  # noqa: E402

API_URL = os.environ.get("HEMICICLO_API_URL", "http://localhost:8000")
PAGES = ("Resumen", "Tópicos", "Series y regímenes", "Eventos", "Sentimiento")


@st.cache_data(ttl=300)
def fetch(path: str, params: tuple[tuple[str, object], ...] = ()) -> object:
    """GET cacheado contra la API (params como tupla para ser hashable)."""
    return api_get(API_URL, path, dict(params))


def load(path: str, params: tuple[tuple[str, object], ...] = ()) -> object:
    """Envuelve ``fetch`` con un aviso claro si la API no está disponible."""
    try:
        return fetch(path, params)
    except requests.RequestException as exc:
        st.error(f"API no disponible en {API_URL}: {exc}")
        st.stop()
        return None


def page_summary() -> None:
    meta = load("/meta")
    st.subheader("Resumen del corpus y del modelo de tópicos")
    columns = st.columns(4)
    columns[0].metric("Intervenciones", f"{int(meta['intervenciones']):,}".replace(",", "."))
    columns[1].metric("Tópicos", int(meta["topicos"]))
    columns[2].metric("Tasa de outliers", f"{float(meta['tasa_outliers']):.1%}")
    columns[3].metric("Coherencia c_v", f"{float(meta['coherencia_cv']):.3f}")
    st.caption(f"Rejilla seleccionada: {meta['rejilla_seleccionada']}")
    st.markdown("### Anexo de sensibilidad de embeddings (D-39)")
    st.dataframe(records_to_frame(load("/sensitivity")), width="stretch", hide_index=True)


def page_topics() -> None:
    topics = records_to_frame(load("/topics"))
    st.subheader("Tópicos de BERTopic con etiquetas propuestas")
    st.dataframe(
        topics.loc[:, ["topic", "size", "label"]],
        width="stretch",
        hide_index=True,
    )
    options = {
        int(row["topic"]): f"{int(row['topic'])} · {row['label']}" for _, row in topics.iterrows()
    }
    labels = {topic: options[topic] for topic in sorted(options)}
    selected = st.selectbox(
        "Detalle del tópico",
        options=list(labels),
        format_func=lambda topic: labels[topic],
    )
    detail = load(f"/topics/{selected}")
    st.markdown(f"**{detail.get('label', 'sin etiqueta')}** — {detail.get('description', '')}")
    st.markdown("**Términos c-TF-IDF:** " + str(detail.get("top_terms", "")))
    documents = detail.get("representative_texts", [])
    for index, text in enumerate(documents, start=1):
        with st.expander(f"Intervención representativa {index}"):
            st.write(text)


def page_series() -> None:
    topics = records_to_frame(load("/topics"))
    st.subheader("Series mensuales y cambios de régimen")
    series_type = st.radio("Serie", ["topic", "tone"], horizontal=True)
    series_id: str | None = None
    if series_type == "topic":
        series_id = st.selectbox("Tópico", [str(value) for value in topics["topic"].tolist()])
    series_params: list[tuple[str, object]] = [("series_type", series_type)]
    if series_id is not None:
        series_params.append(("series_id", series_id))
    series = records_to_frame(load("/series", tuple(series_params)))

    change_params: list[tuple[str, object]] = [("serie", series_type)]
    if series_id is not None:
        change_params.append(("serie_id", series_id))
    changes = records_to_frame(load("/changes", tuple(change_params)))

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(x=series["month"], y=series["value"], mode="lines", name=series_type)
    )
    for fecha in changes.get("fecha", pd.Series(dtype=str)).tolist():
        figure.add_vline(x=fecha, line_dash="dash", line_color="black")
    figure.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="valor")
    st.plotly_chart(figure, width="stretch")
    if not changes.empty:
        st.markdown("**Cambios detectados**")
        st.dataframe(changes, width="stretch", hide_index=True)


def page_events() -> None:
    st.subheader("Eventos y asociaciones exploratorias")
    st.dataframe(records_to_frame(load("/events")), width="stretch", hide_index=True)
    relations = records_to_frame(load("/events/relations"))
    st.caption(
        "Spearman con ventana ±3 meses y Benjamini-Hochberg sobre una familia de 472 "
        "contrastes: ninguna asociación supera q < 0,05 (resultado nulo exploratorio, D-09)."
    )
    events = sorted(relations["evento"].unique().tolist()) if not relations.empty else []
    event = st.selectbox("Evento", ["(todos)", *events])
    subset = relations if event == "(todos)" else relations.loc[relations["evento"] == event]
    if subset.empty:
        st.info("Sin filas para el evento seleccionado.")
        return
    ordered = subset.reindex(subset["rho"].abs().sort_values(ascending=False).index).head(15)
    figure = px.bar(
        ordered,
        x="rho",
        y="serie_id",
        orientation="h",
        color="q",
        color_continuous_scale="RdYlGn_r",
        labels={"serie_id": "tópico", "q": "q (BH)"},
    )
    figure.update_layout(height=460, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(figure, width="stretch")


def page_sentiment() -> None:
    payload = load("/sentiment")
    st.subheader("Validación de sentimiento contra revisión humana (D-36 y D-37)")
    st.markdown("**Métricas principales**")
    st.dataframe(
        records_to_frame(payload["revision_metricas"]),
        width="stretch",
        hide_index=True,
    )
    st.markdown("**Acuerdo a tres bandas (ParlaSent · LLM · humano)**")
    st.dataframe(
        records_to_frame(payload["acuerdo_3bandas"]),
        width="stretch",
        hide_index=True,
    )
    level = st.radio("Matriz de confusión", ["senti_3", "senti_6"], horizontal=True)
    confusion = load(f"/sentiment/confusion/{level}")
    frame = pd.DataFrame(
        confusion["values"], index=confusion["index"], columns=confusion["columns"]
    )
    figure = px.imshow(frame, text_auto=True, color_continuous_scale="Blues", aspect="auto")
    figure.update_layout(height=440, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(figure, width="stretch")


def main() -> None:
    st.set_page_config(page_title="hemiciclo-nlp", page_icon="🏛️", layout="wide")
    st.title("hemiciclo-nlp · Congreso de los Diputados (2015-2023)")
    st.caption(f"API: {API_URL}")
    page = st.sidebar.radio("Sección", PAGES)
    if page == "Resumen":
        page_summary()
    elif page == "Tópicos":
        page_topics()
    elif page == "Series y regímenes":
        page_series()
    elif page == "Eventos":
        page_events()
    else:
        page_sentiment()


main()

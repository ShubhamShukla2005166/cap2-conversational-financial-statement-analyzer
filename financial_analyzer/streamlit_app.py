from __future__ import annotations

import os
from uuid import uuid4

import requests
import streamlit as st

API_URL = os.getenv("FINANCIAL_ANALYZER_API_URL", "http://localhost:8000")


def analyze_via_api(file_data: bytes, filename: str, company: str) -> dict:
    response = requests.post(
        f"{API_URL}/analyze",
        files={"file": (filename, file_data)},
        data={"company": company, "session_id": st.session_state.session_id},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def ask_via_api(question: str) -> dict:
    response = requests.post(
        f"{API_URL}/ask",
        json={
            "session_id": st.session_state.session_id,
            "question": question,
            "history": st.session_state.get("messages", []),
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def show_request_error(error: requests.RequestException, message: str) -> None:
    detail = error.response.json().get("detail", str(error)) if error.response is not None else str(error)
    st.error(f"{message}: {detail}")


def ratio_rows(ratios: dict) -> list[dict]:
    return [
        {"Ratio": name.replace("_", " ").title(), "Period": point["period"], "Value": point["value"]}
        for name, points in ratios.items()
        for point in points
    ]


def latest_ratio(ratios: dict, name: str) -> str:
    points = ratios.get(name, [])
    return f"{points[-1]['value']:g}" if points else "N/A"


st.set_page_config(page_title="Financial Statement Analyzer", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
    :root {
        --ink: #172033;
        --muted: #687386;
        --panel: #ffffff;
        --line: #e3e8f0;
        --accent: #e45757;
        --accent-soft: #fff1ef;
        --navy: #172033;
    }
    .stApp { background: #f6f8fb; color: var(--ink); }
    [data-testid="stMainBlockContainer"] { max-width: 1180px; padding-top: 2.5rem; }
    [data-testid="stSidebar"] { background: var(--navy); }
    [data-testid="stSidebar"] * { color: #f7f9fc; }
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background: #ffffff; color: var(--ink); }
    [data-testid="stSidebar"] [data-testid="stFileUploader"] label,
    [data-testid="stSidebar"] [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] * {
        color: var(--ink) !important;
    }
    h1 { color: var(--ink); font-family: Georgia, serif; letter-spacing: 0; }
    h2, h3 { color: var(--ink); letter-spacing: 0; }
    [data-baseweb="tab-list"] { gap: 1.25rem; border-bottom: 1px solid var(--line); }
    [data-baseweb="tab"] { color: var(--muted); font-weight: 600; }
    [aria-selected="true"] { color: var(--accent) !important; }
    .metric-card {
        background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
        padding: 1rem 1.1rem; min-height: 92px; box-shadow: 0 3px 14px rgba(23, 32, 51, .04);
    }
    .metric-label { color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }
    .metric-value { color: var(--ink); font-size: 1.55rem; font-weight: 700; margin-top: .35rem; }
    .metric-period { color: var(--muted); font-size: .75rem; margin-top: .2rem; }
    .section-note { color: var(--muted); font-size: .9rem; margin-bottom: 1rem; }
    .flag-title { color: #8a3f27; font-weight: 700; }
    div[data-testid="stAlert"] { border-radius: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Conversational Financial Statement Analyzer")
st.caption("A focused view of financial health, trends, and risks.")

if "result" not in st.session_state:
    st.session_state.result = None
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())

with st.sidebar:
    st.header("Statement workspace")
    st.caption("Upload one statement to create an analysis session.")
    company = st.text_input("Company name", "My Company")
    uploaded = st.file_uploader("CSV, Excel, or PDF", type=["csv", "xlsx", "xls", "pdf"])
    if uploaded and st.button("Analyze statements", type="primary"):
        try:
            st.session_state.result = analyze_via_api(uploaded.getvalue(), uploaded.name, company)
            st.session_state.messages = []
        except requests.RequestException as exc:
            show_request_error(exc, "FastAPI request failed. Start the API with `python -m uvicorn financial_analyzer.api:app --reload`")

result: dict | None = st.session_state.result
if result is None:
    st.info("Add a table with metric names in the first column and periods across the remaining columns.")
else:
    overview, ratios, questions = st.tabs(["Overview", "Ratios", "Grounded Q&A"])
    with overview:
        st.subheader(result["company"])
        st.markdown('<div class="section-note">Latest available indicators</div>', unsafe_allow_html=True)
        metric_columns = st.columns(4)
        headline_metrics = [
            ("Current ratio", "current_ratio"),
            ("Debt to equity", "debt_to_equity"),
            ("Operating margin", "operating_margin_percent"),
            ("DSO", "dso_days"),
        ]
        latest_period = result["periods"][-1] if result["periods"] else ""
        for column, (label, name) in zip(metric_columns, headline_metrics):
            with column:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">{label}</div>'
                    f'<div class="metric-value">{latest_ratio(result["ratios"], name)}</div>'
                    f'<div class="metric-period">{latest_period}</div></div>',
                    unsafe_allow_html=True,
                )
        st.markdown("### Executive view")
        st.write(result["narrative"])
        if result["red_flags"]:
            st.markdown("### Watch areas")
            for red_flag in result["red_flags"]:
                with st.expander(f"{red_flag['name']}  |  {red_flag['severity'].upper()}", expanded=False):
                    st.markdown(f'<div class="flag-title">{red_flag["message"]}</div>', unsafe_allow_html=True)
                    st.caption("Evidence: " + " ".join(red_flag["citations"]))
        else:
            st.success("No configured red-flag rule fired for the available data.")
    with ratios:
        st.markdown('<div class="section-note">Calculated indicators by reporting period</div>', unsafe_allow_html=True)
        st.dataframe(
            ratio_rows(result["ratios"]),
            column_config={
                "Ratio": st.column_config.TextColumn("Ratio", alignment="center"),
                "Period": st.column_config.TextColumn("Period", alignment="center"),
                "Value": st.column_config.NumberColumn("Value", alignment="center"),
            },
            use_container_width=True,
            hide_index=True,
        )
    with questions:
        st.markdown('<div class="section-note">Ask a grounded question about the uploaded statement.</div>', unsafe_allow_html=True)
        if "messages" not in st.session_state:
            st.session_state.messages = []
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["text"])
                if message.get("citations"):
                    st.caption("Citations: " + " ".join(message["citations"]))
        question = st.chat_input("Ask about revenue, liquidity, leverage, margins, or trends")
        if question:
            try:
                response = ask_via_api(question)
            except requests.RequestException as exc:
                show_request_error(exc, "FastAPI request failed")
            else:
                st.session_state.messages.extend([
                    {"role": "user", "text": question},
                    {"role": "assistant", "text": response["answer"], "citations": response["citations"]},
                ])
                st.rerun()
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from financial_analyzer.core import AnalysisResult, analyze_upload, answer_question
from financial_analyzer.llm import answer_with_openai

st.set_page_config(page_title="Financial Statement Analyzer", page_icon="📊", layout="wide")
st.title("Conversational Financial Statement Analyzer")
st.caption("Upload a statement, inspect computed evidence, and ask grounded questions.")

if "result" not in st.session_state:
    st.session_state.result = None

with st.sidebar:
    st.header("Upload")
    company = st.text_input("Company name", "My Company")
    uploaded = st.file_uploader("CSV, Excel, or PDF", type=["csv", "xlsx", "xls", "pdf"])
    if uploaded and st.button("Analyze statements", type="primary"):
        try:
            st.session_state.result = analyze_upload(uploaded.getvalue(), uploaded.name, company)
            st.session_state.messages = []
        except ValueError as exc:
            st.error(str(exc))

result: AnalysisResult | None = st.session_state.result
if result is None:
    st.info("Add a table with metric names in the first column and periods across the remaining columns.")
else:
    overview, ratios, questions = st.tabs(["Overview", "Ratios", "Grounded Q&A"])
    with overview:
        st.subheader(result.company)
        st.write(result.narrative)
        if result.red_flags:
            for red_flag in result.red_flags:
                st.warning(f"{red_flag['name']}: {red_flag['message']}")
                st.caption("Evidence: " + " ".join(red_flag["citations"]))
        else:
            st.success("No configured red-flag rule fired for the available data.")
    with ratios:
        rows = []
        for name, points in result.ratios.items():
            for point in points:
                rows.append({"Ratio": name.replace("_", " ").title(), "Period": point["period"], "Value": point["value"]})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    with questions:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["text"])
                if message.get("citations"):
                    st.caption("Citations: " + " ".join(message["citations"]))
        question = st.chat_input("Ask about revenue, liquidity, leverage, margins, or trends")
        if question:
            response = answer_with_openai(result, question) or answer_question(result, question)
            st.session_state.messages.extend([
                {"role": "user", "text": question},
                {"role": "assistant", "text": response["answer"], "citations": response["citations"]},
            ])
            st.rerun()
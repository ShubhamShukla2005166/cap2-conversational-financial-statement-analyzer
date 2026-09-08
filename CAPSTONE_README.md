# Capstone 2: Conversational Financial Statement Analyzer

Owner: **Shubham Shukla** (Trend & Red Flag Agent)

This project turns a CSV, Excel, or tabular PDF financial statement into a grounded analysis. It computes liquidity, leverage, profitability, cash-conversion, DSO, and inventory ratios; checks the six assignment red-flag patterns; and attaches a source citation to every returned figure.

## Project structure

- `financial_analyzer/core.py`: parsing, ratio computation, trend detection, red flags, and citation-aware Q&A.
- `financial_analyzer/embeddings.py`: shared OpenAI embedding client and normalized FAISS build/save/load helpers for all agents.
- `financial_analyzer/llm.py`: shared grounded `ChatOpenAI` Q&A helper with deterministic fallback.
- `financial_analyzer/api.py`: FastAPI upload and question endpoints.
- `financial_analyzer/streamlit_app.py`: interactive upload, dashboard, and chat surface.
- `tests/test_financial_analyzer.py`: offline tests for the trend/red-flag slice.

The implementation follows examples in `AgenticAI-Full-main`: FAISS/RAG exercises informed the explicit grounding and refusal behavior, the shared embedding module follows `Session-03a_basicrag/lab1_vector_store.py`, the grounded Q&A helper follows the `ChatPromptTemplate | ChatOpenAI | StrOutputParser` pattern from the RAG labs, the agent labs informed tool boundaries, and `Session-Streamlit-FastApi` informed the API/UI split. Financial calculations remain deterministic; Q&A uses the configured OpenAI key when available and falls back locally when it is not. Future agents should import the shared helpers rather than creating separate model or embedding settings.

## Shared embeddings

```python
from financial_analyzer.embeddings import (
	build_vector_store,
	create_embeddings,
	save_vector_store,
)

embeddings = create_embeddings()
store = build_vector_store(documents, embeddings, ids=document_ids)
save_vector_store(store)
```

The shared module uses `text-embedding-3-small`, normalized FAISS vectors, and the same cosine relevance conversion as the AgenticAI RAG labs. It requires `OPENAI_API_KEY` in `.env`; numeric trend and red-flag analysis remains usable without embeddings.

## Input format

Use a table with metric names in column one and periods across the remaining columns:

```csv
Metric,2023,2024
Revenue,1000,1100
Net Income,100,95
Current Assets,500,450
Current Liabilities,450,500
```

Supported aliases include Revenue, Gross Profit, Operating Income, Net Income, Cash From Operations, Accounts Receivable, Inventory, Current Assets, Current Liabilities, Total Assets, Total Debt, Total Equity, and Interest Expense.

## Run

From the workspace root:

```powershell
pip install -r requirements.txt
python -m pytest tests
python -m uvicorn financial_analyzer.api:app --reload
streamlit run financial_analyzer/streamlit_app.py
```

The Streamlit app can run by itself. The FastAPI service is provided for the team integration path and currently keeps sessions in memory for local development.
Conversational Financial Statement Analyzer
============================================

This capstone analyzes uploaded CSV, Excel, and tabular PDF financial
statements. It calculates financial ratios, period trends, and six red flags:

- Accrual-quality gap
- DSO climbing
- Margin compression
- Leverage stress
- Inventory build-up
- Liquidity deterioration

The application also provides citation-backed Q&A through the optional
OpenAI integration. Financial calculations remain deterministic and can run
without an API request.

Setup
-----

1. Create the virtual environment:

	py -3.12 -m venv .venv

2. Activate it:

	.venv\Scripts\activate

3. Upgrade pip and install the existing project requirements:

	python -m pip install --upgrade pip
	pip install -r requirements.txt

4. Add your OpenAI key to the local .env file if grounded LLM Q&A or shared
	embeddings are required:

	OPENAI_API_KEY=your_key_here

Run the Streamlit application
-----------------------------

From the project root:

	streamlit run financial_analyzer\streamlit_app.py

Upload sample_financial_statement.csv to exercise the analyzer. Enter a
company name such as Sample Company.

If port 8501 is already occupied, use:

	streamlit run financial_analyzer\streamlit_app.py --server.port 8502

Run the FastAPI service
-----------------------

	uvicorn financial_analyzer.api:app --reload

The API provides /analyze, /ask, /compare, and /health endpoints. API
sessions are stored in memory for local development.

Run tests
---------

	python -m pytest tests

Documentation
-------------

- CAPSTONE_README.md: project overview and setup notes.
- FINANCIAL_ANALYZER_CODE_WALKTHROUGH.md: detailed file-by-file code flow.
- sample_financial_statement.csv: ready-to-upload demonstration data.

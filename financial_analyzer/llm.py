"""Shared grounded language-model helpers for the financial agent team."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .embeddings import build_fact_documents, build_text_documents, build_vector_store, create_embeddings

if TYPE_CHECKING:
    from .core import AnalysisResult


MODEL = "gpt-4o-mini"
GROUNDED_PROMPT = ChatPromptTemplate.from_template("""Answer the financial question using ONLY the facts below.

If the facts do not answer the question, reply exactly:
I don't have that information in the uploaded statements.

Do not calculate or invent facts that are not present. Keep the answer concise.
End with a line beginning 'Sources:' and include the complete source labels for
the facts used.

Facts:
{context}

Question: {question}

Answer:
""")

_FACT_STORES: dict[int, FAISS] = {}


def openai_is_configured() -> bool:
    """Return whether the local environment has an OpenAI key configured."""
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY"))


def _fact_store(result: "AnalysisResult") -> FAISS:
    """Build one searchable fact index for each analysis session."""
    result_key = id(result)
    if result_key not in _FACT_STORES:
        documents = build_fact_documents(result.facts)
        if result.source_text:
            documents.extend(build_text_documents(result.source_text, result.source_name))
        _FACT_STORES[result_key] = build_vector_store(documents, create_embeddings())
    return _FACT_STORES[result_key]


def answer_with_openai(result: "AnalysisResult", question: str) -> dict[str, object] | None:
    """Answer from uploaded facts through the shared grounded ChatOpenAI client.

    ``None`` means the caller should use its deterministic fallback. This keeps
    the financial analyzer usable when the API is unavailable.
    """
    if not openai_is_configured():
        return None

    try:
        documents = _fact_store(result).similarity_search(question, k=min(8, len(result.facts)))
        context = "\n".join(f"- {document.page_content}" for document in documents)
        llm = ChatOpenAI(model=MODEL, temperature=0)
        response = (GROUNDED_PROMPT | llm).invoke({"context": context, "question": question})
        answer = response.content.strip() if isinstance(response.content, str) else str(response.content)
        citations = [document.metadata["citation"] for document in documents if document.metadata["citation"] in answer]
        return {"answer": answer, "citations": citations}
    except Exception:
        return None
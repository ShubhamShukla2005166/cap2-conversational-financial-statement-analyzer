"""Shared grounded language-model helpers for the financial agent team."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

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


def openai_is_configured() -> bool:
    """Return whether the local environment has an OpenAI key configured."""
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY"))


def answer_with_openai(result: "AnalysisResult", question: str) -> dict[str, object] | None:
    """Answer from uploaded facts through the shared grounded ChatOpenAI client.

    ``None`` means the caller should use its deterministic fallback. This keeps
    the financial analyzer usable when the API is unavailable.
    """
    if not openai_is_configured():
        return None

    context = "\n".join(
        f"- {fact.metric} | {fact.period} | {fact.value:g} | {fact.citation()}"
        for fact in result.facts
    )
    try:
        llm = ChatOpenAI(model=MODEL, temperature=0)
        response = (GROUNDED_PROMPT | llm).invoke({"context": context, "question": question})
        answer = response.content.strip() if isinstance(response.content, str) else str(response.content)
        citations = [fact.citation() for fact in result.facts if fact.citation() in answer]
        return {"answer": answer, "citations": citations}
    except Exception:
        return None
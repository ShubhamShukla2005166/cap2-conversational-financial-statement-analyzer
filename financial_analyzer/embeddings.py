"""Shared embedding and FAISS utilities for the financial agent team.

This module follows the embedding/indexing pattern used by the AgenticAI
training labs. Other agents should import these helpers instead of creating a
second embedding client or using different FAISS distance settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings


EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_INDEX_DIR = Path("financial_analyzer_indexes")
DEFAULT_INDEX_NAME = "financial_statements"
STORE_KWARGS = {
    "normalize_L2": True,
    "distance_strategy": DistanceStrategy.EUCLIDEAN_DISTANCE,
}


def cosine_relevance(distance: float) -> float:
    """Convert normalized squared-L2 distance into cosine relevance."""
    return 1.0 - distance / 2.0


def require_api_key() -> None:
    """Load local environment settings and require an OpenAI API key."""
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to a .env file before creating embeddings.")


def create_embeddings(model: str = EMBEDDING_MODEL) -> OpenAIEmbeddings:
    """Create the shared OpenAI embedding client used by all agents."""
    require_api_key()
    return OpenAIEmbeddings(model=model)


def build_vector_store(
    documents: Sequence[Document],
    embeddings: OpenAIEmbeddings,
    ids: list[str] | None = None,
) -> FAISS:
    """Build an in-memory FAISS store with the team's shared settings."""
    return FAISS.from_documents(
        documents=list(documents),
        embedding=embeddings,
        ids=ids,
        relevance_score_fn=cosine_relevance,
        **STORE_KWARGS,
    )


def save_vector_store(
    vector_store: FAISS,
    index_dir: Path = DEFAULT_INDEX_DIR,
    index_name: str = DEFAULT_INDEX_NAME,
) -> None:
    """Persist a FAISS store so another agent or process can reuse it."""
    index_dir.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(index_dir), index_name)


def load_vector_store(
    embeddings: OpenAIEmbeddings,
    index_dir: Path = DEFAULT_INDEX_DIR,
    index_name: str = DEFAULT_INDEX_NAME,
) -> FAISS:
    """Load a persisted store created by :func:`save_vector_store`."""
    index_file = index_dir / f"{index_name}.faiss"
    if not index_file.exists():
        raise FileNotFoundError(
            f"FAISS store not found at {index_file}. Build and save it before loading it."
        )
    return FAISS.load_local(
        str(index_dir),
        embeddings,
        index_name,
        allow_dangerous_deserialization=True,
        relevance_score_fn=cosine_relevance,
        **STORE_KWARGS,
    )
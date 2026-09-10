from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .core import AnalysisResult, analyze_upload, answer_question, compare_results
from .llm import answer_with_openai

app = FastAPI(title="Conversational Financial Statement Analyzer", version="1.0.0")
SESSIONS: dict[str, AnalysisResult] = {}


class QuestionRequest(BaseModel):
    session_id: str
    question: str
    history: list[dict[str, Any]] = Field(default_factory=list)


class CompareRequest(BaseModel):
    left_session_id: str
    right_session_id: str


def _conversation_text(history: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{message.get('role', 'user')}: {message['text']}"
        for message in history
        if message.get("text")
    )


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), company: str = Form(...), session_id: str = Form(...)):
    try:
        result = analyze_upload(await file.read(), file.filename or "statement.csv", company)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    SESSIONS[session_id] = result
    return result.to_dict()


@app.post("/ask")
def ask(payload: QuestionRequest):
    result = SESSIONS.get(payload.session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis session not found.")
    context = _conversation_text(payload.history)
    question = f"Conversation context:\n{context}\n\nCurrent question: {payload.question}" if context else payload.question
    return answer_question(result, question, answerer=answer_with_openai)


@app.post("/compare")
def compare(payload: CompareRequest):
    left = SESSIONS.get(payload.left_session_id)
    right = SESSIONS.get(payload.right_session_id)
    if not left or not right:
        raise HTTPException(status_code=404, detail="Both analysis sessions are required.")
    return compare_results(left, right)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("financial_analyzer.api:app", host="0.0.0.0", port=8000, reload=True)
from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .core import AnalysisResult, analyze_upload, answer_question, compare_results
from .llm import answer_with_openai

app = FastAPI(title="Conversational Financial Statement Analyzer", version="1.0.0")
SESSIONS: dict[str, AnalysisResult] = {}


class QuestionRequest(BaseModel):
    session_id: str
    question: str


class CompareRequest(BaseModel):
    left_session_id: str
    right_session_id: str


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
    return answer_question(result, payload.question, answerer=answer_with_openai)


@app.post("/compare")
def compare(payload: CompareRequest):
    left = SESSIONS.get(payload.left_session_id)
    right = SESSIONS.get(payload.right_session_id)
    if not left or not right:
        raise HTTPException(status_code=404, detail="Both analysis sessions are required.")
    return compare_results(left, right)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("financial_analyzer.api:app", host="0.0.0.0", port=8000, reload=True)
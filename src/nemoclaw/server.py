"""FastAPI service exposing PII redaction for OpenClaw."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from nemoclaw.redactor import PIIRedactor, RedactResult


API_TOKEN = os.environ.get("API_TOKEN", "change-me")
MODEL_ID = os.environ.get("MODEL_ID", "nvidia/gliner-PII")
THRESHOLD = float(os.environ.get("THRESHOLD", "0.3"))

security = HTTPBearer()


def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(security)],
) -> str:
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials


class TextRequest(BaseModel):
    text: str


class RedactResponse(BaseModel):
    redacted_text: str
    redacted_count: int
    redacted_items: list[dict]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redactor = PIIRedactor(model_id=MODEL_ID, threshold=THRESHOLD)
    yield


app = FastAPI(title="NemoClaw PII Redaction Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/redact", response_model=RedactResponse, dependencies=[Depends(verify_token)])
async def redact(req: TextRequest) -> RedactResponse:
    result: RedactResult = app.state.redactor.redact(req.text)
    return RedactResponse(
        redacted_text=result.redacted_text,
        redacted_count=result.redacted_count,
        redacted_items=result.redacted_items,
    )

"""FastAPI service exposing PII redaction for OpenClaw."""

from __future__ import annotations

import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from clawguard.redactor import PIIRedactor, RedactResult


_raw_token = os.environ.get("CLAWGUARD_TOKEN", "")
if not _raw_token or _raw_token == "change-me":
    raise RuntimeError(
        "CLAWGUARD_TOKEN environment variable is not set or uses the default placeholder. "
        "Generate a secret with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    )

API_TOKEN: str = _raw_token
MODEL_ID: str = os.environ.get("MODEL_ID", "nvidia/gliner-PII")
THRESHOLD: float = float(os.environ.get("THRESHOLD", "0.5"))
MAX_TEXT_LENGTH: int = int(os.environ.get("MAX_TEXT_LENGTH", "50000"))

security = HTTPBearer()


def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(security)],
) -> str:
    if not hmac.compare_digest(credentials.credentials, API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials


class TextRequest(BaseModel):
    text: str


class RedactedItem(BaseModel):
    label: str
    replacement: str
    confidence: float
    original: str | None = None


class RedactResponse(BaseModel):
    redacted_text: str
    redacted_count: int
    redacted_items: list[RedactedItem]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redactor = PIIRedactor(model_id=MODEL_ID, threshold=THRESHOLD)
    yield


app = FastAPI(title="ClawGuard PII Redaction Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/redact", response_model=RedactResponse, dependencies=[Depends(verify_token)])
async def redact(
    req: TextRequest,
    include_original: Annotated[bool, Query()] = False,
) -> RedactResponse:
    if not req.text:
        return RedactResponse(redacted_text="", redacted_count=0, redacted_items=[])

    if len(req.text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Text exceeds maximum allowed length of {MAX_TEXT_LENGTH} characters.",
        )

    result: RedactResult = await asyncio.to_thread(app.state.redactor.redact, req.text)

    items = [
        RedactedItem(
            label=item["label"],
            replacement=item["replacement"],
            confidence=item["confidence"],
            original=item["original"] if include_original else None,
        )
        for item in result.redacted_items
    ]

    return RedactResponse(
        redacted_text=result.redacted_text,
        redacted_count=result.redacted_count,
        redacted_items=items,
    )

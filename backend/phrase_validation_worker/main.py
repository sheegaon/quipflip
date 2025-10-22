"""Standalone FastAPI application exposing the phrase validation engine."""

from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend.phrase_validation.engine import get_phrase_validator

logger = logging.getLogger(__name__)

app = FastAPI(title="Phrase Validation Service", version="1.0.0")


class ValidationResponse(BaseModel):
    """Standard response payload for validation requests."""

    is_valid: bool
    error: str = ""


class ValidateRequest(BaseModel):
    phrase: str


class PromptValidationRequest(ValidateRequest):
    prompt_text: str | None = None


class CopyValidationRequest(ValidateRequest):
    original_phrase: str
    other_copy_phrase: str | None = None
    prompt_text: str | None = None


@app.on_event("startup")
async def startup_event() -> None:
    """Ensure the phrase validator is initialised before serving requests."""
    validator = get_phrase_validator()
    logger.info("Phrase validation engine ready with %d words", len(validator.dictionary))


@app.get("/healthz", response_model=dict)
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.post("/validate", response_model=ValidationResponse)
async def validate_phrase(payload: ValidateRequest) -> ValidationResponse:
    validator = get_phrase_validator()
    is_valid, error = await run_in_threadpool(validator.validate, payload.phrase)
    return ValidationResponse(is_valid=is_valid, error=error)


@app.post("/validate/prompt", response_model=ValidationResponse)
async def validate_prompt(payload: PromptValidationRequest) -> ValidationResponse:
    validator = get_phrase_validator()
    is_valid, error = await run_in_threadpool(
        validator.validate_prompt_phrase,
        payload.phrase,
        payload.prompt_text,
    )
    return ValidationResponse(is_valid=is_valid, error=error)


@app.post("/validate/copy", response_model=ValidationResponse)
async def validate_copy(payload: CopyValidationRequest) -> ValidationResponse:
    validator = get_phrase_validator()
    is_valid, error = await run_in_threadpool(
        validator.validate_copy,
        payload.phrase,
        payload.original_phrase,
        payload.other_copy_phrase,
        payload.prompt_text,
    )
    return ValidationResponse(is_valid=is_valid, error=error)

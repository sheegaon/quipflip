"""Schemas for AI-generated copy hints."""
from pydantic import Field

from backend.schemas.base import BaseSchema


class HintResponse(BaseSchema):
    """Response payload containing AI-generated hints for a copy round."""

    hints: list[str] = Field(..., min_length=1, max_length=3, description="AI-generated hint phrases")

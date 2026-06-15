from typing import Any

from pydantic import BaseModel, Field


class PdfOptionsDTO(BaseModel):
    landscape: bool = False
    format: str = "A4"


class PdfRequestDTO(BaseModel):
    template: str
    data: dict[str, Any]
    options: PdfOptionsDTO | None = Field(default_factory=PdfOptionsDTO)

"""Request and response models for the HTTP API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    kind: str
    status: str
    value: float | None
    detail: str
    items: list[dict] = []  # older reports have none


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_count: int
    char_count: int
    text: str
    ocr_engine: str
    mean_confidence: float | None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    band: str
    summary: str
    signals: list[SignalOut]
    limitations: list[str]
    pipeline_version: str


class ScanCreated(BaseModel):
    id: str
    status: str


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    input_kind: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    document: DocumentOut | None
    report: ReportOut | None

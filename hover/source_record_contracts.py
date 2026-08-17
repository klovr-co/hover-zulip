"""Strict transport contracts for browsing authoritative Source records."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_UNSAFE_DISPLAY_NAME_PATTERN = re.compile(
    r"(?:\d[\s()+-]*){8,}|@(?:g\.us|lid|s\.whatsapp\.net)$", re.IGNORECASE
)


def _validate_display_name(value: str) -> str:
    if " ".join(value.strip().split()) != value or _UNSAFE_DISPLAY_NAME_PATTERN.search(value):
        raise ValueError("display name is not safe")
    return value


def _validate_timestamp(value: object) -> object:
    if not isinstance(value, str) or _RFC3339_PATTERN.fullmatch(value) is None:
        raise ValueError("timestamp must be RFC3339")
    return value


class ClawerSourceRecordSender(_ContractModel):
    ref: str = Field(pattern=r"^person_[0-9a-f]{32}$")
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def safe_display_name(cls, value: str) -> str:
        return _validate_display_name(value)


class ClawerSourceRecordContent(_ContractModel):
    text: str | None = Field(default=None, min_length=1, max_length=50_000)
    voice_transcript: str | None = Field(default=None, min_length=1, max_length=50_000)
    media_description: str | None = Field(default=None, min_length=1, max_length=50_000)


class ClawerSourceRecordMedia(_ContractModel):
    type: str = Field(min_length=1, max_length=100)
    mime_type: str | None = Field(default=None, min_length=1, max_length=200)
    byte_size: int | None = Field(default=None, ge=0)
    available: bool


class ClawerSourceRecordReplyContext(_ContractModel):
    record_ref: str = Field(pattern=r"^record_[0-9a-f]{32}$")
    sender_display_name: str = Field(min_length=1, max_length=200)
    timestamp: datetime
    excerpt: str = Field(min_length=1, max_length=2_000)

    @field_validator("sender_display_name")
    @classmethod
    def safe_display_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("timestamp", mode="before")
    @classmethod
    def strict_timestamp(cls, value: object) -> object:
        return _validate_timestamp(value)

    @field_validator("timestamp")
    @classmethod
    def timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("reply timestamp must be timezone-aware")
        return value


class ClawerSourceRecord(_ContractModel):
    record_ref: str = Field(pattern=r"^record_[0-9a-f]{32}$")
    source_ref: str = Field(pattern=r"^src_[0-9a-f]{32}$")
    sender: ClawerSourceRecordSender
    timestamp: datetime
    content: ClawerSourceRecordContent
    media: ClawerSourceRecordMedia | None
    reply_context: ClawerSourceRecordReplyContext | None

    @field_validator("timestamp", mode="before")
    @classmethod
    def strict_timestamp(cls, value: object) -> object:
        return _validate_timestamp(value)

    @field_validator("timestamp")
    @classmethod
    def timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("record timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def valid_record(self) -> ClawerSourceRecord:
        if self.media is None and not any(
            [self.content.text, self.content.voice_transcript, self.content.media_description]
        ):
            raise ValueError("record must contain browsable content")
        if self.reply_context is not None and self.reply_context.timestamp > self.timestamp:
            raise ValueError("reply context cannot be newer than the record")
        return self


class ClawerSourceRecordPage(_ContractModel):
    schema_version: Literal["1.0"]
    records: list[ClawerSourceRecord] = Field(max_length=50)
    next_cursor: str = Field(max_length=10_000)
    has_more: bool

    @model_validator(mode="after")
    def valid_page(self) -> ClawerSourceRecordPage:
        refs = [record.record_ref for record in self.records]
        ordering = [(record.timestamp, record.record_ref) for record in self.records]
        if len(refs) != len(set(refs)) or ordering != sorted(ordering):
            raise ValueError("records must be unique and strictly chronological")
        if self.has_more != bool(self.next_cursor):
            raise ValueError("cursor presence must match has_more")
        return self

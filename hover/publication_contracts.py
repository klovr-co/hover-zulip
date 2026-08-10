"""Strict, versioned contracts accepted from Clawer through Studio.

This module intentionally mirrors the public transport contract rather than
importing Clawer internals.  Hover is a separate trust boundary and must reject
malformed data before any native message is created.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UNSAFE_DISPLAY_NAME_PATTERN = re.compile(r"(?:\d[\s()+-]*){8,}|@(?:g\.us|lid)$", re.IGNORECASE)
UNSAFE_SUMMARY_PATTERN = re.compile(
    r"(?:\d[\s()+-]*){8,}|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|"
    r"(?:src|person|evidence)_[0-9a-f]{32}",
    re.IGNORECASE,
)
EVIDENCE_REF_PATTERN = re.compile(r"^evidence_[0-9a-f]{32}$")
PERSON_REF_PATTERN = re.compile(r"^person_[0-9a-f]{32}$")


def _validated_display_name(value: str) -> str:
    if " ".join(value.strip().split()) != value or UNSAFE_DISPLAY_NAME_PATTERN.search(value):
        raise ValueError("display name must be normalized and cannot expose a provider identifier")
    return value


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DigestMetrics(_ContractModel):
    messages: int = Field(ge=0)
    text: int = Field(ge=0)
    media: int = Field(ge=0)
    voice: int = Field(ge=0)

    @model_validator(mode="after")
    def component_counts_fit_total(self) -> DigestMetrics:
        if self.text + self.media + self.voice > self.messages:
            raise ValueError("digest metric components exceed message count")
        return self


class DigestPayload(_ContractModel):
    contract: Literal["digest"]
    schema_version: Literal["1.0"]
    title: str = Field(min_length=1, max_length=300)
    timezone: str = Field(min_length=1, max_length=100)
    operation: str = Field(min_length=1, max_length=100_000)
    marketing: str = Field(min_length=1, max_length=100_000)
    metrics: DigestMetrics
    generation_context: str = Field(min_length=1, max_length=300)
    # Personal editions are not one of the six Space pipelines.  Preserve the
    # additive field at the transport boundary without interpreting it here.
    personal: dict[str, object] | None = None


class FeedUpdatePayload(_ContractModel):
    contract: Literal["feed_update"]
    schema_version: Literal["1.0", "1.1"]
    title: str = Field(min_length=1, max_length=300)
    update_type: Literal["development", "milestone", "blocker"]
    developments: list[str] = Field(min_length=1, max_length=50)


class ProgressUpdatePayload(_ContractModel):
    contract: Literal["progress_update"]
    schema_version: Literal["1.0", "1.1"]
    title: str = Field(min_length=1, max_length=300)
    status: Literal["not_started", "in_progress", "blocked", "completed"]
    updates: list[str] = Field(min_length=1, max_length=50)
    resolved_items: list[str] = Field(default_factory=list, max_length=50)
    blockers: list[str] = Field(default_factory=list, max_length=50)


class DecisionPayload(_ContractModel):
    contract: Literal["decision"]
    schema_version: Literal["1.0", "1.1"]
    title: str = Field(min_length=1, max_length=300)
    decision: str = Field(min_length=1, max_length=50_000)
    rationale: str = Field(min_length=1, max_length=50_000)
    lifecycle: Literal["active", "superseded", "reversed"]
    supersedes_publication_id: str | None = None
    reverses_publication_id: str | None = None

    @model_validator(mode="after")
    def valid_lifecycle(self) -> DecisionPayload:
        if self.lifecycle == "active" and (
            self.supersedes_publication_id or self.reverses_publication_id
        ):
            raise ValueError("active decision cannot reference another decision")
        if self.lifecycle == "superseded" and not self.supersedes_publication_id:
            raise ValueError("superseded decision requires its predecessor")
        if self.lifecycle == "reversed" and not self.reverses_publication_id:
            raise ValueError("reversed decision requires its predecessor")
        if self.lifecycle != "superseded" and self.supersedes_publication_id:
            raise ValueError("unexpected superseded decision reference")
        if self.lifecycle != "reversed" and self.reverses_publication_id:
            raise ValueError("unexpected reversed decision reference")
        return self


class SuggestedActionAssignee(_ContractModel):
    kind: Literal["user", "member"]
    ref: str = Field(pattern=r"^person_[0-9a-f]{32}$")
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def safe_display_name(cls, value: str) -> str:
        return _validated_display_name(value)


class SuggestedActionPayload(_ContractModel):
    contract: Literal["suggested_action"]
    schema_version: Literal["1.0"]
    wording: str = Field(min_length=1, max_length=50_000)
    proposed_assignee: SuggestedActionAssignee | None
    proposed_due_date: date | None


class AnalysisFinding(_ContractModel):
    title: str = Field(min_length=1, max_length=300)
    detail: str = Field(min_length=1, max_length=50_000)


class AnalysisSentiment(_ContractModel):
    label: Literal["positive", "neutral", "negative"]
    summary: str = Field(min_length=1, max_length=50_000)


class AnalysisPayload(_ContractModel):
    contract: Literal["analysis"]
    schema_version: Literal["1.0"]
    title: str = Field(min_length=1, max_length=300)
    timezone: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=50_000)
    findings: list[AnalysisFinding] = Field(min_length=1, max_length=50)
    generation_context: str = Field(min_length=1, max_length=300)
    sentiment: AnalysisSentiment | None


PublicationPayload = Annotated[
    DigestPayload
    | FeedUpdatePayload
    | ProgressUpdatePayload
    | DecisionPayload
    | SuggestedActionPayload
    | AnalysisPayload,
    Field(discriminator="contract"),
]


class CoveredPeriod(_ContractModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def valid_period(self) -> CoveredPeriod:
        if self.start.tzinfo is None or self.end.tzinfo is None or self.start >= self.end:
            raise ValueError("covered period must be timezone-aware and increasing")
        return self


class PublicationDisputedDetail(_ContractModel):
    """A source-produced, field-scoped conflict with no provider identity data."""

    ambiguity_key: str = Field(pattern=r"^ambiguity_[0-9a-f]{32}$")
    field_path: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    summary: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(min_length=2, max_length=20)
    involved_person_refs: list[str] = Field(default_factory=list, max_length=20)
    material: bool

    @field_validator("summary")
    @classmethod
    def safe_summary(cls, value: str) -> str:
        if " ".join(value.strip().split()) != value or UNSAFE_SUMMARY_PATTERN.search(value):
            raise ValueError("summary must be normalized and cannot expose a provider identifier")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def unique_conflicting_evidence(cls, value: list[str]) -> list[str]:
        if any(EVIDENCE_REF_PATTERN.fullmatch(ref) is None for ref in value) or len(value) != len(
            set(value)
        ):
            raise ValueError("conflicting evidence references must be unique and bounded")
        return value

    @field_validator("involved_person_refs")
    @classmethod
    def unique_participants(cls, value: list[str]) -> list[str]:
        if any(PERSON_REF_PATTERN.fullmatch(ref) is None for ref in value) or len(value) != len(
            set(value)
        ):
            raise ValueError("involved participant references must be unique and bounded")
        return value


class ClawerPublication(_ContractModel):
    publication_id: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=1000)
    business_identity: str = Field(min_length=1, max_length=1000)
    contract: Literal[
        "digest",
        "feed_update",
        "progress_update",
        "decision",
        "suggested_action",
        "analysis",
    ]
    schema_version: Literal["1.0", "1.1"]
    producer_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
    producer_name: str = Field(min_length=1, max_length=200)
    producing_version: str = Field(min_length=1, max_length=1000)
    run_reference: str = Field(min_length=1, max_length=1000)
    source_ref: str = Field(pattern=r"^src_[0-9a-f]{32}$")
    covered_period: CoveredPeriod
    payload: PublicationPayload
    evidence_refs: list[str] = Field(max_length=100)
    disputed_details: list[PublicationDisputedDetail] = Field(default_factory=list, max_length=20)
    importance: Literal["low", "normal", "high", "urgent"]
    occurred_at: datetime
    generated_at: datetime
    published_at: datetime
    lineage_key: str | None
    parent_publication_id: str | None
    material_change: bool

    @field_validator("occurred_at", "generated_at", "published_at")
    @classmethod
    def timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("publication timestamps must be timezone-aware")
        return value

    @field_validator("producer_name")
    @classmethod
    def safe_producer_name(cls, value: str) -> str:
        return _validated_display_name(value)

    @field_validator("evidence_refs")
    @classmethod
    def unique_evidence_refs(cls, value: list[str]) -> list[str]:
        if any(EVIDENCE_REF_PATTERN.fullmatch(ref) is None for ref in value) or len(value) != len(
            set(value)
        ):
            raise ValueError("publication evidence references must be unique and bounded")
        return value

    @model_validator(mode="after")
    def matching_contract(self) -> ClawerPublication:
        if self.payload.contract != self.contract:
            raise ValueError("publication payload contract does not match envelope")
        if self.payload.schema_version != self.schema_version:
            raise ValueError("publication payload schema version does not match envelope")
        if self.schema_version == "1.0" and self.disputed_details:
            raise ValueError("publication schema 1.0 cannot carry disputed details")
        if self.schema_version == "1.1" and self.contract not in {
            "feed_update",
            "progress_update",
            "decision",
        }:
            raise ValueError("publication schema 1.1 is not supported for this contract")
        payload_fields = set(self.payload.model_fields)
        ambiguity_keys: set[str] = set()
        field_paths: set[str] = set()
        envelope_evidence = set(self.evidence_refs)
        for detail in self.disputed_details:
            if detail.ambiguity_key in ambiguity_keys:
                raise ValueError("publication ambiguity keys must be unique")
            if detail.field_path in field_paths:
                raise ValueError("publication disputed fields must be unique")
            if detail.field_path not in payload_fields or detail.field_path in {
                "contract",
                "schema_version",
            }:
                raise ValueError("publication disputed field must name an existing payload field")
            if not set(detail.evidence_refs).issubset(envelope_evidence):
                raise ValueError("conflicting evidence must belong to the publication")
            ambiguity_keys.add(detail.ambiguity_key)
            field_paths.add(detail.field_path)
        return self


class ClawerPublicationPage(_ContractModel):
    publications: list[ClawerPublication] = Field(max_length=100)
    next_cursor: str = Field(min_length=1, max_length=10_000)
    has_more: bool


class EvidenceSender(_ContractModel):
    ref: str = Field(pattern=r"^person_[0-9a-f]{32}$")
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def safe_display_name(cls, value: str) -> str:
        return _validated_display_name(value)


class EvidenceContent(_ContractModel):
    text: str | None = Field(min_length=1)
    voice_transcript: str | None = Field(min_length=1)
    media_description: str | None = Field(min_length=1)


class EvidenceMedia(_ContractModel):
    type: str = Field(min_length=1, max_length=100)
    mime_type: str | None = Field(default=None, max_length=200)
    byte_size: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, max_length=200)
    available: bool


class ResolvedEvidence(_ContractModel):
    evidence_ref: str = Field(pattern=r"^evidence_[0-9a-f]{32}$")
    source_ref: str = Field(pattern=r"^src_[0-9a-f]{32}$")
    sender: EvidenceSender
    timestamp: datetime
    content: EvidenceContent
    media: EvidenceMedia | None

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("evidence timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def has_exact_content(self) -> ResolvedEvidence:
        if (
            self.content.text is None
            and self.content.voice_transcript is None
            and self.content.media_description is None
            and self.media is None
        ):
            raise ValueError("evidence must contain source content or media")
        return self


class ResolvedEvidenceBatch(_ContractModel):
    evidence: list[ResolvedEvidence] = Field(max_length=100)

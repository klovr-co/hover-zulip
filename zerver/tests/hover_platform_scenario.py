from __future__ import annotations

from pathlib import Path
from typing import Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field, model_validator

from hover.publication_contracts import ClawerPublication

SCENARIO_FIXTURE = Path(__file__).parent / "fixtures" / "hover" / "platform_scenario_v1.json"

ProviderKey = Literal["whatsapp", "instagram", "github"]
StepKind = Literal[
    "generated_update",
    "conflict_detected",
    "suggested_action",
    "todo_created",
    "todo_completed",
    "review_submitted",
    "conflict_resolved",
]
REQUIRED_STEP_KINDS: set[StepKind] = {
    "generated_update",
    "conflict_detected",
    "suggested_action",
    "todo_created",
    "todo_completed",
    "review_submitted",
    "conflict_resolved",
}


class PlatformProvider(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_key: ProviderKey
    provider_name: str
    source_ref: str = Field(pattern=r"^src_[0-9a-f]{32}$")
    source_type: str
    display_name: str


class PlatformScenarioStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    kind: StepKind
    provider_key: ProviderKey | None = None
    publication: ClawerPublication | None = None
    references_step_id: str | None = None

    @model_validator(mode="after")
    def publication_shape_matches_step(self) -> PlatformScenarioStep:
        publication_kinds = {"generated_update", "conflict_detected", "suggested_action"}
        if (self.kind in publication_kinds) != (self.publication is not None):
            raise ValueError("scenario publication steps must carry exactly one publication")
        if (self.kind in publication_kinds) != (self.provider_key is not None):
            raise ValueError("scenario publication steps must identify one provider")
        if (self.kind not in publication_kinds) != (self.references_step_id is not None):
            raise ValueError("scenario action steps must reference their predecessor")
        return self


class HoverPlatformScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    providers: list[PlatformProvider]
    steps: list[PlatformScenarioStep]

    @model_validator(mode="after")
    def complete_and_ordered_workflow(self) -> HoverPlatformScenario:
        provider_by_key = {provider.provider_key: provider for provider in self.providers}
        if set(provider_by_key) != {"whatsapp", "instagram", "github"}:
            raise ValueError("scenario must cover all supported fixture providers exactly once")
        if len(provider_by_key) != len(self.providers):
            raise ValueError("scenario providers must be unique")

        step_by_id: dict[str, PlatformScenarioStep] = {}
        seen_kinds: set[StepKind] = set()
        for step in self.steps:
            if step.step_id in step_by_id:
                raise ValueError("scenario step IDs must be unique")
            if step.references_step_id is not None and step.references_step_id not in step_by_id:
                raise ValueError("scenario references must point to an earlier step")
            if step.publication is not None:
                assert step.provider_key is not None
                provider = provider_by_key[step.provider_key]
                if step.publication.source_ref != provider.source_ref:
                    raise ValueError("scenario publication must use its provider source")
            step_by_id[step.step_id] = step
            seen_kinds.add(step.kind)
        if seen_kinds != REQUIRED_STEP_KINDS:
            raise ValueError("scenario must cover the complete platform workflow")
        return self

    def publication(self, step_id: str) -> ClawerPublication:
        step = next((step for step in self.steps if step.step_id == step_id), None)
        if step is None or step.publication is None:
            raise KeyError(step_id)
        return step.publication.model_copy(deep=True)


def load_hover_platform_scenario() -> HoverPlatformScenario:
    return HoverPlatformScenario.model_validate(orjson.loads(SCENARIO_FIXTURE.read_bytes()))

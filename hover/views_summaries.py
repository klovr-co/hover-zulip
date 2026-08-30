from datetime import time
from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import BaseModel, Field, Json, StringConstraints

from hover.actions_modules import installation_data
from hover.actions_summaries import SummaryInputSpec, do_create_summary, do_update_summary
from hover.lib_spaces import (
    access_space_for_administration,
    get_space_data,
    space_projection_queryset,
)
from hover.models import ModuleInstallation
from zerver.decorator import require_non_guest_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile


class SummaryInput(BaseModel):
    topic_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
    ]
    kind: Literal["regular", "source"]
    attachment_id: int | None = None


def _parse_local_time(value: str) -> time:
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        raise JsonableError(_("Invalid scheduled local time."))
    if parsed.tzinfo is not None:
        raise JsonableError(_("Scheduled local time must not contain an offset."))
    return parsed


@require_non_guest_user
@typed_endpoint
def create_summary(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    version_id: Json[int],
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)],
    inputs: Json[list[SummaryInput]],
    local_time: Annotated[str, StringConstraints(max_length=15)],
    timezone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)],
    member_ids: Json[list[Annotated[int, Field(gt=0)]]],
) -> HttpResponse:
    space = access_space_for_administration(user_profile, space_id)
    installation = do_create_summary(
        acting_user=user_profile,
        space=space,
        version_id=version_id,
        label=label,
        inputs=[
            SummaryInputSpec(
                topic_name=item.topic_name,
                kind=item.kind,
                attachment_id=item.attachment_id,
            )
            for item in inputs
        ],
        local_time=_parse_local_time(local_time),
        timezone=timezone,
        member_ids=member_ids,
    )
    projected_space = space_projection_queryset().get(id=space.id)
    return json_success(
        request,
        data={
            "installation": installation_data(installation),
            "space": get_space_data(projected_space, viewer=user_profile),
            "created": True,
        },
    )


@require_non_guest_user
@typed_endpoint
def update_summary(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    installation_id: PathOnly[int],
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)],
    inputs: Json[list[SummaryInput]],
    local_time: Annotated[str, StringConstraints(max_length=15)],
    timezone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)],
    member_ids: Json[list[Annotated[int, Field(gt=0)]]],
) -> HttpResponse:
    try:
        installation = ModuleInstallation.objects.select_related("space").get(
            id=installation_id,
            realm=user_profile.realm,
            summary_stream__isnull=False,
        )
    except ModuleInstallation.DoesNotExist:
        raise JsonableError(_("Invalid Summary ID."))
    updated = do_update_summary(
        acting_user=user_profile,
        installation=installation,
        label=label,
        inputs=[
            SummaryInputSpec(
                topic_name=item.topic_name,
                kind=item.kind,
                attachment_id=item.attachment_id,
            )
            for item in inputs
        ],
        local_time=_parse_local_time(local_time),
        timezone=timezone,
        member_ids=member_ids,
    )
    projected_space = space_projection_queryset().get(id=updated.space_id)
    return json_success(
        request,
        data={
            "installation": installation_data(updated),
            "space": get_space_data(projected_space, viewer=user_profile),
            "updated": True,
        },
    )

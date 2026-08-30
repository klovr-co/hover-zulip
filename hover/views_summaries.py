from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import orjson
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, Field, Json, StringConstraints

from hover.actions_modules import installation_data
from hover.actions_summaries import SummaryInputSpec, do_create_summary, do_update_summary
from hover.actions_summary_executions import (
    access_summary_execution,
    do_accept_summary_result,
    do_prepare_summary_execution,
    do_publish_summary_execution,
    execution_data,
)
from hover.lib_spaces import (
    access_space_for_administration,
    get_space_data,
    space_projection_queryset,
)
from hover.models import ModuleInstallation, SummaryExecution
from hover.summary_dispatch import get_summary_dispatcher
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
    interval_seconds: Json[Annotated[int, Field(ge=3600, le=2592000)]],
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
        interval_seconds=interval_seconds,
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
    interval_seconds: Json[Annotated[int, Field(ge=3600, le=2592000)]],
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
        interval_seconds=interval_seconds,
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


def _access_summary(user_profile: UserProfile, installation_id: int) -> ModuleInstallation:
    try:
        return ModuleInstallation.objects.select_related("space", "realm").get(
            id=installation_id,
            realm=user_profile.realm,
            summary_stream__isnull=False,
        )
    except ModuleInstallation.DoesNotExist:
        raise JsonableError(_("Invalid Summary ID."))


@require_non_guest_user
@typed_endpoint
def generate_summary_preview(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    installation_id: PathOnly[int],
    start_at: Json[datetime],
    end_at: Json[datetime],
    request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ],
) -> HttpResponse:
    installation = _access_summary(user_profile, installation_id)
    dispatch = do_prepare_summary_execution(
        installation=installation,
        kind=SummaryExecution.Kind.MANUAL,
        window_start=start_at,
        window_end=end_at,
        requester=user_profile,
        manual_request_id=request_id,
    )
    get_summary_dispatcher().dispatch(
        realm_uuid=user_profile.realm.uuid,
        dispatch=dispatch,
    )
    dispatch.execution.refresh_from_db()
    return json_success(request, data={"execution": execution_data(dispatch.execution)})


@require_non_guest_user
@typed_endpoint
def get_summary_execution(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    installation_id: PathOnly[int],
    execution_id: PathOnly[UUID],
) -> HttpResponse:
    installation = _access_summary(user_profile, installation_id)
    execution = access_summary_execution(
        user=user_profile,
        installation=installation,
        execution_id=str(execution_id),
    )
    return json_success(request, data={"execution": execution_data(execution)})


@require_non_guest_user
@typed_endpoint
def publish_summary_preview(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    installation_id: PathOnly[int],
    execution_id: PathOnly[UUID],
) -> HttpResponse:
    installation = _access_summary(user_profile, installation_id)
    execution = access_summary_execution(
        user=user_profile,
        installation=installation,
        execution_id=str(execution_id),
    )
    published = do_publish_summary_execution(execution=execution, acting_user=user_profile)
    return json_success(request, data={"execution": execution_data(published)})


@csrf_exempt
def summary_execution_callback(request: HttpRequest, *, execution_id: UUID) -> HttpResponse:
    if request.method != "POST" or len(request.body) > 128 * 1024:
        raise JsonableError(_("Invalid Summary callback."))
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise JsonableError(_("Invalid Summary callback credential."))
    try:
        payload = orjson.loads(request.body)
    except orjson.JSONDecodeError:
        raise JsonableError(_("Invalid Summary result contract."))
    if not isinstance(payload, dict):
        raise JsonableError(_("Invalid Summary result contract."))
    execution = do_accept_summary_result(
        execution_id=str(execution_id),
        callback_bearer=authorization.removeprefix("Bearer "),
        payload=payload,
    )
    if execution.kind == SummaryExecution.Kind.SCHEDULED and execution.status in {
        SummaryExecution.Status.SUCCEEDED,
        SummaryExecution.Status.NO_CHANGE,
    }:
        execution = do_publish_summary_execution(execution=execution)
    return json_success(
        request,
        data={
            "execution_id": str(execution.id),
            "status": execution.status,
            "result_hash": execution.result_hash,
        },
    )

from datetime import date
from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Field, Json, StringConstraints

from hover.actions_sources import do_attach_source, do_delete_source_evidence, do_detach_source
from hover.clawer_sync import get_clawer_sync
from hover.lib_connected_accounts import access_connected_account
from hover.lib_sources import (
    canonical_source_for_attachment,
    discover_allowed_sources,
    get_actor_grant,
    get_attachment_data,
)
from hover.lib_spaces import (
    access_space_by_id,
    access_space_for_administration,
    get_space_data,
    space_projection_queryset,
    user_is_space_administrator,
)
from hover.models import ConnectedAccountGrantSelector, SpaceAttachment
from zerver.decorator import require_non_guest_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile

SourceRef = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^src_[0-9a-f]{32}$",
        max_length=ConnectedAccountGrantSelector.MAX_SOURCE_REF_LENGTH,
    ),
]


@require_non_guest_user
@typed_endpoint
def discover_sources(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    account_id: Json[int],
    cursor: Json[str | None] = None,
    limit: Json[Annotated[int, Field(ge=1, le=100)]] = 20,
    query: Json[Annotated[str, StringConstraints(max_length=100)]] = "",
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    if not user_is_space_administrator(user_profile, space):
        raise JsonableError(_("Invalid Space ID"))
    account = access_connected_account(user_profile, account_id)
    data = discover_allowed_sources(
        user_profile=user_profile,
        space=space,
        account=account,
        cursor=cursor,
        limit=limit,
        query=query,
        clawer_sync=get_clawer_sync(),
    )
    return json_success(request, data=data)


@require_non_guest_user
@typed_endpoint
def preview_source(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    account_id: Json[int],
    source_ref: Json[SourceRef],
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    if not user_is_space_administrator(user_profile, space):
        raise JsonableError(_("Invalid Space ID"))
    account = access_connected_account(user_profile, account_id)
    grant = get_actor_grant(user_profile, account)
    source = canonical_source_for_attachment(
        user_profile=user_profile,
        account=account,
        grant=grant,
        source_ref=source_ref,
        clawer_sync=get_clawer_sync(),
    )
    return json_success(
        request,
        data={
            "source": {
                "source_ref": source.source_ref,
                "provider_key": source.provider,
                "source_type": source.source_type,
                "display_name": source.display_name,
                "account_id": account.id,
                "account_display_name": account.display_name,
            }
        },
    )


@require_non_guest_user
@typed_endpoint
def attach_source(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    account_id: Json[int],
    source_ref: Json[SourceRef],
    history_window: Json[Literal["today", "last_30_days", "custom"]],
    history_timezone: Json[
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                min_length=1,
                max_length=SpaceAttachment.MAX_TIMEZONE_LENGTH,
            ),
        ]
    ],
    custom_start_date: Json[date | None] = None,
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    attachment, created = do_attach_source(
        acting_user=user_profile,
        space=space,
        account_id=account_id,
        source_ref=source_ref,
        history_window=history_window,
        history_timezone=history_timezone,
        custom_start_date=custom_start_date,
        clawer_sync=get_clawer_sync(),
    )
    refreshed_space = access_space_by_id(user_profile, space_id)
    return json_success(
        request,
        data={
            "space": get_space_data(refreshed_space, viewer=user_profile),
            "attachment": get_attachment_data(attachment),
            "created": created,
        },
    )


@require_non_guest_user
@typed_endpoint
def detach_source(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    attachment_id: PathOnly[int],
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    attachment, changed = do_detach_source(
        acting_user=user_profile, space=space, attachment_id=attachment_id
    )
    return json_success(
        request,
        data={
            "space": get_space_data(
                space_projection_queryset().get(id=space.id), viewer=user_profile
            ),
            "attachment_id": attachment.id,
            "changed": changed,
        },
    )


@require_non_guest_user
@typed_endpoint
def delete_source_evidence(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    attachment_id: PathOnly[int],
    confirmation: Json[Annotated[str, StringConstraints(max_length=200)]],
) -> HttpResponse:
    space = access_space_for_administration(user_profile, space_id)
    attachment, changed, deleted_count = do_delete_source_evidence(
        acting_user=user_profile,
        space=space,
        attachment_id=attachment_id,
        confirmation=confirmation,
    )
    return json_success(
        request,
        data={
            "space": get_space_data(
                space_projection_queryset().get(id=space.id), viewer=user_profile
            ),
            "attachment_id": attachment.id,
            "changed": changed,
            "deleted_evidence_link_count": deleted_count,
        },
    )

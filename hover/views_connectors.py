from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import Json, StringConstraints

from hover.actions_connectors import (
    access_connector,
    do_create_connector,
    do_disable_connector,
    do_reconcile_connector,
    do_rotate_connector,
    do_update_connector,
)
from hover.lib_connectors import connector_data, visible_connectors
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint, typed_endpoint_without_parameters
from zerver.models.users import UserProfile

ProviderKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
DestinationName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=60),
]


@require_non_guest_user
@typed_endpoint_without_parameters
def list_connectors(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    connectors = visible_connectors(user_profile).order_by("provider_name", "id")
    return json_success(
        request,
        data={
            "connectors": [
                connector_data(connector, viewer=user_profile) for connector in connectors
            ]
        },
    )


@require_non_guest_user
@typed_endpoint
def create_connector(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    provider_key: Json[ProviderKey],
    name: Json[str] = "",
    destination_name: Json[DestinationName],
    topic: Json[str] = "",
    event_options: Json[list[str]] | None = None,
) -> HttpResponse:
    connector = do_create_connector(
        acting_user=user_profile,
        provider_key=provider_key,
        name=name,
        destination_name=destination_name,
        topic=topic,
        event_options=event_options or [],
    )
    return json_success(
        request,
        data={"connector": connector_data(connector, viewer=user_profile, include_url=True)},
    )


@require_non_guest_user
@typed_endpoint
def get_connector(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    connector_id: PathOnly[int],
) -> HttpResponse:
    connector = access_connector(user_profile, connector_id)
    return json_success(
        request,
        data={"connector": connector_data(connector, viewer=user_profile, include_url=True)},
    )


@require_non_guest_user
@typed_endpoint
def update_connector(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    connector_id: PathOnly[int],
    name: Json[str] | None = None,
    destination_name: Json[DestinationName] | None = None,
    topic: Json[str] | None = None,
    event_options: Json[list[str]] | None = None,
) -> HttpResponse:
    connector = access_connector(user_profile, connector_id)
    connector = do_update_connector(
        connector,
        acting_user=user_profile,
        name=name,
        destination_name=destination_name,
        topic=topic,
        event_options=event_options,
    )
    return json_success(
        request,
        data={"connector": connector_data(connector, viewer=user_profile, include_url=True)},
    )


@require_non_guest_user
@typed_endpoint
def reconcile_connector(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    connector_id: PathOnly[int],
    provider_key: Json[ProviderKey],
    destination_name: Json[DestinationName],
    topic: Json[str] = "",
    event_options: Json[list[str]] | None = None,
) -> HttpResponse:
    connector = access_connector(user_profile, connector_id)
    connector = do_reconcile_connector(
        connector,
        acting_user=user_profile,
        provider_key=provider_key,
        destination_name=destination_name,
        topic=topic,
        event_options=event_options or [],
    )
    return json_success(
        request,
        data={"connector": connector_data(connector, viewer=user_profile, include_url=True)},
    )


@require_non_guest_user
@typed_endpoint
def rotate_connector(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    connector_id: PathOnly[int],
) -> HttpResponse:
    connector = access_connector(user_profile, connector_id)
    connector = do_rotate_connector(connector, acting_user=user_profile)
    return json_success(
        request,
        data={"connector": connector_data(connector, viewer=user_profile, include_url=True)},
    )


@require_non_guest_user
@typed_endpoint
def disable_connector(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    connector_id: PathOnly[int],
) -> HttpResponse:
    connector = access_connector(user_profile, connector_id)
    connector = do_disable_connector(connector, acting_user=user_profile)
    return json_success(
        request,
        data={"connector": connector_data(connector, viewer=user_profile)},
    )

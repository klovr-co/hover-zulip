from collections.abc import Sequence

from django.db.models import F, Q

from hover.models import IntegrationMessageProvenance, IntegrationRouteAssociation, SpaceAttachment
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    emit_hover_telemetry_on_commit,
)
from zerver.models.messages import Message


def route_integration_messages(messages: Sequence[Message]) -> None:
    """Apply the server-owned Source topic before messages become durable."""

    channel_messages = [message for message in messages if message.is_channel_message]
    if not channel_messages:
        return
    route_keys = {(message.sender_id, message.recipient.type_id) for message in channel_messages}
    route_filter = Q()
    for bot_id, stream_id in route_keys:
        route_filter |= Q(bot_id=bot_id, stream_id=stream_id)
    routes = IntegrationRouteAssociation.objects.select_related("attachment").filter(
        route_filter,
        state=IntegrationRouteAssociation.State.ACTIVE,
        bot__is_active=True,
        attachment__state=SpaceAttachment.State.ACTIVE,
        attachment__source__supports_live_capture=True,
        attachment__source__account__approval_state="approved",
        attachment__source__account__connection_kind="native_integration",
        attachment__source__account__incoming_webhook_bot_id=F("bot_id"),
        attachment__space__state="launched",
    )
    routes_by_key = {(route.bot_id, route.stream_id): route for route in routes}
    for message in channel_messages:
        route = routes_by_key.get((message.sender_id, message.recipient.type_id))
        if route is not None and route.attachment.destination_topic:
            message.set_topic_name(route.attachment.destination_topic)


def capture_integration_message_provenance(messages: Sequence[Message]) -> None:
    """Persist native integration provenance before any message payload is serialized.

    Messages are matched only by their actual incoming bot and actual destination
    stream.  The configured Source metadata is snapshotted so later edits or route
    detachment cannot rewrite historical provenance.
    """
    channel_messages = [message for message in messages if message.is_channel_message]
    if not channel_messages:
        return
    route_keys = {(message.sender_id, message.recipient.type_id) for message in channel_messages}
    route_filter = Q()
    for bot_id, stream_id in route_keys:
        route_filter |= Q(bot_id=bot_id, stream_id=stream_id)
    routes = (
        IntegrationRouteAssociation.objects.select_for_update(no_key=True, of=("self",))
        .select_related("attachment__source__account", "attachment__space", "bot")
        .filter(
            route_filter,
            state=IntegrationRouteAssociation.State.ACTIVE,
            bot__is_active=True,
            attachment__state=SpaceAttachment.State.ACTIVE,
            attachment__source__supports_live_capture=True,
            attachment__source__account__approval_state="approved",
            attachment__source__account__connection_kind="native_integration",
            attachment__source__account__incoming_webhook_bot_id=F("bot_id"),
            attachment__space__state="launched",
        )
    )
    routes_by_key = {(route.bot_id, route.stream_id): route for route in routes}
    routes_by_id = {route.id: route for route in routes_by_key.values()}
    existing_message_ids = set(
        IntegrationMessageProvenance.objects.filter(
            message_id__in=[message.id for message in channel_messages]
        ).values_list("message_id", flat=True)
    )
    provenance = []
    for message in channel_messages:
        if message.id in existing_message_ids:
            continue
        route = routes_by_key.get((message.sender_id, message.recipient.type_id))
        if (
            route is None
            or route.attachment.space.stream_id != route.stream_id
            or message.topic_name().casefold() != route.attachment.destination_topic.casefold()
        ):
            continue
        source = route.attachment.source
        provenance.append(
            IntegrationMessageProvenance(
                message=message,
                realm_id=message.realm_id,
                association=route,
                attachment=route.attachment,
                source=source,
                provider_key=source.provider_key,
                provider_name=source.provider_name,
                source_type=source.source_type,
                display_name=source.display_name,
                external_url=source.external_url,
            )
        )
    IntegrationMessageProvenance.objects.bulk_create(provenance)
    counts_by_route: dict[int, int] = {}
    for item in provenance:
        counts_by_route[item.association_id] = counts_by_route.get(item.association_id, 0) + 1
    for route_id, message_count in counts_by_route.items():
        route = routes_by_id[route_id]
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.NATIVE_INGESTION,
            HoverTelemetryOutcome.SUCCESS,
            dimensions={
                "realm_id": route.realm_id,
                "space_id": route.attachment.space_id,
                "attachment_id": route.attachment_id,
                "message_count_bucket": count_bucket(message_count),
                "posthog": route.attachment.source.provider_key == "posthog",
                "provisioned": False,
            },
        )

from dataclasses import dataclass
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.lib_spaces import (
    send_space_update_on_commit,
    space_projection_queryset,
    user_is_space_administrator,
)
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    IntegrationRouteAssociation,
    Source,
    SourceCapability,
    Space,
    SpaceAttachment,
    SpaceMembership,
)
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    emit_hover_telemetry_on_commit,
)
from zerver.actions.create_user import notify_created_bot
from zerver.actions.streams import bulk_add_subscriptions
from zerver.actions.user_settings import do_regenerate_api_key
from zerver.lib.create_user import create_user
from zerver.lib.exceptions import InvalidJSONError, JsonableError
from zerver.lib.users import validate_short_name_and_construct_bot_email
from zerver.models.users import UserProfile, get_user_profile_by_id


@dataclass(frozen=True)
class NativeSourceAdapter:
    provider_name: str
    source_type: str
    webhook_integration: str


NATIVE_SOURCE_ADAPTERS = {
    "github": NativeSourceAdapter("GitHub", "repository_events", "github"),
    "posthog": NativeSourceAdapter("PostHog", "product_analytics_events", "slack_incoming"),
}


@dataclass(frozen=True)
class ProvisionedNativeSource:
    attachment: SpaceAttachment
    route: IntegrationRouteAssociation
    webhook_url: str


def _native_webhook_url(*, route: IntegrationRouteAssociation, integration: str) -> str:
    query = urlencode({"stream": route.stream.name, "api_key": route.bot.api_key})
    return f"{settings.EXTERNAL_URI_SCHEME}{route.realm.host}/api/v1/external/{integration}?{query}"


@transaction.atomic(durable=True)
def do_provision_native_source(
    *,
    acting_user: UserProfile,
    space: Space,
    provider_key: str,
    display_name: str,
) -> ProvisionedNativeSource:
    adapter = NATIVE_SOURCE_ADAPTERS.get(provider_key)
    display_name = " ".join(display_name.split())
    if adapter is None or not display_name or len(display_name) > Source.MAX_DISPLAY_NAME_LENGTH:
        raise JsonableError(_("Choose GitHub or PostHog and enter a Source name."))
    locked_space = (
        Space.objects.select_for_update(no_key=True, of=("self",))
        .select_related("stream")
        .get(id=space.id, realm=space.realm)
    )
    _assert_launched_space_administrator(acting_user=acting_user, space=locked_space)
    assert locked_space.stream is not None

    token = uuid4().hex[:12]
    _short_name, email = validate_short_name_and_construct_bot_email(
        f"hover-{provider_key}-{token}", locked_space.realm
    )
    bot = create_user(
        email,
        None,
        locked_space.realm,
        f"{adapter.provider_name} · {display_name}"[: UserProfile.MAX_NAME_LENGTH],
        bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        bot_owner=acting_user,
    )
    notify_created_bot(bot)
    bulk_add_subscriptions(
        locked_space.realm,
        [locked_space.stream],
        [bot],
        acting_user=acting_user,
    )
    account = ConnectedAccount.objects.create(
        realm=locked_space.realm,
        provider_key=provider_key,
        provider_name=adapter.provider_name,
        external_account_id=uuid4(),
        display_name=display_name,
        connection_kind=ConnectedAccount.ConnectionKind.NATIVE_INTEGRATION,
        incoming_webhook_bot=bot,
        created_by=acting_user,
        owner=acting_user,
        approval_state=ConnectedAccount.ApprovalState.APPROVED,
        health_status=ConnectedAccount.HealthStatus.UNKNOWN,
    )
    grant = ConnectedAccountGrant.objects.create(
        realm=locked_space.realm,
        account=account,
        user=acting_user,
        created_by=acting_user,
        state=ConnectedAccountGrant.State.ACTIVE,
        all_selectors=True,
    )
    source = Source.objects.create(
        realm=locked_space.realm,
        account=account,
        adapter_key="zulip_native",
        provider_key=provider_key,
        provider_name=adapter.provider_name,
        source_type=adapter.source_type,
        external_ref=f"src_{uuid4().hex}",
        display_name=display_name,
        supports_live_capture=True,
    )
    from hover.actions_sources import _available_destination_topic

    setup_at = timezone_now()
    attachment = SpaceAttachment.objects.create(
        realm=locked_space.realm,
        space=locked_space,
        source=source,
        state=SpaceAttachment.State.ACTIVE,
        history_window=SpaceAttachment.HistoryWindow.TODAY,
        history_timezone=acting_user.timezone or "UTC",
        history_start_at=setup_at,
        destination_topic=_available_destination_topic(locked_space, display_name),
        next_publication_sync_at=None,
        attached_by=acting_user,
    )
    SourceCapability.objects.create(source=source, capability="message_history")
    route = IntegrationRouteAssociation.objects.create(
        realm=locked_space.realm,
        attachment=attachment,
        bot=bot,
        stream=locked_space.stream,
        configured_by=acting_user,
        live_since=setup_at,
    )
    try:
        account.full_clean()
        grant.full_clean()
        source.full_clean()
        attachment.clean()
        route.full_clean()
    except ValidationError as exc:
        raise InvalidJSONError(str(exc))
    _notify_space(locked_space)
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.NATIVE_INGESTION,
        HoverTelemetryOutcome.SUCCESS,
        dimensions={
            "realm_id": locked_space.realm_id,
            "space_id": locked_space.id,
            "attachment_id": attachment.id,
            "posthog": provider_key == "posthog",
            "provisioned": True,
        },
    )
    return ProvisionedNativeSource(
        attachment=attachment,
        route=route,
        webhook_url=_native_webhook_url(route=route, integration=adapter.webhook_integration),
    )


def do_rotate_native_source_webhook(
    *, acting_user: UserProfile, space: Space, attachment_id: int
) -> str:
    _assert_launched_space_administrator(acting_user=acting_user, space=space)
    try:
        route = IntegrationRouteAssociation.objects.select_related(
            "realm", "stream", "bot", "attachment__source"
        ).get(
            attachment_id=attachment_id,
            attachment__space=space,
            state=IntegrationRouteAssociation.State.ACTIVE,
            attachment__state=SpaceAttachment.State.ACTIVE,
        )
    except IntegrationRouteAssociation.DoesNotExist:
        raise JsonableError(_("Invalid Source attachment ID"))
    adapter = NATIVE_SOURCE_ADAPTERS.get(route.attachment.source.provider_key)
    if adapter is None:
        raise JsonableError(_("This Source does not use a native webhook."))
    do_regenerate_api_key(route.bot, acting_user)
    route.bot.refresh_from_db(fields=["api_key"])
    return _native_webhook_url(route=route, integration=adapter.webhook_integration)


def get_integration_route_data(route: IntegrationRouteAssociation) -> dict[str, object]:
    return {
        "id": route.id,
        "state": route.state,
        "bot_user_id": route.bot_id,
        "bot_name": route.bot.full_name,
        "stream_id": route.stream_id,
        "topic_name": route.attachment.destination_topic,
        "live_since": route.live_since.isoformat(),
    }


def _member_ids(space: Space) -> list[int]:
    return list(
        SpaceMembership.objects.filter(space=space, user__is_active=True).values_list(
            "user_id", flat=True
        )
    )


def _notify_space(space: Space) -> None:
    projected = space_projection_queryset().get(id=space.id)
    send_space_update_on_commit(projected, _member_ids(space))


def _assert_launched_space_administrator(*, acting_user: UserProfile, space: Space) -> None:
    if (
        acting_user.realm_id != space.realm_id
        or space.state != Space.State.LAUNCHED
        or space.stream_id is None
        or not acting_user.is_active
        or not user_is_space_administrator(acting_user, space)
        or not SpaceMembership.objects.filter(space=space, user=acting_user).exists()
    ):
        raise JsonableError(_("Invalid Space ID"))


def _assert_source_grant(*, acting_user: UserProfile, source: Source) -> None:
    try:
        grant = ConnectedAccountGrant.objects.select_for_update(no_key=True).get(
            account=source.account,
            user=acting_user,
            state=ConnectedAccountGrant.State.ACTIVE,
        )
    except ConnectedAccountGrant.DoesNotExist:
        raise JsonableError(_("This Connected Account is not available."))
    if grant.all_selectors:
        return
    selector_types = {source.source_type, f"{source.provider_key}_{source.source_type}"}
    if not grant.selectors.filter(
        selector_type__in=selector_types, source_ref=source.external_ref
    ).exists():
        raise JsonableError(_("This Connected Account is not available."))


@transaction.atomic(durable=True)
def do_associate_integration_route(
    *,
    acting_user: UserProfile,
    space: Space,
    attachment_id: int,
    bot_user_id: int,
) -> tuple[IntegrationRouteAssociation, bool]:
    locked_space = (
        Space.objects.select_for_update(no_key=True, of=("self",))
        .select_related("stream")
        .get(id=space.id, realm=space.realm)
    )
    _assert_launched_space_administrator(acting_user=acting_user, space=locked_space)

    try:
        attachment = (
            SpaceAttachment.objects.select_for_update(no_key=True, of=("self",))
            .select_related("source__account__incoming_webhook_bot", "space")
            .get(
                id=attachment_id,
                space=locked_space,
                realm=locked_space.realm,
                state=SpaceAttachment.State.ACTIVE,
            )
        )
    except SpaceAttachment.DoesNotExist:
        raise JsonableError(_("Invalid Source attachment ID"))

    source = attachment.source
    account = ConnectedAccount.objects.select_for_update(no_key=True).get(id=source.account_id)
    source.account = account
    if (
        account.approval_state != ConnectedAccount.ApprovalState.APPROVED
        or account.connection_kind != ConnectedAccount.ConnectionKind.NATIVE_INTEGRATION
        or account.incoming_webhook_bot_id != bot_user_id
        or not source.supports_live_capture
    ):
        raise JsonableError(_("This Source does not support live integration capture."))
    _assert_source_grant(acting_user=acting_user, source=source)

    try:
        bot = get_user_profile_by_id(bot_user_id)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Invalid integration bot ID"))
    if (
        bot.realm_id != locked_space.realm_id
        or not bot.is_active
        or not bot.is_bot
        or bot.bot_type != UserProfile.INCOMING_WEBHOOK_BOT
    ):
        raise JsonableError(_("Invalid integration bot ID"))

    existing = (
        IntegrationRouteAssociation.objects.select_for_update(no_key=True)
        .filter(attachment=attachment, state=IntegrationRouteAssociation.State.ACTIVE)
        .first()
    )
    if existing is not None:
        if existing.bot_id == bot.id and existing.stream_id == locked_space.stream_id:
            return existing, False
        raise JsonableError(_("This Source already has an active integration route."))
    if IntegrationRouteAssociation.objects.filter(
        bot=bot, state=IntegrationRouteAssociation.State.ACTIVE
    ).exists():
        raise JsonableError(_("This integration bot is already assigned to another Source."))

    route = IntegrationRouteAssociation(
        realm=locked_space.realm,
        attachment=attachment,
        bot=bot,
        stream=locked_space.stream,
        configured_by=acting_user,
    )
    try:
        source.full_clean()
        route.full_clean()
        route.save()
    except ValidationError as exc:
        raise InvalidJSONError(str(exc))
    except IntegrityError:
        raise JsonableError(_("This integration route is already assigned."))
    _notify_space(locked_space)
    return route, True


@transaction.atomic(durable=True)
def do_detach_integration_route(
    *, acting_user: UserProfile, space: Space, route_id: int
) -> IntegrationRouteAssociation:
    locked_space = Space.objects.select_for_update(no_key=True).get(id=space.id, realm=space.realm)
    _assert_launched_space_administrator(acting_user=acting_user, space=locked_space)
    try:
        route = (
            IntegrationRouteAssociation.objects.select_for_update(no_key=True, of=("self",))
            .select_related("attachment__space", "bot", "stream")
            .get(id=route_id, attachment__space=locked_space, realm=locked_space.realm)
        )
    except IntegrationRouteAssociation.DoesNotExist:
        raise JsonableError(_("Invalid integration route ID"))
    if route.state == IntegrationRouteAssociation.State.DETACHED:
        return route
    route.state = IntegrationRouteAssociation.State.DETACHED
    route.detached_at = timezone_now()
    route.save(update_fields=["state", "detached_at", "date_updated"])
    _notify_space(locked_space)
    return route

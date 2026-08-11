from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.lib_spaces import get_space_data, space_projection_queryset, user_is_space_administrator
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    IntegrationRouteAssociation,
    Source,
    Space,
    SpaceAttachment,
    SpaceMembership,
)
from zerver.lib.exceptions import InvalidJSONError, JsonableError
from zerver.models.users import UserProfile, get_user_profile_by_id
from zerver.tornado.django_api import send_event_on_commit


def get_integration_route_data(route: IntegrationRouteAssociation) -> dict[str, object]:
    return {
        "id": route.id,
        "state": route.state,
        "bot_user_id": route.bot_id,
        "bot_name": route.bot.full_name,
        "stream_id": route.stream_id,
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
    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "update", "space": get_space_data(projected)},
        _member_ids(space),
    )


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

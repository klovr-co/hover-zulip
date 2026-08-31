from collections.abc import Iterable
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.lib_connectors import (
    connector_projection_queryset,
    connector_recipient_ids,
    get_connector_provider_name,
    user_can_manage_connector,
    validate_event_options,
)
from hover.models import Connector
from zerver.actions.create_user import do_create_user, notify_created_bot
from zerver.actions.user_settings import do_regenerate_api_key
from zerver.actions.users import do_deactivate_user
from zerver.lib.bot_config import set_bot_config
from zerver.lib.exceptions import InvalidJSONError, JsonableError
from zerver.lib.streams import access_stream_by_name
from zerver.lib.users import check_can_create_bot, validate_short_name_and_construct_bot_email
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def access_connector(user: UserProfile, connector_id: int) -> Connector:
    try:
        connector = connector_projection_queryset().get(id=connector_id, realm=user.realm)
    except Connector.DoesNotExist:
        raise JsonableError(_("Invalid connector ID."))
    if not user_can_manage_connector(user, connector):
        raise JsonableError(_("You do not have permission to manage this connector."))
    return connector


def notify_connector(connector: Connector, *, op: str) -> None:
    send_event_on_commit(
        connector.realm,
        {"type": "hover_connector", "op": op, "connector_id": connector.id},
        connector_recipient_ids(connector),
    )


def _clean_connector(connector: Connector) -> None:
    try:
        connector.full_clean()
    except ValidationError as exc:
        raise InvalidJSONError(str(exc))


def _ensure_active(connector: Connector) -> None:
    if connector.state == Connector.State.DISABLED:
        raise JsonableError(_("This connector is disabled."))


@transaction.atomic(durable=True)
def do_create_connector(
    *,
    acting_user: UserProfile,
    provider_key: str,
    name: str,
    destination_name: str,
    topic: str,
    event_options: Iterable[str],
) -> Connector:
    check_can_create_bot(acting_user, UserProfile.INCOMING_WEBHOOK_BOT)
    provider_name = get_connector_provider_name(provider_key)
    destination, _subscription = access_stream_by_name(acting_user, destination_name)
    normalized_topic = topic.strip()
    if len(normalized_topic) > Connector.MAX_TOPIC_LENGTH:
        raise JsonableError(_("Topic is too long."))
    validated_event_options = validate_event_options(provider_key, event_options)
    normalized_name = name.strip() or provider_name
    if len(normalized_name) > Connector.MAX_NAME_LENGTH:
        raise JsonableError(_("Data source names must contain 1 to 80 characters."))

    token = uuid4().hex[:12]
    _short_name, email = validate_short_name_and_construct_bot_email(
        f"hover-connector-{token}", acting_user.realm
    )
    bot = do_create_user(
        email=email,
        password=None,
        realm=acting_user.realm,
        full_name=f"{provider_name} connector {token[:4]}",
        bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        bot_owner=acting_user,
        default_sending_stream=destination,
        acting_user=acting_user,
    )
    set_bot_config(bot, "integration_id", "json" if provider_key == "rest_api" else provider_key)
    connector = Connector(
        realm=acting_user.realm,
        bot=bot,
        provider_key=provider_key,
        provider_name=provider_name,
        name=normalized_name,
        destination=destination,
        topic=normalized_topic,
        event_options=validated_event_options,
        created_by=acting_user,
        owner=acting_user,
    )
    _clean_connector(connector)
    connector.save()
    notify_created_bot(bot)
    notify_connector(connector, op="add")
    return connector


@transaction.atomic(durable=True)
def do_update_connector(
    connector: Connector,
    *,
    acting_user: UserProfile,
    name: str | None,
    destination_name: str | None,
    topic: str | None,
    event_options: Iterable[str] | None,
) -> Connector:
    _ensure_active(connector)
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name or len(normalized_name) > Connector.MAX_NAME_LENGTH:
            raise JsonableError(_("Data source names must contain 1 to 80 characters."))
        connector.name = normalized_name
    if destination_name is not None:
        destination, _subscription = access_stream_by_name(acting_user, destination_name)
        connector.destination = destination
    if topic is not None:
        normalized_topic = topic.strip()
        if len(normalized_topic) > Connector.MAX_TOPIC_LENGTH:
            raise JsonableError(_("Topic is too long."))
        connector.topic = normalized_topic
    if event_options is not None:
        connector.event_options = validate_event_options(connector.provider_key, event_options)
    _clean_connector(connector)
    connector.save()
    notify_connector(connector, op="update")
    return connector


@transaction.atomic(durable=True)
def do_reconcile_connector(
    connector: Connector,
    *,
    acting_user: UserProfile,
    provider_key: str,
    destination_name: str,
    topic: str,
    event_options: Iterable[str],
) -> Connector:
    connector.provider_key = provider_key
    connector.provider_name = get_connector_provider_name(provider_key)
    destination, _subscription = access_stream_by_name(acting_user, destination_name)
    connector.destination = destination
    connector.topic = topic.strip()
    if len(connector.topic) > Connector.MAX_TOPIC_LENGTH:
        raise JsonableError(_("Topic is too long."))
    connector.event_options = validate_event_options(provider_key, event_options)
    connector.state = Connector.State.ACTIVE
    connector.reconciliation_state = Connector.ReconciliationState.CANONICAL
    _clean_connector(connector)
    connector.save()
    set_bot_config(
        connector.bot,
        "integration_id",
        "json" if provider_key == "rest_api" else provider_key,
    )
    notify_connector(connector, op="update")
    return connector


def do_rotate_connector(connector: Connector, *, acting_user: UserProfile) -> Connector:
    _ensure_active(connector)
    if connector.reconciliation_state != Connector.ReconciliationState.CANONICAL:
        raise JsonableError(_("Reconcile this legacy connector before rotating its URL."))
    do_regenerate_api_key(connector.bot, acting_user)
    connector.bot.refresh_from_db(fields=["api_key"])
    connector.date_updated = timezone_now()
    connector.save(update_fields=["date_updated"])
    notify_connector(connector, op="update")
    return connector


@transaction.atomic(durable=True)
def do_disable_connector(connector: Connector, *, acting_user: UserProfile) -> Connector:
    if connector.state == Connector.State.DISABLED:
        return connector
    do_deactivate_user(connector.bot, acting_user=acting_user)
    connector.state = Connector.State.DISABLED
    connector.health_status = Connector.HealthStatus.UNKNOWN
    connector.save(update_fields=["state", "health_status", "date_updated"])
    notify_connector(connector, op="update")
    return connector


def record_connector_delivery(bot: UserProfile, *, successful: bool) -> None:
    try:
        connector = connector_projection_queryset().get(bot=bot, state=Connector.State.ACTIVE)
    except Connector.DoesNotExist:
        return
    delivered_at = timezone_now()
    connector.last_delivery_attempt = delivered_at
    if successful:
        connector.last_successful_delivery = delivered_at
        connector.last_delivery_status = Connector.LastDeliveryStatus.SUCCESS
        connector.health_status = Connector.HealthStatus.HEALTHY
    else:
        connector.last_delivery_status = Connector.LastDeliveryStatus.FAILURE
        connector.health_status = Connector.HealthStatus.DEGRADED
    connector.date_updated = delivered_at
    connector.save(
        update_fields=[
            "last_delivery_attempt",
            "last_successful_delivery",
            "last_delivery_status",
            "health_status",
            "date_updated",
        ]
    )
    notify_connector(connector, op="update")

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _

from hover.lib_connected_accounts import get_realm_administrator_ids
from hover.models import Connector
from zerver.lib.exceptions import JsonableError
from zerver.lib.integrations import (
    INCOMING_WEBHOOK_INTEGRATIONS,
    IncomingWebhookIntegration,
    get_all_event_types_for_integration,
)
from zerver.models.users import UserProfile

PROVIDER_DESCRIPTIONS = {
    "gitea": "Repository activity",
    "github": "Repository activity and deployment events",
    "github_actions": "Workflow runs and build status",
    "gitlab": "Projects, issues and pipelines",
    "slack_incoming": "Updates from any Slack-compatible service",
    "rest_api": "Internal tools and custom payloads",
}

INTEGRATIONS_BY_NAME = {
    integration.name: integration
    for integration in INCOMING_WEBHOOK_INTEGRATIONS
    if not integration.legacy
}


def get_connector_integration(provider_key: str) -> IncomingWebhookIntegration:
    integration_key = "json" if provider_key == "rest_api" else provider_key
    integration = INTEGRATIONS_BY_NAME.get(integration_key)
    if integration is None:
        raise JsonableError(_("Invalid connector provider."))
    return integration


def get_connector_provider_name(provider_key: str) -> str:
    if provider_key == "rest_api":
        return "REST API"
    return get_connector_integration(provider_key).display_name


def get_connector_provider_metadata(provider_key: str) -> dict[str, Any]:
    integration = get_connector_integration(provider_key)
    all_event_types = get_all_event_types_for_integration(integration)
    return {
        "key": provider_key,
        "name": get_connector_provider_name(provider_key),
        "logo_url": integration.logo_url,
        "description": PROVIDER_DESCRIPTIONS.get(
            provider_key, f"{integration.display_name} events and updates"
        ),
        "all_event_types": all_event_types,
        "supports_event_filters": all_event_types is not None
        and provider_key not in {"slack", "slack_incoming", "rest_api"},
        "setup_instructions_url": f"/integrations/doc/{integration.name}",
    }


def connector_projection_queryset() -> QuerySet[Connector]:
    return Connector.objects.select_related("bot", "destination", "owner", "realm")


def user_can_manage_connector(user: UserProfile, connector: Connector) -> bool:
    if user.realm_id != connector.realm_id:
        return False
    if user.is_realm_admin or connector.owner_id == user.id:
        return True
    destination = connector.destination
    if destination is None:
        return False
    space = getattr(destination, "hover_space", None)
    if space is None:
        return False
    return space.administrator_assignments.filter(user=user).exists()


def visible_connectors(user: UserProfile) -> QuerySet[Connector]:
    connectors = connector_projection_queryset().filter(realm=user.realm)
    if user.is_realm_admin:
        return connectors
    return connectors.filter(
        Q(owner=user) | Q(destination__hover_space__administrator_assignments__user=user)
    ).distinct()


def connector_recipient_ids(connector: Connector) -> list[int]:
    recipient_ids = get_realm_administrator_ids(connector.realm_id)
    if connector.owner_id is not None:
        recipient_ids.add(connector.owner_id)
    destination = connector.destination
    space = getattr(destination, "hover_space", None) if destination is not None else None
    if space is not None:
        recipient_ids.update(
            space.administrator_assignments.filter(user__is_active=True).values_list(
                "user_id", flat=True
            )
        )
    return sorted(recipient_ids)


def connector_webhook_url(connector: Connector) -> str:
    if (
        connector.reconciliation_state != Connector.ReconciliationState.CANONICAL
        or connector.destination is None
        or connector.state != Connector.State.ACTIVE
    ):
        raise JsonableError(_("This connector does not have an active webhook URL."))
    integration = get_connector_integration(connector.provider_key)
    params: dict[str, str] = {
        "api_key": connector.bot.api_key,
        "stream": str(connector.destination_id),
    }
    if connector.topic:
        params["topic"] = connector.topic
    if connector.event_options:
        import orjson

        params["only_events"] = orjson.dumps(connector.event_options).decode()
    return (
        f"{settings.EXTERNAL_URI_SCHEME}{connector.realm.host}/{integration.url}?"
        f"{urlencode(params)}"
    )


def connector_data(
    connector: Connector,
    *,
    viewer: UserProfile,
    include_url: bool = False,
) -> dict[str, Any]:
    provider_metadata = None
    if connector.provider_key != "legacy":
        provider_metadata = get_connector_provider_metadata(connector.provider_key)
    data: dict[str, Any] = {
        "id": connector.id,
        "name": connector.name or connector.provider_name,
        "provider_key": connector.provider_key,
        "provider_name": connector.provider_name,
        "provider_logo_url": provider_metadata["logo_url"] if provider_metadata else None,
        "setup_instructions_url": (
            provider_metadata["setup_instructions_url"] if provider_metadata else None
        ),
        "credential_identity_id": connector.bot_id,
        "destination": connector.destination.name if connector.destination is not None else None,
        "destination_id": connector.destination_id,
        "topic": connector.topic,
        "event_options": connector.event_options,
        "state": connector.state,
        "reconciliation_state": connector.reconciliation_state,
        "health_status": connector.health_status,
        "last_delivery_status": connector.last_delivery_status,
        "owner": connector.owner.full_name if connector.owner is not None else None,
        "owner_id": connector.owner_id,
        "is_owner": connector.owner_id == viewer.id,
        "can_manage": user_can_manage_connector(viewer, connector),
        "last_successful_delivery": (
            connector.last_successful_delivery.isoformat()
            if connector.last_successful_delivery
            else None
        ),
        "last_delivery_attempt": (
            connector.last_delivery_attempt.isoformat() if connector.last_delivery_attempt else None
        ),
        "date_updated": connector.date_updated.isoformat(),
    }
    if (
        include_url
        and connector.reconciliation_state == Connector.ReconciliationState.CANONICAL
        and connector.state == Connector.State.ACTIVE
    ):
        data["webhook_url"] = connector_webhook_url(connector)
    return data


def validate_event_options(provider_key: str, event_options: Iterable[str]) -> list[str]:
    metadata = get_connector_provider_metadata(provider_key)
    options = list(dict.fromkeys(event_options))
    supported_events = metadata["all_event_types"]
    if options and (
        not metadata["supports_event_filters"]
        or supported_events is None
        or not set(options).issubset(supported_events)
    ):
        raise JsonableError(_("Choose supported events for this connector."))
    return options

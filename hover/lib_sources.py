from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core import signing
from django.db.models import Prefetch, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.clawer_sync import MAX_DISCOVERY_LIMIT, ClawerSource, ClawerSync, ClawerSyncError
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    IntegrationRouteAssociation,
    Source,
    Space,
    SpaceAttachment,
)
from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.models.users import UserProfile

MAX_UPSTREAM_SCAN_PAGES = 100
DISCOVERY_CURSOR_SALT = "hover-source-discovery-v1"


@dataclass(frozen=True)
class HistoryBoundary:
    history_window: str
    history_timezone: str
    history_start_at: datetime
    custom_start_date: date | None


def attachment_queryset() -> Prefetch[str, QuerySet[SpaceAttachment], str]:
    return Prefetch(
        "attachments",
        queryset=SpaceAttachment.objects.filter(
            state__in=[SpaceAttachment.State.ACTIVE, SpaceAttachment.State.DETACHED]
        )
        .select_related("source", "source__account")
        .prefetch_related(
            Prefetch(
                "integration_routes",
                queryset=IntegrationRouteAssociation.objects.filter(
                    state=IntegrationRouteAssociation.State.ACTIVE
                )
                .select_related("bot", "stream")
                .order_by("id"),
            )
        )
        .order_by("source__display_name", "id"),
    )


def get_source_data(source: Source) -> dict[str, Any]:
    return {
        "id": source.id,
        "provider_key": source.provider_key,
        "provider_name": source.provider_name,
        "source_type": source.source_type,
        "display_name": source.display_name,
        "external_url": source.external_url,
        "supports_live_capture": source.supports_live_capture,
        "account_id": source.account_id,
        "account_display_name": source.account.display_name,
    }


def get_attachment_data(attachment: SpaceAttachment) -> dict[str, Any]:
    routes = [
        {
            "id": route.id,
            "state": route.state,
            "bot_user_id": route.bot_id,
            "bot_name": route.bot.full_name,
            "stream_id": route.stream_id,
            "live_since": route.live_since.isoformat(),
        }
        for route in attachment.integration_routes.all()
        if route.state == IntegrationRouteAssociation.State.ACTIVE
    ]
    return {
        "id": attachment.id,
        "state": attachment.state,
        "history_window": attachment.history_window,
        "history_timezone": attachment.history_timezone,
        "history_start_at": attachment.history_start_at.isoformat(),
        "custom_start_date": (
            attachment.custom_start_date.isoformat()
            if attachment.custom_start_date is not None
            else None
        ),
        "can_browse_records": (
            attachment.space.state == Space.State.LAUNCHED
            and attachment.state in [SpaceAttachment.State.ACTIVE, SpaceAttachment.State.DETACHED]
            and attachment.evidence_deleted_at is None
        ),
        "evidence_deleted": attachment.evidence_deleted_at is not None,
        "source": get_source_data(attachment.source),
        "integration_routes": routes,
    }


def get_space_attachment_data(space: Space) -> list[dict[str, Any]]:
    return [
        get_attachment_data(attachment)
        for attachment in space.attachments.all()
        if attachment.state in [SpaceAttachment.State.ACTIVE, SpaceAttachment.State.DETACHED]
    ]


def get_actor_grant(user_profile: UserProfile, account: ConnectedAccount) -> ConnectedAccountGrant:
    if (
        account.realm_id != user_profile.realm_id
        or account.approval_state != ConnectedAccount.ApprovalState.APPROVED
    ):
        raise JsonableError(_("This Connected Account is not available."))
    try:
        return ConnectedAccountGrant.objects.prefetch_related("selectors").get(
            account=account,
            user=user_profile,
            state=ConnectedAccountGrant.State.ACTIVE,
        )
    except ConnectedAccountGrant.DoesNotExist:
        raise JsonableError(_("This Connected Account is not available."))


def _allowed_whatsapp_refs(grant: ConnectedAccountGrant) -> set[str] | None:
    if grant.all_selectors:
        return None
    return set(
        grant.selectors.filter(selector_type="whatsapp_group").values_list("source_ref", flat=True)
    )


def _normalize_query(query: str | None) -> str:
    return " ".join((query or "").strip().split())


def _decode_cursor(
    cursor: str | None,
    *,
    user_profile: UserProfile,
    space: Space,
    account: ConnectedAccount,
    query: str,
) -> int:
    if cursor is None:
        return 0
    if len(cursor) > 1000:
        raise JsonableError(_("Invalid Source discovery cursor."))
    try:
        payload = signing.loads(cursor, salt=DISCOVERY_CURSOR_SALT, max_age=3600)
    except signing.BadSignature:
        raise JsonableError(_("Invalid Source discovery cursor."))
    if not isinstance(payload, dict):
        raise JsonableError(_("Invalid Source discovery cursor."))
    if set(payload) != {"v", "user_id", "space_id", "account_id", "query", "offset"}:
        raise JsonableError(_("Invalid Source discovery cursor."))
    if (
        payload["v"] != 1
        or payload["user_id"] != user_profile.id
        or payload["space_id"] != space.id
        or payload["account_id"] != account.id
        or payload["query"] != query
    ):
        raise JsonableError(_("Invalid Source discovery cursor."))
    offset = payload["offset"]
    if not isinstance(offset, int) or offset < 0:
        raise JsonableError(_("Invalid Source discovery cursor."))
    return offset


def _encode_cursor(
    offset: int,
    *,
    user_profile: UserProfile,
    space: Space,
    account: ConnectedAccount,
    query: str,
) -> str:
    return signing.dumps(
        {
            "v": 1,
            "user_id": user_profile.id,
            "space_id": space.id,
            "account_id": account.id,
            "query": query,
            "offset": offset,
        },
        salt=DISCOVERY_CURSOR_SALT,
        compress=True,
    )


def _collect_allowed_sources(
    *,
    user_profile: UserProfile,
    account: ConnectedAccount,
    grant: ConnectedAccountGrant,
    query: str,
    clawer_sync: ClawerSync,
) -> list[ClawerSource]:
    allowed_refs = _allowed_whatsapp_refs(grant)
    if allowed_refs == set():
        return []

    sources: list[ClawerSource] = []
    seen_refs: set[str] = set()
    upstream_cursor: str | None = None
    for _page_number in range(MAX_UPSTREAM_SCAN_PAGES):
        page = clawer_sync.discover_sources(
            realm_uuid=user_profile.realm.uuid,
            account_external_id=account.external_account_id,
            cursor=upstream_cursor,
            limit=MAX_DISCOVERY_LIMIT,
            query=query or None,
        )
        for source in page.sources:
            if source.provider != "whatsapp" or source.source_type != "group":
                continue
            if allowed_refs is not None and source.source_ref not in allowed_refs:
                continue
            if source.source_ref in seen_refs:
                continue
            seen_refs.add(source.source_ref)
            sources.append(source)
        if not page.has_more:
            return sources
        if not page.next_cursor or page.next_cursor == upstream_cursor:
            raise ClawerSyncError(
                error_code="invalid_upstream_contract",
                operation="source_discovery",
                http_status_code=502,
                retryable=False,
            )
        upstream_cursor = page.next_cursor

    # A partial page would make denied-source density observable, so bounded
    # exhaustion fails retryably instead.
    raise ClawerSyncError(
        error_code="clawer_unavailable",
        operation="source_discovery",
        http_status_code=503,
        retryable=True,
    )


def discover_allowed_sources(
    *,
    user_profile: UserProfile,
    space: Space,
    account: ConnectedAccount,
    cursor: str | None,
    limit: int,
    query: str | None,
    clawer_sync: ClawerSync,
) -> dict[str, Any]:
    grant = get_actor_grant(user_profile, account)
    normalized_query = _normalize_query(query)
    offset = _decode_cursor(
        cursor,
        user_profile=user_profile,
        space=space,
        account=account,
        query=normalized_query,
    )
    sources = _collect_allowed_sources(
        user_profile=user_profile,
        account=account,
        grant=grant,
        query=normalized_query,
        clawer_sync=clawer_sync,
    )
    page = sources[offset : offset + limit]
    next_offset = offset + len(page)
    return {
        "sources": [
            {
                "source_ref": source.source_ref,
                "provider_key": source.provider,
                "source_type": source.source_type,
                "display_name": source.display_name,
                "account_id": account.id,
                "account_display_name": account.display_name,
            }
            for source in page
        ],
        "next_cursor": _encode_cursor(
            next_offset,
            user_profile=user_profile,
            space=space,
            account=account,
            query=normalized_query,
        ),
        "has_more": next_offset < len(sources),
    }


def canonical_source_for_attachment(
    *,
    user_profile: UserProfile,
    account: ConnectedAccount,
    grant: ConnectedAccountGrant,
    source_ref: str,
    clawer_sync: ClawerSync,
) -> ClawerSource:
    allowed_refs = _allowed_whatsapp_refs(grant)
    if allowed_refs is not None and source_ref not in allowed_refs:
        raise ResourceNotFoundError(_("Source not found."))
    sources = _collect_allowed_sources(
        user_profile=user_profile,
        account=account,
        grant=grant,
        query="",
        clawer_sync=clawer_sync,
    )
    try:
        return next(source for source in sources if source.source_ref == source_ref)
    except StopIteration:
        raise ResourceNotFoundError(_("Source not found."))


def history_boundary(
    *,
    history_window: str,
    history_timezone: str,
    custom_start_date: date | None,
    now: datetime | None = None,
) -> HistoryBoundary:
    if not 1 <= len(history_timezone) <= SpaceAttachment.MAX_TIMEZONE_LENGTH:
        raise JsonableError(_("Invalid history timezone."))
    try:
        local_timezone = ZoneInfo(history_timezone)
    except (ValueError, ZoneInfoNotFoundError):
        raise JsonableError(_("Invalid history timezone."))

    current = (now or timezone_now()).astimezone(local_timezone)
    local_today = current.date()
    if history_window == SpaceAttachment.HistoryWindow.TODAY:
        if custom_start_date is not None:
            raise JsonableError(_("A custom date is only valid for a custom history window."))
        start_date = local_today
    elif history_window == SpaceAttachment.HistoryWindow.LAST_30_DAYS:
        if custom_start_date is not None:
            raise JsonableError(_("A custom date is only valid for a custom history window."))
        start_date = local_today - timedelta(days=30)
    elif history_window == SpaceAttachment.HistoryWindow.CUSTOM:
        if custom_start_date is None:
            raise JsonableError(_("Choose a custom history start date."))
        if custom_start_date > local_today:
            raise JsonableError(_("The history start date cannot be in the future."))
        start_date = custom_start_date
    else:
        raise JsonableError(_("Invalid history window."))

    local_midnight = datetime.combine(start_date, time.min, tzinfo=local_timezone)
    return HistoryBoundary(
        history_window=history_window,
        history_timezone=history_timezone,
        history_start_at=local_midnight.astimezone(timezone.utc),
        custom_start_date=custom_start_date,
    )

from __future__ import annotations

import hashlib
from typing import Any

from django.core import signing
from django.db.models import QuerySet
from django.utils.translation import gettext as _

from hover.clawer_sync import ClawerSync
from hover.models import Space, SpaceAttachment
from hover.source_record_contracts import ClawerSourceRecord
from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.models.users import UserProfile

SOURCE_RECORD_CURSOR_SALT = "hover-source-records-v1"
BROWSEABLE_ATTACHMENT_STATES = {
    SpaceAttachment.State.ACTIVE,
    SpaceAttachment.State.DETACHED,
}


def normalize_source_record_query(query: str | None) -> str:
    normalized = " ".join((query or "").split())
    if len(normalized) > 100:
        raise JsonableError(_("Search terms must be 100 characters or fewer."))
    return normalized


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()


def _authorized_attachments(user_profile: UserProfile) -> QuerySet[SpaceAttachment]:
    return SpaceAttachment.objects.select_related("space", "source", "source__account").filter(
        realm=user_profile.realm,
        space__state=Space.State.LAUNCHED,
        state__in=BROWSEABLE_ATTACHMENT_STATES,
        space__memberships__user=user_profile,
        space__memberships__user__is_active=True,
    )


def access_attachment_for_records(
    user_profile: UserProfile, *, space_id: int, attachment_id: int
) -> SpaceAttachment:
    if not user_profile.is_active or user_profile.is_guest or user_profile.is_bot:
        raise ResourceNotFoundError(_("Source not found."))
    try:
        return _authorized_attachments(user_profile).get(
            id=attachment_id,
            space_id=space_id,
        )
    except SpaceAttachment.DoesNotExist:
        raise ResourceNotFoundError(_("Source not found."))


def _decode_cursor(
    cursor: str | None,
    *,
    user_profile: UserProfile,
    attachment: SpaceAttachment,
    query: str,
) -> str | None:
    if cursor is None:
        return None
    if len(cursor) > 20_000:
        raise JsonableError(_("Invalid Source record cursor."))
    try:
        payload = signing.loads(cursor, salt=SOURCE_RECORD_CURSOR_SALT, max_age=86_400)
    except signing.BadSignature:
        raise JsonableError(_("Invalid Source record cursor."))
    expected = {
        "v",
        "user_id",
        "space_id",
        "attachment_id",
        "history_start_at",
        "query_hash",
        "upstream_cursor",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise JsonableError(_("Invalid Source record cursor."))
    upstream_cursor = payload["upstream_cursor"]
    if (
        payload["v"] != 1
        or payload["user_id"] != user_profile.id
        or payload["space_id"] != attachment.space_id
        or payload["attachment_id"] != attachment.id
        or payload["history_start_at"] != attachment.history_start_at.isoformat()
        or payload["query_hash"] != _query_hash(query)
        or not isinstance(upstream_cursor, str)
        or not 1 <= len(upstream_cursor) <= 10_000
    ):
        raise JsonableError(_("Invalid Source record cursor."))
    return upstream_cursor


def _encode_cursor(
    upstream_cursor: str,
    *,
    user_profile: UserProfile,
    attachment: SpaceAttachment,
    query: str,
) -> str:
    return signing.dumps(
        {
            "v": 1,
            "user_id": user_profile.id,
            "space_id": attachment.space_id,
            "attachment_id": attachment.id,
            "history_start_at": attachment.history_start_at.isoformat(),
            "query_hash": _query_hash(query),
            "upstream_cursor": upstream_cursor,
        },
        salt=SOURCE_RECORD_CURSOR_SALT,
        compress=True,
    )


def _browser_record(record: ClawerSourceRecord) -> dict[str, Any]:
    return {
        "id": record.record_ref,
        "sender_display_name": record.sender.display_name,
        "timestamp": record.timestamp.isoformat(),
        "content": record.content.model_dump(mode="json"),
        "media": record.media.model_dump(mode="json") if record.media is not None else None,
        "reply_context": (
            {
                "sender_display_name": record.reply_context.sender_display_name,
                "timestamp": record.reply_context.timestamp.isoformat(),
                "excerpt": record.reply_context.excerpt,
            }
            if record.reply_context is not None
            else None
        ),
    }


def browse_attachment_records(
    *,
    user_profile: UserProfile,
    space_id: int,
    attachment_id: int,
    cursor: str | None,
    limit: int,
    query: str | None,
    clawer_sync: ClawerSync,
) -> dict[str, Any]:
    attachment = access_attachment_for_records(
        user_profile, space_id=space_id, attachment_id=attachment_id
    )
    normalized_query = normalize_source_record_query(query)
    upstream_cursor = _decode_cursor(
        cursor,
        user_profile=user_profile,
        attachment=attachment,
        query=normalized_query,
    )
    source = attachment.source
    page = clawer_sync.browse_source_records(
        realm_uuid=user_profile.realm.uuid,
        account_external_id=source.account.external_account_id,
        source_ref=source.external_ref,
        start_at=attachment.history_start_at.isoformat(),
        cursor=upstream_cursor,
        limit=limit,
        query=normalized_query or None,
    )

    # The remote call deliberately runs without a transaction. Re-fetching here
    # makes membership removal or attachment deletion win an in-flight race.
    current = access_attachment_for_records(
        user_profile, space_id=space_id, attachment_id=attachment_id
    )
    if (
        current.history_start_at != attachment.history_start_at
        or current.source_id != attachment.source_id
    ):
        raise ResourceNotFoundError(_("Source not found."))

    return {
        "source": {
            "attachment_id": current.id,
            "display_name": current.source.display_name,
            "provider_key": current.source.provider_key,
            "source_type": current.source.source_type,
            "account_display_name": current.source.account.display_name,
            "state": current.state,
        },
        "records": [_browser_record(record) for record in page.records],
        "next_cursor": (
            _encode_cursor(
                page.next_cursor,
                user_profile=user_profile,
                attachment=current,
                query=normalized_query,
            )
            if page.has_more
            else ""
        ),
        "has_more": page.has_more,
    }

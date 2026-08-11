from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

import orjson
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from hover.clawer_sync import ClawerSync, ClawerSyncError
from hover.models import (
    ConnectedAccount,
    GeneratedItem,
    PersonalEdition,
    PersonalEditionSyncState,
    SourceParticipantBinding,
    SpaceAttachment,
    SpaceMembership,
)
from hover.publication_contracts import ClawerPublication, DigestPayload, PersonalDigestItem
from zerver.lib.url_encoding import stream_message_url
from zerver.models.users import UserProfile

PERSONAL_EDITION_SYNC_LIMIT = 50
PERSONAL_EDITION_SYNC_MAX_PAGES = 100
PERSONAL_EDITION_HISTORY_DAYS = 31


class PersonalEditionError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _publication_hash(publication: ClawerPublication) -> str:
    data = publication.model_dump(mode="json")
    if publication.schema_version == "1.0":
        data.pop("disputed_details", None)
    return hashlib.sha256(orjson.dumps(data, option=orjson.OPT_SORT_KEYS)).hexdigest()


def _verified_personal_streams(
    user_profile: UserProfile,
) -> list[tuple[ConnectedAccount, str]]:
    if (
        not user_profile.realm.hover_enabled
        or not user_profile.is_active
        or user_profile.is_guest
        or user_profile.is_bot
    ):
        return []
    bindings = list(
        SourceParticipantBinding.objects.select_related("source__account")
        .filter(
            realm=user_profile.realm,
            user=user_profile,
            source__account__approval_state=ConnectedAccount.ApprovalState.APPROVED,
            source__space_attachments__state=SpaceAttachment.State.ACTIVE,
            source__space_attachments__space__state="launched",
            source__space_attachments__space__memberships__user=user_profile,
            source__space_attachments__space__memberships__role__in=[
                SpaceMembership.Role.CONTRIBUTOR,
                SpaceMembership.Role.SUBSCRIBER,
            ],
        )
        .order_by("source__account_id", "participant_ref", "id")
        .distinct()
    )
    streams: dict[tuple[int, str], tuple[ConnectedAccount, str]] = {}
    for binding in bindings:
        streams[(binding.source.account_id, binding.participant_ref)] = (
            binding.source.account,
            binding.participant_ref,
        )
    return list(streams.values())


def _accept_publication(
    *,
    user_profile: UserProfile,
    account: ConnectedAccount,
    teammate_ref: str,
    publication: ClawerPublication,
) -> None:
    payload = publication.payload
    if not isinstance(payload, DigestPayload) or payload.personal is None:
        raise PersonalEditionError("invalid_personal_edition_contract")
    personal = payload.personal
    expected_producer = (
        "personal_morning_brief" if personal.edition == "morning" else "personal_eod_roundup"
    )
    if personal.teammate_ref != teammate_ref or publication.producer_key != expected_producer:
        raise PersonalEditionError("invalid_personal_edition_contract")

    envelope_hash = _publication_hash(publication)
    existing = (
        PersonalEdition.objects.filter(account=account)
        .filter(
            Q(publication_id=publication.publication_id)
            | Q(idempotency_key=publication.idempotency_key)
        )
        .first()
    )
    if existing is not None:
        if (
            existing.user_id != user_profile.id
            or existing.teammate_ref != teammate_ref
            or existing.publication_id != publication.publication_id
            or existing.idempotency_key != publication.idempotency_key
            or existing.publication_envelope_hash != envelope_hash
        ):
            raise PersonalEditionError("personal_edition_identity_conflict")
        return

    PersonalEdition.objects.create(
        realm=user_profile.realm,
        user=user_profile,
        account=account,
        teammate_ref=teammate_ref,
        publication_id=publication.publication_id,
        idempotency_key=publication.idempotency_key,
        publication_envelope_hash=envelope_hash,
        source_ref=publication.source_ref,
        edition=personal.edition,
        payload=payload.model_dump(mode="json"),
        evidence_refs=publication.evidence_refs,
        covered_start_at=publication.covered_period.start,
        covered_end_at=publication.covered_period.end,
        producing_version=publication.producing_version,
        generated_at=publication.generated_at,
        published_at=publication.published_at,
    )


def _sync_personal_stream(
    *,
    user_profile: UserProfile,
    account: ConnectedAccount,
    teammate_ref: str,
    clawer_sync: ClawerSync,
) -> None:
    state, _ = PersonalEditionSyncState.objects.get_or_create(
        realm=user_profile.realm,
        user=user_profile,
        account=account,
        teammate_ref=teammate_ref,
        defaults={"start_at": timezone.now() - timedelta(days=PERSONAL_EDITION_HISTORY_DAYS)},
    )
    requested_cursor = state.cursor
    seen_cursors = {requested_cursor}
    for _page_number in range(PERSONAL_EDITION_SYNC_MAX_PAGES):
        page = clawer_sync.sync_personal_editions(
            realm_uuid=user_profile.realm.uuid,
            account_external_id=account.external_account_id,
            teammate_ref=teammate_ref,
            cursor=requested_cursor or None,
            limit=PERSONAL_EDITION_SYNC_LIMIT,
            start_at=state.start_at.isoformat(),
        )
        if page.has_more and page.next_cursor in seen_cursors:
            raise PersonalEditionError("invalid_personal_edition_contract")
        with transaction.atomic(durable=True):
            locked = PersonalEditionSyncState.objects.select_for_update(no_key=False).get(
                id=state.id
            )
            if locked.cursor != requested_cursor:
                return
            for publication in page.publications:
                _accept_publication(
                    user_profile=user_profile,
                    account=account,
                    teammate_ref=teammate_ref,
                    publication=publication,
                )
            locked.cursor = page.next_cursor
            locked.last_sync_at = timezone.now()
            locked.last_error = ""
            locked.sync_failures = 0
            locked.save(
                update_fields=[
                    "cursor",
                    "last_sync_at",
                    "last_error",
                    "sync_failures",
                    "date_updated",
                ]
            )
        if not page.has_more:
            return
        requested_cursor = page.next_cursor
        seen_cursors.add(requested_cursor)

    # Preserve the cursor committed for the last complete page so a later
    # request can resume without replaying the bounded scan from the start.
    raise PersonalEditionError("personal_edition_sync_incomplete")


def sync_personal_editions(
    *, user_profile: UserProfile, clawer_sync: ClawerSync
) -> tuple[str, list[str]]:
    errors: list[str] = []
    streams = _verified_personal_streams(user_profile)
    for account, teammate_ref in streams:
        try:
            _sync_personal_stream(
                user_profile=user_profile,
                account=account,
                teammate_ref=teammate_ref,
                clawer_sync=clawer_sync,
            )
        except (ClawerSyncError, PersonalEditionError) as error:
            error_code = error.error_code if isinstance(error, ClawerSyncError) else error.code
            errors.append(error_code)
            PersonalEditionSyncState.objects.filter(
                user=user_profile,
                account=account,
                teammate_ref=teammate_ref,
            ).update(
                last_error=error_code[:64],
                sync_failures=F("sync_failures") + 1,
            )
    if errors:
        return "degraded", errors
    if not streams:
        return "empty", []
    return "current", []


def _authorized_updates(
    *, user_profile: UserProfile, edition: PersonalEdition
) -> dict[str, GeneratedItem]:
    payload = DigestPayload.model_validate(edition.payload)
    assert payload.personal is not None
    refs = payload.personal.operational_publication_ids
    items = (
        GeneratedItem.objects.select_related(
            "message",
            "message__recipient",
            "attachment__space",
            "attachment__space__stream",
        )
        .filter(
            realm=user_profile.realm,
            publication_id__in=refs,
            attachment__isnull=False,
            attachment__state=SpaceAttachment.State.ACTIVE,
            attachment__source__account=edition.account,
            attachment__space__state="launched",
            attachment__space__memberships__user=user_profile,
            attachment__space__memberships__role__in=[
                SpaceMembership.Role.CONTRIBUTOR,
                SpaceMembership.Role.SUBSCRIBER,
            ],
        )
        .prefetch_related("evidence_links")
        .distinct()
    )
    return {item.publication_id: item for item in items if item.publication_id is not None}


def _project_item(
    *,
    item: PersonalDigestItem,
    authorized_updates: dict[str, GeneratedItem],
    user_profile: UserProfile,
) -> dict[str, Any] | None:
    refs = item.operational_publication_ids
    if not refs or any(ref not in authorized_updates for ref in refs):
        return None
    update = authorized_updates[refs[0]]
    assert update.attachment is not None
    space = update.attachment.space
    assert space.stream is not None
    message = update.message
    evidence_available = bool(update.evidence_links.all())
    return {
        "title": item.title,
        "detail": item.detail,
        "update": {
            "message_id": message.id,
            "space_name": space.name,
            "topic": message.topic_name(),
            "url": stream_message_url(
                realm=user_profile.realm,
                message={
                    "id": message.id,
                    "stream_id": space.stream_id,
                    "display_recipient": space.stream.name,
                    "subject": message.topic_name(),
                },
            ),
            "evidence_url": (
                f"/json/hover/spaces/{space.id}/generated-items/{update.id}/evidence"
                if evidence_available
                else None
            ),
        },
    }


def _project_personal_edition(
    *, user_profile: UserProfile, edition: PersonalEdition
) -> dict[str, Any]:
    payload = DigestPayload.model_validate(edition.payload)
    personal = payload.personal
    assert personal is not None
    authorized = _authorized_updates(user_profile=user_profile, edition=edition)
    section_items: dict[str, list[PersonalDigestItem]]
    if personal.edition == "morning":
        assert personal.morning is not None
        section_items = {
            "urgency": personal.morning.urgency,
            "unresolved_carryover": personal.morning.unresolved_carryover,
            "guidance": personal.morning.guidance,
        }
    else:
        assert personal.end_of_day is not None
        section_items = {
            "meaningful_movement": personal.end_of_day.meaningful_movement,
            "completed_work": personal.end_of_day.completed_work,
            "carryover": personal.end_of_day.carryover,
            "delegated_dependencies": personal.end_of_day.delegated_dependencies,
            "tomorrow_preview": personal.end_of_day.tomorrow_preview,
        }
    sections: dict[str, list[dict[str, Any]]] = {}
    for key, items in section_items.items():
        sections[key] = []
        for item in items:
            projected = _project_item(
                item=item,
                authorized_updates=authorized,
                user_profile=user_profile,
            )
            if projected is not None:
                sections[key].append(projected)
    all_clear = (
        personal.edition == "morning"
        and personal.morning is not None
        and bool(personal.morning.all_clear_context)
        and bool(personal.operational_publication_ids)
        and all(ref in authorized for ref in personal.operational_publication_ids)
    )
    return {
        "edition": personal.edition,
        "title": payload.title,
        "covered_end": edition.covered_end_at.isoformat(),
        "published_at": edition.published_at.isoformat(),
        "sections": sections,
        "all_clear": all_clear,
    }


def get_personal_editions_for_user(*, user_profile: UserProfile) -> dict[str, Any]:
    if (
        not user_profile.realm.hover_enabled
        or not user_profile.is_active
        or user_profile.is_guest
        or user_profile.is_bot
    ):
        return {"morning": None, "end_of_day": None}
    verified_streams = {
        (account.id, teammate_ref)
        for account, teammate_ref in _verified_personal_streams(user_profile)
    }
    if not verified_streams:
        return {"morning": None, "end_of_day": None}
    stream_filter = Q()
    for account_id, teammate_ref in verified_streams:
        stream_filter |= Q(account_id=account_id, teammate_ref=teammate_ref)
    editions: dict[str, Any] = {"morning": None, "end_of_day": None}
    for edition_kind in editions:
        edition = (
            PersonalEdition.objects.filter(
                stream_filter,
                user=user_profile,
                edition=edition_kind,
            )
            .select_related("account")
            .order_by("-covered_end_at", "-id")
            .first()
        )
        if edition is not None:
            editions[edition_kind] = _project_personal_edition(
                user_profile=user_profile, edition=edition
            )
    return editions

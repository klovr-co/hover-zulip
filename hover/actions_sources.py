from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.clawer_sync import ClawerSource, ClawerSync
from hover.lib_connected_accounts import access_connected_account
from hover.lib_sources import (
    HistoryBoundary,
    canonical_source_for_attachment,
    get_actor_grant,
    history_boundary,
)
from hover.lib_spaces import get_space_data, user_is_space_administrator
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    DisputedEvidenceLink,
    EvidenceLink,
    IntegrationMessageProvenance,
    IntegrationRouteAssociation,
    Source,
    SourceCapability,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
)
from hover.participant_selector_reconciliation import schedule_participant_selector_reconciliation
from zerver.lib.exceptions import ErrorCode, InvalidJSONError, JsonableError
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


class HistoryWindowConflictError(JsonableError):
    code = ErrorCode.HISTORY_WINDOW_CONFLICT
    http_status_code = 409
    data_fields = ["error_code"]

    def __init__(self) -> None:
        super().__init__(_("This Source is already attached with a different history window."))
        self.error_code = "history_window_conflict"


def _space_administrator_ids(space: Space) -> list[int]:
    return list(
        SpaceAdministrator.objects.filter(
            space=space,
            user__is_active=True,
            user__is_bot=False,
        ).values_list("user_id", flat=True)
    )


def _same_semantic_window(attachment: SpaceAttachment, boundary: HistoryBoundary) -> bool:
    return (
        attachment.history_window == boundary.history_window
        and attachment.history_timezone == boundary.history_timezone
        and attachment.custom_start_date == boundary.custom_start_date
    )


def _existing_attachment(
    *,
    space: Space,
    account: ConnectedAccount,
    source_ref: str,
) -> SpaceAttachment | None:
    return (
        SpaceAttachment.objects.select_related("source", "source__account")
        .filter(
            space=space,
            source__account=account,
            source__external_ref=source_ref,
        )
        .first()
    )


def _assert_local_authorization(
    *,
    acting_user: UserProfile,
    space: Space,
    account: ConnectedAccount,
) -> ConnectedAccountGrant:
    _assert_space_administrator(acting_user=acting_user, space=space)
    return get_actor_grant(acting_user, account)


def _assert_space_administrator(*, acting_user: UserProfile, space: Space) -> None:
    if acting_user.realm_id != space.realm_id or not user_is_space_administrator(
        acting_user, space
    ):
        raise JsonableError(_("Invalid Space ID"))


def _attach_canonical_source(
    *,
    acting_user: UserProfile,
    space: Space,
    account: ConnectedAccount,
    canonical_source: ClawerSource,
    boundary: HistoryBoundary,
) -> tuple[SpaceAttachment, bool]:
    with transaction.atomic(durable=True):
        locked_space = Space.objects.select_for_update(no_key=True).get(
            id=space.id, realm=space.realm
        )
        if locked_space.state != Space.State.SETUP:
            raise JsonableError(_("Invalid Space ID"))
        locked_account = ConnectedAccount.objects.select_for_update(no_key=True).get(
            id=account.id, realm=space.realm
        )
        _assert_local_authorization(
            acting_user=acting_user,
            space=locked_space,
            account=locked_account,
        )
        source, source_created = Source.objects.get_or_create(
            realm=locked_space.realm,
            account=locked_account,
            external_ref=canonical_source.source_ref,
            defaults={
                "adapter_key": "clawer_sync",
                "provider_key": canonical_source.provider,
                "provider_name": locked_account.provider_name,
                "source_type": canonical_source.source_type,
                "display_name": canonical_source.display_name,
            },
        )
        if source_created:
            try:
                source.full_clean()
            except ValidationError as exc:
                raise InvalidJSONError(str(exc))
            SourceCapability.objects.create(source=source, capability="message_history")
        elif (
            source.provider_key != canonical_source.provider
            or source.source_type != canonical_source.source_type
        ):
            raise JsonableError(_("The connected service returned inconsistent Source metadata."))
        elif source.display_name != canonical_source.display_name:
            source.display_name = canonical_source.display_name
            source.save(update_fields=["display_name", "date_updated"])

        attachment = (
            SpaceAttachment.objects.select_for_update(no_key=True, of=("self",))
            .select_related("source", "source__account")
            .filter(space=locked_space, source=source)
            .first()
        )
        if attachment is not None:
            if not _same_semantic_window(attachment, boundary):
                raise HistoryWindowConflictError
            if attachment.state == SpaceAttachment.State.DETACHED:
                if attachment.evidence_deleted_at is not None:
                    raise JsonableError(
                        _("Permanently deleted Source evidence cannot be reattached.")
                    )
                attachment.state = SpaceAttachment.State.ACTIVE
                attachment.detached_at = None
                attachment.detached_by = None
                attachment.next_publication_sync_at = timezone_now()
                attachment.save(
                    update_fields=[
                        "state",
                        "detached_at",
                        "detached_by",
                        "next_publication_sync_at",
                        "date_updated",
                    ]
                )
                schedule_participant_selector_reconciliation(locked_account.id)
            return attachment, False

        attachment = SpaceAttachment.objects.create(
            realm=locked_space.realm,
            space=locked_space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=boundary.history_window,
            history_timezone=boundary.history_timezone,
            history_start_at=boundary.history_start_at,
            custom_start_date=boundary.custom_start_date,
            attached_by=acting_user,
        )
        RealmAuditLog.objects.create(
            realm=attachment.realm,
            acting_user=acting_user,
            event_type=AuditLogEventType.HOVER_SOURCE_ATTACHED,
            event_time=attachment.date_updated,
            extra_data={
                "space_id": attachment.space_id,
                "source_id": attachment.source_id,
                "account_id": attachment.source.account_id,
                "attachment_id": attachment.id,
                "history_window": attachment.history_window,
            },
        )
        # Refresh the server projection with only active, sanitized Sources.
        projected_space = (
            Space.objects.select_related("category", "created_by", "stream")
            .prefetch_related("attachments__source__account")
            .get(id=attachment.space_id)
        )
        send_event_on_commit(
            attachment.realm,
            {"type": "hover_space", "op": "update", "space": get_space_data(projected_space)},
            _space_administrator_ids(locked_space),
        )
        schedule_participant_selector_reconciliation(locked_account.id)
        return attachment, True


def do_attach_source(
    *,
    acting_user: UserProfile,
    space: Space,
    account_id: int,
    source_ref: str,
    history_window: str,
    history_timezone: str,
    custom_start_date: date | None,
    clawer_sync: ClawerSync,
    now: datetime | None = None,
) -> tuple[SpaceAttachment, bool]:
    # Check the Space capability before resolving the account ID so a future
    # post-launch member cannot use this endpoint as an account oracle.
    _assert_space_administrator(acting_user=acting_user, space=space)
    account = access_connected_account(acting_user, account_id)
    grant = _assert_local_authorization(
        acting_user=acting_user,
        space=space,
        account=account,
    )
    boundary = history_boundary(
        history_window=history_window,
        history_timezone=history_timezone,
        custom_start_date=custom_start_date,
        now=now,
    )
    existing = _existing_attachment(space=space, account=account, source_ref=source_ref)
    if existing is not None:
        if not _same_semantic_window(existing, boundary):
            raise HistoryWindowConflictError
        if existing.state == SpaceAttachment.State.ACTIVE:
            return existing, False
        if existing.evidence_deleted_at is not None:
            raise JsonableError(_("Permanently deleted Source evidence cannot be reattached."))

    canonical_source = canonical_source_for_attachment(
        user_profile=acting_user,
        account=account,
        grant=grant,
        source_ref=source_ref,
        clawer_sync=clawer_sync,
    )
    # Attachment persists the exact UTC boundary that H#9 will pass as
    # Studio's `start_at`. H#7 deliberately does not call the publication
    # sync endpoint: consuming a page here would discard its cursor and data.
    return _attach_canonical_source(
        acting_user=acting_user,
        space=space,
        account=account,
        canonical_source=canonical_source,
        boundary=boundary,
    )


@transaction.atomic(durable=True)
def do_detach_source(
    *, acting_user: UserProfile, space: Space, attachment_id: int
) -> tuple[SpaceAttachment, bool]:
    locked_space = Space.objects.select_for_update(no_key=True).get(id=space.id)
    _assert_space_administrator(acting_user=acting_user, space=locked_space)
    try:
        attachment = (
            SpaceAttachment.objects.select_for_update(no_key=True, of=("self",))
            .select_related("source__account")
            .get(id=attachment_id, space=locked_space)
        )
    except SpaceAttachment.DoesNotExist:
        raise JsonableError(_("Invalid Space attachment."))
    get_actor_grant(acting_user, attachment.source.account)
    if attachment.state == SpaceAttachment.State.DETACHED:
        IntegrationRouteAssociation.objects.filter(
            attachment=attachment,
            state=IntegrationRouteAssociation.State.ACTIVE,
        ).update(
            state=IntegrationRouteAssociation.State.DETACHED,
            detached_at=attachment.detached_at,
            date_updated=attachment.detached_at,
        )
        from hover.actions_modules import pause_installations_for_attachment

        pause_installations_for_attachment(attachment)
        if (
            attachment.publication_sync_state != SpaceAttachment.PublicationSyncState.IDLE
            or attachment.publication_sync_lease_token is not None
            or attachment.publication_sync_lease_expires_at is not None
            or attachment.next_publication_sync_at is not None
        ):
            attachment.publication_sync_state = SpaceAttachment.PublicationSyncState.IDLE
            attachment.publication_sync_lease_token = None
            attachment.publication_sync_lease_expires_at = None
            attachment.next_publication_sync_at = None
            attachment.save(
                update_fields=[
                    "publication_sync_state",
                    "publication_sync_lease_token",
                    "publication_sync_lease_expires_at",
                    "next_publication_sync_at",
                    "date_updated",
                ]
            )
        return attachment, False
    attachment.state = SpaceAttachment.State.DETACHED
    attachment.detached_at = timezone_now()
    attachment.detached_by = acting_user
    attachment.publication_sync_state = SpaceAttachment.PublicationSyncState.IDLE
    attachment.publication_sync_lease_token = None
    attachment.publication_sync_lease_expires_at = None
    attachment.next_publication_sync_at = None
    attachment.save(
        update_fields=[
            "state",
            "detached_at",
            "detached_by",
            "publication_sync_state",
            "publication_sync_lease_token",
            "publication_sync_lease_expires_at",
            "next_publication_sync_at",
            "date_updated",
        ]
    )
    IntegrationRouteAssociation.objects.filter(
        attachment=attachment,
        state=IntegrationRouteAssociation.State.ACTIVE,
    ).update(
        state=IntegrationRouteAssociation.State.DETACHED,
        detached_at=attachment.detached_at,
        date_updated=attachment.detached_at,
    )
    from hover.actions_modules import pause_installations_for_attachment

    pause_installations_for_attachment(attachment)
    RealmAuditLog.objects.create(
        realm=attachment.realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.HOVER_SOURCE_DETACHED,
        event_time=attachment.detached_at,
        extra_data={
            "space_id": attachment.space_id,
            "source_id": attachment.source_id,
            "account_id": attachment.source.account_id,
            "attachment_id": attachment.id,
        },
    )
    projected_space = Space.objects.get(id=locked_space.id)
    send_event_on_commit(
        locked_space.realm,
        {"type": "hover_space", "op": "update", "space": get_space_data(projected_space)},
        (
            _space_administrator_ids(locked_space)
            if locked_space.state == Space.State.SETUP
            else list(
                SpaceMembership.objects.filter(
                    space=locked_space, user__is_active=True
                ).values_list("user_id", flat=True)
            )
        ),
    )
    schedule_participant_selector_reconciliation(attachment.source.account_id)
    return attachment, True


@transaction.atomic(durable=True)
def do_delete_source_evidence(
    *,
    acting_user: UserProfile,
    space: Space,
    attachment_id: int,
    confirmation: str,
) -> tuple[SpaceAttachment, bool, int]:
    """Permanently remove retained evidence through an explicit admin-only action."""

    locked_space = Space.objects.select_for_update(no_key=True).get(id=space.id)
    if acting_user.realm_id != locked_space.realm_id or not acting_user.is_realm_admin:
        raise JsonableError(_("Only an Organization Admin may permanently delete evidence."))
    try:
        attachment = (
            SpaceAttachment.objects.select_for_update(no_key=True, of=("self",))
            .select_related("source__account")
            .get(id=attachment_id, space=locked_space)
        )
    except SpaceAttachment.DoesNotExist:
        raise JsonableError(_("Invalid Space attachment."))
    if attachment.state != SpaceAttachment.State.DETACHED:
        raise JsonableError(_("Detach this Source before permanently deleting its evidence."))
    expected_confirmation = f"DELETE {attachment.source.display_name}"
    if confirmation != expected_confirmation:
        raise JsonableError(_("Evidence deletion confirmation did not match."))
    if attachment.evidence_deleted_at is not None:
        return attachment, False, 0

    evidence_links = EvidenceLink.objects.filter(generated_item__attachment=attachment)
    evidence_link_ids = list(evidence_links.values_list("id", flat=True))
    if evidence_link_ids:
        DisputedEvidenceLink.objects.filter(evidence_link_id__in=evidence_link_ids).delete()
    deleted_count = evidence_links.count()
    evidence_links.delete()
    IntegrationMessageProvenance.objects.filter(attachment=attachment).delete()
    attachment.evidence_deleted_at = timezone_now()
    attachment.evidence_deleted_by = acting_user
    attachment.save(update_fields=["evidence_deleted_at", "evidence_deleted_by", "date_updated"])
    RealmAuditLog.objects.create(
        realm=attachment.realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.HOVER_SOURCE_EVIDENCE_DELETED,
        event_time=attachment.evidence_deleted_at,
        extra_data={
            "space_id": attachment.space_id,
            "source_id": attachment.source_id,
            "account_id": attachment.source.account_id,
            "attachment_id": attachment.id,
            "evidence_link_count": deleted_count,
        },
    )
    projected_space = Space.objects.get(id=locked_space.id)
    send_event_on_commit(
        locked_space.realm,
        {"type": "hover_space", "op": "update", "space": get_space_data(projected_space)},
        list(
            SpaceMembership.objects.filter(space=locked_space, user__is_active=True).values_list(
                "user_id", flat=True
            )
        ),
    )
    return attachment, True, deleted_count

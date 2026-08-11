from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from hover.clawer_sync import MAX_PARTICIPANT_SELECTORS, ClawerSync, ClawerSyncError
from hover.models import (
    ConnectedAccount,
    ParticipantSelectorReconciliation,
    SourceParticipantBinding,
    SpaceAttachment,
    SpaceMembership,
)
from zerver.models.users import UserProfile

PARTICIPANT_RECONCILIATION_LEASE_SECONDS = 300


@dataclass(frozen=True)
class ParticipantReconciliationResult:
    account_id: int
    participant_count: int
    success: bool
    current: bool = False
    error_code: str = ""


@dataclass(frozen=True)
class ClaimedParticipantReconciliation:
    reconciliation_id: int
    generation: int
    lease_token: UUID
    realm_uuid: UUID
    account_external_id: UUID
    account_id: int
    participant_refs: list[str]


def desired_participant_refs(account: ConnectedAccount) -> list[str]:
    if account.approval_state != ConnectedAccount.ApprovalState.APPROVED:
        return []
    return list(
        SourceParticipantBinding.objects.filter(
            realm=account.realm,
            source__account=account,
            user__is_active=True,
            user__is_bot=False,
            source__space_attachments__state=SpaceAttachment.State.ACTIVE,
            source__space_attachments__space__state="launched",
            source__space_attachments__space__memberships__user_id=F("user_id"),
            source__space_attachments__space__memberships__role__in=[
                SpaceMembership.Role.CONTRIBUTOR,
                SpaceMembership.Role.SUBSCRIBER,
            ],
        )
        .exclude(user__role=UserProfile.ROLE_GUEST)
        .order_by("participant_ref")
        .values_list("participant_ref", flat=True)
        .distinct()
    )


def schedule_participant_selector_reconciliation(account_id: int) -> None:
    account = (
        ConnectedAccount.objects.only("id", "realm_id")
        .filter(
            id=account_id,
            connection_kind=ConnectedAccount.ConnectionKind.REMOTE_STUDIO,
        )
        .first()
    )
    if account is None:
        return
    now = timezone.now()
    with transaction.atomic():
        row, created = ParticipantSelectorReconciliation.objects.get_or_create(
            account=account,
            defaults={
                "realm_id": account.realm_id,
                "state": ParticipantSelectorReconciliation.State.PENDING,
                "next_attempt_at": now,
            },
        )
        if created:
            return
        row = ParticipantSelectorReconciliation.objects.select_for_update().get(id=row.id)
        row.generation += 1
        row.attempts = 0
        row.next_attempt_at = now
        row.last_error_code = ""
        if not (
            row.state == ParticipantSelectorReconciliation.State.LEASED
            and row.lease_expires_at is not None
            and row.lease_expires_at > now
        ):
            row.state = ParticipantSelectorReconciliation.State.PENDING
            row.lease_token = None
            row.lease_expires_at = None
        row.save(
            update_fields=[
                "generation",
                "state",
                "attempts",
                "next_attempt_at",
                "lease_token",
                "lease_expires_at",
                "last_error_code",
                "date_updated",
            ]
        )


def schedule_space_participant_reconciliations(space_id: int) -> None:
    account_ids = (
        SpaceAttachment.objects.filter(space_id=space_id)
        .values_list("source__account_id", flat=True)
        .distinct()
    )
    for account_id in account_ids:
        schedule_participant_selector_reconciliation(account_id)


def schedule_all_participant_selector_reconciliations() -> int:
    account_ids = ConnectedAccount.objects.filter(
        connection_kind=ConnectedAccount.ConnectionKind.REMOTE_STUDIO
    ).values_list("id", flat=True)
    count = 0
    for account_id in account_ids:
        schedule_participant_selector_reconciliation(account_id)
        count += 1
    return count


def due_participant_reconciliation_ids(*, limit: int, account_id: int | None = None) -> list[int]:
    now = timezone.now()
    account_filter = Q() if account_id is None else Q(account_id=account_id)
    return list(
        ParticipantSelectorReconciliation.objects.filter(
            account_filter,
            Q(
                Q(
                    state=ParticipantSelectorReconciliation.State.PENDING,
                    next_attempt_at__lte=now,
                )
                | Q(
                    state=ParticipantSelectorReconciliation.State.BACKOFF,
                    next_attempt_at__lte=now,
                )
                | Q(
                    state=ParticipantSelectorReconciliation.State.LEASED,
                    lease_expires_at__lte=now,
                )
            ),
        )
        .order_by("next_attempt_at", "id")
        .values_list("id", flat=True)[:limit]
    )


def _claim_participant_selector_reconciliation(
    reconciliation_id: int,
) -> ClaimedParticipantReconciliation:
    with transaction.atomic(durable=True):
        row = (
            ParticipantSelectorReconciliation.objects.select_for_update()
            .select_related("account", "realm")
            .get(id=reconciliation_id)
        )
        participant_refs = desired_participant_refs(row.account)
        lease_token = uuid4()
        now = timezone.now()
        row.state = ParticipantSelectorReconciliation.State.LEASED
        row.lease_token = lease_token
        row.lease_expires_at = now + timedelta(seconds=PARTICIPANT_RECONCILIATION_LEASE_SECONDS)
        row.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "date_updated",
            ]
        )
        return ClaimedParticipantReconciliation(
            reconciliation_id=row.id,
            generation=row.generation,
            lease_token=lease_token,
            realm_uuid=row.realm.uuid,
            account_external_id=row.account.external_account_id,
            account_id=row.account_id,
            participant_refs=participant_refs,
        )


def _finish_participant_selector_reconciliation(
    claim: ClaimedParticipantReconciliation,
    *,
    error_code: str = "",
    retry_after_seconds: int = 0,
) -> bool:
    """Return whether this claim became the current account projection."""

    with transaction.atomic(durable=True):
        row = ParticipantSelectorReconciliation.objects.select_for_update().get(
            id=claim.reconciliation_id
        )
        if row.lease_token != claim.lease_token:
            return False
        now = timezone.now()
        row.lease_token = None
        row.lease_expires_at = None
        if row.generation != claim.generation:
            row.state = ParticipantSelectorReconciliation.State.PENDING
            row.next_attempt_at = now
            row.last_error_code = error_code
            row.save(
                update_fields=[
                    "state",
                    "next_attempt_at",
                    "lease_token",
                    "lease_expires_at",
                    "last_error_code",
                    "date_updated",
                ]
            )
            return False
        if error_code:
            row.attempts += 1
            delay = max(retry_after_seconds, min(2**row.attempts, 3_600))
            row.state = ParticipantSelectorReconciliation.State.BACKOFF
            row.next_attempt_at = now + timedelta(seconds=delay)
            row.last_error_code = error_code[:64]
            row.save(
                update_fields=[
                    "attempts",
                    "state",
                    "next_attempt_at",
                    "lease_token",
                    "lease_expires_at",
                    "last_error_code",
                    "date_updated",
                ]
            )
            return False
        row.state = ParticipantSelectorReconciliation.State.CURRENT
        row.attempts = 0
        row.next_attempt_at = now
        row.last_error_code = ""
        row.last_reconciled_at = now
        row.save(
            update_fields=[
                "state",
                "attempts",
                "next_attempt_at",
                "lease_token",
                "lease_expires_at",
                "last_error_code",
                "last_reconciled_at",
                "date_updated",
            ]
        )
        return True


def reconcile_participant_selector_row(
    *, reconciliation_id: int, clawer_sync: ClawerSync
) -> ParticipantReconciliationResult:
    claim = _claim_participant_selector_reconciliation(reconciliation_id)
    if len(claim.participant_refs) > MAX_PARTICIPANT_SELECTORS:
        error_code = "participant_selector_limit_exceeded"
        _finish_participant_selector_reconciliation(claim, error_code=error_code)
        return ParticipantReconciliationResult(
            account_id=claim.account_id,
            participant_count=0,
            success=False,
            error_code=error_code,
        )
    try:
        clawer_sync.reconcile_participant_selectors(
            realm_uuid=claim.realm_uuid,
            account_external_id=claim.account_external_id,
            participant_refs=claim.participant_refs,
        )
    except ValueError:
        error_code = "invalid_selector_set"
        _finish_participant_selector_reconciliation(claim, error_code=error_code)
        return ParticipantReconciliationResult(
            account_id=claim.account_id,
            participant_count=0,
            success=False,
            error_code=error_code,
        )
    except ClawerSyncError as exc:
        _finish_participant_selector_reconciliation(
            claim,
            error_code=exc.error_code,
            retry_after_seconds=exc.retry_after_seconds or 0,
        )
        return ParticipantReconciliationResult(
            account_id=claim.account_id,
            participant_count=0,
            success=False,
            error_code=exc.error_code,
        )
    current = _finish_participant_selector_reconciliation(claim)
    return ParticipantReconciliationResult(
        account_id=claim.account_id,
        participant_count=len(claim.participant_refs),
        success=True,
        current=current,
    )

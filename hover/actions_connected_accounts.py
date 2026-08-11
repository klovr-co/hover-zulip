from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.lib_connected_accounts import (
    get_connected_account_data,
    get_connected_account_grant_data,
    get_realm_administrator_ids,
)
from hover.models import ConnectedAccount, ConnectedAccountGrant, ConnectedAccountGrantSelector
from hover.participant_selector_reconciliation import schedule_participant_selector_reconciliation
from zerver.lib.exceptions import InvalidJSONError, JsonableError
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog
from zerver.models.realms import Realm
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


@dataclass(frozen=True)
class ConnectedAccountSelectorSpec:
    selector_type: str
    source_ref: str
    display_name: str


def _check_actor_is_realm_administrator(
    account: ConnectedAccount, acting_user: UserProfile
) -> None:
    if acting_user.realm_id != account.realm_id or not acting_user.is_realm_admin:
        raise JsonableError(_("Invalid Connected Account ID"))


def _check_grantee(target: UserProfile, realm: Realm) -> None:
    if target.realm_id != realm.id or not target.is_active or target.is_bot or target.is_guest:
        raise JsonableError(_("Invalid user ID"))


def _account_recipient_ids(account: ConnectedAccount) -> set[int]:
    recipient_ids = get_realm_administrator_ids(account.realm_id)
    if account.created_by_id is not None:
        recipient_ids.add(account.created_by_id)
    if account.owner_id is not None:
        recipient_ids.add(account.owner_id)
    recipient_ids.update(account.grants.values_list("user_id", flat=True))
    return recipient_ids


def _notify_account(account: ConnectedAccount, *, op: str) -> None:
    if not account.realm.hover_enabled:
        return
    send_event_on_commit(
        account.realm,
        {
            "type": "hover_connected_account",
            "op": op,
            "account": get_connected_account_data(account),
        },
        _account_recipient_ids(account),
    )


def _notify_grant(grant: ConnectedAccountGrant, *, op: str) -> None:
    if not grant.realm.hover_enabled:
        return
    recipient_ids = get_realm_administrator_ids(grant.realm_id)
    recipient_ids.add(grant.user_id)
    send_event_on_commit(
        grant.realm,
        {
            "type": "hover_connected_account",
            "op": op,
            "grant": get_connected_account_grant_data(grant),
        },
        recipient_ids,
    )


def _create_audit_log(
    *,
    account: ConnectedAccount,
    acting_user: UserProfile | None,
    event_type: AuditLogEventType,
    extra_data: dict[str, object],
    modified_user: UserProfile | None = None,
) -> None:
    # Keep this payload intentionally limited to Hover database IDs, states,
    # selector types, and counts. External account/selector IDs and labels are
    # never needed for the audit trail.
    RealmAuditLog.objects.create(
        realm=account.realm,
        acting_user=acting_user,
        modified_user=modified_user,
        event_type=event_type,
        event_time=timezone_now(),
        extra_data={"account_id": account.id, **extra_data},
    )


@transaction.atomic(durable=True)
def do_create_connected_account(
    *,
    realm: Realm,
    provider_key: str,
    provider_name: str,
    external_account_id: UUID,
    display_name: str,
    created_by: UserProfile,
    owner: UserProfile,
    connection_kind: str = ConnectedAccount.ConnectionKind.REMOTE_STUDIO,
    incoming_webhook_bot: UserProfile | None = None,
) -> ConnectedAccount:
    _check_grantee(created_by, realm)
    _check_grantee(owner, realm)
    account = ConnectedAccount(
        realm=realm,
        provider_key=provider_key.strip(),
        provider_name=provider_name.strip(),
        external_account_id=external_account_id,
        display_name=display_name.strip(),
        created_by=created_by,
        owner=owner,
        connection_kind=connection_kind,
        incoming_webhook_bot=incoming_webhook_bot,
    )
    if ConnectedAccount.objects.filter(
        realm=realm,
        provider_key=account.provider_key,
        external_account_id=external_account_id,
    ).exists():
        raise JsonableError(_("Connected Account already exists."))
    try:
        account.full_clean()
        account.save()
    except ValidationError as exc:
        raise InvalidJSONError(str(exc))
    except IntegrityError:
        raise JsonableError(_("Connected Account already exists."))

    _create_audit_log(
        account=account,
        acting_user=created_by,
        event_type=AuditLogEventType.HOVER_CONNECTED_ACCOUNT_CREATED,
        extra_data={"approval_state": account.approval_state},
    )
    _notify_account(account, op="account_add")
    return account


@transaction.atomic(durable=True)
def do_set_connected_account_approval_state(
    account: ConnectedAccount,
    approval_state: str,
    *,
    acting_user: UserProfile,
) -> None:
    _check_actor_is_realm_administrator(account, acting_user)
    if approval_state not in {
        ConnectedAccount.ApprovalState.APPROVED,
        ConnectedAccount.ApprovalState.REVOKED,
    }:
        raise JsonableError(_("Invalid Connected Account approval state."))
    if account.approval_state == approval_state:
        return

    old_state = account.approval_state
    account.approval_state = approval_state
    account.save(update_fields=["approval_state", "date_updated"])
    _create_audit_log(
        account=account,
        acting_user=acting_user,
        event_type=AuditLogEventType.HOVER_CONNECTED_ACCOUNT_APPROVAL_CHANGED,
        extra_data={"old_state": old_state, "new_state": approval_state},
    )
    _notify_account(account, op="account_update")
    schedule_participant_selector_reconciliation(account.id)


@transaction.atomic(durable=True)
def do_update_connected_account_health(
    account: ConnectedAccount,
    *,
    health_status: str,
    checked_at: datetime,
) -> None:
    if health_status not in ConnectedAccount.HealthStatus.values:
        raise JsonableError(_("Invalid Connected Account health status."))
    if account.health_status == health_status and account.health_checked_at == checked_at:
        return

    account.health_status = health_status
    account.health_checked_at = checked_at
    account.save(update_fields=["health_status", "health_checked_at", "date_updated"])
    _create_audit_log(
        account=account,
        acting_user=None,
        event_type=AuditLogEventType.HOVER_CONNECTED_ACCOUNT_HEALTH_CHANGED,
        extra_data={"health_status": health_status},
    )
    _notify_account(account, op="account_update")


def _normalized_selector_specs(
    selector_specs: list[ConnectedAccountSelectorSpec],
) -> list[ConnectedAccountSelectorSpec]:
    normalized = [
        ConnectedAccountSelectorSpec(
            selector_type=spec.selector_type.strip(),
            source_ref=spec.source_ref.strip(),
            display_name=spec.display_name.strip(),
        )
        for spec in selector_specs
    ]
    keys = {(spec.selector_type, spec.source_ref) for spec in normalized}
    if len(keys) != len(normalized):
        raise JsonableError(_("Duplicate Connected Account selector."))
    return sorted(normalized, key=lambda spec: (spec.selector_type, spec.source_ref))


@transaction.atomic(durable=True)
def do_upsert_connected_account_grant(
    account: ConnectedAccount,
    target: UserProfile,
    *,
    all_selectors: bool,
    selector_specs: list[ConnectedAccountSelectorSpec],
    acting_user: UserProfile,
) -> ConnectedAccountGrant:
    _check_actor_is_realm_administrator(account, acting_user)
    _check_grantee(target, account.realm)
    if account.approval_state != ConnectedAccount.ApprovalState.APPROVED:
        raise JsonableError(_("Approve this Connected Account before assigning it."))
    if all_selectors and selector_specs:
        raise JsonableError(_("An all-selectors grant cannot also list individual selectors."))

    selector_specs = _normalized_selector_specs(selector_specs)
    grant, created = ConnectedAccountGrant.objects.get_or_create(
        realm=account.realm,
        account=account,
        user=target,
        defaults={
            "created_by": acting_user,
            "state": ConnectedAccountGrant.State.ACTIVE,
            "all_selectors": all_selectors,
        },
    )
    old_selector_keys = {
        (selector.selector_type, selector.source_ref, selector.display_name)
        for selector in grant.selectors.all()
    }
    new_selector_keys = {
        (spec.selector_type, spec.source_ref, spec.display_name) for spec in selector_specs
    }
    changed = (
        created
        or grant.state != ConnectedAccountGrant.State.ACTIVE
        or grant.all_selectors != all_selectors
        or old_selector_keys != new_selector_keys
    )
    if not changed:
        return grant

    grant.state = ConnectedAccountGrant.State.ACTIVE
    grant.all_selectors = all_selectors
    grant.save(update_fields=["state", "all_selectors", "date_updated"])
    grant.selectors.all().delete()
    selectors = [
        ConnectedAccountGrantSelector(
            realm=account.realm,
            grant=grant,
            selector_type=spec.selector_type,
            source_ref=spec.source_ref,
            display_name=spec.display_name,
        )
        for spec in selector_specs
    ]
    for selector in selectors:
        try:
            selector.full_clean()
        except ValidationError as exc:
            raise InvalidJSONError(str(exc))
    ConnectedAccountGrantSelector.objects.bulk_create(selectors)

    # Prefetch caches are stale after replacement.
    grant = ConnectedAccountGrant.objects.prefetch_related("selectors").get(id=grant.id)
    _create_audit_log(
        account=account,
        acting_user=acting_user,
        modified_user=target,
        event_type=AuditLogEventType.HOVER_CONNECTED_ACCOUNT_GRANT_CHANGED,
        extra_data={
            "grant_id": grant.id,
            "all_selectors": all_selectors,
            "selector_count": len(selector_specs),
            "selector_types": sorted({spec.selector_type for spec in selector_specs}),
        },
    )
    _notify_grant(grant, op="grant_upsert")
    return grant


@transaction.atomic(durable=True)
def do_revoke_connected_account_grant(
    account: ConnectedAccount,
    grant: ConnectedAccountGrant,
    *,
    acting_user: UserProfile,
) -> None:
    _check_actor_is_realm_administrator(account, acting_user)
    if grant.account_id != account.id or grant.realm_id != account.realm_id:
        raise JsonableError(_("Invalid Connected Account grant ID"))
    if grant.state == ConnectedAccountGrant.State.REVOKED:
        return

    grant.state = ConnectedAccountGrant.State.REVOKED
    grant.save(update_fields=["state", "date_updated"])
    _create_audit_log(
        account=account,
        acting_user=acting_user,
        modified_user=grant.user,
        event_type=AuditLogEventType.HOVER_CONNECTED_ACCOUNT_GRANT_REVOKED,
        extra_data={"grant_id": grant.id},
    )
    _notify_grant(grant, op="grant_upsert")

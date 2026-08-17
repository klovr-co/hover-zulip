from typing import Any

from django.db.models import Prefetch, Q, QuerySet
from django.utils.translation import gettext as _

from hover.models import ConnectedAccount, ConnectedAccountGrant
from zerver.lib.exceptions import JsonableError
from zerver.models.users import UserProfile


def get_realm_administrator_ids(realm_id: int) -> set[int]:
    return set(
        UserProfile.objects.filter(
            realm_id=realm_id,
            is_active=True,
            is_bot=False,
            role__in=[
                UserProfile.ROLE_REALM_OWNER,
                UserProfile.ROLE_REALM_ADMINISTRATOR,
            ],
        ).values_list("id", flat=True)
    )


def get_visible_connected_accounts(user_profile: UserProfile) -> QuerySet[ConnectedAccount]:
    accounts = ConnectedAccount.objects.filter(realm=user_profile.realm)
    if not user_profile.realm.hover_enabled:
        return accounts.none()

    if not user_profile.is_realm_admin:
        accounts = accounts.filter(
            Q(created_by=user_profile) | Q(owner=user_profile) | Q(grants__user=user_profile)
        )

    visible_grants = ConnectedAccountGrant.objects.select_related("user").prefetch_related(
        "selectors"
    )
    if not user_profile.is_realm_admin:
        visible_grants = visible_grants.filter(user=user_profile)

    return (
        accounts.select_related("created_by", "owner")
        .prefetch_related(Prefetch("grants", queryset=visible_grants))
        .distinct()
        .order_by("provider_name", "display_name", "id")
    )


def access_connected_account(
    user_profile: UserProfile, account_id: int, *, require_administrator: bool = False
) -> ConnectedAccount:
    if require_administrator and not user_profile.is_realm_admin:
        raise JsonableError(_("Invalid Connected Account ID"))

    queryset = (
        ConnectedAccount.objects.filter(realm=user_profile.realm)
        .select_related("created_by", "owner")
        .prefetch_related("grants__user", "grants__selectors")
    )
    if not user_profile.realm.hover_enabled:
        queryset = queryset.none()
    elif not require_administrator:
        queryset = get_visible_connected_accounts(user_profile)

    try:
        return queryset.get(id=account_id)
    except ConnectedAccount.DoesNotExist:
        raise JsonableError(_("Invalid Connected Account ID"))


def access_connected_account_grant(
    user_profile: UserProfile, account: ConnectedAccount, grant_id: int
) -> ConnectedAccountGrant:
    if not user_profile.is_realm_admin:
        raise JsonableError(_("Invalid Connected Account grant ID"))
    try:
        return (
            ConnectedAccountGrant.objects.select_related("user")
            .prefetch_related("selectors")
            .get(id=grant_id, account=account, realm=user_profile.realm)
        )
    except ConnectedAccountGrant.DoesNotExist:
        raise JsonableError(_("Invalid Connected Account grant ID"))


def get_connected_account_data(account: ConnectedAccount) -> dict[str, Any]:
    return {
        "id": account.id,
        "provider_key": account.provider_key,
        "provider_name": account.provider_name,
        "external_account_id": str(account.external_account_id),
        "display_name": account.display_name,
        "connection_kind": account.connection_kind,
        "incoming_webhook_bot_id": account.incoming_webhook_bot_id,
        "created_by_id": account.created_by_id,
        "owner_id": account.owner_id,
        "approval_state": account.approval_state,
        "health_status": account.health_status,
        "health_checked_at": (
            account.health_checked_at.isoformat() if account.health_checked_at is not None else None
        ),
        "link_state": account.link_state,
        "link_expires_at": (
            account.link_expires_at.isoformat() if account.link_expires_at is not None else None
        ),
    }


def get_connected_account_grant_data(grant: ConnectedAccountGrant) -> dict[str, Any]:
    selectors = sorted(
        grant.selectors.all(), key=lambda selector: (selector.selector_type, selector.display_name)
    )
    return {
        "id": grant.id,
        "account_id": grant.account_id,
        "user_id": grant.user_id,
        "state": grant.state,
        "all_selectors": grant.all_selectors,
        "selectors": [
            {
                "selector_type": selector.selector_type,
                "source_ref": selector.source_ref,
                "display_name": selector.display_name,
            }
            for selector in selectors
        ],
    }


def get_visible_connected_account_data(
    user_profile: UserProfile,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accounts = list(get_visible_connected_accounts(user_profile))
    account_data = [get_connected_account_data(account) for account in accounts]
    grant_data = [
        get_connected_account_grant_data(grant)
        for account in accounts
        for grant in account.grants.all()
    ]
    return account_data, grant_data


def user_can_use_connected_account(
    user_profile: UserProfile,
    account: ConnectedAccount,
    *,
    selector_type: str,
    source_ref: str,
) -> bool:
    """Apply Hover's teammate-level grant below Studio's organization ceiling.

    Studio remains authoritative for whether this account/selector is available
    to the organization at all. This helper only evaluates the narrower Hover
    grant and deliberately treats an empty selector list as deny-all.
    """
    if (
        not user_profile.realm.hover_enabled
        or account.realm_id != user_profile.realm_id
        or account.approval_state != ConnectedAccount.ApprovalState.APPROVED
        or (
            account.provider_key == "whatsapp"
            and account.connection_kind == ConnectedAccount.ConnectionKind.REMOTE_STUDIO
            and account.link_state
            in {
                ConnectedAccount.LinkState.PENDING,
                ConnectedAccount.LinkState.EXPIRED,
                ConnectedAccount.LinkState.FAILED,
            }
        )
    ):
        return False

    try:
        grant = ConnectedAccountGrant.objects.get(
            account=account,
            user=user_profile,
            state=ConnectedAccountGrant.State.ACTIVE,
        )
    except ConnectedAccountGrant.DoesNotExist:
        return False

    if grant.all_selectors:
        return True
    return grant.selectors.filter(selector_type=selector_type, source_ref=source_ref).exists()

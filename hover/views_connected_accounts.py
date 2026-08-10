from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import BaseModel, Json, StringConstraints

from hover.actions_connected_accounts import (
    ConnectedAccountSelectorSpec,
    do_revoke_connected_account_grant,
    do_set_connected_account_approval_state,
    do_upsert_connected_account_grant,
)
from hover.lib_connected_accounts import (
    access_connected_account,
    access_connected_account_grant,
    get_connected_account_data,
    get_connected_account_grant_data,
    get_visible_connected_account_data,
)
from hover.models import ConnectedAccountGrantSelector
from zerver.decorator import require_non_guest_user, require_realm_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile, get_user_profile_by_id_in_realm


class ConnectedAccountSelectorInput(BaseModel):
    selector_type: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    ]
    source_ref: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            pattern=r"^src_[0-9a-f]{32}$",
            max_length=ConnectedAccountGrantSelector.MAX_SOURCE_REF_LENGTH,
        ),
    ]
    display_name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=ConnectedAccountGrantSelector.MAX_DISPLAY_NAME_LENGTH,
        ),
    ]


@require_non_guest_user
@typed_endpoint
def list_connected_accounts(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    accounts, grants = get_visible_connected_account_data(user_profile)
    return json_success(
        request,
        data={"connected_accounts": accounts, "connected_account_grants": grants},
    )


@require_non_guest_user
@typed_endpoint
def get_connected_account(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    account_id: PathOnly[int],
) -> HttpResponse:
    account = access_connected_account(user_profile, account_id)
    visible_grants = account.grants.all()
    return json_success(
        request,
        data={
            "connected_account": get_connected_account_data(account),
            "connected_account_grants": [
                get_connected_account_grant_data(grant) for grant in visible_grants
            ],
        },
    )


@require_realm_admin
@typed_endpoint
def update_connected_account(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    account_id: PathOnly[int],
    approval_state: Json[Literal["approved", "revoked"]],
) -> HttpResponse:
    account = access_connected_account(user_profile, account_id, require_administrator=True)
    do_set_connected_account_approval_state(account, approval_state, acting_user=user_profile)
    return json_success(request, data={"connected_account": get_connected_account_data(account)})


@require_realm_admin
@typed_endpoint
def upsert_connected_account_grant(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    account_id: PathOnly[int],
    user_id: Json[int],
    all_selectors: Json[bool],
    selectors: Json[list[ConnectedAccountSelectorInput]],
) -> HttpResponse:
    account = access_connected_account(user_profile, account_id, require_administrator=True)
    try:
        target = get_user_profile_by_id_in_realm(user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Invalid user ID"))
    grant = do_upsert_connected_account_grant(
        account,
        target,
        all_selectors=all_selectors,
        selector_specs=[
            ConnectedAccountSelectorSpec(
                selector_type=selector.selector_type,
                source_ref=selector.source_ref,
                display_name=selector.display_name,
            )
            for selector in selectors
        ],
        acting_user=user_profile,
    )
    return json_success(
        request, data={"connected_account_grant": get_connected_account_grant_data(grant)}
    )


@require_realm_admin
@typed_endpoint
def revoke_connected_account_grant(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    account_id: PathOnly[int],
    grant_id: PathOnly[int],
) -> HttpResponse:
    account = access_connected_account(user_profile, account_id, require_administrator=True)
    grant = access_connected_account_grant(user_profile, account, grant_id)
    do_revoke_connected_account_grant(account, grant, acting_user=user_profile)
    return json_success(
        request, data={"connected_account_grant": get_connected_account_grant_data(grant)}
    )

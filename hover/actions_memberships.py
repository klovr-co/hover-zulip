import re
from collections.abc import Iterable

from django.db import transaction
from django.utils.translation import gettext as _

from hover.lib_spaces import get_space_data, user_is_space_administrator
from hover.models import Space, SpaceAdministrator, SpaceMembership, SpaceMembershipSuggestion
from hover.observations import ResolvedIdentityObservation
from zerver.lib.exceptions import JsonableError
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def _lock_setup_space(space: Space) -> Space:
    locked = (
        Space.objects.select_for_update(no_key=False).select_related("category").get(id=space.id)
    )
    if locked.state != Space.State.SETUP:
        raise JsonableError(_("This Space has already launched."))
    return locked


def _require_space_administrator(space: Space, acting_user: UserProfile) -> None:
    if acting_user.realm_id != space.realm_id or (
        not acting_user.is_realm_admin and not user_is_space_administrator(acting_user, space)
    ):
        raise JsonableError(_("You do not have permission to administer this Space."))


def _validate_role(role: str) -> None:
    if role not in SpaceMembership.Role.values:
        raise JsonableError(_("Invalid Space membership role."))


def _validate_target(space: Space, target: UserProfile) -> None:
    if (
        target.realm_id != space.realm_id
        or not target.is_active
        or target.is_bot
        or target.is_guest
    ):
        raise JsonableError(_("Invalid user ID"))


def _send_admin_update(space: Space) -> None:
    administrator_ids = list(
        SpaceAdministrator.objects.filter(space=space, user__is_active=True).values_list(
            "user_id", flat=True
        )
    )
    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "update", "space": get_space_data(space)},
        administrator_ids,
    )


@transaction.atomic(durable=True)
def refresh_space_membership_suggestions(
    space: Space,
    observations: Iterable[ResolvedIdentityObservation],
    *,
    acting_user: UserProfile,
) -> list[SpaceMembershipSuggestion]:
    space = _lock_setup_space(space)
    _require_space_administrator(space, acting_user)
    changed: list[SpaceMembershipSuggestion] = []

    for observation in observations:
        if observation.user_id is None:
            continue
        if observation.match_basis not in {
            SpaceMembershipSuggestion.MatchBasis.VERIFIED_EMAIL,
            SpaceMembershipSuggestion.MatchBasis.VERIFIED_PHONE,
        }:
            continue
        if re.fullmatch(r"obs_[0-9a-f]{32}", observation.observation_basis) is None:
            continue
        if observation.suggested_role not in SpaceMembership.Role.values:
            continue
        try:
            target = UserProfile.objects.get(
                id=observation.user_id,
                realm=space.realm,
                is_active=True,
                is_bot=False,
            )
        except UserProfile.DoesNotExist:
            continue
        if target.is_guest or SpaceMembership.objects.filter(space=space, user=target).exists():
            continue
        suggestion, created = SpaceMembershipSuggestion.objects.get_or_create(
            realm=space.realm,
            space=space,
            user=target,
            defaults={
                "suggested_role": observation.suggested_role,
                "state": SpaceMembershipSuggestion.State.PENDING,
                "match_basis": observation.match_basis,
                "observation_basis": observation.observation_basis,
                "updated_by": acting_user,
            },
        )
        # Refresh never resurrects or rewrites an explicit admin decision.
        if created:
            changed.append(suggestion)

    if changed:
        _send_admin_update(space)
    return changed


@transaction.atomic(durable=True)
def do_confirm_space_member(
    space: Space,
    target: UserProfile,
    *,
    role: str,
    acting_user: UserProfile,
) -> SpaceMembership:
    """Confirm an observation or directly add an unobserved internal teammate."""

    space = _lock_setup_space(space)
    _require_space_administrator(space, acting_user)
    _validate_target(space, target)
    _validate_role(role)

    membership, _created = SpaceMembership.objects.update_or_create(
        space=space,
        user=target,
        defaults={"realm": space.realm, "role": role, "added_by": acting_user},
    )
    suggestion = SpaceMembershipSuggestion.objects.filter(space=space, user=target).first()
    if suggestion is not None:
        suggestion.suggested_role = role
        suggestion.state = SpaceMembershipSuggestion.State.CONFIRMED
        suggestion.updated_by = acting_user
        suggestion.save(update_fields=["suggested_role", "state", "updated_by", "date_updated"])
    _send_admin_update(space)
    return membership


@transaction.atomic(durable=True)
def do_remove_space_member(space: Space, target: UserProfile, *, acting_user: UserProfile) -> None:
    space = _lock_setup_space(space)
    _require_space_administrator(space, acting_user)
    _validate_target(space, target)
    if SpaceAdministrator.objects.filter(space=space, user=target).exists():
        raise JsonableError(_("Remove Space administration before removing this member."))

    SpaceMembership.objects.filter(space=space, user=target).delete()
    suggestion = SpaceMembershipSuggestion.objects.filter(space=space, user=target).first()
    if suggestion is not None:
        suggestion.state = SpaceMembershipSuggestion.State.REMOVED
        suggestion.updated_by = acting_user
        suggestion.save(update_fields=["state", "updated_by", "date_updated"])
    _send_admin_update(space)

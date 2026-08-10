import re
from collections.abc import Iterable

from django.db import transaction
from django.utils.translation import gettext as _

from hover.lib_spaces import get_space_data, user_is_space_administrator
from hover.models import Space, SpaceAdministrator, SpaceMembership, SpaceMembershipSuggestion
from hover.observations import ResolvedIdentityObservation
from zerver.lib.exceptions import JsonableError
from zerver.models.users import UserProfile, base_bulk_get_user_queryset
from zerver.tornado.django_api import send_event_on_commit


def _lock_setup_space(space: Space) -> Space:
    locked = Space.objects.select_for_update(no_key=True).get(id=space.id)
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

    eligible_observations = {
        observation.user_id: observation
        for observation in observations
        if observation.user_id is not None
        and observation.match_basis
        in {
            SpaceMembershipSuggestion.MatchBasis.VERIFIED_EMAIL,
            SpaceMembershipSuggestion.MatchBasis.VERIFIED_PHONE,
        }
        and re.fullmatch(r"obs_[0-9a-f]{32}", observation.observation_basis) is not None
        and observation.suggested_role in SpaceMembership.Role.values
    }
    users_by_id = {
        user.id: user
        for user in base_bulk_get_user_queryset().filter(
            id__in=eligible_observations,
            realm=space.realm,
            is_active=True,
            is_bot=False,
        )
        if not user.is_guest
    }
    existing_member_ids = set(
        SpaceMembership.objects.filter(space=space, user_id__in=users_by_id).values_list(
            "user_id", flat=True
        )
    )
    existing_suggestion_ids = set(
        SpaceMembershipSuggestion.objects.filter(
            space=space, user_id__in=users_by_id
        ).values_list("user_id", flat=True)
    )

    for user_id, observation in eligible_observations.items():
        target = users_by_id.get(user_id)
        if target is None or user_id in existing_member_ids or user_id in existing_suggestion_ids:
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
            existing_suggestion_ids.add(user_id)

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

from typing import Any

from django.db.models import QuerySet
from django.utils.translation import gettext as _

from hover.models import Space, SpaceAdministrator
from zerver.lib.exceptions import JsonableError
from zerver.models.users import UserProfile


def get_accessible_spaces(user_profile: UserProfile) -> QuerySet[Space]:
    spaces = (
        Space.objects.filter(
            realm=user_profile.realm,
            administrator_assignments__user=user_profile,
            administrator_assignments__user__is_active=True,
        )
        .select_related("category", "created_by", "stream")
        .distinct()
        .order_by("category__order", "name", "id")
    )
    if not user_profile.realm.hover_enabled:
        return spaces.none()
    return spaces


def access_space_by_id(user_profile: UserProfile, space_id: int) -> Space:
    try:
        return get_accessible_spaces(user_profile).get(id=space_id)
    except Space.DoesNotExist:
        raise JsonableError(_("Invalid Space ID"))


def access_space_for_administration(user_profile: UserProfile, space_id: int) -> Space:
    """Return a Space the actor may administer.

    Realm administrators may use a known Space ID to recover administration of
    a Setup Space, but this helper is deliberately not used for discovery or
    read access. Those paths always require an explicit SpaceAdministrator row.
    """
    if not user_profile.is_realm_admin:
        return access_space_by_id(user_profile, space_id)

    try:
        return Space.objects.select_related("category", "created_by", "stream").get(
            id=space_id, realm=user_profile.realm
        )
    except Space.DoesNotExist:
        raise JsonableError(_("Invalid Space ID"))


def get_space_data(space: Space) -> dict[str, Any]:
    return {
        "id": space.id,
        "name": space.name,
        "description": space.description,
        "state": space.state,
        "category": {"id": space.category_id, "name": space.category.name},
        "created_by_id": space.created_by_id,
        "stream_id": space.stream_id,
    }


def user_is_space_administrator(user_profile: UserProfile, space: Space) -> bool:
    return SpaceAdministrator.objects.filter(space=space, user=user_profile).exists()

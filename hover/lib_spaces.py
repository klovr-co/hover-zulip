from typing import Any

from django.db.models import Count, Prefetch, Q, QuerySet
from django.utils.translation import gettext as _

from hover.lib_sources import attachment_queryset, get_space_attachment_data
from hover.models import (
    EvidenceLink,
    GeneratedItem,
    ModuleInstallation,
    Space,
    SpaceAdministrator,
    SpaceDocument,
    SpaceMembership,
    SpaceMembershipSuggestion,
)
from zerver.lib.exceptions import JsonableError
from zerver.models.users import UserProfile


def space_projection_queryset() -> QuerySet[Space]:
    return Space.objects.select_related("category", "created_by", "stream").prefetch_related(
        attachment_queryset(),
        Prefetch(
            "memberships",
            queryset=SpaceMembership.objects.select_related("user").order_by(
                "user__full_name", "user_id"
            ),
        ),
        Prefetch(
            "administrator_assignments",
            queryset=SpaceAdministrator.objects.select_related("user").order_by(
                "user__full_name", "user_id"
            ),
        ),
        Prefetch(
            "membership_suggestions",
            queryset=SpaceMembershipSuggestion.objects.select_related("user").filter(
                state=SpaceMembershipSuggestion.State.PENDING
            ),
        ),
        Prefetch(
            "module_installations",
            queryset=ModuleInstallation.objects.select_related("version__definition")
            .prefetch_related(
                "bindings__requirement",
                "bindings__attachment",
                "triggers__supported_trigger",
            )
            .order_by("version__navigation_order", "id"),
        ),
        Prefetch(
            "documents",
            queryset=SpaceDocument.objects.select_related("created_by").order_by(
                "state", "-date_updated", "id"
            ),
        ),
    )


def get_accessible_spaces(user_profile: UserProfile) -> QuerySet[Space]:
    spaces = (
        space_projection_queryset()
        .filter(realm=user_profile.realm)
        .filter(
            Q(
                state=Space.State.SETUP,
                administrator_assignments__user=user_profile,
                administrator_assignments__user__is_active=True,
            )
            | Q(
                state=Space.State.LAUNCHED,
                memberships__user=user_profile,
                memberships__user__is_active=True,
            )
        )
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
    required_prefetches = {
        "attachments",
        "memberships",
        "administrator_assignments",
        "membership_suggestions",
        "module_installations",
        "documents",
    }
    prefetch_cache = getattr(space, "_prefetched_objects_cache", {})
    if not required_prefetches.issubset(prefetch_cache):
        space = space_projection_queryset().get(id=space.id)
    administrators = list(space.administrator_assignments.all())
    administrator_ids = {assignment.user_id for assignment in administrators}
    memberships = list(space.memberships.all())
    suggestions = (
        list(space.membership_suggestions.all()) if space.state == Space.State.SETUP else []
    )
    from hover.actions_modules import get_module_catalog, installation_data

    module_counts = {
        row["module_key"]: row["count"]
        for row in GeneratedItem.objects.filter(attachment__space=space)
        .values("module_key")
        .annotate(count=Count("id"))
    }
    source_counts: dict[int, int] = {}
    source_count_rows = (
        EvidenceLink.objects.filter(generated_item__attachment__space=space)
        .values("source_id")
        .annotate(count=Count("generated_item_id", distinct=True))
    )
    for row in source_count_rows:
        source_id = row["source_id"]
        if source_id is not None:
            source_counts[source_id] = row["count"]
    attachments = get_space_attachment_data(space)
    for attachment in attachments:
        attachment["generated_count"] = source_counts.get(attachment["source"]["id"], 0)
    installations = []
    for installation in space.module_installations.all():
        data = installation_data(installation)
        data["generated_count"] = module_counts.get(data["definition_key"], 0)
        installations.append(data)

    return {
        "id": space.id,
        "name": space.name,
        "description": space.description,
        "state": space.state,
        "category": {"id": space.category_id, "name": space.category.name},
        "created_by_id": space.created_by_id,
        "stream_id": space.stream_id,
        "attachments": attachments,
        "administrators": [
            {"user_id": assignment.user_id, "full_name": assignment.user.full_name}
            for assignment in administrators
        ],
        "memberships": [
            {
                "id": membership.id,
                "user_id": membership.user_id,
                "full_name": membership.user.full_name,
                "role": membership.role,
                "is_administrator": membership.user_id in administrator_ids,
            }
            for membership in memberships
        ],
        "membership_suggestions": [
            {
                "id": suggestion.id,
                "user_id": suggestion.user_id,
                "full_name": suggestion.user.full_name,
                "suggested_role": suggestion.suggested_role,
                "state": suggestion.state,
                "match_basis": suggestion.match_basis,
            }
            for suggestion in suggestions
        ],
        "module_installations": installations,
        "module_catalog": get_module_catalog(space.realm),
        "documents": [
            {
                "id": document.id,
                "title": document.title,
                "state": document.state,
                "default_view": document.default_view,
                "created_by_id": document.created_by_id,
                "date_updated": document.date_updated.isoformat(),
            }
            for document in space.documents.all()
        ],
    }


def user_is_space_administrator(user_profile: UserProfile, space: Space) -> bool:
    return SpaceAdministrator.objects.filter(space=space, user=user_profile).exists()


def user_can_edit_space_documents(user_profile: UserProfile, space: Space) -> bool:
    if user_is_space_administrator(user_profile, space):
        return True
    return SpaceMembership.objects.filter(
        space=space,
        user=user_profile,
        role=SpaceMembership.Role.CONTRIBUTOR,
    ).exists()

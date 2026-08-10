from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from hover.lib_spaces import get_space_data, user_is_space_administrator
from hover.models import Space, SpaceAdministrator
from zerver.lib.exceptions import JsonableError
from zerver.models.channel_folders import ChannelFolder
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def _check_space_administrator_target(user_profile: UserProfile) -> None:
    if not user_profile.is_active or user_profile.is_bot or user_profile.is_guest:
        raise JsonableError(_("Space administrators must be active organization members."))


@transaction.atomic(durable=True)
def do_create_space(
    user_profile: UserProfile,
    *,
    name: str,
    description: str,
    category: ChannelFolder,
) -> Space:
    realm = user_profile.realm
    name = name.strip()
    description = description.strip()

    if not user_profile.can_create_hover_spaces(realm):
        raise JsonableError(_("You do not have permission to create Spaces."))
    if not name:
        raise JsonableError(_("Space name can't be empty."))
    if category.realm_id != realm.id or category.is_archived:
        raise JsonableError(_("Invalid Space category."))
    if Space.objects.filter(realm=realm, name__iexact=name).exists():
        raise JsonableError(_("Space name already in use."))

    try:
        space = Space.objects.create(
            realm=realm,
            name=name,
            description=description,
            state=Space.State.SETUP,
            category=category,
            created_by=user_profile,
            stream=None,
        )
    except IntegrityError:
        raise JsonableError(_("Space name already in use."))

    SpaceAdministrator.objects.create(
        realm=realm,
        space=space,
        user=user_profile,
        added_by=user_profile,
    )
    send_event_on_commit(
        realm,
        {"type": "hover_space", "op": "add", "space": get_space_data(space)},
        [user_profile.id],
    )
    return space


@transaction.atomic(durable=True)
def do_add_space_administrator(
    space: Space, target: UserProfile, *, acting_user: UserProfile
) -> None:
    if acting_user.realm_id != space.realm_id or (
        not acting_user.is_realm_admin and not user_is_space_administrator(acting_user, space)
    ):
        raise JsonableError(_("You do not have permission to administer this Space."))
    if target.realm_id != space.realm_id:
        raise JsonableError(_("Invalid user ID"))
    _check_space_administrator_target(target)

    _, created = SpaceAdministrator.objects.get_or_create(
        realm=space.realm,
        space=space,
        user=target,
        defaults={"added_by": acting_user},
    )
    if not created:
        return

    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "add", "space": get_space_data(space)},
        [target.id],
    )


@transaction.atomic(durable=True)
def do_remove_space_administrator(
    space: Space, target: UserProfile, *, acting_user: UserProfile
) -> None:
    if acting_user.realm_id != space.realm_id or (
        not acting_user.is_realm_admin and not user_is_space_administrator(acting_user, space)
    ):
        raise JsonableError(_("You do not have permission to administer this Space."))

    assignment = SpaceAdministrator.objects.filter(space=space, user=target).first()
    if assignment is None:
        return
    if SpaceAdministrator.objects.filter(space=space).count() == 1:
        raise JsonableError(_("A Space must have at least one administrator."))

    assignment.delete()
    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "delete", "space_id": space.id},
        [target.id],
    )

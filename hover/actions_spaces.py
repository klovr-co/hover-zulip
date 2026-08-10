from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from hover.lib_spaces import get_space_data, user_is_space_administrator
from hover.models import (
    ConnectedAccount,
    ModuleInstallation,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
    SpaceMembershipSuggestion,
)
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.user_groups import get_role_based_system_groups_dict
from zerver.models.channel_folders import ChannelFolder
from zerver.models.groups import SystemGroups, UserGroup, UserGroupMembership
from zerver.models.streams import Stream
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def _check_space_administrator_target(user_profile: UserProfile) -> None:
    if not user_profile.is_active or user_profile.is_bot or user_profile.is_guest:
        raise JsonableError(_("Space administrators must be active organization members."))


def _administrator_ids(space: Space) -> list[int]:
    return list(
        SpaceAdministrator.objects.filter(space=space, user__is_active=True).values_list(
            "user_id", flat=True
        )
    )


def _send_space_update_to_administrators(
    space: Space, *, exclude_user_ids: set[int] | None = None
) -> None:
    target_ids = _administrator_ids(space)
    if exclude_user_ids is not None:
        target_ids = [user_id for user_id in target_ids if user_id not in exclude_user_ids]
    if not target_ids:
        return
    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "update", "space": get_space_data(space)},
        target_ids,
    )


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
    # Creating a Space is an explicit acceptance by its creator. This also
    # satisfies the invariant that every administrator is a member at launch.
    SpaceMembership.objects.create(
        realm=realm,
        space=space,
        user=user_profile,
        role=SpaceMembership.Role.CONTRIBUTOR,
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
    space = Space.objects.select_for_update(no_key=True).get(id=space.id)
    if space.state != Space.State.SETUP:
        raise JsonableError(_("Space administrators can only be changed during Setup."))
    if acting_user.realm_id != space.realm_id or (
        not acting_user.is_realm_admin and not user_is_space_administrator(acting_user, space)
    ):
        raise JsonableError(_("You do not have permission to administer this Space."))
    if target.realm_id != space.realm_id:
        raise JsonableError(_("Invalid user ID"))
    _check_space_administrator_target(target)
    if not SpaceMembership.objects.filter(space=space, user=target).exists():
        raise JsonableError(_("Only confirmed Space members can become administrators."))

    _assignment, created = SpaceAdministrator.objects.get_or_create(
        realm=space.realm,
        space=space,
        user=target,
        defaults={"added_by": acting_user},
    )
    if not created:
        return

    _send_space_update_to_administrators(space, exclude_user_ids={target.id})
    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "add", "space": get_space_data(space)},
        [target.id],
    )


@transaction.atomic(durable=True)
def do_remove_space_administrator(
    space: Space, target: UserProfile, *, acting_user: UserProfile
) -> None:
    space = Space.objects.select_for_update(no_key=True).get(id=space.id)
    if space.state != Space.State.SETUP:
        raise JsonableError(_("Space administrators can only be changed during Setup."))
    if acting_user.realm_id != space.realm_id or (
        not acting_user.is_realm_admin and not user_is_space_administrator(acting_user, space)
    ):
        raise JsonableError(_("You do not have permission to administer this Space."))

    assignment = SpaceAdministrator.objects.filter(space=space, user=target).first()
    if assignment is None:
        return
    if SpaceAdministrator.objects.select_for_update(no_key=True).filter(space=space).count() == 1:
        raise JsonableError(_("A Space must have at least one administrator."))

    assignment.delete()
    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "delete", "space_id": space.id},
        [target.id],
    )
    _send_space_update_to_administrators(space)


def _validate_launch_attachments(space: Space) -> None:
    attachments = list(
        SpaceAttachment.objects.select_related("source__account").filter(space=space)
    )
    if not attachments:
        raise JsonableError(_("Attach at least one active Source before launch."))
    for attachment in attachments:
        if (
            attachment.realm_id != space.realm_id
            or attachment.state != SpaceAttachment.State.ACTIVE
            or attachment.source.realm_id != space.realm_id
            or attachment.source.account.realm_id != space.realm_id
            or attachment.source.account.approval_state != ConnectedAccount.ApprovalState.APPROVED
            or not attachment.history_timezone
            or (
                attachment.history_window == SpaceAttachment.HistoryWindow.CUSTOM
                and attachment.custom_start_date is None
            )
            or (
                attachment.history_window != SpaceAttachment.HistoryWindow.CUSTOM
                and attachment.custom_start_date is not None
            )
        ):
            raise JsonableError(_("A Source attachment is not ready for launch."))


@transaction.atomic(durable=True)
def do_launch_space(space: Space, *, acting_user: UserProfile) -> tuple[Space, bool]:
    space = (
        Space.objects.select_for_update(no_key=True, of=("self",))
        .select_related("category")
        .get(id=space.id)
    )
    if acting_user.realm_id != space.realm_id or (
        not acting_user.is_realm_admin and not user_is_space_administrator(acting_user, space)
    ):
        raise JsonableError(_("You do not have permission to administer this Space."))
    if space.state == Space.State.LAUNCHED:
        return space, False

    _validate_launch_attachments(space)
    memberships = list(
        SpaceMembership.objects.select_related("user").filter(space=space).order_by("user_id")
    )
    if not memberships:
        raise JsonableError(_("Confirm at least one Space member before launch."))
    for membership in memberships:
        if (
            membership.realm_id != space.realm_id
            or membership.role not in SpaceMembership.Role.values
            or membership.user.realm_id != space.realm_id
            or not membership.user.is_active
            or membership.user.is_bot
            or membership.user.is_guest
        ):
            raise JsonableError(_("A confirmed Space member is not eligible for launch."))

    member_ids = {membership.user_id for membership in memberships}
    administrators = list(
        SpaceAdministrator.objects.select_related("user")
        .select_for_update(no_key=True, of=("self",))
        .filter(space=space)
    )
    if not administrators or any(
        assignment.user_id not in member_ids
        or not assignment.user.is_active
        or assignment.user.realm_id != space.realm_id
        for assignment in administrators
    ):
        raise JsonableError(_("Every Space administrator must be a confirmed active member."))
    if SpaceMembershipSuggestion.objects.filter(
        space=space,
        state=SpaceMembershipSuggestion.State.PENDING,
    ).exists():
        raise JsonableError(_("Resolve all pending membership suggestions before launch."))
    if Stream.objects.filter(realm=space.realm, name__iexact=space.name).exists():
        raise JsonableError(_("A channel already uses this Space name."))

    configured_installations = list(
        ModuleInstallation.objects.select_for_update(no_key=True)
        .prefetch_related("bindings__attachment__source__capabilities", "version__requirements")
        .filter(space=space, state=ModuleInstallation.State.CONFIGURED)
    )
    for installation in configured_installations:
        bindings = list(installation.bindings.all())
        requirements = list(installation.version.requirements.all())
        if any(binding.attachment.state != SpaceAttachment.State.ACTIVE for binding in bindings):
            raise JsonableError(_("A configured Module is bound to an inactive Source."))
        for requirement in requirements:
            matching_bindings = [
                binding for binding in bindings if binding.requirement_id == requirement.id
            ]
            count = len(matching_bindings)
            if not requirement.minimum_count <= count <= requirement.maximum_count:
                raise JsonableError(
                    _("A configured Module no longer satisfies Source requirements.")
                )
            if any(
                requirement.capability
                not in {
                    capability.capability
                    for capability in binding.attachment.source.capabilities.all()
                }
                for binding in matching_bindings
            ):
                raise JsonableError(_("A configured Module Source lost a required capability."))

    administrator_ids = {assignment.user_id for assignment in administrators}
    contributor_ids = {
        membership.user_id
        for membership in memberships
        if membership.role == SpaceMembership.Role.CONTRIBUTOR
    } | administrator_ids
    administrator_group = UserGroup.objects.create(realm=space.realm)
    contributor_group = UserGroup.objects.create(realm=space.realm)
    UserGroupMembership.objects.bulk_create(
        [
            UserGroupMembership(user_group=administrator_group, user_profile_id=user_id)
            for user_id in sorted(administrator_ids)
        ]
        + [
            UserGroupMembership(user_group=contributor_group, user_profile_id=user_id)
            for user_id in sorted(contributor_ids)
        ]
    )
    nobody_group = get_role_based_system_groups_dict(space.realm)[SystemGroups.NOBODY]
    stream, created = create_stream_if_needed(
        space.realm,
        space.name,
        stream_description=space.description,
        invite_only=True,
        history_public_to_subscribers=False,
        default_push_notifications=False,
        folder=space.category,
        can_administer_channel_group=administrator_group,
        can_add_subscribers_group=administrator_group,
        can_remove_subscribers_group=administrator_group,
        can_send_message_group=contributor_group,
        can_subscribe_group=nobody_group,
        acting_user=acting_user,
    )
    if not created:
        raise JsonableError(_("A channel already uses this Space name."))

    bulk_add_subscriptions(
        space.realm,
        [stream],
        [membership.user for membership in memberships],
        acting_user=acting_user,
    )
    space.stream = stream
    space.state = Space.State.LAUNCHED
    space.save(update_fields=["stream", "state", "date_updated"])
    launch_time = space.date_updated
    for installation in configured_installations:
        installation.state = ModuleInstallation.State.ENABLED
        installation.activated_at = launch_time
        if installation.processing_start_at is None:
            installation.processing_start_at = launch_time
        installation.save(
            update_fields=["state", "activated_at", "processing_start_at", "date_updated"]
        )
    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "update", "space": get_space_data(space)},
        sorted(member_ids),
    )
    return space, True

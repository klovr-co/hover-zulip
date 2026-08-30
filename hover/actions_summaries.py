from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import IntegrityError, transaction
from django.db.models.functions import Lower
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.lib_spaces import send_space_update_on_commit, user_is_space_administrator
from hover.models import (
    ModuleInstallation,
    ModuleInstallationBinding,
    ModuleInstallationTrigger,
    ModuleSupportedTrigger,
    ModuleVersion,
    Space,
    SpaceAttachment,
    SpaceMembership,
    SummaryTopicInput,
)
from zerver.actions.streams import bulk_add_subscriptions, bulk_remove_subscriptions
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.user_groups import get_role_based_system_groups_dict
from zerver.models.groups import SystemGroups, UserGroup, UserGroupMembership
from zerver.models.messages import Message
from zerver.models.streams import Stream
from zerver.models.users import UserProfile


@dataclass(frozen=True)
class SummaryInputSpec:
    topic_name: str
    kind: str
    attachment_id: int | None


def _policy_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _available_stream_name(space: Space, label: str) -> str:
    suffix_number = 1
    while True:
        suffix = "" if suffix_number == 1 else f" ({suffix_number})"
        stem_length = Stream.MAX_NAME_LENGTH - len(suffix)
        candidate = f"{space.name} · {label}"[:stem_length].rstrip() + suffix
        if not Stream.objects.filter(realm=space.realm, name__iexact=candidate).exists():
            return candidate
        suffix_number += 1


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise JsonableError(_("Invalid IANA timezone."))


@transaction.atomic(durable=True)
def do_create_summary(
    *,
    acting_user: UserProfile,
    space: Space,
    version_id: int,
    label: str,
    inputs: list[SummaryInputSpec],
    local_time: time,
    timezone: str,
    member_ids: list[int],
) -> ModuleInstallation:
    locked_space = (
        Space.objects.select_for_update(no_key=True, of=("self",))
        .select_related("category", "stream")
        .get(id=space.id)
    )
    if (
        acting_user.realm_id != locked_space.realm_id
        or locked_space.state != Space.State.LAUNCHED
        or locked_space.stream_id is None
        or not user_is_space_administrator(acting_user, locked_space)
    ):
        raise JsonableError(_("You do not have permission to create a Summary."))
    assert locked_space.stream is not None

    label = label.strip()
    if not label:
        raise JsonableError(_("Summary name can't be empty."))
    if len(label) > 60:
        raise JsonableError(_("Summary names may not exceed 60 characters."))
    if (
        ModuleInstallation.objects.annotate(normalized_label=Lower("label"))
        .filter(
            space=locked_space,
            normalized_label=label.casefold(),
            state__in=[
                ModuleInstallation.State.CONFIGURED,
                ModuleInstallation.State.ENABLED,
                ModuleInstallation.State.PAUSED_DETACHED,
            ],
        )
        .exists()
    ):
        raise JsonableError(_("A Summary already uses that name."))
    if (
        SpaceAttachment.objects.filter(
            space=locked_space,
            destination_topic__iexact=label,
            state__in=[SpaceAttachment.State.ACTIVE, SpaceAttachment.State.DETACHED],
        ).exists()
        or Message.objects.filter(
            realm=locked_space.realm,
            recipient=locked_space.stream.recipient,
            subject__iexact=label,
            is_channel_message=True,
        ).exists()
    ):
        raise JsonableError(_("A topic already uses that name."))

    _validate_timezone(timezone)
    try:
        version = (
            ModuleVersion.objects.select_for_update(no_key=True, of=("self",))
            .select_related("definition")
            .prefetch_related("requirements", "supported_triggers")
            .get(
                id=version_id,
                definition__realm=locked_space.realm,
                definition__archive_record__isnull=True,
                archive_record__isnull=True,
                is_sealed=True,
            )
        )
        schedule_trigger = version.supported_triggers.get(kind=ModuleSupportedTrigger.Kind.SCHEDULE)
    except (ModuleVersion.DoesNotExist, ModuleSupportedTrigger.DoesNotExist):
        raise JsonableError(_("Invalid scheduled Summary version."))

    if not inputs:
        raise JsonableError(_("Select at least one Summary input."))
    normalized_topics: set[str] = set()
    source_attachment_ids = {
        item.attachment_id for item in inputs if item.attachment_id is not None
    }
    attachments = {
        attachment.id: attachment
        for attachment in SpaceAttachment.objects.select_for_update(no_key=True)
        .select_related("source__account")
        .filter(
            id__in=source_attachment_ids,
            space=locked_space,
            state=SpaceAttachment.State.ACTIVE,
        )
    }
    validated_inputs: list[tuple[SummaryInputSpec, SpaceAttachment | None]] = []
    for item in inputs:
        topic_name = item.topic_name.strip()
        normalized_topic = topic_name.casefold()
        if not topic_name or len(topic_name) > 60 or normalized_topic in normalized_topics:
            raise JsonableError(_("Summary inputs must be unique, named topics."))
        normalized_topics.add(normalized_topic)
        if item.kind == SummaryTopicInput.Kind.SOURCE:
            attachment = attachments.get(item.attachment_id or 0)
            if attachment is None or attachment.destination_topic.casefold() != normalized_topic:
                raise JsonableError(_("Invalid Source topic input."))
        elif item.kind == SummaryTopicInput.Kind.REGULAR:
            if (
                item.attachment_id is not None
                or not Message.objects.filter(
                    realm=locked_space.realm,
                    recipient=locked_space.stream.recipient,
                    subject__iexact=topic_name,
                    is_channel_message=True,
                ).exists()
            ):
                raise JsonableError(_("Invalid Regular topic input."))
            attachment = None
        else:
            raise JsonableError(_("Invalid Summary input kind."))
        validated_inputs.append((item, attachment))

    if len(member_ids) != len(set(member_ids)) or acting_user.id not in member_ids:
        raise JsonableError(_("Summary members must be unique and include its creator."))
    members = list(
        UserProfile.objects.filter(
            id__in=member_ids,
            realm=locked_space.realm,
            is_active=True,
            is_bot=False,
            hover_space_memberships__space=locked_space,
        )
        .exclude(role=UserProfile.ROLE_GUEST)
        .order_by("id")
    )
    if {member.id for member in members} != set(member_ids):
        raise JsonableError(_("Summary members must be active members of its Space."))

    member_group = UserGroup.objects.create(realm=locked_space.realm)
    UserGroupMembership.objects.bulk_create(
        [
            UserGroupMembership(user_group=member_group, user_profile_id=user_id)
            for user_id in sorted(member_ids)
        ]
    )
    nobody_group = get_role_based_system_groups_dict(locked_space.realm)[SystemGroups.NOBODY]
    summary_stream, created = create_stream_if_needed(
        locked_space.realm,
        _available_stream_name(locked_space, label),
        stream_description=f"Summary in {locked_space.name}: {label}",
        invite_only=True,
        history_public_to_subscribers=False,
        default_push_notifications=False,
        folder=locked_space.category,
        can_administer_channel_group=nobody_group,
        can_add_subscribers_group=nobody_group,
        can_remove_subscribers_group=nobody_group,
        can_send_message_group=member_group,
        can_subscribe_group=nobody_group,
        acting_user=acting_user,
    )
    if not created:
        raise JsonableError(_("A Summary container could not be created."))
    bulk_add_subscriptions(
        locked_space.realm,
        [summary_stream],
        members,
        acting_user=acting_user,
    )

    policy = {
        "version_id": version.id,
        "label": label,
        "inputs": [
            {
                "topic_name": item.topic_name,
                "kind": item.kind,
                "attachment_id": item.attachment_id,
            }
            for item, _attachment in validated_inputs
        ],
        "schedule": {
            "cadence": "daily",
            "local_time": local_time.isoformat(),
            "timezone": timezone,
        },
        "member_ids": sorted(member_ids),
    }
    activated_at = timezone_now()
    try:
        installation = ModuleInstallation.objects.create(
            realm=locked_space.realm,
            space=locked_space,
            version=version,
            label=label,
            summary_stream=summary_stream,
            state=ModuleInstallation.State.ENABLED,
            activation_timezone=timezone,
            activated_at=activated_at,
            processing_start_at=activated_at,
            policy_hash=_policy_hash(policy),
            configured_by=acting_user,
        )
    except IntegrityError:
        raise JsonableError(_("A Summary already uses that name."))

    SummaryTopicInput.objects.bulk_create(
        [
            SummaryTopicInput(
                installation=installation,
                stream=locked_space.stream,
                topic_name=item.topic_name.strip(),
                kind=item.kind,
                source_attachment=attachment,
                position=position,
            )
            for position, (item, attachment) in enumerate(validated_inputs)
        ]
    )
    requirements = list(version.requirements.all())
    source_attachments = [
        attachment for _item, attachment in validated_inputs if attachment is not None
    ]
    if len(requirements) == 1:
        ModuleInstallationBinding.objects.bulk_create(
            [
                ModuleInstallationBinding(
                    installation=installation,
                    requirement=requirements[0],
                    attachment=attachment,
                )
                for attachment in source_attachments
            ]
        )
    ModuleInstallationTrigger.objects.create(
        installation=installation,
        supported_trigger=schedule_trigger,
        cadence=ModuleInstallationTrigger.Cadence.DAILY,
        local_time=local_time,
        timezone=timezone,
    )
    member_ids_for_space = list(
        SpaceMembership.objects.filter(space=locked_space, user__is_active=True).values_list(
            "user_id", flat=True
        )
    )
    send_space_update_on_commit(locked_space, member_ids_for_space)
    return installation


@transaction.atomic(durable=True)
def do_update_summary(
    *,
    acting_user: UserProfile,
    installation: ModuleInstallation,
    label: str,
    inputs: list[SummaryInputSpec],
    local_time: time,
    timezone: str,
    member_ids: list[int],
) -> ModuleInstallation:
    current = (
        ModuleInstallation.objects.select_for_update(no_key=True, of=("self",))
        .select_related("space__stream", "summary_stream", "version")
        .prefetch_related("version__requirements")
        .get(id=installation.id)
    )
    space = current.space
    if (
        current.state != ModuleInstallation.State.ENABLED
        or current.summary_stream_id is None
        or acting_user.realm_id != space.realm_id
        or not user_is_space_administrator(acting_user, space)
    ):
        raise JsonableError(_("You do not have permission to update this Summary."))
    assert space.stream is not None

    label = label.strip()
    if not label or len(label) > 60:
        raise JsonableError(_("Summary names must contain 1 to 60 characters."))
    if (
        ModuleInstallation.objects.annotate(normalized_label=Lower("label"))
        .filter(
            space=space,
            normalized_label=label.casefold(),
            state__in=[
                ModuleInstallation.State.CONFIGURED,
                ModuleInstallation.State.ENABLED,
                ModuleInstallation.State.PAUSED_DETACHED,
            ],
        )
        .exclude(id=current.id)
        .exists()
    ):
        raise JsonableError(_("A Summary already uses that name."))
    if (
        SpaceAttachment.objects.filter(
            space=space,
            destination_topic__iexact=label,
            state__in=[SpaceAttachment.State.ACTIVE, SpaceAttachment.State.DETACHED],
        ).exists()
        or Message.objects.filter(
            realm=space.realm,
            recipient=space.stream.recipient,
            subject__iexact=label,
            is_channel_message=True,
        ).exists()
    ):
        raise JsonableError(_("A topic already uses that name."))
    _validate_timezone(timezone)

    if not inputs:
        raise JsonableError(_("Select at least one Summary input."))
    attachment_ids = {item.attachment_id for item in inputs if item.attachment_id is not None}
    attachments = {
        attachment.id: attachment
        for attachment in SpaceAttachment.objects.select_for_update(no_key=True).filter(
            id__in=attachment_ids,
            space=space,
            state=SpaceAttachment.State.ACTIVE,
        )
    }
    normalized_topics: set[str] = set()
    validated_inputs: list[tuple[SummaryInputSpec, SpaceAttachment | None]] = []
    for item in inputs:
        topic_name = item.topic_name.strip()
        normalized_topic = topic_name.casefold()
        if not topic_name or len(topic_name) > 60 or normalized_topic in normalized_topics:
            raise JsonableError(_("Summary inputs must be unique, named topics."))
        normalized_topics.add(normalized_topic)
        if item.kind == SummaryTopicInput.Kind.SOURCE:
            attachment = attachments.get(item.attachment_id or 0)
            if attachment is None or attachment.destination_topic.casefold() != normalized_topic:
                raise JsonableError(_("Invalid Source topic input."))
        elif item.kind == SummaryTopicInput.Kind.REGULAR:
            if (
                item.attachment_id is not None
                or not Message.objects.filter(
                    realm=space.realm,
                    recipient=space.stream.recipient,
                    subject__iexact=topic_name,
                    is_channel_message=True,
                ).exists()
            ):
                raise JsonableError(_("Invalid Regular topic input."))
            attachment = None
        else:
            raise JsonableError(_("Invalid Summary input kind."))
        validated_inputs.append((item, attachment))

    if len(member_ids) != len(set(member_ids)) or acting_user.id not in member_ids:
        raise JsonableError(_("Summary members must be unique and include the administrator."))
    members = list(
        UserProfile.objects.filter(
            id__in=member_ids,
            realm=space.realm,
            is_active=True,
            is_bot=False,
            hover_space_memberships__space=space,
        )
        .exclude(role=UserProfile.ROLE_GUEST)
        .order_by("id")
    )
    if {member.id for member in members} != set(member_ids):
        raise JsonableError(_("Summary members must be active members of its Space."))

    summary_stream = current.summary_stream
    assert summary_stream is not None
    existing_members = list(
        UserProfile.objects.filter(
            subscription__recipient=summary_stream.recipient,
            subscription__active=True,
        )
    )
    existing_ids = {member.id for member in existing_members}
    desired_ids = set(member_ids)
    removed = [member for member in existing_members if member.id not in desired_ids]
    added = [member for member in members if member.id not in existing_ids]
    if removed:
        bulk_remove_subscriptions(space.realm, removed, [summary_stream], acting_user=acting_user)
    if added:
        bulk_add_subscriptions(space.realm, [summary_stream], added, acting_user=acting_user)
    UserGroupMembership.objects.filter(
        user_group_id=summary_stream.can_send_message_group_id
    ).exclude(user_profile_id__in=desired_ids).delete()
    UserGroupMembership.objects.bulk_create(
        [
            UserGroupMembership(
                user_group_id=summary_stream.can_send_message_group_id,
                user_profile_id=user_id,
            )
            for user_id in sorted(desired_ids)
        ],
        ignore_conflicts=True,
    )

    SummaryTopicInput.objects.filter(installation=current).delete()
    SummaryTopicInput.objects.bulk_create(
        [
            SummaryTopicInput(
                installation=current,
                stream=space.stream,
                topic_name=item.topic_name.strip(),
                kind=item.kind,
                source_attachment=attachment,
                position=position,
            )
            for position, (item, attachment) in enumerate(validated_inputs)
        ]
    )
    ModuleInstallationBinding.objects.filter(installation=current).delete()
    requirements = list(current.version.requirements.all())
    if len(requirements) == 1:
        ModuleInstallationBinding.objects.bulk_create(
            [
                ModuleInstallationBinding(
                    installation=current,
                    requirement=requirements[0],
                    attachment=attachment,
                )
                for _item, attachment in validated_inputs
                if attachment is not None
            ]
        )
    trigger = current.triggers.select_for_update().get(
        supported_trigger__kind=ModuleSupportedTrigger.Kind.SCHEDULE
    )
    trigger.local_time = local_time
    trigger.timezone = timezone
    trigger.save(update_fields=["local_time", "timezone"])

    policy = {
        "version_id": current.version_id,
        "label": label,
        "inputs": [
            {
                "topic_name": item.topic_name.strip(),
                "kind": item.kind,
                "attachment_id": item.attachment_id,
            }
            for item, _attachment in validated_inputs
        ],
        "schedule": {
            "cadence": "daily",
            "local_time": local_time.isoformat(),
            "timezone": timezone,
        },
        "member_ids": sorted(member_ids),
    }
    current.label = label
    current.activation_timezone = timezone
    current.policy_revision += 1
    current.policy_hash = _policy_hash(policy)
    current.configured_by = acting_user
    current.save(
        update_fields=[
            "label",
            "activation_timezone",
            "policy_revision",
            "policy_hash",
            "configured_by",
            "date_updated",
        ]
    )
    space_member_ids = list(
        SpaceMembership.objects.filter(space=space, user__is_active=True).values_list(
            "user_id", flat=True
        )
    )
    send_space_update_on_commit(space, space_member_ids)
    return current

from datetime import datetime
from typing import Any, Literal, TypedDict, cast

from hover.lib import add_hover_metadata
from hover.models import (
    GeneratedItem,
    Response,
    ReviewRequest,
    ReviewRequestTarget,
    Revision,
    Space,
    SpaceMembership,
    SuggestedAction,
    Todo,
)
from zerver.models import UserMessage, UserProfile

AwarenessSurface = Literal["for_you", "team_pulse"]


class AwarenessProjection(TypedDict):
    message_id: int
    generated_item_id: int
    space_id: int
    space_name: str
    stream_id: int
    topic: str
    rendered_content: str
    sender_id: int
    sender_name: str
    timestamp: str
    is_unread: bool
    rank: int
    reasons: list[str]
    hover_generated_item: dict[str, Any]


IMPORTANCE_SCORE = {"low": 10, "normal": 20, "high": 60, "urgent": 80}
IMPORTANT_LEVELS = {"high", "urgent"}
FOR_YOU_WEIGHTS = {
    "assignment": 1 << 20,
    "ownership": 1 << 19,
    "mention": 1 << 18,
    "review_request": 1 << 17,
    "personal_activity": 1 << 16,
    "important": 1 << 15,
    "contributor_space": 1 << 14,
}
TEAM_PULSE_WEIGHTS = {
    "urgent": 1 << 20,
    "high_importance": 1 << 19,
    "open_review": 1 << 18,
    "active_todo": 1 << 17,
    "material_change": 1 << 16,
}


def _meaningful_time(item: GeneratedItem) -> datetime:
    return item.occurred_at or item.generated_at or item.published_at or item.message.date_sent


def _latest_meaningful_items(items: list[GeneratedItem]) -> list[GeneratedItem]:
    """Collapse linked developments while retaining unrelated publications."""
    latest: dict[tuple[int, str], GeneratedItem] = {}
    for item in items:
        assert item.attachment is not None
        lineage_identity = item.lineage_key or f"item:{item.id}"
        key = (item.attachment.space_id, lineage_identity)
        current = latest.get(key)
        if current is None or (_meaningful_time(item), item.message_id) > (
            _meaningful_time(current),
            current.message_id,
        ):
            latest[key] = item
    return list(latest.values())


def get_awareness_projection(
    user_profile: UserProfile, *, surface: AwarenessSurface, limit: int = 100
) -> list[AwarenessProjection]:
    """Project authorized live Hover records without copying their state.

    For You may use personal relationships. Team Pulse deliberately never uses
    per-user activity, flags, or targeting in its rank so two teammates with
    identical memberships receive the same shared projection.
    """
    memberships = list(
        SpaceMembership.objects.filter(
            realm=user_profile.realm,
            user=user_profile,
            user__is_active=True,
            role__in=[
                SpaceMembership.Role.CONTRIBUTOR,
                SpaceMembership.Role.SUBSCRIBER,
            ],
            space__state=Space.State.LAUNCHED,
            space__stream__isnull=False,
        ).select_related("space__stream")
    )
    membership_by_space_id = {membership.space_id: membership for membership in memberships}
    if not membership_by_space_id:
        return []

    items = list(
        GeneratedItem.objects.filter(
            realm=user_profile.realm,
            attachment__space_id__in=membership_by_space_id,
            attachment__space__state=Space.State.LAUNCHED,
            message__realm=user_profile.realm,
        )
        .select_related("attachment__space__stream", "message__sender")
        .prefetch_related("disputed_details")
    )
    items = _latest_meaningful_items(items)
    item_ids = [item.id for item in items]
    message_ids = [item.message_id for item in items]

    directly_mentioned_ids = set(
        UserMessage.objects.filter(
            user_profile=user_profile,
            message_id__in=message_ids,
            flags__andnz=UserMessage.flags.mentioned.mask,
        ).values_list("message_id", flat=True)
    )
    unread_by_message_id = {
        message_id: not bool(flags & UserMessage.flags.read.mask)
        for message_id, flags in UserMessage.objects.filter(
            user_profile=user_profile, message_id__in=message_ids
        ).values_list("message_id", "flags")
    }
    targeted_review_item_ids = set(
        ReviewRequestTarget.objects.filter(
            user=user_profile,
            review_request__state=ReviewRequest.State.OPEN,
            review_request__disputed_detail__generated_item_id__in=item_ids,
        ).values_list("review_request__disputed_detail__generated_item_id", flat=True)
    )
    open_review_item_ids = set(
        ReviewRequest.objects.filter(
            state=ReviewRequest.State.OPEN,
            disputed_detail__generated_item_id__in=item_ids,
        ).values_list("disputed_detail__generated_item_id", flat=True)
    )
    personally_active_item_ids = set(
        Response.objects.filter(
            generated_item_id__in=item_ids, message__sender=user_profile
        ).values_list("generated_item_id", flat=True)
    ) | set(
        Revision.objects.filter(generated_item_id__in=item_ids, actor=user_profile).values_list(
            "generated_item_id", flat=True
        )
    )
    owned_action_item_ids = set(
        SuggestedAction.objects.filter(
            generated_item_id__in=item_ids,
            assignee=user_profile,
            state__in=[SuggestedAction.State.PENDING, SuggestedAction.State.APPROVED],
        ).values_list("generated_item_id", flat=True)
    )
    active_todos = Todo.objects.filter(
        suggested_action__generated_item_id__in=item_ids,
        state=Todo.State.ACTIVE,
    )
    active_todo_item_ids = set(
        active_todos.values_list("suggested_action__generated_item_id", flat=True)
    )
    assigned_todo_item_ids = set(
        active_todos.filter(assignee=user_profile).values_list(
            "suggested_action__generated_item_id", flat=True
        )
    )

    metadata_messages = [{"id": message_id} for message_id in message_ids]
    add_hover_metadata(
        metadata_messages,
        realm_id=user_profile.realm_id,
        user_profile=user_profile,
    )
    metadata_by_message_id: dict[int, dict[str, Any]] = {
        message["id"]: cast(dict[str, Any], message["hover_generated_item"])
        for message in metadata_messages
        if "hover_generated_item" in message
    }

    projections: list[AwarenessProjection] = []
    meaningful_time_by_item_id = {item.id: _meaningful_time(item) for item in items}
    for item in items:
        assert item.attachment is not None
        membership = membership_by_space_id[item.attachment.space_id]
        importance_score = IMPORTANCE_SCORE.get(item.importance, 0)
        reasons: list[str] = []
        rank = importance_score

        if surface == "for_you":
            if item.id in assigned_todo_item_ids:
                rank += FOR_YOU_WEIGHTS["assignment"]
                reasons.append("assignment")
            if item.id in owned_action_item_ids:
                rank += FOR_YOU_WEIGHTS["ownership"]
                reasons.append("ownership")
            if item.message_id in directly_mentioned_ids:
                rank += FOR_YOU_WEIGHTS["mention"]
                reasons.append("mention")
            if item.id in targeted_review_item_ids:
                rank += FOR_YOU_WEIGHTS["review_request"]
                reasons.append("review_request")
            if item.id in personally_active_item_ids:
                rank += FOR_YOU_WEIGHTS["personal_activity"]
                reasons.append("personal_activity")
            if item.importance in IMPORTANT_LEVELS:
                rank += FOR_YOU_WEIGHTS["important"]
                reasons.append("important")
            if membership.role == SpaceMembership.Role.CONTRIBUTOR:
                rank += FOR_YOU_WEIGHTS["contributor_space"]
                reasons.append("contributor_space")
            elif not reasons:
                # Subscriber membership provides broad awareness, not routine
                # day-to-day activity. Direct relevance above still wins.
                continue
        else:
            if item.importance == "urgent":
                rank += TEAM_PULSE_WEIGHTS["urgent"]
                reasons.append("urgent")
            elif item.importance == "high":
                rank += TEAM_PULSE_WEIGHTS["high_importance"]
                reasons.append("high_importance")
            if item.id in open_review_item_ids:
                rank += TEAM_PULSE_WEIGHTS["open_review"]
                reasons.append("open_review")
            if item.id in active_todo_item_ids:
                rank += TEAM_PULSE_WEIGHTS["active_todo"]
                reasons.append("active_todo")
            if item.material_change:
                rank += TEAM_PULSE_WEIGHTS["material_change"]
                reasons.append("material_change")
            if not reasons:
                continue

        space = membership.space
        assert space.stream is not None
        assert space.stream_id is not None
        assert item.message.rendered_content is not None
        metadata = metadata_by_message_id.get(item.message_id)
        if metadata is None:
            continue
        projections.append(
            {
                "message_id": item.message_id,
                "generated_item_id": item.id,
                "space_id": space.id,
                "space_name": space.name,
                "stream_id": space.stream_id,
                "topic": item.message.topic_name(),
                "rendered_content": item.message.rendered_content,
                "sender_id": item.message.sender_id,
                "sender_name": item.message.sender.full_name,
                "timestamp": item.message.date_sent.isoformat(),
                "is_unread": unread_by_message_id.get(item.message_id, False),
                "rank": rank,
                "reasons": reasons,
                "hover_generated_item": metadata,
            }
        )

    # Dict construction and SQL row order never influence the result.
    projections.sort(
        key=lambda projection: (
            -projection["rank"],
            -int(meaningful_time_by_item_id[projection["generated_item_id"]].timestamp()),
            -projection["message_id"],
        )
    )
    return projections[:limit]

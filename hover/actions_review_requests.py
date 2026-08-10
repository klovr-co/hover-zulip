from __future__ import annotations

from collections.abc import Mapping, Sequence

from django.db import transaction
from django.utils import timezone

from hover.models import (
    DisputedDetail,
    DisputedEvidenceLink,
    EvidenceLink,
    GeneratedItem,
    ReviewRequest,
    ReviewRequestTarget,
    Revision,
    SpaceAdministrator,
)
from hover.publication_contracts import PublicationDisputedDetail
from zerver.actions.message_send import internal_send_stream_message
from zerver.models import Message, UserProfile

MAX_REVIEW_REQUEST_TARGETS = 20


def _notification_mention_syntax_for_user(user: UserProfile) -> str:
    """Return stable ID mention syntax that creates Zulip's native mention flag."""
    return f"@**{user.full_name}|{user.id}**"


class ReviewRequestMaterializationError(Exception):
    """A content-free failure that aborts the enclosing publication page."""

    def __init__(self, error_code: str, *, retryable: bool) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.retryable = retryable


def _eligible_targets(
    generated_item: GeneratedItem,
    involved_person_refs: Sequence[str],
) -> tuple[list[UserProfile], str]:
    attachment = generated_item.attachment
    if attachment is None:
        raise ReviewRequestMaterializationError(
            "review_request_missing_attachment", retryable=False
        )
    space = attachment.space
    targets = list(
        UserProfile.objects.filter(
            hover_source_participant_bindings__source=attachment.source,
            hover_source_participant_bindings__participant_ref__in=involved_person_refs,
            hover_space_memberships__space=space,
            realm=generated_item.realm,
            is_active=True,
            is_bot=False,
        )
        .exclude(role=UserProfile.ROLE_GUEST)
        .exclude(is_mirror_dummy=True)
        .distinct()
        .order_by("id")[:MAX_REVIEW_REQUEST_TARGETS]
    )
    if targets:
        return targets, ReviewRequestTarget.Reason.INVOLVED_TEAMMATE

    fallback = (
        SpaceAdministrator.objects.select_related("user")
        .filter(
            space=space,
            realm=generated_item.realm,
            user__hover_space_memberships__space=space,
            user__is_active=True,
            user__is_bot=False,
        )
        .exclude(user__role=UserProfile.ROLE_GUEST)
        .exclude(user__is_mirror_dummy=True)
        .order_by("date_created", "user_id")
        .first()
    )
    if fallback is None:
        raise ReviewRequestMaterializationError("review_request_has_no_target", retryable=True)
    return [fallback.user], ReviewRequestTarget.Reason.SPACE_ADMIN_FALLBACK


def _create_native_request_message(
    *, generated_item: GeneratedItem, detail: PublicationDisputedDetail, targets: list[UserProfile]
) -> Message:
    attachment = generated_item.attachment
    assert attachment is not None
    stream = attachment.space.stream
    if stream is None:
        raise ReviewRequestMaterializationError(
            "review_request_space_not_launched", retryable=False
        )
    mentions = " ".join(_notification_mention_syntax_for_user(user) for user in targets)
    field_label = detail.field_path.replace("_", " ").capitalize()
    content = (
        f"**Review request · {field_label}**\n\n"
        f"{detail.summary}\n\n"
        f"Review requested from {mentions}."
    )
    message_id = internal_send_stream_message(
        sender=generated_item.message.sender,
        stream=stream,
        topic_name=generated_item.message.topic_name(),
        content=content,
        acting_user=generated_item.message.sender,
    )
    if message_id is None:
        raise ReviewRequestMaterializationError(
            "review_request_message_not_created", retryable=True
        )
    message = Message.objects.filter(
        id=message_id,
        realm=generated_item.realm,
        recipient=generated_item.message.recipient,
        sender=generated_item.message.sender,
    ).first()
    if message is None:
        raise ReviewRequestMaterializationError(
            "review_request_message_not_created", retryable=True
        )
    return message


def materialize_disputed_details(
    *,
    generated_item: GeneratedItem,
    details: Sequence[PublicationDisputedDetail],
    evidence_by_ref: Mapping[str, EvidenceLink],
) -> None:
    """Materialize validated v1.1 disputes in the publication transaction."""
    for transport in details:
        detail = DisputedDetail(
            realm=generated_item.realm,
            generated_item=generated_item,
            ambiguity_key=transport.ambiguity_key,
            field_path=transport.field_path,
            summary=transport.summary,
            material=transport.material,
        )
        detail.full_clean()
        detail.save()
        links: list[DisputedEvidenceLink] = []
        for position, evidence_ref in enumerate(transport.evidence_refs):
            evidence_link = evidence_by_ref.get(evidence_ref)
            if (
                evidence_link is None
                or evidence_link.generated_item_id != generated_item.id
                or evidence_link.realm_id != generated_item.realm_id
            ):
                raise ReviewRequestMaterializationError(
                    "invalid_disputed_evidence", retryable=False
                )
            link = DisputedEvidenceLink(
                realm=generated_item.realm,
                disputed_detail=detail,
                evidence_link=evidence_link,
                position=position,
            )
            link.full_clean()
            links.append(link)
        DisputedEvidenceLink.objects.bulk_create(links)

        if not transport.material:
            continue
        targets, reason = _eligible_targets(generated_item, transport.involved_person_refs)
        message = _create_native_request_message(
            generated_item=generated_item,
            detail=transport,
            targets=targets,
        )
        review_request = ReviewRequest(
            realm=generated_item.realm,
            disputed_detail=detail,
            message=message,
        )
        review_request.full_clean()
        review_request.save()
        target_rows = [
            ReviewRequestTarget(
                realm=generated_item.realm,
                review_request=review_request,
                user=target,
                reason=reason,
            )
            for target in targets
        ]
        for target_row in target_rows:
            target_row.full_clean()
        ReviewRequestTarget.objects.bulk_create(target_rows)


def resolve_matching_dispute(revision: Revision) -> DisputedDetail | None:
    """Append the exact H14 Revision to the matching open material dispute."""
    with transaction.atomic():
        detail = (
            DisputedDetail.objects.select_for_update()
            .filter(
                generated_item=revision.generated_item,
                field_path=revision.field_path,
                material=True,
                state=DisputedDetail.State.NEEDS_REVIEW,
            )
            .first()
        )
        if detail is None:
            return None
        resolved_at = timezone.now()
        detail.state = DisputedDetail.State.RESOLVED
        detail.resolved_by_revision = revision
        detail.save(update_fields=["state", "resolved_by_revision", "date_updated"])
        request = ReviewRequest.objects.select_for_update().get(disputed_detail=detail)
        request.state = ReviewRequest.State.RESOLVED
        request.resolved_by_revision = revision
        request.resolved_at = resolved_at
        request.save(update_fields=["state", "resolved_by_revision", "resolved_at"])
        return detail

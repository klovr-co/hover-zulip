from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from hover.clawer_sync import ClawerSync, ClawerSyncError
from hover.lib_source_records import browse_attachment_records, normalize_source_record_query
from hover.models import GeneratedItem, Space, SpaceAttachment, SpaceMembership
from zerver.lib.exceptions import ResourceNotFoundError
from zerver.lib.narrow import NarrowParameter, add_narrow_conditions, get_base_query_for_search
from zerver.lib.url_encoding import stream_message_url
from zerver.models import Message, UserMessage
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile

HOVER_SEARCH_KNOWLEDGE_LIMIT = 40
HOVER_SEARCH_SOURCE_LIMIT = 8


def _authorized_spaces(user_profile: UserProfile) -> QuerySet[Space]:
    if (
        not user_profile.realm.hover_enabled
        or not user_profile.is_active
        or user_profile.is_guest
        or user_profile.is_bot
    ):
        return Space.objects.none()
    return (
        Space.objects.filter(
            realm=user_profile.realm,
            state=Space.State.LAUNCHED,
            stream__isnull=False,
            memberships__user=user_profile,
            memberships__user__is_active=True,
            memberships__role__in=[
                SpaceMembership.Role.CONTRIBUTOR,
                SpaceMembership.Role.SUBSCRIBER,
            ],
        )
        .select_related("stream")
        .distinct()
    )


def _native_knowledge_results(
    *, user_profile: UserProfile, spaces: list[Space], query_text: str
) -> list[dict[str, Any]]:
    if not spaces:
        return []
    spaces_by_stream_id = {space.stream_id: space for space in spaces}
    assert None not in spaces_by_stream_id
    query = get_base_query_for_search(
        user_profile.realm_id, user_profile, need_user_message=True
    ).filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=spaces_by_stream_id,
    )
    query, _is_search, _is_dm_narrow = add_narrow_conditions(
        user_profile=user_profile,
        query=query,
        narrow=[NarrowParameter(operator="search", operand=query_text)],
        is_web_public_query=False,
        realm=user_profile.realm,
    )
    # Integration messages are evidence records, not concise Hover knowledge.
    # Their authoritative records enter through the Source-search seam below.
    query = query.exclude(hover_source_provenance__isnull=False).filter(
        Q(sender__is_bot=False) | Q(hover_generated_item__isnull=False)
    )
    messages = list(
        query.select_related("sender", "recipient")
        .only(
            "id",
            "date_sent",
            "rendered_content",
            "subject",
            "sender__full_name",
            "recipient__type_id",
        )
        .order_by("-id")[:HOVER_SEARCH_KNOWLEDGE_LIMIT]
    )
    generated = {
        item.message_id: item
        for item in GeneratedItem.objects.filter(
            message_id__in=[message.id for message in messages]
        )
    }
    starred_ids = set(
        UserMessage.objects.filter(
            user_profile=user_profile,
            message_id__in=[message.id for message in messages],
            flags__andnz=UserMessage.flags.starred.mask,
        ).values_list("message_id", flat=True)
    )
    results: list[dict[str, Any]] = []
    for message in messages:
        stream_id = message.recipient.type_id
        space = spaces_by_stream_id[stream_id]
        assert space.stream is not None
        item = generated.get(message.id)
        results.append(
            {
                "kind": "generated" if item is not None else "human",
                "message_id": message.id,
                "space": {"id": space.id, "name": space.name},
                "topic": message.topic_name(),
                "sender_name": message.sender.full_name,
                "timestamp": message.date_sent.isoformat(),
                "rendered_content": message.rendered_content,
                "module_name": item.module_name if item is not None else "",
                "output_type": item.output_type if item is not None else "",
                "saved": message.id in starred_ids,
                "saveable": True,
                "url": stream_message_url(
                    realm=user_profile.realm,
                    message={
                        "id": message.id,
                        "stream_id": stream_id,
                        "display_recipient": space.stream.name,
                        "subject": message.topic_name(),
                    },
                ),
            }
        )
    return results


def _source_results(
    *,
    user_profile: UserProfile,
    spaces: list[Space],
    query_text: str,
    clawer_sync: ClawerSync,
) -> tuple[list[dict[str, Any]], list[int]]:
    space_ids = [space.id for space in spaces]
    attachments = list(
        SpaceAttachment.objects.select_related("space", "source", "source__account")
        .filter(
            space_id__in=space_ids,
            state__in=[SpaceAttachment.State.ACTIVE, SpaceAttachment.State.DETACHED],
        )
        .order_by("space_id", "source__display_name", "id")
    )
    results: list[dict[str, Any]] = []
    unavailable_space_ids: list[int] = []
    for attachment in attachments:
        try:
            data = browse_attachment_records(
                user_profile=user_profile,
                space_id=attachment.space_id,
                attachment_id=attachment.id,
                cursor=None,
                limit=HOVER_SEARCH_SOURCE_LIMIT,
                query=query_text,
                clawer_sync=clawer_sync,
            )
        except ResourceNotFoundError:
            # Authorization changed while the upstream request was in flight.
            continue
        except ClawerSyncError:
            unavailable_space_ids.append(attachment.space_id)
            continue
        for record in data["records"]:
            results.append(
                {
                    "kind": "source",
                    "space": {"id": attachment.space_id, "name": attachment.space.name},
                    "source": data["source"],
                    "record": record,
                    "saveable": False,
                }
            )
    return results, unavailable_space_ids


def search_hover_knowledge(
    *, user_profile: UserProfile, query: str, clawer_sync: ClawerSync
) -> dict[str, Any]:
    query_text = normalize_source_record_query(query)
    if not query_text:
        return {"query": "", "knowledge": [], "sources": [], "source_unavailable_count": 0}

    spaces = list(_authorized_spaces(user_profile))
    knowledge = _native_knowledge_results(
        user_profile=user_profile, spaces=spaces, query_text=query_text
    )
    sources, unavailable_space_ids = _source_results(
        user_profile=user_profile,
        spaces=spaces,
        query_text=query_text,
        clawer_sync=clawer_sync,
    )

    # Re-authorize once more after every upstream request. This filter also
    # removes native results if membership was revoked during Source search.
    final_space_ids = set(_authorized_spaces(user_profile).values_list("id", flat=True))
    knowledge = [result for result in knowledge if result["space"]["id"] in final_space_ids]
    sources = [result for result in sources if result["space"]["id"] in final_space_ids]
    return {
        "query": query_text,
        "knowledge": knowledge,
        "sources": sources,
        "source_unavailable_count": sum(
            space_id in final_space_ids for space_id in unavailable_space_ids
        ),
    }

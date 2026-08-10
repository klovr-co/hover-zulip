from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from typing import Any

from django.db.models import Q

from hover.models import GeneratedItem, IntegrationMessageProvenance, Space

PROVIDER_ICON_CLASSES = {
    "whatsapp": "fa fa-whatsapp",
    "github": "fa fa-github",
    "instagram": "fa fa-instagram",
}


def add_hover_metadata(message_dicts: list[dict[str, Any]], *, realm_id: int) -> None:
    """Add Hover metadata to native messages after message access has been authorized."""
    message_ids = [message["id"] for message in message_dicts]
    items = list(
        GeneratedItem.objects.filter(
            realm_id=realm_id,
            message_id__in=message_ids,
            message__realm_id=realm_id,
        )
        .select_related("attachment", "message")
        .prefetch_related("evidence_links")
        .order_by("id")
    )
    recipient_ids = {item.message.recipient_id for item in items}
    space_by_recipient_id = dict(
        Space.objects.filter(
            realm_id=realm_id,
            stream__recipient_id__in=recipient_ids,
        ).values_list("stream__recipient_id", "id")
    )

    def lineage_scope(item: GeneratedItem) -> tuple[str, int, str] | None:
        if not item.lineage_key:
            return None
        if item.attachment is not None:
            return ("space", item.attachment.space_id, item.lineage_key)
        space_id = space_by_recipient_id.get(item.message.recipient_id)
        if space_id is not None:
            return ("space", space_id, item.lineage_key)
        return ("recipient", item.message.recipient_id, item.lineage_key)

    requested_lineages = {scope for item in items if (scope := lineage_scope(item)) is not None}
    lineage_items: dict[tuple[str, int, str], list[GeneratedItem]] = defaultdict(list)
    if requested_lineages:
        space_ids = {scope_id for kind, scope_id, _key in requested_lineages if kind == "space"}
        fallback_recipient_ids = {
            scope_id for kind, scope_id, _key in requested_lineages if kind == "recipient"
        }
        space_recipient_ids = {
            recipient_id
            for recipient_id, space_id in space_by_recipient_id.items()
            if space_id in space_ids
        }
        keys = {lineage_key for _kind, _scope_id, lineage_key in requested_lineages}
        related_items = (
            GeneratedItem.objects.filter(
                realm_id=realm_id,
                lineage_key__in=keys,
                message__realm_id=realm_id,
            )
            .filter(
                Q(attachment__space_id__in=space_ids)
                | Q(message__recipient_id__in=space_recipient_ids | fallback_recipient_ids)
            )
            .select_related("attachment", "message")
        )
        for related in related_items:
            scope = lineage_scope(related)
            if scope in requested_lineages:
                assert scope is not None
                lineage_items[scope].append(related)

    def item_time(item: GeneratedItem) -> tuple[datetime, int]:
        return (
            item.occurred_at
            or item.generated_at
            or item.published_at
            or datetime.min.replace(tzinfo=timezone.utc),
            item.message_id,
        )

    for history in lineage_items.values():
        history.sort(key=item_time)
    metadata_by_message_id: dict[int, dict[str, Any]] = {}
    for item in items:
        sources: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for evidence in item.evidence_links.all():
            if evidence.realm_id != realm_id:
                continue
            source = sources.setdefault(
                evidence.provider_key,
                {
                    "id": evidence.source_id,
                    "key": evidence.provider_key,
                    "name": evidence.provider_name,
                    "icon_class": PROVIDER_ICON_CLASSES.get(
                        evidence.provider_key, "zulip-icon zulip-icon-link"
                    ),
                    "count": 0,
                    "url": evidence.url,
                },
            )
            source["count"] += 1
            if evidence.url and not source["url"]:
                source["url"] = evidence.url

        attachment_space_id = item.attachment.space_id if item.attachment is not None else None
        payload = item.payload if isinstance(item.payload, dict) else {}
        lifecycle = payload.get("lifecycle")
        status = payload.get("status")
        state = (
            lifecycle if isinstance(lifecycle, str) else status if isinstance(status, str) else None
        )
        lineage_history: list[dict[str, Any]] = []
        is_latest = True
        scope = lineage_scope(item)
        if scope is not None:
            history = lineage_items.get(scope, [])
            is_latest = not history or history[-1].id == item.id
            for related in reversed(history):
                related_payload = related.payload if isinstance(related.payload, dict) else {}
                title = related_payload.get("title") or related_payload.get("decision")
                lineage_history.append(
                    {
                        "message_id": related.message_id,
                        "title": title if isinstance(title, str) else related.module_name,
                        "state": (
                            related_payload.get("lifecycle")
                            if isinstance(related_payload.get("lifecycle"), str)
                            else related_payload.get("status")
                            if isinstance(related_payload.get("status"), str)
                            else None
                        ),
                        "occurred_at": related.occurred_at.isoformat()
                        if related.occurred_at is not None
                        else None,
                        "is_current": related.id == item.id,
                    }
                )

        metadata_by_message_id[item.message_id] = {
            "id": item.id,
            "output_type": item.output_type,
            "module": {
                "key": item.module_key,
                "name": item.module_name,
                "version": item.module_version,
            },
            "source_summary": item.source_summary,
            "presentation": {
                "label": item.get_output_type_display(),
                "importance": item.importance,
                "state": state,
                "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
                "generated_at": item.generated_at.isoformat() if item.generated_at else None,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "run_reference": item.run_reference,
            },
            "lineage": {
                "is_latest": is_latest,
                "history_count": len(lineage_history),
                "history": lineage_history,
            },
            "evidence_available": bool(sources),
            "evidence_url": (
                f"/json/hover/spaces/{attachment_space_id}/generated-items/{item.id}/evidence"
                if attachment_space_id is not None and sources
                else None
            ),
            "sources": list(sources.values()),
        }

    for message in message_dicts:
        metadata = metadata_by_message_id.get(message["id"])
        if metadata is not None:
            message["hover_generated_item"] = metadata

    provenance_by_message_id = {
        provenance.message_id: {
            "captured_at": provenance.captured_at.isoformat(),
            "source": {
                "id": provenance.source_id,
                "provider_key": provenance.provider_key,
                "provider_name": provenance.provider_name,
                "source_type": provenance.source_type,
                "display_name": provenance.display_name,
                "external_url": provenance.external_url,
            },
        }
        for provenance in IntegrationMessageProvenance.objects.filter(
            realm_id=realm_id,
            message_id__in=message_ids,
            message__realm_id=realm_id,
        )
    }
    for message in message_dicts:
        provenance = provenance_by_message_id.get(message["id"])
        if provenance is not None:
            message["hover_source_provenance"] = provenance

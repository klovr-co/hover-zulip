from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from typing import Any

from hover.models import GeneratedItem, IntegrationMessageProvenance

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
        .select_related("attachment")
        .prefetch_related("evidence_links")
        .order_by("id")
    )
    lineage_spaces = {
        (item.attachment.space_id, item.lineage_key)
        for item in items
        if item.attachment is not None and item.lineage_key
    }
    lineage_items: dict[tuple[int, str], list[GeneratedItem]] = defaultdict(list)
    if lineage_spaces:
        space_ids = {space_id for space_id, _lineage_key in lineage_spaces}
        keys = {lineage_key for _space_id, lineage_key in lineage_spaces}
        related_items = GeneratedItem.objects.filter(
            realm_id=realm_id,
            attachment__space_id__in=space_ids,
            lineage_key__in=keys,
            message__realm_id=realm_id,
        ).select_related("attachment", "message")
        for related in related_items:
            assert related.attachment is not None
            key = (related.attachment.space_id, related.lineage_key or "")
            if key in lineage_spaces:
                lineage_items[key].append(related)

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
        state = lifecycle if isinstance(lifecycle, str) else status if isinstance(status, str) else None
        lineage_history: list[dict[str, Any]] = []
        is_latest = True
        if item.attachment is not None and item.lineage_key:
            history = lineage_items.get((item.attachment.space_id, item.lineage_key), [])
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

from collections import OrderedDict
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
    items = (
        GeneratedItem.objects.filter(
            realm_id=realm_id,
            message_id__in=message_ids,
            message__realm_id=realm_id,
        )
        .select_related("attachment")
        .prefetch_related("evidence_links")
        .order_by("id")
    )
    metadata_by_message_id: dict[int, dict[str, Any]] = {}
    for item in items:
        sources: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for evidence in item.evidence_links.all():
            if evidence.realm_id != realm_id:
                continue
            source = sources.setdefault(
                evidence.provider_key,
                {
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
        metadata_by_message_id[item.message_id] = {
            "id": item.id,
            "output_type": item.output_type,
            "module": {
                "key": item.module_key,
                "name": item.module_name,
                "version": item.module_version,
            },
            "source_summary": item.source_summary,
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

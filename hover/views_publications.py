from django.http import HttpRequest, HttpResponse

from hover.clawer_sync import get_clawer_sync
from hover.lib_spaces import access_space_by_id
from hover.models import GeneratedItem
from zerver.decorator import require_non_guest_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile


@require_non_guest_user
@typed_endpoint
def resolve_generated_item_evidence(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    generated_item_id: PathOnly[int],
) -> HttpResponse:
    """Resolve server-owned evidence refs without accepting refs from the browser."""
    space = access_space_by_id(user_profile, space_id)
    if space.state != space.State.LAUNCHED or space.stream is None:
        raise JsonableError("Invalid generated item ID")
    try:
        generated_item = (
            GeneratedItem.objects.select_related("attachment__source__account", "message")
            .prefetch_related("evidence_links")
            .get(
                id=generated_item_id,
                realm=user_profile.realm,
                attachment__space=space,
                message__recipient=space.stream.recipient,
            )
        )
    except GeneratedItem.DoesNotExist:
        raise JsonableError("Invalid generated item ID")

    assert generated_item.attachment is not None
    source = generated_item.attachment.source
    links = list(generated_item.evidence_links.all())
    evidence_refs = [
        link.evidence_ref for link in links if link.evidence_ref and link.source_id == source.id
    ]
    if len(evidence_refs) != len(links):
        raise JsonableError("Generated item evidence is unavailable")
    evidence = get_clawer_sync().resolve_evidence(
        realm_uuid=user_profile.realm.uuid,
        account_external_id=source.account.external_account_id,
        source_ref=source.external_ref,
        refs=evidence_refs,
    )
    return json_success(
        request,
        data={"evidence": [item.model_dump(mode="json") for item in evidence]},
    )

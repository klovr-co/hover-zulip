from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from hover.clawer_sync import get_clawer_sync
from hover.lib_spaces import access_space_by_id
from hover.models import ConnectedAccount, GeneratedItem
from zerver.decorator import require_non_guest_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile


class EvidenceResolutionError(JsonableError):
    data_fields = ["error_code", "retryable"]
    http_status_code = 404

    def __init__(self) -> None:
        super().__init__(_("The exact source evidence is no longer available."))
        self.error_code = "evidence_not_resolvable"
        self.retryable = False


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
        raise JsonableError(_("Invalid generated item ID"))
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
        raise JsonableError(_("Invalid generated item ID"))

    assert generated_item.attachment is not None
    source = generated_item.attachment.source
    access_message(user_profile, generated_item.message_id, is_modifying_message=False)
    if source.account.approval_state != ConnectedAccount.ApprovalState.APPROVED:
        raise EvidenceResolutionError
    links = list(generated_item.evidence_links.all())
    evidence_refs = [
        link.evidence_ref for link in links if link.evidence_ref and link.source_id == source.id
    ]
    if not links or len(evidence_refs) != len(links):
        raise EvidenceResolutionError
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

from django.http import HttpRequest, HttpResponse

from hover.clawer_sync import get_clawer_sync
from hover.personal_editions import get_personal_editions_for_user, sync_personal_editions
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.models.users import UserProfile


@require_non_guest_user
@typed_endpoint_without_parameters
def personal_editions(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    sync_status, _errors = sync_personal_editions(
        user_profile=user_profile,
        clawer_sync=get_clawer_sync(),
    )
    response = json_success(
        request,
        data={
            "sync_status": sync_status,
            "editions": get_personal_editions_for_user(user_profile=user_profile),
        },
    )
    response["Cache-Control"] = "no-store"
    return response

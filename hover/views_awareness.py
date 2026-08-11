from typing import Literal

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from hover.lib_awareness import get_awareness_projection
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


@require_non_guest_user
@typed_endpoint
def get_awareness(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    surface: Json[Literal["for_you", "team_pulse"]],
) -> HttpResponse:
    return json_success(
        request,
        data={
            "surface": surface,
            "items": get_awareness_projection(user_profile, surface=surface),
        },
    )

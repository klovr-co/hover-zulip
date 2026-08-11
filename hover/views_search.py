from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import Json, StringConstraints

from hover.clawer_sync import get_clawer_sync
from hover.lib_search import search_hover_knowledge
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models.users import UserProfile


@typed_endpoint
def hover_search(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    query: Json[Annotated[str, StringConstraints(max_length=100)]],
) -> HttpResponse:
    response = json_success(
        request,
        data=search_hover_knowledge(
            user_profile=user_profile,
            query=query,
            clawer_sync=get_clawer_sync(),
        ),
    )
    response["Cache-Control"] = "no-store"
    return response

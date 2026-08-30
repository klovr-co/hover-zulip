from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

import requests
from django.conf import settings

from hover.actions_summary_executions import SummaryDispatch
from hover.clawer_sync import REQUEST_ID_PATTERN, SERVER_CREDENTIAL_PATTERN
from zerver.lib.exceptions import JsonableError
from zerver.lib.outgoing_http import OutgoingSession


class SummaryDispatcher(Protocol):
    def dispatch(self, *, realm_uuid: UUID, dispatch: SummaryDispatch) -> None: ...


class InMemorySummaryDispatcher:
    def __init__(self) -> None:
        self.dispatches: list[dict[str, object]] = []

    def dispatch(self, *, realm_uuid: UUID, dispatch: SummaryDispatch) -> None:
        if dispatch.operation is None or dispatch.callback_bearer is None:
            return
        self.dispatches.append(
            {
                "realm_uuid": str(realm_uuid),
                "operation": dispatch.operation,
                "callback_bearer": dispatch.callback_bearer,
            }
        )


class StudioSummaryDispatcher:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        credentials: Mapping[str, str] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = (
            base_url if base_url is not None else settings.HOVER_STUDIO_API_URL
        ).rstrip("/")
        self.credentials = dict(
            credentials if credentials is not None else settings.HOVER_STUDIO_SERVER_CREDENTIALS
        )
        self.session = session or OutgoingSession(role="hover_studio", timeout=30)

    def dispatch(self, *, realm_uuid: UUID, dispatch: SummaryDispatch) -> None:
        if dispatch.operation is None or dispatch.callback_bearer is None:
            return
        credential = self.credentials.get(str(realm_uuid))
        if (
            not self.base_url
            or credential is None
            or SERVER_CREDENTIAL_PATTERN.fullmatch(credential) is None
        ):
            raise JsonableError("Summary generation is temporarily unavailable.")
        url = f"{self.base_url}/api/hover/v1/organizations/{realm_uuid}/summary-executions"
        try:
            response = self.session.post(
                url,
                json={
                    "operation": dispatch.operation,
                    "callback_bearer": dispatch.callback_bearer,
                },
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {credential}",
                    "Content-Type": "application/json",
                },
            )
        except (requests.Timeout, requests.RequestException):
            raise JsonableError("Summary generation is temporarily unavailable.")
        request_id = response.headers.get("X-Request-Id", "")
        if REQUEST_ID_PATTERN.fullmatch(request_id) is None or response.status_code != 202:
            raise JsonableError("Summary generation is temporarily unavailable.")
        try:
            payload = response.json()
        except requests.JSONDecodeError:
            raise JsonableError("Summary generation is temporarily unavailable.")
        expected = {
            "schema_version": "1.0",
            "execution_id": str(dispatch.execution.id),
            "status": "accepted",
            "request_hash": dispatch.execution.request_hash,
        }
        if payload != expected:
            raise JsonableError("Summary generation is temporarily unavailable.")


def get_summary_dispatcher() -> SummaryDispatcher:
    return StudioSummaryDispatcher()

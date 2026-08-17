"""Bounded Hover-server client for Studio-mediated WhatsApp QR linking."""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import requests
from django.conf import settings

from hover.clawer_sync import (
    MAX_RESPONSE_BYTES,
    REQUEST_ID_PATTERN,
    SERVER_CREDENTIAL_PATTERN,
    ClawerSyncError,
)
from zerver.lib.outgoing_http import OutgoingSession

_QR_IMAGE_MAX_BYTES = 500_000
_LINK_STATES = {"pending", "linked", "expired", "failed"}
_STUDIO_LINK_ERROR_STATUS = {
    "invalid_request": (400, False),
    "unauthorized": (401, False),
    "forbidden": (403, False),
    "connected_account_not_found": (404, False),
    "link_not_found": (404, False),
    "rate_limited": (429, True),
    "clawer_unavailable": (503, True),
    "clawer_timeout": (504, True),
    "upstream_auth_failed": (503, True),
    "invalid_upstream_contract": (502, False),
    "internal_error": (503, True),
}


@dataclass(frozen=True)
class WhatsAppLinkStatus:
    state: str
    expires_at: datetime | None
    qr_image: str | None


class StudioWhatsAppLink:
    """Use the fixed Hover → Studio link contract; never call Clawer directly."""

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

    def _request(
        self, *, realm_uuid: UUID, account_external_id: UUID, action: str
    ) -> WhatsAppLinkStatus:
        credential = self.credentials.get(str(realm_uuid))
        if (
            not self.base_url
            or credential is None
            or SERVER_CREDENTIAL_PATTERN.fullmatch(credential) is None
        ):
            raise self._error("clawer_unavailable", retryable=True, status=503)
        method = self.session.get if action == "status" else self.session.post
        suffix = "link" if action == "status" else f"link/{action}"
        try:
            response = method(
                f"{self.base_url}/api/hover/v1/connected-accounts/{account_external_id}/{suffix}",
                headers={"Accept": "application/json", "Authorization": f"Bearer {credential}"},
            )
        except requests.Timeout:
            raise self._error("clawer_timeout", retryable=True, status=504)
        except requests.RequestException:
            raise self._error("clawer_unavailable", retryable=True, status=503)
        request_id = response.headers.get("X-Request-Id")
        if request_id is None or REQUEST_ID_PATTERN.fullmatch(request_id) is None:
            raise self._invalid_contract()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise self._invalid_contract()
        if not response.ok:
            raise self._parse_error(response)
        try:
            payload = response.json()
        except requests.JSONDecodeError:
            raise self._invalid_contract()
        return self._parse_status(payload)

    @staticmethod
    def _error(code: str, *, retryable: bool, status: int) -> ClawerSyncError:
        return ClawerSyncError(
            error_code=code,
            operation="whatsapp_link",
            http_status_code=status,
            retryable=retryable,
        )

    @classmethod
    def _invalid_contract(cls) -> ClawerSyncError:
        return cls._error("invalid_upstream_contract", retryable=False, status=502)

    def _parse_error(self, response: requests.Response) -> ClawerSyncError:
        try:
            payload = response.json()
        except requests.JSONDecodeError:
            return self._invalid_contract()
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return self._invalid_contract()
        code = error.get("code")
        retryable = error.get("retryable")
        if (
            not isinstance(code, str)
            or code not in _STUDIO_LINK_ERROR_STATUS
            or not isinstance(retryable, bool)
            or error.get("operation") != "whatsapp_link"
        ):
            return self._invalid_contract()
        status, expected_retryable = _STUDIO_LINK_ERROR_STATUS[code]
        if response.status_code != status or retryable != expected_retryable:
            return self._invalid_contract()
        return self._error(code, retryable=retryable, status=status)

    def _parse_status(self, payload: object) -> WhatsAppLinkStatus:
        if not isinstance(payload, dict) or set(payload) != {"status", "expires_at", "qr_image"}:
            raise self._invalid_contract()
        state = payload["status"]
        expires_at = payload["expires_at"]
        qr_image = payload["qr_image"]
        if state not in _LINK_STATES:
            raise self._invalid_contract()
        parsed_expiry: datetime | None = None
        if expires_at is not None:
            if not isinstance(expires_at, str) or len(expires_at) > 64:
                raise self._invalid_contract()
            try:
                parsed_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except (ValueError, binascii.Error):
                raise self._invalid_contract()
            if parsed_expiry.tzinfo is None:
                raise self._invalid_contract()
        if qr_image is not None:
            if (
                not isinstance(qr_image, str)
                or len(qr_image) > _QR_IMAGE_MAX_BYTES
                or re.fullmatch(r"[A-Za-z0-9+/=]+", qr_image) is None
            ):
                raise self._invalid_contract()
            try:
                base64.b64decode(qr_image, validate=True)
            except ValueError:
                raise self._invalid_contract()
        if state != "pending" and (parsed_expiry is not None or qr_image is not None):
            raise self._invalid_contract()
        return WhatsAppLinkStatus(state=state, expires_at=parsed_expiry, qr_image=qr_image)

    def start(self, *, realm_uuid: UUID, account_external_id: UUID) -> WhatsAppLinkStatus:
        return self._request(
            realm_uuid=realm_uuid, account_external_id=account_external_id, action="start"
        )

    def retry(self, *, realm_uuid: UUID, account_external_id: UUID) -> WhatsAppLinkStatus:
        return self._request(
            realm_uuid=realm_uuid, account_external_id=account_external_id, action="retry"
        )

    def status(self, *, realm_uuid: UUID, account_external_id: UUID) -> WhatsAppLinkStatus:
        return self._request(
            realm_uuid=realm_uuid, account_external_id=account_external_id, action="status"
        )


def get_whatsapp_link() -> StudioWhatsAppLink:
    return StudioWhatsAppLink()

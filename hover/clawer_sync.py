import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import requests
from django.conf import settings
from django.utils.translation import gettext as _
from pydantic import ValidationError
from typing_extensions import override

from hover.models import Source
from hover.publication_contracts import (
    ClawerPublicationPage,
    DigestPayload,
    ResolvedEvidence,
    ResolvedEvidenceBatch,
)
from hover.source_record_contracts import ClawerSourceRecordPage
from zerver.lib.exceptions import JsonableError
from zerver.lib.outgoing_http import OutgoingSession

MAX_DISCOVERY_LIMIT = 100
MAX_PUBLICATION_LIMIT = 100
MAX_EVIDENCE_LIMIT = 100
MAX_SOURCE_RECORD_LIMIT = 50
MAX_RESPONSE_BYTES = 2_000_000
STUDIO_OPERATION_PATHS = {
    "source_discovery": "sources/discover",
    "sync": "sync",
    "personal_edition_sync": "personal-editions/sync",
    "evidence_resolution": "evidence/resolve",
    "source_records": "records/browse",
}
SERVER_CREDENTIAL_PATTERN = re.compile(r"hvr_srv_[A-Za-z0-9_-]{32,128}")
UNSAFE_DISPLAY_NAME_PATTERN = re.compile(r"(?:\d[\s()+-]*){8,}|@(?:g\.us|lid)$", re.IGNORECASE)
REQUEST_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.IGNORECASE,
)
STUDIO_ERROR_STATUS = {
    "invalid_request": (400, False),
    "unauthorized": (401, False),
    "forbidden": (403, False),
    "connected_account_not_found": (404, False),
    "selector_not_found": (404, False),
    "evidence_not_resolvable": (404, False),
    "rate_limited": (429, True),
    "clawer_unavailable": (503, True),
    "clawer_timeout": (504, True),
    "upstream_auth_failed": (503, True),
    "invalid_upstream_contract": (502, False),
    "internal_error": (503, True),
}


class ClawerSyncError(JsonableError):
    data_fields = [
        "error_code",
        "retryable",
        "operation",
        "retry_after_seconds",
        "upstream_request_id",
    ]

    def __init__(
        self,
        *,
        error_code: str,
        operation: str,
        http_status_code: int,
        retryable: bool,
        retry_after_seconds: int | None = None,
        upstream_request_id: str | None = None,
    ) -> None:
        super().__init__(_("The connected service could not complete this request."))
        self.error_code = error_code
        self.operation = operation
        self.http_status_code = http_status_code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.upstream_request_id = upstream_request_id

    @property
    @override
    def extra_headers(self) -> dict[str, Any]:
        if self.retry_after_seconds is None:
            return {}
        return {"Retry-After": str(self.retry_after_seconds)}


@dataclass(frozen=True)
class ClawerSource:
    source_ref: str
    provider: str
    source_type: str
    display_name: str


@dataclass(frozen=True)
class ClawerSourcePage:
    sources: list[ClawerSource]
    next_cursor: str
    has_more: bool


class ClawerSync(Protocol):
    def discover_sources(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        cursor: str | None,
        limit: int,
        query: str | None,
    ) -> ClawerSourcePage: ...

    def sync_publications(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        cursor: str | None,
        limit: int,
        start_at: str,
    ) -> ClawerPublicationPage: ...

    def sync_personal_editions(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        teammate_ref: str,
        cursor: str | None,
        limit: int,
        start_at: str,
    ) -> ClawerPublicationPage: ...

    def resolve_evidence(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        refs: list[str],
    ) -> list[ResolvedEvidence]: ...

    def browse_source_records(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        start_at: str,
        cursor: str | None,
        limit: int,
        query: str | None,
    ) -> ClawerSourceRecordPage: ...


def _validate_discovery_request(*, cursor: str | None, limit: int, query: str | None) -> None:
    if limit < 1 or limit > MAX_DISCOVERY_LIMIT:
        raise ValueError("invalid discovery limit")
    if cursor is not None and not 1 <= len(cursor) <= 10_000:
        raise ValueError("invalid discovery cursor")
    if query is not None and not 1 <= len(query) <= 100:
        raise ValueError("invalid discovery query")


class InMemoryClawerSync:
    def __init__(
        self,
        sources: Mapping[tuple[str, str], list[ClawerSource]] | None = None,
    ) -> None:
        self.sources = dict(sources or {})
        self.discovery_calls: list[dict[str, object]] = []
        self.publication_pages: dict[tuple[str, str, str, str | None], ClawerPublicationPage] = {}
        self.evidence: dict[tuple[str, str, str], ResolvedEvidence] = {}
        self.sync_calls: list[dict[str, object]] = []
        self.personal_edition_pages: dict[
            tuple[str, str, str, str | None], ClawerPublicationPage
        ] = {}
        self.personal_edition_sync_calls: list[dict[str, object]] = []
        self.evidence_calls: list[dict[str, object]] = []
        self.source_record_pages: dict[
            tuple[str, str, str, str | None, str | None], ClawerSourceRecordPage
        ] = {}
        self.source_record_calls: list[dict[str, object]] = []

    def discover_sources(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        cursor: str | None,
        limit: int,
        query: str | None,
    ) -> ClawerSourcePage:
        _validate_discovery_request(cursor=cursor, limit=limit, query=query)
        self.discovery_calls.append(
            {
                "realm_uuid": realm_uuid,
                "account_external_id": account_external_id,
                "cursor": cursor,
                "limit": limit,
                "query": query,
            }
        )
        offset = 0
        if cursor is not None:
            if not cursor.startswith("memory:") or not cursor.removeprefix("memory:").isdigit():
                raise ClawerSyncError(
                    error_code="invalid_upstream_contract",
                    operation="source_discovery",
                    http_status_code=502,
                    retryable=False,
                )
            offset = int(cursor.removeprefix("memory:"))
        candidates = self.sources.get((str(realm_uuid), str(account_external_id)), [])
        normalized_query = (query or "").strip().casefold()
        if normalized_query:
            candidates = [
                source
                for source in candidates
                if normalized_query in source.display_name.casefold()
            ]
        page = candidates[offset : offset + limit]
        next_offset = offset + len(page)
        return ClawerSourcePage(
            sources=page,
            next_cursor=f"memory:{next_offset}",
            has_more=next_offset < len(candidates),
        )

    def sync_publications(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        cursor: str | None,
        limit: int,
        start_at: str,
    ) -> ClawerPublicationPage:
        _validate_publication_request(
            source_ref=source_ref,
            cursor=cursor,
            limit=limit,
            start_at=start_at,
        )
        self.sync_calls.append(
            {
                "realm_uuid": realm_uuid,
                "account_external_id": account_external_id,
                "source_ref": source_ref,
                "cursor": cursor,
                "limit": limit,
                "start_at": start_at,
            }
        )
        return self.publication_pages.get(
            (str(realm_uuid), str(account_external_id), source_ref, cursor),
            ClawerPublicationPage(
                publications=[],
                next_cursor=cursor or "memory:empty",
                has_more=False,
            ),
        )

    def resolve_evidence(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        refs: list[str],
    ) -> list[ResolvedEvidence]:
        _validate_evidence_request(source_ref=source_ref, refs=refs)
        self.evidence_calls.append(
            {
                "realm_uuid": realm_uuid,
                "account_external_id": account_external_id,
                "source_ref": source_ref,
                "refs": list(refs),
            }
        )
        try:
            return [
                self.evidence[(str(realm_uuid), source_ref, evidence_ref)] for evidence_ref in refs
            ]
        except KeyError:
            raise ClawerSyncError(
                error_code="evidence_not_resolvable",
                operation="evidence_resolution",
                http_status_code=404,
                retryable=False,
            )

    def sync_personal_editions(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        teammate_ref: str,
        cursor: str | None,
        limit: int,
        start_at: str,
    ) -> ClawerPublicationPage:
        _validate_personal_edition_request(
            teammate_ref=teammate_ref,
            cursor=cursor,
            limit=limit,
            start_at=start_at,
        )
        self.personal_edition_sync_calls.append(
            {
                "realm_uuid": realm_uuid,
                "account_external_id": account_external_id,
                "teammate_ref": teammate_ref,
                "cursor": cursor,
                "limit": limit,
                "start_at": start_at,
            }
        )
        page = self.personal_edition_pages.get(
            (str(realm_uuid), str(account_external_id), teammate_ref, cursor),
            ClawerPublicationPage(
                publications=[],
                next_cursor=cursor or "memory:empty",
                has_more=False,
            ),
        )
        _validate_personal_edition_page(page, teammate_ref=teammate_ref, cursor=cursor, limit=limit)
        return page

    def browse_source_records(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        start_at: str,
        cursor: str | None,
        limit: int,
        query: str | None,
    ) -> ClawerSourceRecordPage:
        _validate_source_records_request(
            source_ref=source_ref,
            start_at=start_at,
            cursor=cursor,
            limit=limit,
            query=query,
        )
        self.source_record_calls.append(
            {
                "realm_uuid": realm_uuid,
                "account_external_id": account_external_id,
                "source_ref": source_ref,
                "start_at": start_at,
                "cursor": cursor,
                "limit": limit,
                "query": query,
            }
        )
        page = self.source_record_pages.get(
            (str(realm_uuid), str(account_external_id), source_ref, cursor, query),
            ClawerSourceRecordPage(
                schema_version="1.0", records=[], next_cursor="", has_more=False
            ),
        )
        _validate_source_record_page(
            page,
            source_ref=source_ref,
            start_at=start_at,
            cursor=cursor,
            limit=limit,
        )
        return page


class StudioClawerSync:
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
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        operation: str,
        body: dict[str, object],
    ) -> dict[str, object]:
        credential = self.credentials.get(str(realm_uuid))
        if (
            not self.base_url
            or credential is None
            or SERVER_CREDENTIAL_PATTERN.fullmatch(credential) is None
        ):
            raise ClawerSyncError(
                error_code="clawer_unavailable",
                operation=operation,
                http_status_code=503,
                retryable=True,
            )
        path = STUDIO_OPERATION_PATHS[operation]
        url = f"{self.base_url}/api/hover/v1/connected-accounts/{account_external_id}/{path}"
        try:
            response = self.session.post(
                url,
                json=body,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {credential}",
                    "Content-Type": "application/json",
                },
            )
        except requests.Timeout:
            raise ClawerSyncError(
                error_code="clawer_timeout",
                operation=operation,
                http_status_code=504,
                retryable=True,
            )
        except requests.RequestException:
            raise ClawerSyncError(
                error_code="clawer_unavailable",
                operation=operation,
                http_status_code=503,
                retryable=True,
            )

        upstream_request_id = response.headers.get("X-Request-Id")
        if upstream_request_id is None or REQUEST_ID_PATTERN.fullmatch(upstream_request_id) is None:
            raise self._invalid_contract(operation)
        retry_after = response.headers.get("Retry-After")
        retry_after_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
        if not response.ok:
            raise self._parse_error_response(
                response=response,
                operation=operation,
                upstream_request_id=upstream_request_id,
                retry_after_seconds=retry_after_seconds,
            )
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise self._invalid_contract(operation)
        try:
            payload = response.json()
        except requests.JSONDecodeError:
            raise self._invalid_contract(operation)
        if not isinstance(payload, dict):
            raise self._invalid_contract(operation)
        return payload

    def _parse_error_response(
        self,
        *,
        response: requests.Response,
        operation: str,
        upstream_request_id: str,
        retry_after_seconds: int | None,
    ) -> ClawerSyncError:
        if len(response.content) > MAX_RESPONSE_BYTES:
            return self._invalid_contract(operation)
        try:
            payload = response.json()
        except requests.JSONDecodeError:
            return self._invalid_contract(operation)
        if not isinstance(payload, dict) or set(payload) != {"error"}:
            return self._invalid_contract(operation)
        error = payload["error"]
        if not isinstance(error, dict) or set(error) not in [
            {"code", "message", "retryable", "operation", "request_id"},
            {
                "code",
                "message",
                "retryable",
                "operation",
                "request_id",
                "retry_after_seconds",
            },
        ]:
            return self._invalid_contract(operation)
        code = error["code"]
        message = error["message"]
        retryable = error["retryable"]
        request_id = error["request_id"]
        body_retry_after = error.get("retry_after_seconds")
        if (
            not isinstance(code, str)
            or code not in STUDIO_ERROR_STATUS
            or not isinstance(message, str)
            or not 1 <= len(message) <= 500
            or not isinstance(retryable, bool)
            or error["operation"] != operation
            or request_id != upstream_request_id
            or (body_retry_after is not None and not isinstance(body_retry_after, int))
            or (body_retry_after is not None and body_retry_after < 0)
            or (
                retry_after_seconds is not None
                and body_retry_after is not None
                and retry_after_seconds != body_retry_after
            )
        ):
            return self._invalid_contract(operation)
        expected_status, expected_retryable = STUDIO_ERROR_STATUS[code]
        if response.status_code != expected_status or retryable != expected_retryable:
            return self._invalid_contract(operation)
        return ClawerSyncError(
            error_code=code,
            operation=operation,
            http_status_code=expected_status,
            retryable=retryable,
            retry_after_seconds=(
                body_retry_after if body_retry_after is not None else retry_after_seconds
            ),
            upstream_request_id=upstream_request_id,
        )

    @staticmethod
    def _invalid_contract(operation: str) -> ClawerSyncError:
        return ClawerSyncError(
            error_code="invalid_upstream_contract",
            operation=operation,
            http_status_code=502,
            retryable=False,
        )

    def discover_sources(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        cursor: str | None,
        limit: int,
        query: str | None,
    ) -> ClawerSourcePage:
        _validate_discovery_request(cursor=cursor, limit=limit, query=query)
        body: dict[str, object] = {"limit": limit}
        if cursor is not None:
            body["cursor"] = cursor
        if query is not None:
            body["query"] = query
        payload = self._request(
            realm_uuid=realm_uuid,
            account_external_id=account_external_id,
            operation="source_discovery",
            body=body,
        )
        if set(payload) != {"schema_version", "sources", "next_cursor", "has_more"}:
            raise self._invalid_contract("source_discovery")
        if (
            payload["schema_version"] != "1.0"
            or not isinstance(payload["sources"], list)
            or len(payload["sources"]) > MAX_DISCOVERY_LIMIT
            or not isinstance(payload["next_cursor"], str)
            or not 1 <= len(payload["next_cursor"]) <= 10_000
            or not isinstance(payload["has_more"], bool)
        ):
            raise self._invalid_contract("source_discovery")
        sources: list[ClawerSource] = []
        for raw_source in payload["sources"]:
            if not isinstance(raw_source, dict) or set(raw_source) != {
                "source_ref",
                "provider",
                "source_type",
                "display_name",
            }:
                raise self._invalid_contract("source_discovery")
            source_ref = raw_source["source_ref"]
            provider = raw_source["provider"]
            source_type = raw_source["source_type"]
            display_name = raw_source["display_name"]
            if (
                not isinstance(source_ref, str)
                or not isinstance(provider, str)
                or not isinstance(source_type, str)
                or not isinstance(display_name, str)
                or re.fullmatch(r"src_[0-9a-f]{32}", source_ref) is None
                or not 1 <= len(display_name) <= Source.MAX_DISPLAY_NAME_LENGTH
                or " ".join(display_name.strip().split()) != display_name
                or UNSAFE_DISPLAY_NAME_PATTERN.search(display_name) is not None
                or re.fullmatch(r"[a-z][a-z0-9_]{0,31}", provider) is None
                or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", source_type) is None
            ):
                raise self._invalid_contract("source_discovery")
            sources.append(
                ClawerSource(
                    source_ref=source_ref,
                    provider=provider,
                    source_type=source_type,
                    display_name=display_name,
                )
            )
        return ClawerSourcePage(
            sources=sources,
            next_cursor=payload["next_cursor"],
            has_more=payload["has_more"],
        )

    def sync_publications(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        cursor: str | None,
        limit: int,
        start_at: str,
    ) -> ClawerPublicationPage:
        _validate_publication_request(
            source_ref=source_ref,
            cursor=cursor,
            limit=limit,
            start_at=start_at,
        )
        body: dict[str, object] = {
            "source_ref": source_ref,
            "limit": limit,
            "start_at": start_at,
        }
        if cursor is not None:
            body["cursor"] = cursor
        payload = self._request(
            realm_uuid=realm_uuid,
            account_external_id=account_external_id,
            operation="sync",
            body=body,
        )
        try:
            page = ClawerPublicationPage.model_validate(payload)
        except ValidationError:
            raise self._invalid_contract("sync")
        if any(publication.source_ref != source_ref for publication in page.publications):
            raise self._invalid_contract("sync")
        return page

    def resolve_evidence(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        refs: list[str],
    ) -> list[ResolvedEvidence]:
        _validate_evidence_request(source_ref=source_ref, refs=refs)
        payload = self._request(
            realm_uuid=realm_uuid,
            account_external_id=account_external_id,
            operation="evidence_resolution",
            body={"source_ref": source_ref, "refs": refs},
        )
        try:
            batch = ResolvedEvidenceBatch.model_validate(payload)
        except ValidationError:
            raise self._invalid_contract("evidence_resolution")
        returned_refs = [item.evidence_ref for item in batch.evidence]
        if (
            len(returned_refs) != len(refs)
            or len(set(returned_refs)) != len(returned_refs)
            or set(returned_refs) != set(refs)
            or any(item.source_ref != source_ref for item in batch.evidence)
        ):
            raise self._invalid_contract("evidence_resolution")
        by_ref = {item.evidence_ref: item for item in batch.evidence}
        return [by_ref[ref] for ref in refs]

    def browse_source_records(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        source_ref: str,
        start_at: str,
        cursor: str | None,
        limit: int,
        query: str | None,
    ) -> ClawerSourceRecordPage:
        _validate_source_records_request(
            source_ref=source_ref,
            start_at=start_at,
            cursor=cursor,
            limit=limit,
            query=query,
        )
        body: dict[str, object] = {
            "source_ref": source_ref,
            "start_at": start_at,
            "limit": limit,
        }
        if cursor is not None:
            body["cursor"] = cursor
        if query is not None:
            body["query"] = query
        payload = self._request(
            realm_uuid=realm_uuid,
            account_external_id=account_external_id,
            operation="source_records",
            body=body,
        )
        try:
            page = ClawerSourceRecordPage.model_validate(payload)
        except ValidationError:
            raise self._invalid_contract("source_records")
        try:
            _validate_source_record_page(
                page,
                source_ref=source_ref,
                start_at=start_at,
                cursor=cursor,
                limit=limit,
            )
        except ClawerSyncError:
            raise self._invalid_contract("source_records")
        return page

    def sync_personal_editions(
        self,
        *,
        realm_uuid: UUID,
        account_external_id: UUID,
        teammate_ref: str,
        cursor: str | None,
        limit: int,
        start_at: str,
    ) -> ClawerPublicationPage:
        _validate_personal_edition_request(
            teammate_ref=teammate_ref,
            cursor=cursor,
            limit=limit,
            start_at=start_at,
        )
        body: dict[str, object] = {
            "teammate_ref": teammate_ref,
            "limit": limit,
            "start_at": start_at,
        }
        if cursor is not None:
            body["cursor"] = cursor
        payload = self._request(
            realm_uuid=realm_uuid,
            account_external_id=account_external_id,
            operation="personal_edition_sync",
            body=body,
        )
        try:
            page = ClawerPublicationPage.model_validate(payload)
        except ValidationError:
            raise self._invalid_contract("personal_edition_sync")
        try:
            _validate_personal_edition_page(
                page, teammate_ref=teammate_ref, cursor=cursor, limit=limit
            )
        except ClawerSyncError:
            raise self._invalid_contract("personal_edition_sync")
        return page


def get_clawer_sync() -> ClawerSync:
    return StudioClawerSync()


def _validate_publication_request(
    *, source_ref: str, cursor: str | None, limit: int, start_at: str
) -> None:
    if re.fullmatch(r"src_[0-9a-f]{32}", source_ref) is None:
        raise ValueError("invalid publication source")
    if limit < 1 or limit > MAX_PUBLICATION_LIMIT:
        raise ValueError("invalid publication limit")
    if cursor is not None and not 1 <= len(cursor) <= 10_000:
        raise ValueError("invalid publication cursor")
    if not start_at or len(start_at) > 100:
        raise ValueError("invalid publication start boundary")


def _validate_personal_edition_request(
    *, teammate_ref: str, cursor: str | None, limit: int, start_at: str
) -> None:
    if re.fullmatch(r"person_[0-9a-f]{32}", teammate_ref) is None:
        raise ValueError("invalid personal edition teammate")
    if limit < 1 or limit > MAX_PUBLICATION_LIMIT:
        raise ValueError("invalid personal edition limit")
    if cursor is not None and not 1 <= len(cursor) <= 10_000:
        raise ValueError("invalid personal edition cursor")
    try:
        parsed_start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid personal edition boundary")
    if parsed_start.tzinfo is None or len(start_at) > 100:
        raise ValueError("invalid personal edition boundary")


def _validate_personal_edition_page(
    page: ClawerPublicationPage, *, teammate_ref: str, cursor: str | None, limit: int
) -> None:
    if (
        len(page.publications) > limit
        or (page.has_more and not page.publications)
        or (page.has_more and page.next_cursor == cursor)
    ):
        raise ClawerSyncError(
            error_code="invalid_upstream_contract",
            operation="personal_edition_sync",
            http_status_code=502,
            retryable=False,
        )
    for publication in page.publications:
        payload = publication.payload
        if not isinstance(payload, DigestPayload) or payload.personal is None:
            break
        personal = payload.personal
        expected_producer = (
            "personal_morning_brief" if personal.edition == "morning" else "personal_eod_roundup"
        )
        if personal.teammate_ref != teammate_ref or publication.producer_key != expected_producer:
            break
    else:
        return
    raise ClawerSyncError(
        error_code="invalid_upstream_contract",
        operation="personal_edition_sync",
        http_status_code=502,
        retryable=False,
    )


def _validate_evidence_request(*, source_ref: str, refs: list[str]) -> None:
    if re.fullmatch(r"src_[0-9a-f]{32}", source_ref) is None:
        raise ValueError("invalid evidence source")
    if not refs or len(refs) > MAX_EVIDENCE_LIMIT or len(refs) != len(set(refs)):
        raise ValueError("invalid evidence references")
    if any(not ref or len(ref) > 100 for ref in refs):
        raise ValueError("invalid evidence reference")


def _validate_source_records_request(
    *, source_ref: str, start_at: str, cursor: str | None, limit: int, query: str | None
) -> None:
    if re.fullmatch(r"src_[0-9a-f]{32}", source_ref) is None:
        raise ValueError("invalid Source record Source")
    try:
        parsed_start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid Source record boundary")
    if parsed_start.tzinfo is None or len(start_at) > 100:
        raise ValueError("invalid Source record boundary")
    if cursor is not None and not 1 <= len(cursor) <= 10_000:
        raise ValueError("invalid Source record cursor")
    if not 1 <= limit <= MAX_SOURCE_RECORD_LIMIT:
        raise ValueError("invalid Source record limit")
    if query is not None and (not 1 <= len(query) <= 100 or " ".join(query.split()) != query):
        raise ValueError("invalid Source record query")


def _validate_source_record_page(
    page: ClawerSourceRecordPage,
    *,
    source_ref: str,
    start_at: str,
    cursor: str | None,
    limit: int,
) -> None:
    start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    if (
        len(page.records) > limit
        or (page.has_more and not page.records)
        or (page.has_more and page.next_cursor == cursor)
        or any(
            record.source_ref != source_ref
            or record.timestamp < start
            or (record.reply_context is not None and record.reply_context.timestamp < start)
            for record in page.records
        )
    ):
        raise ClawerSyncError(
            error_code="invalid_upstream_contract",
            operation="source_records",
            http_status_code=502,
            retryable=False,
        )

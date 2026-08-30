from types import SimpleNamespace
from typing import Any, cast
from unittest import TestCase
from unittest.mock import Mock
from uuid import UUID

from hover.actions_summary_executions import SummaryDispatch
from hover.summary_dispatch import StudioSummaryDispatcher
from zerver.lib.exceptions import JsonableError


class StudioSummaryDispatcherContractTest(TestCase):
    realm_uuid = UUID("22222222-2222-4222-8222-222222222222")
    execution_id = UUID("11111111-1111-4111-8111-111111111111")
    request_hash = "a" * 64
    server_credential = f"hvr_srv_{'s' * 40}"
    callback_bearer = f"hvr_exec_{'c' * 40}"

    def dispatch(self) -> SummaryDispatch:
        execution = cast(
            Any,
            SimpleNamespace(id=self.execution_id, request_hash=self.request_hash),
        )
        return SummaryDispatch(
            execution=execution,
            operation={
                "schema_version": "1.0",
                "execution_id": str(self.execution_id),
                "snapshot_hash": "b" * 64,
            },
            callback_bearer=self.callback_bearer,
        )

    def test_organization_scoped_request_omits_callback_origin_and_accepts_exact_contract(
        self,
    ) -> None:
        session = Mock()
        response = Mock(
            status_code=202,
            headers={"X-Request-Id": "33333333-3333-4333-8333-333333333333"},
        )
        response.json.return_value = {
            "schema_version": "1.0",
            "execution_id": str(self.execution_id),
            "status": "accepted",
            "request_hash": self.request_hash,
        }
        session.post.return_value = response
        dispatcher = StudioSummaryDispatcher(
            base_url="https://studio.example",
            credentials={str(self.realm_uuid): self.server_credential},
            session=session,
        )

        dispatcher.dispatch(realm_uuid=self.realm_uuid, dispatch=self.dispatch())

        session.post.assert_called_once()
        call = session.post.call_args
        self.assertEqual(
            call.args[0],
            f"https://studio.example/api/hover/v1/organizations/{self.realm_uuid}/summary-executions",
        )
        self.assertEqual(
            call.kwargs["headers"]["Authorization"],
            f"Bearer {self.server_credential}",
        )
        self.assertEqual(
            set(call.kwargs["json"]),
            {"operation", "callback_bearer"},
        )
        self.assertNotIn("callback_url", call.kwargs["json"])

    def test_missing_organization_credential_and_wrong_response_fail_closed(self) -> None:
        session = Mock()
        dispatcher = StudioSummaryDispatcher(
            base_url="https://studio.example",
            credentials={},
            session=session,
        )
        with self.assertRaises(JsonableError):
            dispatcher.dispatch(realm_uuid=self.realm_uuid, dispatch=self.dispatch())
        session.post.assert_not_called()

        response = Mock(
            status_code=202,
            headers={"X-Request-Id": "33333333-3333-4333-8333-333333333333"},
        )
        response.json.return_value = {
            "schema_version": "1.0",
            "execution_id": str(self.execution_id),
            "status": "accepted",
            "request_hash": "f" * 64,
        }
        session.post.return_value = response
        dispatcher = StudioSummaryDispatcher(
            base_url="https://studio.example",
            credentials={str(self.realm_uuid): self.server_credential},
            session=session,
        )
        with self.assertRaises(JsonableError):
            dispatcher.dispatch(realm_uuid=self.realm_uuid, dispatch=self.dispatch())

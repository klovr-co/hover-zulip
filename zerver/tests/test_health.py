from unittest import mock

from django.test import override_settings

from zerver.lib.exceptions import ServerNotReadyError
from zerver.lib.queue import SimpleQueueClient
from zerver.lib.test_classes import ZulipTestCase
from zerver.views.health import check_rabbitmq


class HealthTest(ZulipTestCase):
    @override_settings(USING_RABBITMQ=True)
    @mock.patch("zerver.views.health.get_queue_client")
    def test_rabbitmq_health_uses_recoverable_connection_check(
        self, get_queue_client: mock.MagicMock
    ) -> None:
        queue_client = mock.create_autospec(SimpleQueueClient, instance=True)
        get_queue_client.return_value = queue_client

        check_rabbitmq()

        queue_client.check_connection.assert_called_once_with()

    def test_healthy(self) -> None:
        # We do not actually use rabbitmq in tests, so this fails
        # unless it's mocked out.
        with mock.patch("zerver.views.health.check_rabbitmq"):
            result = self.client_get("/health")
        self.assert_json_success(result)

    def test_database_failure(self) -> None:
        with (
            mock.patch(
                "zerver.views.health.check_database",
                side_effect=ServerNotReadyError("Cannot query postgresql"),
            ),
            self.assertLogs(level="ERROR") as logs,
            self.assertRaisesRegex(ServerNotReadyError, r"^Cannot query postgresql$"),
        ):
            self.client_get("/health")
        self.assertIn(
            "zerver.lib.exceptions.ServerNotReadyError: Cannot query postgresql", logs.output[0]
        )

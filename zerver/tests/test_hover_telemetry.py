from typing import Any, cast
from unittest import TestCase
from unittest.mock import patch

from hover.telemetry import (
    HoverTelemetryBucket,
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    duration_bucket,
    emit_hover_telemetry,
    emit_hover_telemetry_on_commit,
    lag_bucket,
)


class HoverTelemetryContractTest(TestCase):
    def test_bucket_boundaries_are_fixed(self) -> None:
        self.assertEqual(count_bucket(0), HoverTelemetryBucket.ZERO)
        self.assertEqual(count_bucket(1), HoverTelemetryBucket.ONE)
        self.assertEqual(count_bucket(5), HoverTelemetryBucket.TWO_TO_FIVE)
        self.assertEqual(count_bucket(20), HoverTelemetryBucket.SIX_TO_TWENTY)
        self.assertEqual(count_bucket(21), HoverTelemetryBucket.OVER_TWENTY)
        self.assertEqual(duration_bucket(99), HoverTelemetryBucket.UNDER_100MS)
        self.assertEqual(duration_bucket(2_000), HoverTelemetryBucket.OVER_2S)
        self.assertEqual(lag_bucket(None), HoverTelemetryBucket.UNKNOWN)
        self.assertEqual(lag_bucket(86_400), HoverTelemetryBucket.OVER_1D)

        with self.assertRaises(ValueError):
            count_bucket(-1)
        with self.assertRaises(ValueError):
            duration_bucket(-1)

    def test_log_shape_is_deterministic_and_content_free(self) -> None:
        with patch("hover.telemetry.logger.info") as info:
            emit_hover_telemetry(
                HoverTelemetryEvent.PUBLICATION_SYNC,
                HoverTelemetryOutcome.SUCCESS,
                dimensions={
                    "retryable": False,
                    "realm_id": 7,
                    "lag_bucket": HoverTelemetryBucket.UNDER_1M,
                },
            )

        info.assert_called_once_with(
            "Hover telemetry event=%s outcome=%s%s",
            "publication_sync",
            "success",
            " lag_bucket=under_1m realm_id=7 retryable=false",
        )

    def test_arbitrary_event_outcome_and_dimension_names_are_rejected(self) -> None:
        with patch("hover.telemetry.logger.info") as info:
            with self.assertRaises(TypeError):
                emit_hover_telemetry(
                    cast(Any, "publication_sync"),
                    HoverTelemetryOutcome.SUCCESS,
                )
            with self.assertRaises(TypeError):
                emit_hover_telemetry(
                    HoverTelemetryEvent.PUBLICATION_SYNC,
                    cast(Any, "success"),
                )
            with self.assertRaises(ValueError):
                emit_hover_telemetry(
                    HoverTelemetryEvent.PUBLICATION_SYNC,
                    HoverTelemetryOutcome.SUCCESS,
                    dimensions={"publication_title": 1},
                )
            with self.assertRaises(ValueError):
                emit_hover_telemetry(
                    HoverTelemetryEvent.NOTIFICATION,
                    HoverTelemetryOutcome.CONTRACT_REJECTED,
                )
            with self.assertRaises(ValueError):
                emit_hover_telemetry_on_commit(
                    HoverTelemetryEvent.PUBLICATION_SYNC,
                    HoverTelemetryOutcome.APPROVED,
                )

        info.assert_not_called()

    def test_private_values_never_reach_logger_or_on_commit_queue(self) -> None:
        private_sentinels = [
            "PRIVATE_MESSAGE_SENTINEL",
            "hvr_srv_PRIVATE_CREDENTIAL",
            "+60 12-345 6789",
            '{"evidence":"PRIVATE_EVIDENCE"}',
            "https://private.example.test/evidence/123",
            "10.240.0.8:3000",
        ]

        with (
            patch("hover.telemetry.logger.info") as info,
            patch("hover.telemetry.transaction.on_commit") as on_commit,
        ):
            for sentinel in private_sentinels:
                with self.subTest(sentinel=sentinel), self.assertRaises(TypeError):
                    emit_hover_telemetry(
                        HoverTelemetryEvent.EVIDENCE_RESOLUTION,
                        HoverTelemetryOutcome.SUCCESS,
                        dimensions={"realm_id": sentinel},
                    )
                with self.subTest(on_commit_sentinel=sentinel), self.assertRaises(TypeError):
                    emit_hover_telemetry_on_commit(
                        HoverTelemetryEvent.REVIEW,
                        HoverTelemetryOutcome.RESOLVED,
                        dimensions={"space_id": sentinel},
                    )

        info.assert_not_called()
        on_commit.assert_not_called()

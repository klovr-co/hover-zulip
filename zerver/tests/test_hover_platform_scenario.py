import hashlib
from unittest import TestCase

from zerver.tests.hover_platform_scenario import SCENARIO_FIXTURE, load_hover_platform_scenario


class HoverPlatformScenarioTest(TestCase):
    def test_fixture_covers_cross_provider_platform_workflow(self) -> None:
        fixture_bytes = SCENARIO_FIXTURE.read_bytes()
        expected_checksum = SCENARIO_FIXTURE.with_suffix(".json.sha256").read_text().strip()
        self.assertEqual(hashlib.sha256(fixture_bytes).hexdigest(), expected_checksum)
        scenario = load_hover_platform_scenario()

        self.assertEqual(
            {provider.provider_key for provider in scenario.providers},
            {"whatsapp", "instagram", "github"},
        )
        self.assertEqual(
            {step.kind for step in scenario.steps},
            {
                "generated_update",
                "conflict_detected",
                "suggested_action",
                "todo_created",
                "todo_completed",
                "review_submitted",
                "conflict_resolved",
            },
        )
        self.assertEqual(scenario.publication("generated-update").contract, "feed_update")
        self.assertEqual(
            scenario.publication("conflict-detected").disputed_details[0].field_path,
            "status",
        )
        self.assertEqual(scenario.publication("suggested-action").contract, "suggested_action")

    def test_fixture_is_sanitized_and_not_tied_to_product_demo_logic(self) -> None:
        fixture = SCENARIO_FIXTURE.read_text()
        for forbidden in [
            "aimto",
            "@g.us",
            "hvr_srv_",
            "private.invalid",
            "+60",
            "10.240.",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture.casefold())

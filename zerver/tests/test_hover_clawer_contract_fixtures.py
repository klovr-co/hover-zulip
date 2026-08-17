import hashlib
from pathlib import Path
from typing import Any
from unittest import TestCase

import orjson
from defusedxml import ElementTree as ET  # noqa: N817
from pydantic import ValidationError

from hover.publication_contracts import ClawerPublication, DigestPayload
from hover.source_record_contracts import ClawerSourceRecordPage

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hover" / "clawer_contract"


class HoverClawerContractFixtureTest(TestCase):
    def test_shared_clawer_fixtures_match_accepted_checksums(self) -> None:
        manifest = orjson.loads((FIXTURE_DIR / "manifest.json").read_bytes())

        self.assertEqual(manifest["upstream"], "klovr-co/clawer#393-#397")
        self.assertEqual(
            set(manifest["files"]),
            {
                "whatsapp_digest_v1.json",
                "operational_publications_v1.json",
                "suggested_actions_v1.json",
                "module_publications_v1.json",
                "personal_editions_v1.json",
                "source_records_v1.json",
            },
        )
        for filename, expected_digest in manifest["files"].items():
            with self.subTest(filename=filename):
                fixture = (FIXTURE_DIR / filename).read_bytes()
                self.assertEqual(hashlib.sha256(fixture).hexdigest(), expected_digest)
                orjson.loads(fixture)

    def publication(self, payload: dict[str, Any]) -> ClawerPublication:
        return ClawerPublication.model_validate(
            {
                "publication_id": "pub_fixture_contract",
                "idempotency_key": "hover:fixture:contract",
                "business_identity": "fixture-contract",
                "contract": payload["contract"],
                "schema_version": payload["schema_version"],
                "producer_key": "fixture_producer",
                "producer_name": "Fixture Producer",
                "producing_version": "fixture-v1",
                "run_reference": "run_fixture",
                "source_ref": f"src_{1:032x}",
                "covered_period": {
                    "start": "2026-08-10T00:00:00Z",
                    "end": "2026-08-11T00:00:00Z",
                },
                "payload": payload,
                "evidence_refs": [f"evidence_{1:032x}"],
                "disputed_details": [],
                "importance": "normal",
                "occurred_at": "2026-08-10T12:00:00Z",
                "generated_at": "2026-08-11T00:00:00Z",
                "published_at": "2026-08-11T00:00:01Z",
                "lineage_key": None,
                "parent_publication_id": None,
                "material_change": False,
            }
        )

    def test_shared_fixtures_cross_hover_transport_boundaries(self) -> None:
        digest = orjson.loads((FIXTURE_DIR / "whatsapp_digest_v1.json").read_bytes())
        operational = orjson.loads((FIXTURE_DIR / "operational_publications_v1.json").read_bytes())
        modules = orjson.loads((FIXTURE_DIR / "module_publications_v1.json").read_bytes())
        suggested = orjson.loads((FIXTURE_DIR / "suggested_actions_v1.json").read_bytes())

        payloads = [
            digest["valid"]["payload"],
            operational["feed"],
            operational["progress_blocked"],
            operational["decision_active"],
            modules["marketing_digest"]["output"],
            {**modules["topic_analysis"]["output"], "sentiment": None},
            modules["negative_sentiment_output"],
        ]
        parsed_action = ET.fromstring(f"<root>{suggested['complete']}</root>").find(
            ".//suggested_action"
        )
        assert parsed_action is not None
        wording = parsed_action.findtext("wording")
        due_date = parsed_action.findtext("proposed_due_date")
        assert wording is not None
        payloads.append(
            {
                "contract": "suggested_action",
                "schema_version": "1.0",
                "wording": wording,
                "proposed_assignee": {
                    "kind": "member",
                    "ref": f"person_{2:032x}",
                    "display_name": "Fixture Teammate",
                },
                "proposed_due_date": due_date,
            }
        )

        self.assertEqual(
            {self.publication(payload).contract for payload in payloads},
            {
                "digest",
                "feed_update",
                "progress_update",
                "decision",
                "suggested_action",
                "analysis",
            },
        )

        source_records = orjson.loads((FIXTURE_DIR / "source_records_v1.json").read_bytes())
        self.assertGreater(
            len(ClawerSourceRecordPage.model_validate(source_records["response"]).records),
            0,
        )
        self.assertGreater(
            len(
                ClawerSourceRecordPage.model_validate(source_records["search"]["response"]).records
            ),
            0,
        )
        invalid_source_page = {
            **source_records["response"],
            "records": [
                {
                    **source_records["response"]["records"][0],
                    **source_records["malformed"]["private_fields"],
                },
                *source_records["response"]["records"][1:],
            ],
        }
        with self.assertRaises(ValidationError):
            ClawerSourceRecordPage.model_validate(invalid_source_page)

    def test_personal_edition_fixture_builds_a_strict_digest(self) -> None:
        personal = orjson.loads((FIXTURE_DIR / "personal_editions_v1.json").read_bytes())
        group = personal["groups"][0]
        payload = DigestPayload.model_validate(
            {
                "contract": "digest",
                "schema_version": "1.0",
                "title": "Morning Daily Brief",
                "timezone": personal["timezone"],
                "operation": "The fixture personal edition is ready.",
                "marketing": "Not applicable to this personal edition.",
                "metrics": {
                    "messages": len(personal["messages"]),
                    "text": len(personal["messages"]),
                    "media": 0,
                    "voice": 0,
                },
                "generation_context": personal["producing_version"],
                "personal": {
                    "edition": "morning",
                    "teammate_ref": f"person_{6:032x}",
                    "teammate_display_name": "Fixture Teammate",
                    "morning": {
                        "urgency": [],
                        "unresolved_carryover": [
                            {
                                "title": group["group_name"],
                                "detail": group["age_label"],
                                "operational_publication_ids": [],
                                "confirmed_todo_refs": [],
                            }
                        ],
                        "guidance": [],
                        "all_clear_context": [],
                    },
                    "operational_publication_ids": [],
                    "confirmed_todo_refs": [],
                },
            }
        )
        self.assertEqual(self.publication(payload.model_dump(mode="json")).contract, "digest")

    def test_shared_clawer_fixtures_remain_sanitized(self) -> None:
        accepted_fixture_values = []
        for filename in orjson.loads((FIXTURE_DIR / "manifest.json").read_bytes())["files"]:
            value = orjson.loads((FIXTURE_DIR / filename).read_bytes())
            if filename == "source_records_v1.json":
                value = {key: item for key, item in value.items() if key != "malformed"}
            accepted_fixture_values.append(value)
        fixture_text = orjson.dumps(accepted_fixture_values).decode().casefold()

        for forbidden in ["+60", "10.240.", "private.invalid"]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture_text)

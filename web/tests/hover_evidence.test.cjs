"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");
const hover_evidence = zrequire("hover_evidence");

function grouped_response() {
    return {
        result: "success",
        msg: "",
        groups: [
            {
                topic: {
                    stream_id: 7,
                    topic_name: "GitHub activity",
                    kind: "source",
                    provider_name: "GitHub",
                },
                messages: [
                    {
                        message_id: 42,
                        sender_name: "GitHub",
                        timestamp: 1_786_000_000,
                        rendered_content: "<p>Validated server HTML</p>",
                    },
                ],
            },
            {
                topic: {
                    stream_id: 7,
                    topic_name: "Launch planning",
                    kind: "regular",
                },
                messages: [],
            },
        ],
        forbidden_count: 2,
    };
}

run_test("validates and presents grouped native-message evidence", () => {
    const presented = hover_evidence.present_evidence(grouped_response());
    assert.equal(presented.groups[0].topic.topic_name, "GitHub activity");
    assert.equal(presented.groups[0].messages[0].message_id, 42);
    assert.equal(presented.groups[0].messages[0].can_open_message, true);
    assert.equal(
        presented.groups[0].messages[0].rendered_content_html,
        "<p>Validated server HTML</p>",
    );
    assert.equal(presented.forbidden_count, 2);
});

run_test("adapts the legacy single-Source response at the service boundary", () => {
    const presented = hover_evidence.present_evidence({
        evidence: [
            {
                evidence_ref: `evidence_${"a".repeat(32)}`,
                source_ref: `src_${"b".repeat(32)}`,
                sender: {ref: `person_${"c".repeat(32)}`, display_name: "Participant"},
                timestamp: "2026-08-11T10:00:00Z",
                content: {
                    text: "Source text",
                    voice_transcript: null,
                    media_description: null,
                },
                media: null,
            },
        ],
    });
    assert.equal(presented.groups.length, 1);
    assert.equal(presented.groups[0].topic.kind, "source");
    assert.equal(presented.groups[0].messages[0].sender_name, "Participant");
    assert.equal(presented.groups[0].messages[0].legacy_content.text, "Source text");
    assert.equal(presented.groups[0].messages[0].can_open_message, false);
});

run_test("classifies retryable transport errors and invalid responses", ({override}) => {
    let options;
    override(channel, "post", (request) => {
        options = request;
    });
    const errors = [];
    hover_evidence.fetch_evidence("/json/hover/evidence/1", {
        success() {
            throw new Error("unexpected success");
        },
        error(error) {
            errors.push(error);
        },
    });
    options.error({status: 504, responseJSON: {retryable: true}});
    options.success({unexpected: "shape"});
    assert.deepEqual(errors, [{retryable: true}, {retryable: false}]);
});

run_test("delivers a validated grouped response", ({override}) => {
    override(channel, "post", ({url, success}) => {
        assert.equal(url, "/json/hover/evidence/2");
        success(grouped_response());
    });
    let result;
    hover_evidence.fetch_evidence("/json/hover/evidence/2", {
        success(evidence) {
            result = evidence;
        },
        error() {
            throw new Error("unexpected error");
        },
    });
    assert.equal(result.groups[0].messages[0].message_id, 42);
});

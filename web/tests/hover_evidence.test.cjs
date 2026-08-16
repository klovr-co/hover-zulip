"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");

const hover_evidence = zrequire("hover_evidence");

run_test("renders a semantic loading state before evidence resolves", ({override}) => {
    const $content = $("#evidence-loading");
    const $result = $.create("evidence-loading-result");
    $content.set_find_results(".simplebar-content", []);
    $content.set_find_results("[data-cf-evidence-result]", $result);
    override(channel, "post", () => {});

    hover_evidence.load_evidence($content, "/json/hover/evidence/loading");

    assert.match($content.html(), /cf-evidence-loading/);
    assert.match($content.html(), /role="status"/);
    assert.match($content.html(), /aria-live="polite"/);
    assert.match($content.html(), /aria-busy="true"/);
    assert.match($content.html(), /tabindex="-1"/);
    assert.match($content.html(), /data-cf-evidence-result/);
    assert.match($content.html(), /cf-evidence-loading__placeholder/);
    assert.match($content.html(), /aria-hidden="true"/);
    assert.equal($result.is_focused(), true);
});

run_test("renders validated exact evidence with escaped content", ({override}) => {
    const $content = $("#evidence-content");
    $content.set_find_results(".simplebar-content", []);
    $content.set_find_results("[data-cf-evidence-result]", $.create("evidence-result"));
    override(channel, "post", ({url, success}) => {
        assert.equal(url, "/json/hover/evidence/1");
        success({
            evidence: [
                {
                    evidence_ref: "evidence-1",
                    source_ref: `src_${"a".repeat(32)}`,
                    sender: {ref: `person_${"b".repeat(32)}`, display_name: "Participant"},
                    timestamp: "2026-08-11T10:00:00Z",
                    content: {
                        text: "<script>unsafe()</script>",
                        voice_transcript: null,
                        media_description: null,
                    },
                    media: {
                        type: "image",
                        mime_type: "image/jpeg",
                        byte_size: 42,
                        sha256: null,
                        available: true,
                    },
                },
            ],
        });
    });

    hover_evidence.load_evidence($content, "/json/hover/evidence/1");
    assert.match($content.html(), /Participant/);
    assert.match($content.html(), /Media evidence/);
    assert.doesNotMatch($content.html(), /<script>/);
    assert.match($content.html(), /&lt;script&gt;unsafe\(\)&lt;\/script&gt;/);
});

run_test("distinguishes retryable, missing, and invalid responses", ({override}) => {
    const $content = $("#evidence-errors");
    $content.set_find_results(".simplebar-content", []);
    $content.set_find_results("[data-cf-evidence-result]", $.create("evidence-result"));
    let error;
    let success;
    override(channel, "post", (options) => {
        error = options.error;
        success = options.success;
    });

    hover_evidence.load_evidence($content, "/json/hover/evidence/2");
    error({status: 504, responseJSON: {retryable: true}});
    assert.match($content.html(), /temporarily unavailable/);
    assert.match($content.html(), /data-cf-evidence-retry-url/);
    assert.match($content.html(), /cf-button cf-button--secondary/);
    assert.match($content.html(), /cf-notice cf-notice--warning/);
    assert.doesNotMatch($content.html(), /alert alert-warning|button rounded small/);
    assert.match($content.html(), /\/json\/hover\/evidence\/2/);

    hover_evidence.load_evidence($content, "/json/hover/evidence/2");
    error({status: 404, responseJSON: {retryable: false}});
    assert.match($content.html(), /no longer available/);
    assert.doesNotMatch($content.html(), /data-cf-evidence-retry-url/);

    hover_evidence.load_evidence($content, "/json/hover/evidence/2");
    error({status: 502, responseJSON: {retryable: false}});
    assert.match($content.html(), /no longer available/);
    assert.doesNotMatch($content.html(), /data-cf-evidence-retry-url/);

    hover_evidence.load_evidence($content, "/json/hover/evidence/2");
    success({evidence: [{unexpected: "shape"}]});
    assert.match($content.html(), /no longer available/);
});

run_test("renders an explicit empty exact-evidence state", ({override}) => {
    const $content = $("#evidence-empty");
    $content.set_find_results(".simplebar-content", []);
    $content.set_find_results("[data-cf-evidence-result]", $.create("evidence-result"));
    override(channel, "post", ({success}) => success({evidence: []}));
    hover_evidence.load_evidence($content, "/json/hover/evidence/3");
    assert.match($content.html(), /No exact source messages/);
    assert.match($content.html(), /class="cf-evidence-empty"/);
    assert.match($content.html(), /role="status"/);
    assert.match($content.html(), /aria-live="polite"/);
    assert.match($content.html(), /tabindex="-1"/);
    assert.match($content.html(), /data-cf-evidence-result/);
});

run_test("updates the visible SimpleBar content after the modal opens", ({override}) => {
    const $content = $("#evidence-simplebar");
    const $simplebar_content = $("#evidence-simplebar-inner");
    $content.set_find_results(".simplebar-content", $simplebar_content);
    $content.set_find_results("[data-cf-evidence-result]", $.create("evidence-result"));
    override(channel, "post", ({error}) => {
        error({status: 503, responseJSON: {retryable: true}});
    });

    hover_evidence.load_evidence($content, "/json/hover/evidence/4");
    assert.match($simplebar_content.html(), /temporarily unavailable/);
    assert.match($simplebar_content.html(), /data-cf-evidence-retry-url/);
});

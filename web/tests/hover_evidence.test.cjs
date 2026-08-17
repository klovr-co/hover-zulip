"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
const dialog_widget = mock_esm("../src/dialog_widget");

let body_click_handler;
class FakeElement {
    constructor(closest_result) {
        this.closest_result = closest_result;
    }

    closest() {
        return this.closest_result;
    }
}
set_global("Element", FakeElement);
set_global("document", {
    body: {
        addEventListener(event, handler, options) {
            assert.equal(event, "click");
            assert.deepEqual(options, {capture: true});
            body_click_handler = handler;
        },
    },
});

const hover_evidence = zrequire("hover_evidence");

run_test("renders validated exact evidence with escaped content", ({override}) => {
    const $content = $("#evidence-content");
    $content.set_find_results(".simplebar-content", []);
    $content.set_find_results("[data-hover-evidence-result]", $.create("evidence-result"));
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
    $content.set_find_results("[data-hover-evidence-result]", $.create("evidence-result"));
    let error;
    let success;
    override(channel, "post", (options) => {
        error = options.error;
        success = options.success;
    });

    hover_evidence.load_evidence($content, "/json/hover/evidence/2");
    error({status: 504, responseJSON: {retryable: true}});
    assert.match($content.html(), /temporarily unavailable/);
    assert.match($content.html(), /hover-evidence-retry/);
    assert.match($content.html(), /\/json\/hover\/evidence\/2/);

    hover_evidence.load_evidence($content, "/json/hover/evidence/2");
    error({status: 404, responseJSON: {retryable: false}});
    assert.match($content.html(), /no longer available/);
    assert.doesNotMatch($content.html(), /hover-evidence-retry/);

    hover_evidence.load_evidence($content, "/json/hover/evidence/2");
    error({status: 502, responseJSON: {retryable: false}});
    assert.match($content.html(), /no longer available/);
    assert.doesNotMatch($content.html(), /hover-evidence-retry/);

    hover_evidence.load_evidence($content, "/json/hover/evidence/2");
    success({evidence: [{unexpected: "shape"}]});
    assert.match($content.html(), /no longer available/);
});

run_test("renders an explicit empty exact-evidence state", ({override}) => {
    const $content = $("#evidence-empty");
    $content.set_find_results(".simplebar-content", []);
    $content.set_find_results("[data-hover-evidence-result]", $.create("evidence-result"));
    override(channel, "post", ({success}) => success({evidence: []}));
    hover_evidence.load_evidence($content, "/json/hover/evidence/3");
    assert.match($content.html(), /No exact source messages/);
});

run_test("updates the visible SimpleBar content after the modal opens", ({override}) => {
    const $content = $("#evidence-simplebar");
    const $simplebar_content = $("#evidence-simplebar-inner");
    $content.set_find_results(".simplebar-content", $simplebar_content);
    $content.set_find_results("[data-hover-evidence-result]", $.create("evidence-result"));
    override(channel, "post", ({error}) => {
        error({status: 503, responseJSON: {retryable: true}});
    });

    hover_evidence.load_evidence($content, "/json/hover/evidence/4");
    assert.match($simplebar_content.html(), /temporarily unavailable/);
    assert.match($simplebar_content.html(), /hover-evidence-retry/);
});

run_test("opens the evidence modal and starts loading its URL", ({override}) => {
    const $content = $("#evidence-modal .modal__content");
    $content.set_find_results(".simplebar-content", []);
    let launch_options;
    override(dialog_widget, "launch", (options) => {
        launch_options = options;
        return "evidence-modal";
    });
    override(channel, "post", ({url}) => {
        assert.equal(url, "/json/hover/evidence/5");
    });

    hover_evidence.show_evidence("/json/hover/evidence/5");

    assert.equal(launch_options.modal_title_text, "translated: Sources");
    assert.equal(launch_options.modal_submit_button_text, "translated: Close");
    assert.equal(launch_options.single_footer_button, true);
    assert.equal(launch_options.close_on_submit, true);
});

run_test("routes evidence and retry clicks while ignoring unrelated targets", ({override}) => {
    const $content = $("#evidence-modal .modal__content");
    $content.set_find_results(".simplebar-content", []);
    let post_count = 0;
    override(dialog_widget, "launch", () => "evidence-modal");
    override(channel, "post", () => {
        post_count += 1;
    });
    hover_evidence.initialize();

    body_click_handler({target: {}, preventDefault() {}, stopPropagation() {}});
    body_click_handler({
        target: new FakeElement(null),
        preventDefault() {},
        stopPropagation() {},
    });
    body_click_handler({
        target: new FakeElement({dataset: {}}),
        preventDefault() {},
        stopPropagation() {},
    });

    let prevented = false;
    let stopped = false;
    body_click_handler({
        target: new FakeElement({dataset: {evidenceUrl: "/json/hover/evidence/6"}}),
        preventDefault() {
            prevented = true;
        },
        stopPropagation() {
            stopped = true;
        },
    });
    assert.equal(prevented, true);
    assert.equal(stopped, true);
    assert.equal(post_count, 1);

    const retry_handler = $("body").get_on_handler("click", ".hover-evidence-retry");
    const $retry = $("#retry");
    const $retry_modal = $("#retry-modal");
    $retry_modal.set_find_results(".simplebar-content", []);
    $retry.set_closest_results(".modal__content", $retry_modal);
    retry_handler({preventDefault() {}, currentTarget: $retry[0]});
    assert.equal(post_count, 1);
    $retry.attr("data-evidence-url", "/json/hover/evidence/7");
    retry_handler({preventDefault() {}, currentTarget: $retry[0]});
    assert.equal(post_count, 2);
});

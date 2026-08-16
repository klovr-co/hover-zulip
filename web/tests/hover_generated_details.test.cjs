"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

let body_click_handler;
let current_message;
const launches = [];

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

mock_esm("../src/dialog_widget", {
    launch(options) {
        launches.push(options);
        return "generated-details-modal";
    },
});
mock_esm("../src/hash_util", {by_stream_url: (stream_id) => `/stream/${stream_id}`});
mock_esm("../src/message_store", {get: () => current_message});

const hover_generated_details = zrequire("hover_generated_details");

function generated_item() {
    return {
        module: {name: "Progress Tracker", version: "1.0.0"},
        presentation: {
            label: "Progress update",
            importance: "high",
            state: null,
            occurred_at: "2026-08-11T10:00:00Z",
            generated_at: null,
            published_at: "2026-08-11T10:05:00Z",
            run_reference: "run-42",
        },
        lineage: {
            history: [
                {
                    message_id: 41,
                    title: "Earlier update",
                    state: null,
                    occurred_at: "2026-08-11T09:00:00Z",
                    is_current: false,
                },
            ],
        },
    };
}

run_test("ignores missing generated messages", () => {
    launches.length = 0;
    current_message = undefined;
    hover_generated_details.show(42, false);
    current_message = {id: 42, type: "stream"};
    hover_generated_details.show(42, false);
    assert.equal(launches.length, 0);
});

run_test("renders details and stream history with display timestamps", () => {
    launches.length = 0;
    current_message = {
        id: 42,
        type: "stream",
        stream_id: 7,
        hover_generated_item: generated_item(),
    };

    hover_generated_details.show(42, true);

    const options = launches.at(-1);
    assert.equal(options.modal_title_text, "translated: Update history");
    assert.equal(options.modal_submit_button_text, "translated: Close");
    assert.match(options.modal_content_html, /Progress Tracker/);
    assert.match(options.modal_content_html, /\/stream\/7\/near\/41/);
    assert.equal(options.on_click(), undefined);
});

run_test("uses the message URL for direct-message history", () => {
    launches.length = 0;
    current_message = {
        id: 43,
        type: "private",
        url: "/#narrow/dm/5/near/43",
        hover_generated_item: generated_item(),
    };

    hover_generated_details.show(43, true);

    const options = launches.at(-1);
    assert.equal(options.modal_title_text, "translated: Update history");
    assert.match(options.modal_content_html, /\/#narrow\/dm\/5\/near\/43/);
});

run_test("routes generated details clicks and ignores invalid targets", () => {
    launches.length = 0;
    current_message = {
        id: 44,
        type: "stream",
        stream_id: 7,
        hover_generated_item: generated_item(),
    };
    hover_generated_details.initialize();

    body_click_handler({target: {}, preventDefault() {}, stopPropagation() {}});
    body_click_handler({
        target: new FakeElement(null),
        preventDefault() {},
        stopPropagation() {},
    });
    body_click_handler({
        target: new FakeElement({dataset: {hoverMessageId: "invalid"}, classList: {contains() {}}}),
        preventDefault() {},
        stopPropagation() {},
    });

    let prevented = false;
    let stopped = false;
    body_click_handler({
        target: new FakeElement({
            dataset: {hoverMessageId: "44"},
            classList: {contains: () => true},
        }),
        preventDefault() {
            prevented = true;
        },
        stopPropagation() {
            stopped = true;
        },
    });
    assert.equal(prevented, true);
    assert.equal(stopped, true);
    assert.equal(launches.at(-1).modal_title_text, "translated: Update history");
});

"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const roots = new Map();
mock_esm("../src/message_store", {
    get(id) {
        return roots.get(id);
    },
});
const message_live_update = mock_esm("../src/message_live_update");

const hover_response = zrequire("hover_response");

function generated_message() {
    return {
        id: 42,
        type: "stream",
        hover_generated_item: {
            id: 7,
            reviewed_payload: {venue: "Hall A", date: "Friday"},
            revisions: [],
        },
    };
}

run_test("maps radiogroup navigation keys to response types", () => {
    const {keyboard_response_type} = hover_response._testing;

    assert.equal(keyboard_response_type("review", "ArrowLeft"), "reply");
    assert.equal(keyboard_response_type("reply", "ArrowRight"), "review");
    assert.equal(keyboard_response_type("review", "ArrowUp"), "reply");
    assert.equal(keyboard_response_type("reply", "ArrowDown"), "review");
    assert.equal(keyboard_response_type("review", "Home"), "reply");
    assert.equal(keyboard_response_type("reply", "End"), "review");
    assert.equal(keyboard_response_type("reply", "Tab"), undefined);
});

run_test("configures Reply and explicit Review request metadata", () => {
    hover_response.configure_for_reply(generated_message());
    assert.equal($("#cf-review-composer-controls").prop("hidden"), false);
    assert.deepEqual(hover_response.get_request_data(), {
        hover_generated_item_id: 7,
        hover_response_type: "reply",
    });

    hover_response.select_response_type("review");
    $("#cf-review-field").val("venue");
    $("#cf-review-value").val('"Hall B"');
    assert.deepEqual(hover_response.get_request_data(), {
        hover_generated_item_id: 7,
        hover_response_type: "review",
        hover_review_field: "venue",
        hover_review_value: '"Hall B"',
    });
});

run_test("an ambiguous Review omits patch metadata and clear removes linkage", () => {
    hover_response.configure_for_reply(generated_message());
    hover_response.select_response_type("review");
    assert.deepEqual(hover_response.get_request_data(), {
        hover_generated_item_id: 7,
        hover_response_type: "review",
    });

    hover_response.clear();
    assert.deepEqual(hover_response.get_request_data(), {});
    assert.equal($("#cf-review-composer-controls").prop("hidden"), true);
});

run_test("preselects the exact disputed field for a Review", () => {
    hover_response.configure_for_reply(generated_message());
    hover_response.preselect_review_field("venue");
    $("#cf-review-value").val('"Hall C"');
    assert.deepEqual(hover_response.get_request_data(), {
        hover_generated_item_id: 7,
        hover_response_type: "review",
        hover_review_field: "venue",
        hover_review_value: '"Hall C"',
    });
});

run_test("messages without Hover responses do not touch rendered views", () => {
    hover_response.apply_realtime_responses([{id: 43}]);
});

run_test("realtime response metadata converges and rerenders the root", ({override}) => {
    const root = generated_message();
    roots.set(root.id, root);
    const updated_item = {...root.hover_generated_item, reviewed_payload: {venue: "Hall B"}};
    let rerendered_ids;
    override(message_live_update, "rerender_messages_view_by_message_ids", (ids) => {
        rerendered_ids = ids;
    });

    hover_response.apply_realtime_responses([
        {
            id: 43,
            hover_response: {
                type: "review",
                clarification_required: false,
                root_message_id: 42,
                generated_item: updated_item,
            },
        },
    ]);
    assert.deepEqual(root.hover_generated_item, updated_item);
    assert.deepEqual(rerendered_ids, [42]);
});

run_test("realtime resolution also converges the native Review request", ({override}) => {
    const root = generated_message();
    const request = {
        id: 44,
        hover_review_request: {
            state: "open",
            generated_item: root.hover_generated_item,
        },
    };
    roots.set(root.id, root);
    roots.set(request.id, request);
    const updated_item = {
        ...root.hover_generated_item,
        disputed_details: [
            {
                state: "resolved",
                review_request: {message_id: request.id, state: "resolved"},
            },
        ],
    };
    let rerendered_ids;
    override(message_live_update, "rerender_messages_view_by_message_ids", (ids) => {
        rerendered_ids = ids;
    });

    hover_response.apply_realtime_responses([
        {
            id: 43,
            hover_response: {
                type: "review",
                clarification_required: false,
                root_message_id: root.id,
                generated_item: updated_item,
            },
        },
    ]);
    assert.equal(request.hover_review_request.state, "resolved");
    assert.deepEqual(request.hover_review_request.generated_item, updated_item);
    assert.deepEqual(rerendered_ids, [42, 44]);
});

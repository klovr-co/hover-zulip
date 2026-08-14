"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const roots = new Map([[42, {id: 42, type: "stream"}]]);
const compose_reply = mock_esm("../src/compose_reply");
const hover_response = mock_esm("../src/hover_response");
mock_esm("../src/message_store", {
    get(id) {
        return roots.get(id);
    },
});

const hover_review_request = zrequire("hover_review_request");

run_test("Review action opens the native composer and preselects its field", ({override}) => {
    let reply_options;
    let selected_field;
    override(compose_reply, "respond_to_message", (options) => {
        reply_options = options;
    });
    override(hover_response, "preselect_review_field", (field) => {
        selected_field = field;
    });
    hover_review_request.initialize();
    const $button = $(".cf-review-detail__review")
        .attr("data-cf-review-message-id", "42")
        .attr("data-cf-review-field-path", "status");
    const handler = $("#main_div").get_on_handler("click", ".cf-review-detail__review");
    handler({preventDefault() {}, currentTarget: $button[0]});

    assert.deepEqual(reply_options, {
        message_id: 42,
        keep_composebox_empty: true,
        trigger: "hover review request",
    });
    assert.equal(selected_field, "status");
});

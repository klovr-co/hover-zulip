"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const compose_actions = mock_esm("../src/compose_actions");
const hover_topic_create = zrequire("hover_topic_create");

run_test("Regular creation hands off to native compose without a placeholder", ({override}) => {
    let request;
    override(compose_actions, "start", (options) => {
        request = options;
    });

    hover_topic_create.start_regular(42, "Launch plan", "Hover chooser");

    assert.deepEqual(request, {
        message_type: "stream",
        stream_id: 42,
        topic: "Launch plan",
        trigger: "Hover chooser",
        keep_composebox_empty: true,
    });
});

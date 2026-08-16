"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const activity = mock_esm("../src/activity");
const pm_list = mock_esm("../src/pm_list");
const util = mock_esm("../src/util");

const {set_realm} = zrequire("state_data");
const activity_ui = zrequire("activity_ui");

run_test("initialize presence polling", ({override}) => {
    const realm = make_realm();
    realm.server_presence_ping_interval_seconds = 42;
    set_realm(realm);

    let periodic_callback;
    override(util, "call_function_periodically", (callback, delay) => {
        periodic_callback = callback;
        assert.equal(delay, 42000);
    });

    const redraw_arguments = [];
    override(activity, "send_presence_to_server", (redraw) => {
        redraw_arguments.push(redraw);
    });

    activity_ui.initialize();
    assert.deepEqual(redraw_arguments, [undefined]);

    periodic_callback();
    assert.deepEqual(redraw_arguments, [undefined, activity_ui.redraw]);
});

run_test("redraw refreshes direct messages", ({override}) => {
    let update_count = 0;
    override(pm_list, "update_private_messages", () => {
        update_count += 1;
    });

    activity_ui.redraw();
    assert.equal(update_count, 1);
});

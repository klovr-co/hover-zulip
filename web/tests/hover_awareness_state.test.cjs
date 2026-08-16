"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const hover_awareness_state = zrequire("hover_awareness_state");

run_test("tracks the active awareness surface", () => {
    assert.equal(hover_awareness_state.get_surface(), undefined);

    hover_awareness_state.set_surface("for_you");
    assert.equal(hover_awareness_state.get_surface(), "for_you");

    hover_awareness_state.set_surface("team_pulse");
    assert.equal(hover_awareness_state.get_surface(), "team_pulse");

    hover_awareness_state.clear();
    assert.equal(hover_awareness_state.get_surface(), undefined);
});

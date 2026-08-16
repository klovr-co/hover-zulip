"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const hover = zrequire("hover");

run_test("recognizes only messages carrying generated-item metadata", () => {
    assert.equal(hover.is_generated_update({hover_generated_item: {id: 1}}), true);
    assert.equal(hover.is_generated_update({hover_generated_item: undefined}), false);
});

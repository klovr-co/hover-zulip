"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const hover = zrequire("hover");

run_test("recognizes only messages carrying generated-item metadata", () => {
    assert.equal(hover.is_generated_update({hover_generated_item: {id: 1}}), true);
    assert.equal(hover.is_generated_update({hover_generated_item: undefined}), false);
});

run_test("normalizes source integrations to the Cofounder view model", () => {
    assert.deepEqual(
        hover.normalize_source_integrations([
            {
                id: 1,
                key: "github",
                name: "GitHub",
                icon_class: "fa fa-github",
                count: 2,
                url: "https://github.com/zulip/zulip",
            },
        ]),
        [
            {
                id: 1,
                key: "github",
                name: "GitHub",
                count: 2,
                url: "https://github.com/zulip/zulip",
            },
        ],
    );
});

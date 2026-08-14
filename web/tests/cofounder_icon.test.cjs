"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const cofounder_icon = zrequire("cofounder/components/icon");

run_test("replaces a Cofounder icon with a typed state icon", () => {
    const calls = [];
    const $root = {
        find(selector) {
            calls.push(["find", selector]);
            return {
                replaceWith(html) {
                    calls.push(["replaceWith", html]);
                },
            };
        },
    };

    cofounder_icon.replace_icon($root, "loader-circle");

    assert.equal(calls[0][1], ".cf-icon");
    assert.match(calls[1][1], /cf-icon--compact cf-icon--spinner/);
    assert.match(calls[1][1], /M21 12a9 9/);
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("check"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("inbox"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("alarm"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("hash"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("lock"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("globe"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("archive"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("eye"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("users"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("panel-left"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("settings"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("bot"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("chevron-right"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("messages"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("folder-cog"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("user-group-x"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("grip-vertical"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("play"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("shield"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("sort-ascending"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("circle-off"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("home"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("pin-off"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("sparkles"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("masked-unread"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("keyboard"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("building"));
    assert.ok(cofounder_icon.COFOUNDER_ICON_NAMES.includes("log-out"));
    assert.equal(cofounder_icon.is_icon_name("trash"), true);
    assert.equal(cofounder_icon.is_icon_name("not-a-real-icon"), false);
});

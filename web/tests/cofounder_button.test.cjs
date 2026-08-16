"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const cofounder_button = zrequire("cofounder/components/button");

run_test("changes a Cofounder button variant", () => {
    const classes = new Set(["cf-button", "cf-button--primary", "save-button"]);
    const $button = {
        addClass(class_name) {
            classes.add(class_name);
        },
        attr(name) {
            assert.equal(name, "class");
            return [...classes].join(" ");
        },
        removeClass(class_name) {
            classes.delete(class_name);
        },
    };

    cofounder_button.set_button_variant($button, "success");

    assert.deepEqual(classes, new Set(["cf-button", "save-button", "cf-button--success"]));
});

run_test("ignores non-Cofounder buttons", () => {
    const classes = new Set(["action-button", "action-button-solid-brand"]);
    const $button = {
        addClass() {
            assert.fail("should not add a class");
        },
        attr() {
            return [...classes].join(" ");
        },
        removeClass() {
            assert.fail("should not remove a class");
        },
    };

    cofounder_button.set_button_variant($button, "success");
});

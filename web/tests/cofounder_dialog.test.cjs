"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const cofounder_dialog = zrequire("cofounder/components/dialog");

function make_dialog_stub() {
    const state = {
        busy: undefined,
        buttons_disabled: undefined,
    };
    const $buttons = {
        prop(name, value) {
            assert.equal(name, "disabled");
            state.buttons_disabled = value;
        },
    };
    const $submit_button = {
        attr(name, value) {
            assert.equal(name, "aria-busy");
            state.busy = value;
        },
    };
    const $dialog = {
        find(selector) {
            if (selector === ".cf-dialog__button") {
                return $buttons;
            }
            assert.equal(selector, ".cf-dialog__submit");
            return $submit_button;
        },
    };
    return {$dialog, state};
}

run_test("sets the Cofounder dialog loading state", () => {
    const {$dialog, state} = make_dialog_stub();

    cofounder_dialog.set_dialog_loading($dialog, true);

    assert.deepEqual(state, {busy: "true", buttons_disabled: true});
});

run_test("clears the Cofounder dialog loading state", () => {
    const {$dialog, state} = make_dialog_stub();

    cofounder_dialog.set_dialog_loading($dialog, false);

    assert.deepEqual(state, {busy: "false", buttons_disabled: false});
});

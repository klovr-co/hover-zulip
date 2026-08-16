"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const cofounder_menu = zrequire("cofounder/components/menu");

run_test("selects enabled Cofounder menu items", () => {
    const $items = {};
    const $root = {
        find(selector) {
            assert.equal(selector, cofounder_menu.COFOUNDER_MENU_ITEM_SELECTOR);
            return $items;
        },
    };

    assert.equal(cofounder_menu.get_menu_items($root), $items);
    assert.match(cofounder_menu.COFOUNDER_MENU_ITEM_SELECTOR, /cf-menu__action/);
    assert.match(cofounder_menu.COFOUNDER_MENU_ITEM_SELECTOR, /menuitemradio/);
});

run_test("synchronizes menu radio state from native inputs", () => {
    function choice(initial_value) {
        let value = initial_value;
        return {
            getAttribute(name) {
                assert.equal(name, "role");
                return "menuitemradio";
            },
            setAttribute(name, next_value) {
                assert.equal(name, "aria-checked");
                value = next_value;
            },
            value() {
                return value;
            },
        };
    }

    const first_choice = choice("false");
    const second_choice = choice("true");
    const root = {
        querySelectorAll(selector) {
            assert.equal(selector, "input[type='radio']");
            return [
                {checked: true, nextElementSibling: first_choice},
                {checked: false, nextElementSibling: second_choice},
            ];
        },
    };

    cofounder_menu.sync_menuitemradio_checked_state(root);

    assert.equal(first_choice.value(), "true");
    assert.equal(second_choice.value(), "false");
});

run_test("focuses a Cofounder menu item", () => {
    const calls = [];
    const $items = {
        eq(index) {
            calls.push(["eq", index]);
            return {
                length: 1,
                trigger(event) {
                    calls.push(["trigger", event]);
                },
            };
        },
    };

    cofounder_menu.focus_first_menu_item($items, 2);

    assert.deepEqual(calls, [
        ["eq", 2],
        ["trigger", "focus"],
    ]);
});

run_test("does not focus when the requested menu item is missing", () => {
    const calls = [];
    const $items = {
        eq(index) {
            calls.push(["eq", index]);
            return {
                length: 0,
                trigger(event) {
                    calls.push(["trigger", event]);
                },
            };
        },
    };

    cofounder_menu.focus_first_menu_item($items, 4);

    assert.deepEqual(calls, [["eq", 4]]);
});

run_test("does not activate a menu item when focus has left the menu", () => {
    const calls = [];
    const $items = {
        eq(index) {
            calls.push(["eq", index]);
            return {
                trigger(event) {
                    calls.push(["trigger", event]);
                },
            };
        },
        filter() {
            return {};
        },
        index() {
            return -1;
        },
    };

    cofounder_menu.menu_items_handle_keyboard("enter", $items);

    assert.deepEqual(calls, []);
});

run_test("Enter activates exactly the focused menu item", () => {
    const calls = [];
    const $items = {
        eq(index) {
            calls.push(["eq", index]);
            return {
                trigger(event) {
                    calls.push(["trigger", event]);
                },
            };
        },
        filter() {
            return {};
        },
        index() {
            return 1;
        },
    };

    cofounder_menu.menu_items_handle_keyboard("enter", $items);

    assert.deepEqual(calls, [
        ["eq", 1],
        ["trigger", "click"],
    ]);
});

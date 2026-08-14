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

run_test("focuses a Cofounder menu item", () => {
    const calls = [];
    const $items = {
        eq(index) {
            calls.push(["eq", index]);
            return {
                expectOne() {
                    calls.push(["expectOne"]);
                    return this;
                },
                trigger(event) {
                    calls.push(["trigger", event]);
                },
            };
        },
    };

    cofounder_menu.focus_first_menu_item($items, 2);

    assert.deepEqual(calls, [["eq", 2], ["expectOne"], ["trigger", "focus"]]);
});

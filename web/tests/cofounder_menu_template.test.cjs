"use strict";

const assert = require("node:assert/strict");

const {run_test} = require("./lib/test.cjs");

const render_menu_example = require("../stories/templates/cofounder_menu_example.hbs");

run_test("renders the standalone Cofounder menu contract", () => {
    const html = render_menu_example();

    assert.match(html, /class="cf-menu"/);
    assert.match(html, /<ul role="menu" class="cf-menu__list">/);
    assert.match(html, /<li role="none" class="cf-menu__item">/);
    assert.match(html, /role="menuitem" class="cf-menu__action/);
    assert.match(html, /cf-menu__action--danger/);
    assert.match(html, /role="menuitem" class="cf-menu__action" disabled/);
    assert.match(html, /<kbd class="cf-menu__shortcut-key">/);
    assert.match(html, /<svg class="cf-icon cf-icon--compact cf-menu__icon"/);
    assert.doesNotMatch(html, /popover-menu/);
    assert.doesNotMatch(html, /zulip-icon/);
});

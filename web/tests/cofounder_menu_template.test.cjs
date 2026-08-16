"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_menu_example = require("../stories/templates/cofounder_menu_example.hbs");

const {run_test} = require("./lib/test.cjs");

const menu_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/menu.css"),
    "utf8",
);

run_test("renders the standalone Cofounder menu contract", () => {
    const html = render_menu_example();

    assert.match(html, /class="cf-menu"/);
    assert.match(
        html,
        /<ul role="menu" class="cf-menu__list" aria-label="translated: Workspace actions">/,
    );
    assert.match(html, /<li role="none" class="cf-menu__item">/);
    assert.match(html, /role="menuitem" class="cf-menu__action/);
    assert.match(html, /cf-menu__action--danger/);
    assert.match(
        html,
        /<a role="menuitem" class="cf-menu__action" aria-disabled="true" tabindex="-1">/,
    );
    assert.doesNotMatch(html, /href="#disabled-target"|target="_blank"|rel="noopener"/);
    assert.match(html, /<kbd class="cf-menu__shortcut-key">/);
    assert.match(html, /<svg class="cf-icon cf-icon--compact cf-menu__icon"/);
    assert.match(html, /class="tippy-box" data-theme="cofounder-menu"/);
    assert.doesNotMatch(html, /style=/);
    assert.doesNotMatch(html, /popover-menu/);
    assert.doesNotMatch(html, /zulip-icon/);
    assert.match(
        menu_css,
        /\.cf-menu__shortcut,\s*\.cf-menu \.popover-menu-hotkey-hints\s*{[^}]*max-width:\s*45%/s,
    );
    assert.match(
        menu_css,
        /\.cf-menu__shortcut-key,\s*\.cf-menu \.popover-menu-hotkey-hint\s*{[^}]*max-width:\s*100%[^}]*overflow:\s*hidden[^}]*text-overflow:\s*ellipsis/s,
    );
});

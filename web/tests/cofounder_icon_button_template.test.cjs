"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_icon_button = require("../templates/components/icon_button.hbs");

const {run_test} = require("./lib/test.cjs");

const component_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/icon-button.css"),
    "utf8",
);

run_test("shared icon button delegates to the Cofounder contract", () => {
    const html = render_icon_button({
        "aria-label": "Delete item",
        custom_classes: "dropdown-list-delete",
        component_classes: "cf-copy-field__button",
        "data-clipboard-text": "copy me",
        "data-tippy-content": "Delete item",
        disabled: false,
        hidden: false,
        icon: "trash",
        intent: "danger",
        squared: true,
    });

    assert.match(html, /class="cf-icon-button cf-icon-button--danger cf-icon-button--square/);
    assert.match(html, /dropdown-list-delete icon-button icon-button-danger icon-button-square/);
    assert.match(html, /cf-copy-field__button dropdown-list-delete/);
    assert.match(html, /aria-label="Delete item"/);
    assert.match(html, /data-tippy-content="Delete item"/);
    assert.match(html, /data-clipboard-text="copy me"/);
    assert.match(html, /M3 6h18/);
    assert.doesNotMatch(html, /zulip-icon|<i/);
});

run_test("icon button preserves modal and disabled behavior attributes", () => {
    const html = render_icon_button({
        "aria-label": "Close",
        "data-micromodal-close": true,
        disabled: true,
        hidden: true,
        icon: "close",
        intent: "neutral",
        squared: false,
    });

    assert.match(html, /cf-icon-button--neutral/);
    assert.match(html, /icon-button-neutral hide/);
    assert.match(html, /data-micromodal-close/);
    assert.match(html, / disabled/);
});

run_test("new Cofounder surfaces can omit the legacy icon-button bridge", () => {
    const html = render_icon_button({
        "aria-controls": "members-list",
        "aria-label": "Toggle members",
        expanded: false,
        has_expanded_state: true,
        icon: "chevron-right",
        intent: "neutral",
        omit_legacy_classes: true,
    });

    assert.match(html, /class="cf-icon-button cf-icon-button--neutral/);
    assert.match(html, /aria-expanded="false"/);
    assert.match(html, /aria-controls="members-list"/);
    assert.doesNotMatch(html, /(?:^|[\s"])icon-button(?:[\s"]|$)|icon-button-neutral/);
});

run_test("icon button exposes checkbox state independently of its icon", () => {
    const html = render_icon_button({
        "aria-label": "Select draft",
        checked: false,
        has_checked_state: true,
        icon: "square",
        intent: "neutral",
        omit_legacy_classes: true,
        role: "checkbox",
    });

    assert.match(html, /role="checkbox"/);
    assert.match(html, /aria-checked="false"/);
    assert.match(html, /<rect x="4" y="4" width="16" height="16" rx="2">/);
    assert.doesNotMatch(html, /fa-square|zulip-icon/);
});

run_test("semantic intent states use explicit soft background colors", () => {
    for (const intent of ["accent", "success", "warning", "danger"]) {
        assert.match(
            component_css,
            new RegExp(`background-color: var\\(--cf-color-${intent}-soft\\)`),
        );
    }
    assert.ok(
        component_css.lastIndexOf("background-color: var(--cf-color-surface-pressed)") >
            component_css.lastIndexOf("background-color: var(--cf-color-danger-soft)"),
    );
    assert.doesNotMatch(component_css, /\bbackground:/);
});

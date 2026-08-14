"use strict";

const assert = require("node:assert/strict");

const {run_test} = require("./lib/test.cjs");

const render_banner = require("../templates/components/banner.hbs");

run_test("renders the standalone Cofounder banner contract", () => {
    const html = render_banner({
        buttons: [
            {label: "Review", variant: "secondary"},
            {custom_classes: "dismiss-example", label: "Dismiss", variant: "ghost"},
        ],
        close_button: true,
        intent: "warning",
        label: "A source needs review.",
        process: "source-review",
    });

    assert.match(html, /role="alert"/);
    assert.match(html, /data-process="source-review"/);
    assert.match(html, /class="cf-banner cf-banner--warning"/);
    assert.match(html, /class="cf-banner__content"/);
    assert.match(html, /class="cf-banner__label"/);
    assert.match(html, /class="cf-banner__actions"/);
    assert.match(html, /cf-button--secondary/);
    assert.match(html, /cf-button--ghost dismiss-example/);
    assert.match(html, /cf-button--ghost cf-button--icon-only cf-banner__close/);
    assert.match(html, /<svg class="cf-icon"/);
    assert.doesNotMatch(html, /action-button/);
    assert.doesNotMatch(html, /icon-button/);
    assert.doesNotMatch(html, /zulip-icon/);
    assert.doesNotMatch(html, /class="(?:[^"]+ )?banner(?: |")/);
});

run_test("uses a polite status role for non-urgent feedback", () => {
    const html = render_banner({
        buttons: [],
        close_button: false,
        intent: "success",
        label: "Source saved.",
    });

    assert.match(html, /role="status"/);
    assert.match(html, /cf-banner--success/);
    assert.doesNotMatch(html, /cf-banner__close/);
});

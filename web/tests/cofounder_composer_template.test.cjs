"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_composer = require("../templates/cofounder/components/composer.hbs");
const render_compose = require("../templates/compose.hbs");
const render_compose_controls = require("../templates/compose_control_buttons.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("production compose shell is owned by Cofounder classes", () => {
    const html = render_compose({embedded: true, file_upload_enabled: true});

    assert.match(html, /id="compose-content" class="cf-composer cf-composer--production"/);
    assert.match(html, /id=["']compose-textarea["']/);
    assert.match(html, /id="compose-send-button"/);
    assert.match(html, /class="loader" alt="" src="\/static\/images\/loading\/loader-white\.svg"/);
    assert.match(html, /cf-composer__send-icon/);
    assert.match(
        html,
        /id="compose_select_recipient_widget" class="dropdown-widget-button cf-dropdown-trigger[^>]*>[\s\S]*?<svg class="cf-icon/,
    );
    assert.match(
        html,
        /id="compose_select_recipient_widget"[^>]*aria-hidden="true"[^>]*tabindex="-1"/,
    );
    assert.match(html, /id="send_later"/);
    assert.match(html, /id=["']compose_close["']/);
    assert.match(html, /id="cf-review-composer-controls" class="cf-review-composer"/);
    assert.match(html, /class="cf-review-composer__mode" data-cf-response-mode="review"/);
    assert.match(html, /id="cf-review-field" class="cf-field__control"/);
    assert.match(html, /id="cf-review-value" class="cf-field__control"/);
    assert.doesNotMatch(
        html,
        /zulip-icon-send|zulip-icon-more-vertical|id='compose_close'[^>]*zulip-icon|hover-response-controls|hover-response-type|hover-review-patch|data-hover-reply-help/,
    );
});

run_test("standalone composer exposes visual states without legacy icons", () => {
    const html = render_composer({
        channel: "design",
        disabled: true,
        placeholder: "Compose a message",
        recipient: "Homepage redesign",
        value: "",
    });

    assert.match(html, /cf-composer--standalone/);
    assert.match(html, /cf-composer__recipient-channel">design/);
    assert.match(html, /cf-composer__recipient-separator" aria-hidden="true">\//);
    assert.match(html, /cf-composer__send-button/);
    assert.match(html, /disabled/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/composer.css"),
        "utf8",
    );
    assert.match(
        component_css,
        /\.cf-composer__recipient-separator\s*{[^}]*color: var\(--cf-text-secondary\)/s,
    );
});

run_test("production formatting controls use typed Cofounder icons", () => {
    const html = render_compose_controls({
        file_upload_enabled: true,
        giphy_enabled: true,
        klipy_enabled: false,
        message_id: undefined,
        preview_mode_on: false,
        tenor_enabled: false,
    });

    assert.match(html, /cf-composer__toolbar-actions/);
    assert.match(html, /cf-composer__toolbar-action/);
    assert.match(html, /compose_upload_file/);
    assert.match(html, /data-format-type="bold"/);
    assert.match(html, /add-poll/);
    assert.match(html, /compose_help_button/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
});

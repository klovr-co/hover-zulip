"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_notice_example = require("../stories/templates/cofounder_notice_example.hbs");
const render_permissions_error = require("../templates/user_group_settings/cannot_deactivate_group_banner.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("renders the standalone Cofounder notice contract", () => {
    const html = render_notice_example();
    const notice_template = fs.readFileSync(
        path.join(__dirname, "../templates/cofounder/components/notice.hbs"),
        "utf8",
    );
    const notice_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/notice.css"),
        "utf8",
    );
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_notice.stories.ts"),
        "utf8",
    );

    assert.match(html, /id="cofounder-notice-review"/);
    assert.equal((html.match(/role="status"/g) ?? []).length, 2);
    assert.match(html, /class="cf-notice cf-notice--warning"/);
    assert.match(html, /class="cf-notice cf-notice--success"/);
    assert.match(html, /class="cf-notice__body"/);
    assert.match(html, /class="cf-notice__content"/);
    assert.match(html, /class="cf-notice__actions"/);
    assert.match(html, /cf-button--secondary cf-notice__action/);
    assert.match(html, /cf-button--ghost cf-button--icon-only cf-notice__close/);
    assert.match(html, /<svg class="cf-icon"/);
    assert.doesNotMatch(html, /main-view-banner/);
    assert.doesNotMatch(html, /action-button/);
    assert.doesNotMatch(html, /zulip-icon/);
    assert.match(notice_template, /#if role/);
    assert.match(notice_css, /\.cf-notice \{[\s\S]*min-width: 0;[\s\S]*max-width: 100%/);
    assert.match(notice_css, /\.cf-notice__actions \{[\s\S]*box-sizing: border-box/);
    assert.match(notice_css, /\.cf-notice__actions \.cf-button \{[\s\S]*overflow-wrap: anywhere/);
    assert.match(story, /Review notice dismissed\./);
    assert.match(story, /\.cf-notice:not\(\[hidden\]\) \.cf-notice__action/);
    assert.match(story, /Source review opened\./);
    assert.match(story, /Source published\./);
});

run_test("forwards caller state through the notice block", () => {
    const html = render_permissions_error({group_used_for_permissions: true});
    const user_group_edit = fs.readFileSync(
        path.join(__dirname, "../src/user_group_edit.ts"),
        "utf8",
    );
    const subscriptions_css = fs.readFileSync(
        path.join(__dirname, "../styles/subscriptions.css"),
        "utf8",
    );
    const notice_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/notice.css"),
        "utf8",
    );
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_product_notices.stories.ts"),
        "utf8",
    );

    assert.match(html, /remove all permissions assigned to it/);
    assert.match(html, /cf-notice__action permissions-button/);
    assert.match(html, /View permissions/);
    assert.match(html, /role="alert"/);
    assert.doesNotMatch(html, /currently a subgroup/);
    assert.doesNotMatch(html, /cf-notice__close/);
    assert.match(
        user_group_edit,
        /dialog_widget\.close\(\(\) => \{[\s\S]*data-tab-key="permissions"[\s\S]*trigger\("focus"\)/,
    );
    assert.match(
        subscriptions_css,
        /#deactivation-confirm-modal[\s\S]*\.alert \{[\s\S]*padding: 0;[\s\S]*background-color: transparent/,
    );
    assert.doesNotMatch(
        subscriptions_css,
        /\.cannot-deactivate-group-banner \{[\s\S]{0,100}border: none/,
    );
    assert.doesNotMatch(subscriptions_css, /\.permissions-button \{[\s\S]*text-wrap: nowrap/);
    assert.match(
        notice_css,
        /\.cf-notice--error \.cf-notice__actions \.cf-button--secondary \{\s*border-color: var\(--cf-color-danger\)/,
    );
    assert.match(story, /function render_permissions_error_notice/);
    assert.match(story, /Permissions panel selected\./);
    assert.match(story, /Return to permissions error/);
    assert.match(story, /permissions\?\.focus\(\)/);
});

"use strict";

const assert = require("node:assert/strict");

const {run_test} = require("./lib/test.cjs");

const render_notice_example = require("../stories/templates/cofounder_notice_example.hbs");
const render_permissions_error = require("../templates/user_group_settings/cannot_deactivate_group_banner.hbs");

run_test("renders the standalone Cofounder notice contract", () => {
    const html = render_notice_example();

    assert.match(html, /id="cofounder-notice-review"/);
    assert.match(html, /role="alert"/);
    assert.match(html, /role="status"/);
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
});

run_test("forwards caller state through the notice block", () => {
    const html = render_permissions_error({group_used_for_permissions: true});

    assert.match(html, /remove all permissions assigned to it/);
    assert.match(html, /cf-notice__action permissions-button/);
    assert.match(html, /View permissions/);
    assert.doesNotMatch(html, /currently a subgroup/);
});

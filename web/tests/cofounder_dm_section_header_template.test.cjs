"use strict";

const assert = require("node:assert/strict");

const render_dm_section_header = require("../templates/cofounder/components/dm_section_header.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("sidebar DM header renders the Cofounder control contract", () => {
    const html = render_dm_section_header({
        custom_classes: "zoomed-out",
        has_filter: false,
        has_toggle: true,
        id: "direct-messages-section-header",
        is_modal: false,
        title: "Direct messages",
    });

    assert.match(html, /id="direct-messages-section-header" class="cf-dm-section-header/);
    assert.match(html, /<button id="toggle-direct-messages-section-icon"[^>]+rotate-icon-down/);
    assert.match(html, /class="cf-dm-section-header__title left-sidebar-title"/);
    assert.match(html, /<a class="cf-dm-section-header__action show-all-direct-messages/);
    assert.match(
        html,
        /<button type="button" class="cf-dm-section-header__action compose-new-direct-message/,
    );
    assert.match(html, /cf-dm-section-header__badge unread_count/);
    assert.doesNotMatch(html, /zulip-icon|<i/);
});

run_test("modal DM header keeps its filter slot without a collapse toggle", () => {
    const html = render_dm_section_header({
        custom_classes: "",
        has_filter: true,
        has_toggle: false,
        id: "direct-messages-modal-section-header",
        is_modal: true,
        title: "All direct messages",
    });

    assert.match(html, /cf-dm-section-header--modal/);
    assert.match(html, /class="cf-dm-section-header__filter"/);
    assert.doesNotMatch(html, /toggle-direct-messages-section-icon/);
});

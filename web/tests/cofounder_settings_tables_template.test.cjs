"use strict";

const assert = require("node:assert/strict");

const render_drag_handle = require("../templates/cofounder/components/drag_handle.hbs");
const render_active_users = require("../templates/settings/active_user_list_admin.hbs");
const render_api_key = require("../templates/settings/api_key_modal.hbs");
const render_filter = require("../templates/settings/filter_text_input.hbs");
const render_stream_members = require("../templates/stream_settings/stream_members_table.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("Settings lists render the Cofounder data-table and filter contracts", () => {
    const html = render_active_users({
        active_user_list_dropdown_widget_name: "active-user-filter",
        is_admin: true,
    });

    assert.match(html, /cf-data-table cf-data-table--settings/);
    assert.match(html, /cf-dropdown-trigger/);
    assert.match(html, /cf-filter-field/);
    assert.match(html, /table-sortable-arrow/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/);
});

run_test("Shared settings controls use typed drag, filter, and password actions", () => {
    const drag_html = render_drag_handle({hidden: false});
    const filter_html = render_filter({aria_label: "Filter users", placeholder: "Filter"});
    const api_key_html = render_api_key({});

    assert.match(drag_html, /cf-drag-handle move-handle/);
    assert.match(drag_html, /cf-icon/);
    assert.match(filter_html, /cf-filter-field__input/);
    assert.match(filter_html, /aria-label="[^"]*Clear filter"/);
    assert.match(api_key_html, /cf-password-toggle/);
    assert.match(api_key_html, /cf-password-toggle__show/);
    assert.match(api_key_html, /copy-button/);
    assert.doesNotMatch(
        `${drag_html}${filter_html}${api_key_html}`,
        /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/,
    );
});

run_test("Membership lists share the Cofounder operational-table contract", () => {
    const html = render_stream_members({can_remove_subscribers: true});

    assert.match(html, /cf-data-table cf-data-table--settings/);
    assert.match(html, /table-sortable-arrow/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/);
});

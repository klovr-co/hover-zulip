"use strict";

const assert = require("node:assert/strict");

const render_folder = require("../templates/inbox_view/inbox_folder_row.hbs");
const render_row = require("../templates/inbox_view/inbox_row.hbs");
const render_view = require("../templates/inbox_view/inbox_view.hbs");

const {run_test} = require("./lib/test.cjs");

const policies = {FOLLOWED: "FOLLOWED", INHERIT: "INHERIT", MUTED: "MUTED", UNMUTED: "UNMUTED"};
const columns = {ACTION_MENU: 3, FULL_ROW: 0, TOPIC_VISIBILITY: 2, UNREAD_COUNT: 1};

run_test("Inbox shell uses the Cofounder conversation-list contract", () => {
    const html = render_view({
        INBOX_SEARCH_ID: "inbox-search",
        dms_dict: new Map(),
        folders_with_stream_rows: [],
        has_dms_post_filter: false,
        normal_view: true,
        search_val: "",
        show_channel_folder_toggle: true,
    });

    assert.match(html, /cf-conversation-list/);
    assert.match(html, /cf-conversation-list__toolbar/);
    assert.match(html, /cf-conversation-list__filter-select/);
    assert.match(html, /cf-conversation-list__folder-menu/);
    assert.match(html, /cf-button--secondary/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
});

run_test("Inbox topic rows use typed policy and action icons", () => {
    const html = render_row({
        all_visibility_policies: policies,
        column_indexes: columns,
        conversation_key: "design:homepage",
        is_direct: false,
        is_stream: false,
        is_topic: true,
        stream_archived: false,
        stream_id: 7,
        topic_display_name: "Homepage redesign",
        topic_name: "Homepage redesign",
        topic_url: "#topic",
        unread_count: 4,
        visibility_policy: policies.FOLLOWED,
    });

    assert.match(html, /cf-conversation-list__row--unread/);
    assert.match(html, /cf-conversation-list__badge/);
    assert.match(html, /cf-conversation-list__action/);
    assert.match(html, /<svg[^>]*cf-icon/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
});

run_test("Inbox direct-message rows use semantic Cofounder identity markers", () => {
    const active = render_row({
        column_indexes: columns,
        conversation_key: "1",
        dm_url: "#dm",
        is_direct: true,
        is_group: false,
        is_stream: false,
        rendered_dm_with_html: "Ava Rodriguez",
        unread_count: 2,
        user_circle_class: "user-circle-active",
        user_ids_string: "1",
    });
    const group = render_row({
        column_indexes: columns,
        conversation_key: "1,2",
        dm_url: "#dm",
        is_direct: true,
        is_group: true,
        is_stream: false,
        rendered_dm_with_html: "Research group",
        unread_count: 0,
        user_ids_string: "1,2",
    });

    assert.match(active, /cf-presence-dot/);
    assert.match(group, /cf-conversation-list__identity-icon/);
    assert.doesNotMatch(`${active}${group}`, /zulip-icon|<i(?:\s|>)/);
});

run_test("Inbox folder rows expose typed collapse controls", () => {
    const html = render_folder({
        header_id: "inbox-folder-product",
        is_collapsed: false,
        is_dm_header: false,
        is_header_visible: true,
        name: "Product",
        unread_count: 6,
    });

    assert.match(html, /cf-conversation-list__section-label/);
    assert.match(html, /cf-conversation-list__collapse/);
    assert.match(html, /type="button"/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
});

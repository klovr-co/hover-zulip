"use strict";

const assert = require("node:assert/strict");

const render_empty = require("../templates/recent_view_empty_list_widget_for_table.hbs");
const render_filters = require("../templates/recent_view_filters.hbs");
const render_row = require("../templates/recent_view_row.hbs");
const render_table = require("../templates/recent_view_table.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("Recent View table uses the Cofounder data-table contract", () => {
    const html = render_table({
        filter_participated: false,
        filter_pm: true,
        filter_unread: false,
        folder_filter_tooltip: "Filter by folder",
        is_spectator: false,
        search_val: "",
        show_folder_filter: false,
    });

    assert.match(html, /cf-data-table__toolbar/);
    assert.match(html, /cf-data-table--header/);
    assert.match(html, /cf-data-table__sort/);
    assert.match(html, /type="button"[^>]*data-sort="channel_sort"/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
});

run_test("Recent View filters expose accessible Cofounder chip state", () => {
    const html = render_filters({
        filter_participated: false,
        filter_pm: true,
        filter_unread: false,
        is_spectator: false,
        show_folder_filter: false,
    });

    assert.match(html, /cf-filter-chip/);
    assert.match(html, /aria-checked="true"[^>]*data-filter="include_private"/);
    assert.match(html, /aria-checked="false"[^>]*data-filter="unread"/);
    assert.doesNotMatch(html, /fa-check-square|fa-square|zulip-icon/);
});

run_test("Recent View rows use Cofounder cells and typed action icons", () => {
    const html = render_row({
        all_visibility_policies: {FOLLOWED: "FOLLOWED", MUTED: "MUTED", UNMUTED: "UNMUTED"},
        column_indexes: {mute: 2, read: 1, topic: 0},
        conversation_key: "design:homepage",
        full_last_msg_date_time: "Today at 10:45 AM",
        is_archived: false,
        is_empty_string_topic: false,
        is_private: false,
        last_msg_time: "10:45 AM",
        last_msg_url: "#message",
        mention_in_unread: false,
        other_senders_count: 0,
        senders: [],
        stream_color: "#4f8394",
        stream_id: 7,
        stream_name: "design",
        topic: "Homepage redesign",
        topic_display_name: "Homepage redesign",
        topic_url: "#topic",
        unread_count: 2,
        visibility_policy: "FOLLOWED",
    });

    assert.match(html, /cf-data-table__row--unread/);
    assert.match(html, /cf-data-table__cell/);
    assert.match(html, /data-cf-icon-name="follow"/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
});

run_test("Recent View empty state uses Cofounder load-more controls", () => {
    const html = render_empty({
        column_count: 3,
        empty_list_message: "No conversations match your filters.",
        load_more_button_text: "Load more",
    });

    assert.match(html, /cf-data-table__empty/);
    assert.match(html, /cf-load-more--empty/);
    assert.match(html, /cf-button--secondary/);
    assert.doesNotMatch(html, /action-button/);
});

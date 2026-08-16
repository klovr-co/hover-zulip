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
    assert.match(html, /role="presentation"/);
    assert.match(html, /cf-data-table__sort/);
    assert.match(html, /aria-label="translated: Clear conversation filter"/);
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
    assert.match(html, /aria-label="translated: Mark as read: Homepage redesign"/);
    assert.match(
        html,
        /role="button" aria-label="translated: Topic actions menu: Homepage redesign"/,
    );
    assert.match(html, /aria-hidden="true" data-cf-icon-name="follow"/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
});

run_test("Recent View Cofounder styles keep zero-count actions hidden", () => {
    const css = require("node:fs").readFileSync(
        require("node:path").join(__dirname, "../styles/cofounder/components/data-table.css"),
        "utf8",
    );

    assert.match(css, /recent-view-table-unread-count\.unread_hidden[\s\S]*display: none/);
    assert.match(css, /cf-data-table__sr-only-head th[\s\S]*clip-path: inset\(50%\)/);
});

run_test("Recent View body table owns its accessible table semantics", () => {
    const index = require("node:fs").readFileSync(
        require("node:path").join(__dirname, "../../templates/zerver/app/index.html"),
        "utf8",
    );

    assert.match(
        index,
        /id="recent-view-content-table"[\s\S]*aria-label="\{\{ _\('Recent conversations'\) \}\}"/,
    );
    assert.match(index, /cf-data-table__sr-only-head[\s\S]*Channel and conversation/);
    assert.match(index, /last-fetched-message" role="status" aria-live="polite"/);
    assert.match(
        index,
        /type="button"[\s\S]*fetch-messages-button notvisible"[\s\S]*aria-busy="false"/,
    );
});

run_test("Recent View load-more workflow preserves a pending accessible name", () => {
    const recent_view_ui = require("node:fs").readFileSync(
        require("node:path").join(__dirname, "../src/recent_view_ui.ts"),
        "utf8",
    );
    const story = require("node:fs").readFileSync(
        require("node:path").join(__dirname, "../stories/cofounder_recent_view.stories.ts"),
        "utf8",
    );

    assert.match(
        recent_view_ui,
        /"aria-busy": "true"[\s\S]*defaultMessage: "Loading older messages"/,
    );
    assert.match(recent_view_ui, /attr\("aria-busy", "false"\)\.removeAttr\("aria-label"\)/);
    assert.match(story, /Loading older conversations…/);
    assert.match(story, /1 older conversation loaded\. All conversations are available\./);
    assert.match(story, /rows\.push\(loaded_row\)[\s\S]*loaded_row\.focus\(\)/);
    assert.match(
        require("node:fs").readFileSync(
            require("node:path").join(__dirname, "../stories/storybook.css"),
            "utf8",
        ),
        /recent-view-load-more-container\[hidden\][\s\S]*display: none/,
    );
});

run_test("Recent View empty state uses Cofounder load-more controls", () => {
    const html = render_empty({
        column_count: 3,
        empty_list_message: "No conversations match your filters.",
        load_more_button_text: "Load more",
    });

    assert.match(html, /cf-data-table__empty/);
    assert.match(
        html,
        /cf-data-table__empty-message"[\s\S]*role="status"[\s\S]*aria-live="polite"[\s\S]*aria-atomic="true"/,
    );
    assert.match(html, /cf-load-more--empty/);
    assert.match(html, /cf-button--secondary/);
    assert.match(html, /type="button"[^>]*fetch-messages-button[^>]*aria-busy="false"/);
    assert.doesNotMatch(html, /action-button/);
});

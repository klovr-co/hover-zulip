"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_stream_actions = require("../templates/popovers/left_sidebar/left_sidebar_stream_actions_popover.hbs");
const render_topic_actions = require("../templates/popovers/left_sidebar/left_sidebar_topic_actions_popover.hbs");
const render_views = require("../templates/popovers/left_sidebar/left_sidebar_views_popover.hbs");

const {run_test} = require("./lib/test.cjs");

const menu_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/menu.css"),
    "utf8",
);
const cofounder_app_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/app.css"),
    "utf8",
);

run_test("Left sidebar popovers use typed Cofounder icons", () => {
    const directory = path.join(__dirname, "../templates/popovers/left_sidebar");
    const source = [
        ...fs.readdirSync(directory).map((file) => path.join(directory, file)),
        path.join(__dirname, "../templates/popovers/left_sidebar_menu_popover.hbs"),
    ]
        .map((file) => fs.readFileSync(file, "utf8"))
        .join("");
    const html = render_views({
        is_home_view_active: false,
        show_unread_count: true,
        unread_messages_present: true,
        views: [
            {
                cf_icon: "inbox",
                css_class_suffix: "inbox",
                fragment: "inbox",
                has_unread_count: true,
                name: "Inbox",
                supports_masked_unread: true,
                tooltip_template_id: "inbox-tooltip-template",
                unread_count: 8,
                unread_count_type: "normal-count",
            },
        ],
    });

    assert.match(html, /cf-menu/);
    assert.match(html, /role="menu" aria-label="[^"]*Views"/);
    assert.match(html, /cf-icon/);
    assert.match(html, /masked-unread-icon/);
    assert.match(html, /aria-label="[^"]*Unread messages[^"]*: 8"/);
    assert.match(html, /role="img" aria-label="[^"]*Some unread messages are hidden"/);
    assert.match(html, /<button type="button" role="menuitem"[^>]*mark_all_messages_as_read/);
    assert.match(
        html,
        /<button type="button" role="menuitem"[^>]*toggle_display_unread_message_count/,
    );
    assert.match(
        menu_css,
        /\.label-and-unread-wrapper\s*{[^}]*min-width:\s*0[^}]*flex:\s*1 1 auto/s,
    );
    assert.doesNotMatch(source, /zulip-icon|\bfa(?:\s|-)|icon_class/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|icon_class/);
});

run_test("Channel actions preserve their curated stream contract", () => {
    const html = render_stream_actions({
        has_unread_messages: true,
        show_go_to_channel_feed: true,
        show_go_to_list_of_topics: true,
        stream: {
            color: "#4f8394",
            invite_only: false,
            is_archived: false,
            is_muted: false,
            is_web_public: false,
            list_of_topics_view_url: "#topics",
            name: "Product design",
            pin_to_top: true,
            stream_id: 7,
            url: "#channel/product-design",
        },
        stream_edit_hash: "#channels/7",
    });

    assert.match(html, /aria-label="[^"]*Channel actions[^"]*Product design"/);
    assert.match(html, /style="color: #4f8394"/);
    assert.match(html, />Product design</);
    assert.match(html, />translated: Mute channel</);
    assert.match(html, />translated: Unpin channel from top</);
    assert.match(html, /href="#topics"/);
    assert.match(html, /data-clipboard-text="#channel\/product-design"/);
    assert.match(html, /<button type="button" role="menuitem"[^>]*mark_stream_as_read/);
    assert.doesNotMatch(
        cofounder_app_css,
        /#stream-actions-menu-popover[^{}]*\.filter-icon\s*{[^}]*!important/s,
    );
    assert.match(
        menu_css,
        /:is\(\.popover-stream-name, \.popover-topic-name\)\s*{[^}]*overflow-wrap:\s*anywhere/s,
    );
});

run_test("Topic actions own their radio and command semantics", () => {
    const html = render_topic_actions({
        all_visibility_policies: {FOLLOWED: 3, INHERIT: 0, MUTED: 1, UNMUTED: 2},
        can_move_topic: true,
        can_rename_topic: true,
        can_resolve_topic: true,
        can_summarize_topics: true,
        has_starred_messages: true,
        has_unread_messages: true,
        is_empty_string_topic: false,
        is_realm_admin: true,
        is_spectator: false,
        is_topic_empty: false,
        show_ai_features: true,
        stream_archived: false,
        stream_muted: false,
        topic_display_name: "Research synthesis",
        topic_is_resolved: false,
        topic_unmuted: false,
        url: "#topic/research-synthesis",
        visibility_policy: 0,
    });

    assert.match(html, /aria-label="[^"]*Topic actions[^"]*Research synthesis"/);
    assert.match(html, /class="cf-menu__choice-group"/);
    assert.equal((html.match(/role="menuitemradio"/g) ?? []).length, 3);
    assert.equal((html.match(/tabindex="-1" aria-hidden="true"/g) ?? []).length, 3);
    assert.equal((html.match(/aria-checked="true"/g) ?? []).length, 1);
    assert.equal((html.match(/aria-checked="false"/g) ?? []).length, 2);
    assert.match(html, /<button type="button" role="menuitem"[^>]*sidebar-popover-summarize-topic/);
    assert.match(html, /sidebar-popover-delete-topic-messages[^>]*cf-menu__action--danger/);
    assert.doesNotMatch(html, /\btab-picker\b|\btab-option\b|class="slider"/);
    assert.match(
        menu_css,
        /@media \(width <= 600px\)[\s\S]*\.cf-menu__choice\s*{[^}]*min-height:\s*var\(--cf-control-height-touch\)/,
    );
});

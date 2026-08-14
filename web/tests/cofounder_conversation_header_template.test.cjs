"use strict";

const assert = require("node:assert/strict");

const render_recipient_row = require("../templates/recipient_row.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("channel conversation header delegates to Cofounder markup", () => {
    const html = render_recipient_row({
        all_visibility_policies: {FOLLOWED: "FOLLOWED", MUTED: "MUTED", UNMUTED: "UNMUTED"},
        date_html: "Today",
        display_recipient: "design",
        is_archived: false,
        is_empty_string_topic: false,
        is_stream: true,
        is_subscribed: true,
        is_topic_editable: true,
        recipient_bar_color: "#4f8394",
        stream_id: 7,
        stream_privacy_icon_color: "#ffffff",
        stream_url: "#channel",
        topic: "Homepage redesign",
        topic_display_name: "Homepage redesign",
        topic_is_resolved: false,
        topic_links: [{text: "spec", url: "https://example.com/spec"}],
        topic_url: "#topic",
        user_can_resolve_topic: true,
        visibility_policy: "INHERIT",
    });

    assert.match(html, /cf-conversation-header--channel/);
    assert.match(html, /--cf-conversation-accent: #4f8394/);
    assert.match(html, /narrows_by_recipient/);
    assert.match(html, /narrows_by_topic/);
    assert.match(html, /recipient-row-topic-menu/);
    assert.match(html, /cf-icon-button--neutral/);
    assert.match(html, /M14 3h7v7/);
    assert.doesNotMatch(html, /zulip-icon|<i class="zulip-icon/);
});

run_test("direct-message conversation header uses typed identity icons", () => {
    const html = render_recipient_row({
        date_html: "Today",
        display_reply_to_for_tooltip: "Ava",
        is_dm_with_self: false,
        is_stream: false,
        pm_with_url: "#dm",
        recipient_users: [{full_name: "Ava", is_bot: true}],
    });

    assert.match(html, /cf-conversation-header--dm/);
    assert.match(html, /cf-conversation-header__dm-icon/);
    assert.match(html, /cf-conversation-header__bot/);
    assert.match(html, /narrows_by_recipient/);
    assert.doesNotMatch(html, /zulip-icon|<i class="zulip-icon/);
});

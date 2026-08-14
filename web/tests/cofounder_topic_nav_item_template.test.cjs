"use strict";

const assert = require("node:assert/strict");

const render_topic_list_item = require("../templates/topic_list_item.hbs");

const {run_test} = require("./lib/test.cjs");

function topic(overrides = {}) {
    return {
        contains_unread_mention: false,
        is_active_topic: false,
        is_empty_string_topic: false,
        is_followed: false,
        is_muted: false,
        is_unmuted_or_followed: false,
        is_zero: false,
        stream_id: 7,
        topic_display_name: "Launch plan",
        topic_name: "Launch plan",
        topic_resolved_prefix: "",
        unread: 4,
        url: "#narrow/channel/7-product-design/topic/Launch-plan",
        ...overrides,
    };
}

run_test("topic row renders the Cofounder navigation contract", () => {
    const html = render_topic_list_item(topic({is_active_topic: true}));

    assert.match(
        html,
        /class="cf-topic-nav bottom_left_row cf-topic-nav--selected active-sub-filter/,
    );
    assert.match(html, /class="cf-topic-nav__main topic-box"[^>]+aria-current="page"/);
    assert.match(html, /class="cf-topic-nav__label-inner sidebar-topic-name-inner">Launch plan/);
    assert.match(html, /class="cf-topic-nav__badge unread_count normal-count">4/);
    assert.match(html, /<button[^>]+topic-sidebar-menu-icon[^>]+aria-label="[^"]*Topic options"/);
    assert.doesNotMatch(html, /zulip-icon/);
});

run_test("topic row renders followed, mentioned, muted, and resolved states", () => {
    const followed = render_topic_list_item(
        topic({is_followed: true, is_muted: true, topic_resolved_prefix: "✔ "}),
    );
    assert.match(followed, /cf-topic-nav--muted muted_topic/);
    assert.match(followed, /change_visibility_policy/);
    assert.match(followed, /<svg class="cf-icon cf-icon--compact"/);
    assert.match(followed, />✔ <\/span>/);

    const mentioned = render_topic_list_item(topic({contains_unread_mention: true}));
    assert.match(mentioned, /cf-topic-nav__mention unread_mention_info">@/);
    assert.doesNotMatch(mentioned, /change_visibility_policy/);
});

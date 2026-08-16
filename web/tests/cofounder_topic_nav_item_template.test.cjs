"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

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
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_topic_nav_item.stories.ts"),
        "utf8",
    );
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/topic-nav-item.css"),
        "utf8",
    );
    const storybook_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");

    assert.match(
        html,
        /class="cf-topic-nav bottom_left_row cf-topic-nav--selected active-sub-filter/,
    );
    assert.match(html, /class="cf-topic-nav__main topic-box"[^>]+aria-current="page"/);
    assert.match(html, /class="cf-topic-nav__label-inner sidebar-topic-name-inner">Launch plan/);
    assert.match(html, /class="cf-topic-nav__badge unread_count normal-count"[^>]*>4/);
    assert.match(html, /aria-label="translated: Unread messages: 4"/);
    assert.match(
        html,
        /<button[^>]+topic-sidebar-menu-icon[^>]+aria-label="translated: Topic options: Launch plan"/,
    );
    assert.doesNotMatch(html, /zulip-icon/);
    assert.match(story_source, /aria-atomic="true"/);
    assert.match(story_source, /storybook-cf-topic-nav-states/);
    assert.match(
        storybook_css,
        /\.storybook-component:has\(\.storybook-cf-topic-nav-states\) \{[\s\S]*width: min\(100%, 314px\);/,
    );
    assert.match(
        story_source,
        /classList\.remove\("cf-topic-nav--selected", "active-sub-filter"\)/,
    );
    assert.match(story_source, /topic_link\.setAttribute\("aria-current", "page"\)/);
    assert.match(story_source, /\.cf-topic-nav-action__main/);
    assert.match(story_source, /utility_link\.focus\(\)/);
    assert.match(
        component_css,
        /\.cf-topic-nav > \.cf-topic-nav__more \{[\s\S]*display: grid;[\s\S]*visibility: hidden;[\s\S]*pointer-events: none;/,
    );
    assert.match(
        component_css,
        /\.cf-topic-nav:is\(:hover, :focus-within, \.highlighted_row\)[\s\S]*visibility: visible;[\s\S]*pointer-events: auto;/,
    );
    assert.match(
        component_css,
        /\.cf-topic-nav--selected,[\s\S]*color: var\(--cf-color-accent-hover\);/,
    );
    assert.match(
        component_css,
        /\.cf-topic-nav__mention \{[\s\S]*color: var\(--cf-color-accent-hover\);/,
    );
});

run_test("topic row renders followed, mentioned, muted, and resolved states", () => {
    const followed = render_topic_list_item(
        topic({is_followed: true, is_muted: true, topic_resolved_prefix: "✔ "}),
    );
    assert.match(followed, /cf-topic-nav--muted muted_topic/);
    assert.match(followed, /change_visibility_policy/);
    assert.match(followed, /aria-label="translated: Change visibility policy: Launch plan"/);
    assert.match(followed, /<svg class="cf-icon cf-icon--compact"/);
    assert.match(followed, /role="img" aria-label="translated: Resolved topic">✔ <\/span>/);

    const mentioned = render_topic_list_item(topic({contains_unread_mention: true}));
    assert.match(mentioned, /cf-topic-nav__mention unread_mention_info"[^>]*>@/);
    assert.match(mentioned, /aria-label="translated: Mentioned you">@/);
    assert.doesNotMatch(mentioned, /change_visibility_policy/);
});

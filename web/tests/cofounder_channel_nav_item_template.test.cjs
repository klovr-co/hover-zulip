"use strict";

const assert = require("node:assert/strict");

const render_stream_sidebar_row = require("../templates/stream_sidebar_row.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("stream sidebar row renders the Cofounder channel contract", () => {
    const html = render_stream_sidebar_row({
        badge_visible: true,
        can_post_messages: true,
        color: "#0878e8",
        id: 7,
        invite_only: false,
        is_archived: false,
        is_empty_topic_only_channel: false,
        is_muted: false,
        is_web_public: false,
        name: "Product design",
        selected: true,
        unread_count: 12,
        url: "#narrow/channel/7-product-design",
    });

    assert.match(html, /class="cf-channel-nav narrow-filter" data-stream-id="7"/);
    assert.match(html, /class="cf-channel-nav__main subscription_block/);
    assert.match(html, /class="cf-channel-nav__label stream-name">Product design/);
    assert.match(html, /aria-current="page"/);
    assert.match(html, /class="cf-channel-nav__badge unread_count normal-count">12/);
    assert.match(
        html,
        /<button[^>]+channel-search-topics-button[^>]+aria-label="[^"]*Search topics"/,
    );
    assert.match(
        html,
        /<button[^>]+channel-new-topic-button[^>]+aria-label="[^"]*Start a new topic"/,
    );
    assert.match(
        html,
        /<button[^>]+stream-sidebar-menu-icon[^>]+aria-label="[^"]*Channel options"/,
    );
    assert.equal((html.match(/<button/g) ?? []).length, 3);
    assert.doesNotMatch(html, /zulip-icon/);
});

run_test("channel contract renders private, muted, and no-compose states", () => {
    const html = render_stream_sidebar_row({
        can_post_messages: false,
        color: "#696b66",
        id: 9,
        invite_only: true,
        is_archived: false,
        is_muted: true,
        is_web_public: false,
        name: "Leadership",
        url: "#narrow/channel/9-leadership",
    });

    assert.match(html, /cf-channel-nav--muted out_of_home_view/);
    assert.match(html, /<rect x="5" y="10" width="14"/);
    assert.doesNotMatch(html, /channel-new-topic-button/);
    assert.equal((html.match(/<button/g) ?? []).length, 2);
});

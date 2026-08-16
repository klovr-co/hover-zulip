"use strict";

const assert = require("node:assert/strict");

const render_more_topics = require("../templates/more_topics.hbs");
const render_topic_list_new_topic = require("../templates/topic_list_new_topic.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("show-all row renders the Cofounder topic action contract", () => {
    const html = render_more_topics({
        more_topics_have_unread_mention_messages: true,
        more_topics_unread_count_muted: false,
        more_topics_unreads: 8,
    });

    assert.match(
        html,
        /class="cf-topic-nav-action bottom_left_row topic-list-item show-more-topics"/,
    );
    assert.match(html, /class="cf-topic-nav-action__main topic-box"/);
    assert.match(html, /sidebar-topic-action-heading">translated: Show all topics/);
    assert.match(html, /cf-topic-nav-action__mention unread_mention_info">@/);
    assert.match(html, /cf-topic-nav-action__badge unread_count normal-count">8/);
    assert.doesNotMatch(html, /zulip-icon/);

    const empty_muted = render_more_topics({
        more_topics_have_unread_mention_messages: false,
        more_topics_unread_count_muted: true,
        more_topics_unreads: 0,
    });
    assert.match(empty_muted, /zero-topic-unreads more_topic_unreads_muted_only/);
    assert.match(empty_muted, /cf-topic-nav-action__badge unread_count normal-count zero_count/);
});

run_test("new-topic row renders a native Cofounder action link", () => {
    const html = render_topic_list_new_topic({stream_id: 7});

    assert.match(
        html,
        /class="cf-topic-nav-action__main cf-topic-nav-action__main--with-icon zoomed-new-topic" data-stream-id="7"/,
    );
    assert.match(html, /class="cf-topic-nav-action__icon"/);
    assert.match(html, /class="cf-topic-nav-action__label new-topic-label">translated: NEW TOPIC/);
    assert.doesNotMatch(html, /zulip-icon/);
});

"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const stream_topic_history_util = mock_esm("../src/stream_topic_history_util");
mock_esm("../src/people.ts", {
    maybe_get_user_by_id: noop,
});

const recent_view_messages_data = zrequire("recent_view_messages_data");
const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");
const topic_list = zrequire("topic_list");

set_realm(make_realm());

function test(label, f) {
    run_test(label, (helpers) => {
        f(helpers);
    });
}

test("is_full_topic_history_available", ({override}) => {
    const stream_id = 21;
    const general = {
        name: "general",
        stream_id,
        first_message_id: null,
        subscriber_count: 0,
    };
    const messages = [
        {id: 1, stream_id},
        {id: 2, stream_id},
        {id: 3, stream_id},
    ];
    const sub = stream_data.create_sub_from_server_data(general);

    // Currently, recent_view_messages_data is empty.
    assert.equal(topic_list.is_full_topic_history_available(stream_id), false);

    recent_view_messages_data.recent_view_messages_data.clear();
    recent_view_messages_data.recent_view_messages_data.add_messages(messages, true);

    let has_found_newest = false;

    override(
        recent_view_messages_data.recent_view_messages_data.fetch_status,
        "has_found_newest",
        () => has_found_newest,
    );

    assert.equal(topic_list.is_full_topic_history_available(stream_id), false);
    has_found_newest = true;
    // sub.first_message_id === null
    assert.equal(topic_list.is_full_topic_history_available(stream_id), true);

    // Note that we'll return `true` here due to
    // fetched_stream_ids having the stream_id now.
    assert.equal(topic_list.is_full_topic_history_available(stream_id), true);

    // Clear the data, otherwise `is_full_topic_history_available`
    // will always return true due to stream_id in fetched_stream_ids.
    stream_topic_history.reset();

    sub.first_message_id = 0;
    assert.equal(topic_list.is_full_topic_history_available(stream_id), false);

    sub.first_message_id = 2;
    let full_topic_history_fetched_and_widget_updated = false;
    stream_topic_history_util.get_server_history = (stream_id) => {
        assert.equal(stream_id, general.stream_id);
        full_topic_history_fetched_and_widget_updated = true;
    };
    assert.equal(topic_list.is_full_topic_history_available(stream_id), true);
    assert.equal(full_topic_history_fetched_and_widget_updated, true);
});

test("topic click uses the topic row stream", () => {
    let clicked_topic;
    topic_list.initialize({
        on_topic_click(stream_id, topic) {
            clicked_topic = {stream_id, topic};
        },
    });

    const $target = $(".summary-topic-name");
    const $topic_row = $(".summary-topic-row")
        .attr("data-stream-id", "23")
        .attr("data-topic-name", "Daily migration brief");
    const $parent_stream_row = $(".parent-stream-row").attr("data-stream-id", "22");

    $target.set_closest_results(".show-more-topics", []);
    $target.set_closest_results(".visibility-policy-icon", []);
    $target.set_closest_results(".topic-sidebar-menu-icon", []);
    $target.set_closest_results("li", $topic_row);
    $target.set_closest_results(".narrow-filter", $parent_stream_row);

    const handler = $("#stream_filters").get_on_handler("click", ".topic-box");
    handler({
        target: {
            to_$() {
                return $target;
            },
        },
        preventDefault() {},
        stopPropagation() {},
    });

    assert.deepEqual(clicked_topic, {
        stream_id: 23,
        topic: "Daily migration brief",
    });
});

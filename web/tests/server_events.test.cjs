"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

mock_esm("../src/loading", {
    destroy_indicator: noop,
});
set_global("addEventListener", noop);

const channel = mock_esm("../src/channel");
mock_esm("../src/reload_state", {
    is_in_progress() {
        return false;
    },
});
page_params.test_suite = false;

// we also directly write to pointer
set_global("pointer", {});

mock_esm("../src/popup_banners", {
    close_connection_error_popup_banner() {},
});

mock_esm("../src/stream_events", {
    update_property() {
        throw new Error("subs update error");
    },
});

mock_esm("../src/sent_messages", {
    report_event_received() {},
    messages: new Map(),
});

const message_events = mock_esm("../src/message_events", {
    insert_new_messages() {
        throw new Error("insert error");
    },
    update_messages() {
        throw new Error("update error");
    },
});

const server_events = zrequire("server_events");

const message = {
    id: 1,
    sender_id: 2,
    content: "hello",
    recipient_id: 3,
    timestamp: 100000000,
    client: "website",
    subject: "server_test",
    topic_links: [],
    is_me_message: false,
    reactions: [
        {
            emoji_name: "foo",
            emoji_code: "bar",
            reaction_type: "unicode_emoji",
            user: {
                email: "user1@foo.com",
                id: 1,
                full_name: "aaron",
            },
            user_id: 1,
        },
    ],
    submessages: [],
    sender_full_name: "user1",
    sender_email: "user2@foo.com",
    display_recipient: "test",
    type: "stream",
    stream_id: 1,
    avatar_url: "bar",
    content_type: "text/html",
};

server_events.finished_initial_fetch();

run_test("message_event", ({override}) => {
    const event = {
        type: "message",
        message,
        flags: [],
    };

    let inserted;
    override(message_events, "insert_new_messages", (message_data) => {
        const messages = message_data.raw_messages;
        assert.equal(messages[0].content, event.message.content);
        inserted = true;
        return messages;
    });

    server_events._get_events_success([event]);
    assert.ok(inserted);
});

run_test("message_event preserves Hover workflow metadata", ({override}) => {
    const generated_item = {
        id: 7,
        output_type: "digest",
        module: {key: "conversation_digest", name: "Conversation Digest", version: "v1"},
        source_summary: "From Review source",
        evidence_available: true,
        evidence_url: "/hover/evidence/7",
        reviewed_payload: {title: "Reviewed title"},
        revisions: [],
        disputed_details: [],
        sources: [],
        presentation: {
            label: "Digest",
            importance: "normal",
            state: null,
            occurred_at: null,
            generated_at: "2026-08-11T00:00:00Z",
            published_at: "2026-08-11T00:00:00Z",
            run_reference: "run_0123456789abcdef0123456789abcdef",
        },
        lineage: {is_latest: true, history_count: 1, history: []},
    };
    const hover_response = {
        type: "review",
        clarification_required: false,
        root_message_id: 42,
        generated_item,
    };
    const hover_review_request = {
        id: 9,
        root_message_id: 42,
        generated_item,
        field_path: "title",
        state: "open",
        target_user_ids: [2],
    };
    const event = {
        type: "message",
        message: {...message, id: 2, hover_response, hover_review_request},
        flags: [],
        local_message_id: "local-hover-review",
    };

    let inserted;
    override(message_events, "insert_new_messages", (message_data) => {
        assert.deepEqual(message_data.raw_messages[0].hover_response, hover_response);
        assert.deepEqual(message_data.raw_messages[0].hover_review_request, hover_review_request);
        inserted = true;
        return message_data.raw_messages;
    });

    server_events._get_events_success([event]);
    assert.ok(inserted);
});

// Start blueslip tests here

const setup = () => {
    server_events.finished_initial_fetch();
};

run_test("event_dispatch_error", () => {
    setup();

    const data = {events: [{type: "stream", op: "update", id: 1, other: "thing"}]};
    channel.get = (options) => {
        options.success(data);
    };

    blueslip.expect("error", "Failed to process an event");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info.event.type, "stream");
    assert.equal(logs[0].more_info.event.op, "update");
    assert.equal(logs[0].more_info.event.id, 1);
    assert.equal(logs[0].more_info.other, undefined);
});

run_test("event_new_message_error", () => {
    setup();

    const data = {events: [{type: "message", id: 1, other: "thing", message}]};
    channel.get = (options) => {
        options.success(data);
    };

    blueslip.expect("error", "Failed to insert new messages");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
});

run_test("event_edit_message_error", () => {
    setup();
    const data = {events: [{type: "update_message", id: 1, other: "thing"}]};
    channel.get = (options) => {
        options.success(data);
    };
    blueslip.expect("error", "Failed to update messages");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
});

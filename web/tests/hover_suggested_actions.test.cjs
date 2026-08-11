"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const messages = new Map();
const channel = mock_esm("../src/channel");
const hover_spaces = mock_esm("../src/hover_spaces");
const message_live_update = mock_esm("../src/message_live_update");
mock_esm("../src/message_store", {
    get(id) {
        return messages.get(id);
    },
});

const hover_suggested_actions = zrequire("hover_suggested_actions");

function action(version, state = "pending") {
    return {
        id: 4,
        state,
        version,
        wording: "Send the venue plan.",
        source_proposal: {assignee_ref: null, assignee_display_name: "Alex"},
        assignee: null,
        assignable_users: [],
        due_date: "2026-08-12",
        history_count: version - 1,
        recent_transitions: [],
        todo: null,
    };
}

function generated_item(version, state = "pending") {
    return {
        id: 7,
        output_type: "suggested_action",
        module: {key: "suggested_actions", name: "Suggested Actions", version: "v1"},
        source_summary: "From volunteers",
        evidence_available: true,
        evidence_url: "/evidence",
        reviewed_payload: {},
        revisions: [],
        sources: [],
        presentation: {
            label: "Suggested action",
            importance: "normal",
            state,
            occurred_at: null,
            generated_at: null,
            published_at: null,
            run_reference: "run-1",
        },
        lineage: {is_latest: true, history_count: 0, history: []},
        suggested_action: action(version, state),
    };
}

run_test("versioned projections cannot rewind a live Suggested Action", ({override}) => {
    const message = {id: 42, stream_id: 8, hover_generated_item: generated_item(3, "approved")};
    messages.set(message.id, message);
    const rerenders = [];
    override(message_live_update, "rerender_messages_view_by_message_ids", (ids) => {
        rerenders.push(ids);
    });

    assert.equal(
        hover_suggested_actions.apply_projection(42, generated_item(2, "not_action")),
        false,
    );
    assert.equal(message.hover_generated_item.suggested_action.state, "approved");
    assert.deepEqual(rerenders, []);

    assert.equal(
        hover_suggested_actions.apply_projection(42, generated_item(4, "not_action")),
        true,
    );
    assert.equal(message.hover_generated_item.suggested_action.state, "not_action");
    assert.deepEqual(rerenders, [[42]]);
});

run_test("unknown messages do not create duplicate feed records", () => {
    assert.equal(hover_suggested_actions.apply_projection(999, generated_item(1)), false);
    assert.equal(messages.has(999), false);
});

run_test("delegates message actions from the message pane", () => {
    hover_suggested_actions.initialize();
    assert.equal(
        typeof $("#main_div").get_on_handler("click", "[data-hover-action-decision]"),
        "function",
    );
});

run_test("approval submits wording, cleared assignee, and due date refinements", ({override}) => {
    const message = {
        id: 43,
        type: "stream",
        stream_id: 8,
        hover_generated_item: generated_item(1),
    };
    messages.set(message.id, message);
    override(hover_spaces, "get_by_stream_id", () => ({id: 9}));
    let request;
    override(channel, "post", (options) => {
        request = options;
    });

    const $panel = $("[data-hover-suggested-action-message-id='43']");
    const $wording = $.create("wording").val("Publish the reviewed venue plan.");
    const $assignee = $.create("assignee").val("");
    const $due_date = $.create("due-date").val("2026-08-20");
    $panel.set_find_results("button", $.create("button"));
    $panel.set_find_results("[data-hover-action-status]", $.create("status"));
    $panel.set_find_results("[data-hover-action-wording]", $wording);
    $panel.set_find_results("[data-hover-action-assignee]", $assignee);
    $panel.set_find_results("[data-hover-action-due-date]", $due_date);

    hover_suggested_actions._testing.submit(message.id, "approve");

    assert.equal(request.url, "/json/hover/spaces/9/generated-items/7/suggested-action/decisions");
    assert.equal(request.data.decision, "approve");
    assert.equal(request.data.expected_version, 1);
    assert.equal(request.data.wording, "Publish the reviewed venue plan.");
    assert.equal(request.data.assignee_user_id, "");
    assert.equal(request.data.due_date, "2026-08-20");
});

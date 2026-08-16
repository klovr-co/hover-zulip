"use strict";

const assert = require("node:assert/strict");

const z = require("zod/mini");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const messages = new Map();
const channel = mock_esm("../src/channel");
const hover_spaces = mock_esm("../src/hover_spaces");
const hover_todos = mock_esm("../src/hover_todos");
const message_live_update = mock_esm("../src/message_live_update");
mock_esm("../src/message_store", {
    hover_generated_item_schema: z.any(),
    hover_suggested_action_schema: z.any(),
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

run_test("a Suggested Action projection also projects its Todo", ({override}) => {
    const message = {id: 46, stream_id: 8, hover_generated_item: generated_item(1)};
    messages.set(message.id, message);
    const embedded_todo = {id: 50};
    const item = generated_item(2);
    item.suggested_action.todo = embedded_todo;
    let projected;
    override(hover_todos, "apply_projection", (todo) => {
        projected = todo;
    });
    override(message_live_update, "rerender_messages_view_by_message_ids", () => {});

    assert.equal(hover_suggested_actions.apply_projection(message.id, item), true);
    assert.equal(projected, embedded_todo);
});

run_test("delegates message actions from the message pane", () => {
    hover_suggested_actions.initialize();
    const handler = $("#main_div").get_on_handler("click", "[data-hover-action-decision]");
    assert.equal(typeof handler, "function");

    const $button = $.create("invalid action button")
        .attr("data-hover-message-id", "not-a-number")
        .attr("data-hover-action-decision", "approve");
    let propagation_stopped = false;
    handler({
        currentTarget: $button[0],
        stopPropagation() {
            propagation_stopped = true;
        },
    });
    assert.equal(propagation_stopped, true);
});

run_test("delegated valid actions submit", ({override}) => {
    const message = {id: 47, type: "stream", stream_id: 8, hover_generated_item: generated_item(1)};
    messages.set(message.id, message);
    override(hover_spaces, "get_by_stream_id", () => ({id: 9}));
    let request;
    override(channel, "post", (options) => {
        request = options;
    });
    const $panel = $("[data-hover-suggested-action-message-id='47']");
    $panel.set_find_results("button", $.create("delegated button"));
    $panel.set_find_results("[data-hover-action-status]", $.create("delegated status"));
    hover_suggested_actions.initialize();
    const handler = $("#main_div").get_on_handler("click", "[data-hover-action-decision]");
    const $button = $.create("valid action button")
        .attr("data-hover-message-id", String(message.id))
        .attr("data-hover-action-decision", "restore");
    handler({currentTarget: $button[0], stopPropagation() {}});
    assert.equal(request.data.decision, "restore");
});

run_test("invalid messages and missing Spaces do not submit", ({disallow, override}) => {
    disallow(channel, "post");
    hover_suggested_actions._testing.submit(999, "approve");
    messages.set(48, {id: 48, type: "private", hover_generated_item: generated_item(1)});
    hover_suggested_actions._testing.submit(48, "approve");
    messages.set(49, {
        id: 49,
        type: "stream",
        stream_id: 8,
        hover_generated_item: generated_item(1),
    });
    override(hover_spaces, "get_by_stream_id", () => undefined);
    hover_suggested_actions._testing.submit(49, "approve");
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

run_test("decision responses converge success, conflict, and error UI", ({override}) => {
    const message = {id: 50, type: "stream", stream_id: 8, hover_generated_item: generated_item(1)};
    messages.set(message.id, message);
    override(hover_spaces, "get_by_stream_id", () => ({id: 9}));
    override(message_live_update, "rerender_messages_view_by_message_ids", () => {});
    let request;
    override(channel, "post", (options) => {
        request = options;
    });
    const $panel = $("[data-hover-suggested-action-message-id='50']");
    const $button = $.create("button");
    const $status = $.create("status");
    $panel.set_find_results("button", $button);
    $panel.set_find_results("[data-hover-action-status]", $status);
    $panel.set_find_results("[data-hover-action-reason]", $.create("reason").val("duplicate"));

    hover_suggested_actions._testing.submit(message.id, "restore");
    request.success({changed: true, suggested_action: action(2, "pending")});
    assert.equal(message.hover_generated_item.suggested_action.version, 2);

    hover_suggested_actions._testing.submit(message.id, "not_action");
    request.error({status: 409, responseJSON: {suggested_action: action(3, "not_action")}});
    assert.equal(message.hover_generated_item.suggested_action.version, 3);

    hover_suggested_actions._testing.submit(message.id, "restore");
    request.error({status: 500, responseJSON: {}});
    assert.equal($button.prop("disabled"), false);
    assert.equal($status.text(), "translated: Could not save. Try again.");
});

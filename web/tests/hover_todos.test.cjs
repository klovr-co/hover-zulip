"use strict";

const assert = require("node:assert/strict");

const z = require("zod/mini");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const messages = new Map();
const channel = mock_esm("../src/channel");
const message_live_update = mock_esm("../src/message_live_update");
mock_esm("../src/message_store", {
    hover_todo_schema: z.any(),
    get(id) {
        return messages.get(id);
    },
});

const hover_todos = zrequire("hover_todos");

function todo(id, version, state = "active", due_date = null) {
    return {
        id,
        state,
        version,
        wording: `Todo ${id}`,
        due_date,
        completed_at: state === "completed" ? "2026-08-11T03:00:00+00:00" : null,
        assignee: null,
        space: {id: 3, name: "Action lab"},
        generated_item: {
            id: 7,
            message_id: 42,
            evidence_count: 1,
            evidence_url: "/evidence",
        },
        approval: null,
        assignable_users: [],
        history_count: version,
        recent_events: [],
    };
}

run_test("Todo projections cannot rewind Space or Home state", ({override}) => {
    hover_todos.todos.clear();
    const action = {todo: todo(5, 2)};
    messages.set(42, {id: 42, hover_generated_item: {id: 7, suggested_action: action}});
    const rerenders = [];
    override(message_live_update, "rerender_messages_view_by_message_ids", (ids) => {
        rerenders.push(ids);
    });

    assert.equal(hover_todos.apply_projection(todo(5, 2)), true);
    assert.equal(hover_todos.apply_projection(todo(5, 1, "completed")), false);
    assert.equal(hover_todos.todos.get(5).state, "active");
    assert.equal(action.todo.version, 2);
    assert.equal(action.todo, hover_todos.todos.get(5));
    assert.deepEqual(rerenders, [[42]]);
});

run_test("Home sorts active Todos first and counts only active work", () => {
    hover_todos.todos.clear();
    hover_todos.apply_projection(todo(1, 1, "completed", "2026-08-09"));
    hover_todos.apply_projection(todo(2, 1, "active", "2026-08-12"));
    hover_todos.apply_projection(todo(3, 1, "active", "2026-08-11"));

    assert.equal(hover_todos.get_count(), 2);
    assert.deepEqual(
        hover_todos.sorted().map((item) => item.id),
        [3, 2, 1],
    );
});

run_test("unknown Todo submissions are ignored", ({disallow}) => {
    hover_todos.todos.clear();
    disallow(channel, "post");
    hover_todos.submit(404, "complete");
});

run_test("Todo mutations handle assignment, success, conflict, and errors", ({override}) => {
    hover_todos.todos.clear();
    hover_todos.apply_projection(todo(6, 1));
    let request;
    override(channel, "post", (options) => {
        request = options;
    });
    const $containers = $("[data-hover-todo-id='6']");
    const $controls = $.create("controls");
    const $status = $.create("status");
    const $assignee = $.create("assignee").val("21");
    $containers.set_find_results("button, select", $controls);
    $containers.set_find_results("[data-hover-todo-status]", $status);
    $containers.set_find_results("[data-hover-todo-assignee]", $assignee);

    hover_todos.submit(6, "assign");
    assert.equal(request.url, "/json/hover/spaces/3/todos/6/events");
    assert.equal(request.data.assignee_user_id, "21");
    request.success({changed: true, todo: todo(6, 2)});
    assert.equal(hover_todos.todos.get(6).version, 2);

    hover_todos.submit(6, "complete");
    assert.equal("assignee_user_id" in request.data, false);
    request.error({status: 409, responseJSON: {todo: todo(6, 3, "completed")}});
    assert.equal(hover_todos.todos.get(6).state, "completed");

    hover_todos.submit(6, "reopen");
    request.error({status: 500, responseJSON: {}});
    assert.equal($controls.prop("disabled"), false);
    assert.equal($status.text(), "translated: Could not save. Try again.");
});

run_test("delegates Todo actions from both message and overlay roots", ({override}) => {
    let get_request;
    override(channel, "get", (options) => {
        get_request = options;
    });

    hover_todos.initialize();

    assert.equal(
        typeof $("#main_div").get_on_handler("click", "[data-hover-todo-operation]"),
        "function",
    );
    assert.equal(
        typeof $("body").get_on_handler("click", "[data-hover-todo-operation]"),
        "function",
    );

    get_request.success({todos: [todo(8, 1)]});
    assert.equal(hover_todos.todos.get(8).id, 8);

    let post_request;
    override(channel, "post", (options) => {
        post_request = options;
    });
    const $containers = $("[data-hover-todo-id='8']");
    $containers.set_find_results("button, select", $.create("delegated todo controls"));
    $containers.set_find_results("[data-hover-todo-status]", $.create("delegated todo status"));
    const handler = $("#main_div").get_on_handler("click", "[data-hover-todo-operation]");
    let propagation_stopped = false;
    const $valid = $.create("valid todo button")
        .attr("data-hover-todo-id", "8")
        .attr("data-hover-todo-operation", "complete");
    handler({
        currentTarget: $valid[0],
        stopPropagation() {
            propagation_stopped = true;
        },
    });
    assert.equal(propagation_stopped, true);
    assert.equal(post_request.data.operation, "complete");

    const previous_request = post_request;
    const $invalid = $.create("invalid todo button")
        .attr("data-hover-todo-id", "invalid")
        .attr("data-hover-todo-operation", "complete");
    handler({currentTarget: $invalid[0], stopPropagation() {}});
    assert.equal(post_request, previous_request);
});

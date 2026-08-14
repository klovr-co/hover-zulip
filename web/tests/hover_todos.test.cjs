"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const messages = new Map();
const channel = mock_esm("../src/channel");
const message_live_update = mock_esm("../src/message_live_update");
mock_esm("../src/message_store", {
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

run_test("delegates Todo actions from both message and overlay roots", ({override}) => {
    override(channel, "get", () => {});

    hover_todos.initialize();

    assert.equal(
        typeof $("#main_div").get_on_handler("click", "[data-cf-todo-operation]"),
        "function",
    );
    assert.equal(typeof $("body").get_on_handler("click", "[data-cf-todo-operation]"), "function");
});

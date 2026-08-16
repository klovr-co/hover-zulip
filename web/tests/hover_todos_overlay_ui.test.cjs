"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const document_stub = set_global("document", {activeElement: null});
set_global("CSS", {escape: (value) => `escaped-${value}`});

const browser_history = mock_esm("../src/browser_history");
const hover_todos = mock_esm("../src/hover_todos");
const overlays = mock_esm("../src/overlays");

const hover_todos_overlay_ui = zrequire("hover_todos_overlay_ui");

function todo(overrides = {}) {
    return {
        id: 1,
        state: "active",
        version: 1,
        wording: "Book the room",
        due_date: null,
        completed_at: null,
        assignee: null,
        space: {id: 3, name: "Action lab"},
        generated_item: {id: 7, message_id: 42, evidence_count: 1, evidence_url: "/evidence"},
        approval: null,
        assignable_users: [
            {user_id: 10, full_name: "Ada"},
            {user_id: 11, full_name: "Grace"},
        ],
        history_count: 0,
        recent_events: [],
        ...overrides,
    };
}

run_test(
    "launch renders formatted Todos and closes through history",
    ({mock_template, override}) => {
        const active = todo({assignee: {user_id: 10, full_name: "Ada"}, due_date: "2026-08-20"});
        const completed = todo({
            id: 2,
            state: "completed",
            recent_events: [
                {
                    id: 9,
                    kind: "completed",
                    actor: {user_id: 11, full_name: "Grace"},
                    occurred_at: "2026-08-17T09:30:00Z",
                    previous_state: "active",
                    new_state: "completed",
                    previous_assignee: null,
                    new_assignee: null,
                    reason: "",
                    notification_message_id: null,
                },
            ],
        });
        override(hover_todos, "sorted", () => [active, completed]);
        let context;
        mock_template("hover_todos_overlay.hbs", false, (data) => {
            context = data;
            return "rendered todos";
        });
        let open_options;
        override(overlays, "open_overlay", (options) => {
            open_options = options;
        });
        let exited = false;
        override(browser_history, "exit_overlay", () => {
            exited = true;
        });

        hover_todos_overlay_ui.launch();
        assert.equal($("#reminders-overlay-container").html(), "rendered todos");
        assert.equal(open_options.name, "reminders");
        assert.equal(context.empty, false);
        assert.equal(context.todos[0].is_active, true);
        assert.equal(context.todos[0].assignee_label, "Ada");
        assert.deepEqual(context.todos[0].assignable_options, [{user_id: 11, full_name: "Grace"}]);
        assert.equal(context.todos[1].is_completed, true);
        assert.equal(context.todos[1].due_label, "translated: No due date");
        assert.equal(context.todos[1].assignee_label, "translated: Unassigned");
        assert.equal(context.todos[1].latest_event.id, 9);
        assert.equal(context.todos[1].latest_event_actor, "Grace");
        assert.equal(context.todos[1].latest_event_time, "2026-08-17T09:30:00Z");
        assert.equal(context.todos[1].evidence_count, 1);
        assert.equal(context.todos[0].source_hash, "#near/42");
        open_options.on_close();
        assert.equal(exited, true);
    },
);

run_test(
    "rerender only updates the open Hover Todo overlay and restores focus",
    ({mock_template, override}) => {
        override(hover_todos, "sorted", () => []);
        mock_template("hover_todos_overlay.hbs", false, (data) => {
            assert.equal(data.empty, true);
            return "empty todos";
        });
        override(overlays, "reminders_open", () => false);
        hover_todos_overlay_ui.rerender();

        override(overlays, "reminders_open", () => true);
        $("#reminders-overlay").attr("data-hover-todos", "false");
        hover_todos_overlay_ui.rerender();

        $("#reminders-overlay").attr("data-hover-todos", "true");
        const $active = $.create("active todo element");
        $active.set_closest_results(
            "[data-hover-todo-id]",
            $.create("active todo card").attr("data-hover-todo-id", "1'2"),
        );
        document_stub.activeElement = {to_$: () => $active};
        hover_todos_overlay_ui.rerender();
        assert.equal($("#reminders-overlay-container").html(), "empty todos");

        document_stub.activeElement = null;
        hover_todos_overlay_ui.rerender();
    },
);

run_test("initialize subscribes to Todo changes", () => {
    hover_todos_overlay_ui.initialize();
    assert.equal(typeof $("body").get_on_handler("hover_todos_changed"), "function");
});

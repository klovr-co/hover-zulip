"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {run_test} = require("./lib/test.cjs");

const render_suggested_action = require("../templates/hover_suggested_action.hbs");
const render_todos = require("../templates/hover_todos_overlay.hbs");

run_test("Todo workflow uses production-owned Cofounder contracts", () => {
    const todo_context = {
        assignee: {full_name: "Priya Shah", user_id: 11},
        assignee_label: "Priya Shah",
        assignable_options: [{full_name: "Morgan Lee", user_id: 12}],
        due_label: "August 20, 2026",
        generated_item: {evidence_count: 3, evidence_url: "#sources"},
        id: 73,
        is_active: true,
        is_completed: false,
        latest_event: null,
        source_hash: "#near/42",
        space: {name: "AIMTO Events"},
        state_label: "Active",
        state_tone: "accent",
        wording: "Publish the reviewed venue plan.",
    };
    const todos_html = render_todos({empty: false, todos: [todo_context]});
    const action_html = render_suggested_action({
        approval_assignable_users: [{full_name: "Morgan Lee", user_id: 12}],
        approval_assignee_user_id: 11,
        approval_due_date: "2026-08-20",
        approval_has_assignee: true,
        due_date: "August 20, 2026",
        is_approved: false,
        is_not_action: false,
        is_pending: true,
        latest_actor: null,
        latest_reason: null,
        latest_time: null,
        message_id: 42,
        responsibility: "Priya Shah",
        state_label: "Awaiting confirmation",
        state_tone: "warning",
        todo_assignee: "Priya Shah",
        todo_assignee_user_id: 11,
        todo_assignable_users: [],
        todo_has_assignee: true,
        todo_id: 73,
        todo_is_active: false,
        todo_is_completed: false,
        todo_latest_actor: null,
        todo_latest_time: null,
        wording: "Publish the reviewed venue plan.",
    });
    const behavior_source = [
        "../src/hover_todos.ts",
        "../src/hover_todos_overlay_ui.ts",
        "../src/hover_suggested_actions.ts",
    ]
        .map((file) => fs.readFileSync(path.join(__dirname, file), "utf8"))
        .join("");
    const workflow_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/todo-workflow.css"),
        "utf8",
    );
    const app_css = fs.readFileSync(path.join(__dirname, "../styles/cofounder/app.css"), "utf8");

    assert.match(todos_html, /class="[^"]*\bcf-todos\b[^"]*"/);
    assert.match(todos_html, /class="cf-todo-card"/);
    assert.match(todos_html, /data-cf-todo-operation="complete"/);
    assert.match(todos_html, /data-cf-evidence-url="#sources"/);
    assert.match(todos_html, /cf-icon-button[^>]*cf-todos__close/);
    assert.match(action_html, /class="cf-suggested-action"/);
    assert.match(action_html, /cf-status--warning/);
    assert.match(action_html, /data-cf-action-decision="approve"/);
    assert.match(action_html, /data-cf-action-wording/);
    assert.match(behavior_source, /\[data-cf-todo-operation\]/);
    assert.match(behavior_source, /\[data-cf-action-decision\]/);
    assert.match(workflow_css, /\.cf-suggested-action/);
    assert.match(workflow_css, /\.cf-todo-card/);
    assert.doesNotMatch(
        todos_html + action_html + behavior_source + app_css,
        /hover-suggested-action|hover-todo-card|hover-todos-(?:home|list)|data-hover-(?:todo|action|suggested-action)/,
    );
    assert.doesNotMatch(
        todos_html + action_html,
        /\bbutton rounded\b|sea-green|zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/,
    );
    assert.doesNotMatch(workflow_css, /var\(--(?:ds|hover)-|#[0-9a-f]{3,8}\b|hsl\(/i);
});

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_suggested_action = require("../templates/hover_suggested_action.hbs");
const render_todos = require("../templates/hover_todos_overlay.hbs");

const {run_test} = require("./lib/test.cjs");

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
    const empty_todos_html = render_todos({empty: true, todos: []});
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
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_suggested_action.stories.ts"),
        "utf8",
    );
    const todos_story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_todos.stories.ts"),
        "utf8",
    );
    const storybook_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");

    assert.match(todos_html, /class="[^"]*\bcf-todos\b[^"]*"/);
    assert.match(todos_html, /class="cf-todo-card cf-todo-card--active"/);
    assert.match(todos_html, /aria-labelledby="cf-todo-card-heading-73"/);
    assert.match(todos_html, /<h2 id="cf-todo-card-heading-73"/);
    assert.match(todos_html, /data-cf-todo-operation="complete"/);
    assert.match(todos_html, /aria-label="translated: Assign to Todo"/);
    assert.match(todos_html, /data-cf-current-assignee="11"/);
    assert.match(todos_html, /data-cf-todo-operation="assign"[\s\S]*disabled/);
    assert.match(todos_html, /data-cf-todo-status[\s\S]*aria-atomic="true"/);
    assert.match(todos_html, /data-cf-evidence-url="#sources"/);
    assert.match(todos_html, /cf-icon-button[^>]*cf-todos__close/);
    assert.match(empty_todos_html, /class="cf-todos__empty"/);
    assert.match(empty_todos_html, /aria-labelledby="cf-todos-empty-heading"/);
    assert.match(empty_todos_html, /aria-describedby="cf-todos-empty-description"/);
    assert.doesNotMatch(empty_todos_html, /no-overlay-messages/);
    assert.match(action_html, /class="cf-suggested-action"/);
    assert.match(action_html, /cf-status--warning/);
    assert.match(action_html, /data-cf-action-decision="approve"/);
    assert.match(action_html, /data-cf-action-wording/);
    assert.match(action_html, /aria-labelledby="cf-suggested-action-heading-42"/);
    assert.match(action_html, /<h3 id="cf-suggested-action-heading-42"/);
    assert.match(behavior_source, /\[data-cf-todo-operation\]/);
    assert.match(behavior_source, /\[data-cf-action-decision\]/);
    assert.match(workflow_css, /\.cf-suggested-action/);
    assert.match(workflow_css, /\.cf-todo-card/);
    assert.match(workflow_css, /\.cf-suggested-action__reason \{[\s\S]*flex: 1;/);
    assert.match(
        workflow_css,
        /\.cf-suggested-action__todo \.cf-suggested-action__controls label > span \{[\s\S]*flex: none;/,
    );
    assert.match(
        workflow_css,
        /\.cf-suggested-action__controls \.cf-button \{[\s\S]*overflow-wrap: anywhere;[\s\S]*white-space: normal;/,
    );
    assert.doesNotMatch(workflow_css, /\.cf-suggested-action__controls input \{/);
    assert.match(
        workflow_css,
        /\.cf-suggested-action \{[\s\S]*min-width: 0;[\s\S]*max-width: 100%;/,
    );
    assert.match(workflow_css, /\.cf-suggested-action__heading \{[\s\S]*flex-wrap: wrap;/);
    assert.match(
        workflow_css,
        /\.cf-suggested-action__facts :is\(dt, dd\)[\s\S]*overflow-wrap: anywhere;/,
    );
    assert.match(story_source, /setup_pending_story/);
    assert.match(story_source, /Approved and created Todo #73\./);
    assert.match(story_source, /Marked as not an action\./);
    assert.match(story_source, /Action wording is required\./);
    assert.match(story_source, /user_id !== Number\(assignee\.value\)/);
    assert.match(story_source, /next_panel\.focus\(\)/);
    assert.match(story_source, /setup_active_story/);
    assert.match(story_source, /Todo #73 assigned to/);
    assert.match(story_source, /Todo #73 completed\./);
    assert.match(story_source, /setup_completed_story/);
    assert.match(story_source, /Todo #73 reopened\./);
    assert.match(story_source, /setup_not_action_story/);
    assert.match(story_source, /Restored for review\./);
    assert.match(story_source, /setup_pending_story\(canvas\)/);
    assert.match(story_source, /mode === "active"[\s\S]*setup_active_story\(canvas\)/);
    assert.match(story_source, /else \{[\s\S]*setup_not_action_story\(canvas\)/);
    assert.match(story_source, /select\.focus\(\)/);
    assert.match(workflow_css, /\.cf-suggested-action--approved/);
    assert.match(workflow_css, /\.cf-suggested-action--completed/);
    assert.match(workflow_css, /\.cf-suggested-action--dismissed/);
    assert.match(workflow_css, /\.cf-todo-card--active/);
    assert.match(workflow_css, /\.cf-todo-card--completed/);
    assert.match(workflow_css, /\.cf-todos__empty \{[\s\S]*min-height: 240px;/);
    assert.match(workflow_css, /\.cf-todo-card \{[\s\S]*min-width: 0;[\s\S]*max-width: 100%;/);
    assert.match(
        workflow_css,
        /\.cf-todo-card__controls \.cf-button \{[\s\S]*white-space: normal;/,
    );
    assert.match(
        workflow_css,
        /\.cf-todo-card__controls label \{[\s\S]*flex-wrap: nowrap;[\s\S]*max-width: 100%;/,
    );
    assert.match(workflow_css, /label > \.cf-field__control \{[\s\S]*min-width: 100px;/);
    assert.match(todos_story_source, /Ready to assign to/);
    assert.match(
        todos_story_source,
        /canvas\.className = "storybook-template-story storybook-todos-story"/,
    );
    assert.match(todos_story_source, /\.cf-todos__close/);
    assert.match(storybook_css, /\.storybook-todos-story \{[\s\S]*width: min\(100vw, 920px\);/);
    assert.match(
        storybook_css,
        /@media \(width <= 600px\) \{[\s\S]*\.storybook-todos-story > \.overlay \{[\s\S]*height: 100vh;/,
    );
    assert.match(todos_story_source, /Todo #\$\{todo\.id\} assigned to/);
    assert.match(todos_story_source, /Todo #\$\{todo\.id\} completed\./);
    assert.match(todos_story_source, /Todo #\$\{todo\.id\} reopened\./);
    assert.match(todos_story_source, /Opened \$\{todo\.generated_item\.evidence_count\} sources/);
    assert.match(todos_story_source, /data-cf-open-todos/);
    assert.match(todos_story_source, /launcher\.focus\(\)/);
    assert.match(todos_story_source, /operation_name === "assign"/);
    assert.match(todos_story_source, /\.cf-todo-card\[data-cf-todo-id\]/);
    assert.doesNotMatch(todos_story_source, /assign\.addEventListener\("click"/);
    assert.doesNotMatch(todos_story_source, /\{capture: true\}/);
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

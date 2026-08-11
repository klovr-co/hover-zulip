"use strict";

const assert = require("node:assert/strict");

const render_suggested_action = require("../templates/hover_suggested_action.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("renders an assigned Todo without treating its numeric user ID as a condition", () => {
    const html = render_suggested_action({
        message_id: 42,
        wording: "Publish the briefing agenda",
        responsibility: "King Hamlet",
        due_date: "No due date",
        is_pending: false,
        is_approved: true,
        is_not_action: false,
        todo_id: 7,
        todo_is_active: true,
        todo_is_completed: false,
        todo_assignee: "King Hamlet",
        todo_has_assignee: true,
        todo_assignee_user_id: 10,
        todo_assignable_users: [],
    });

    assert.match(html, /value="10"/);
    assert.match(html, />\s*King Hamlet\s*<\/option>/);
});

run_test("renders approval refinements from the current reviewed projection", () => {
    const html = render_suggested_action({
        message_id: 42,
        wording: "Publish the reviewed briefing agenda",
        responsibility: "King Hamlet",
        due_date: "2026-08-19",
        approval_due_date: "2026-08-19",
        approval_assignable_users: [{user_id: 11, full_name: "Othello"}],
        approval_has_assignee: true,
        approval_assignee_user_id: 10,
        is_pending: true,
        is_approved: false,
        is_not_action: false,
    });

    assert.match(html, /data-hover-action-wording/);
    assert.match(html, /Publish the reviewed briefing agenda/);
    assert.match(html, /data-hover-action-assignee/);
    assert.match(html, /value="">\s*translated: Unassigned\s*<\/option>/);
    assert.match(html, /value="10" selected/);
    assert.match(html, /value="11"/);
    assert.match(html, /data-hover-action-due-date/);
    assert.match(html, /value="2026-08-19"/);
});

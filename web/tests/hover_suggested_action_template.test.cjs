"use strict";

const assert = require("node:assert/strict");

const {run_test} = require("./lib/test.cjs");

const render_suggested_action = require("../templates/hover_suggested_action.hbs");

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

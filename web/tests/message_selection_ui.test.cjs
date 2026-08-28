"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const message_selection_ui = zrequire("message_selection_ui");

run_test("notification highlight is distinct from message selection", () => {
    const $ordinary_selection = $("<ordinary-selection>");
    message_selection_ui.update_selected_message_row($ordinary_selection, false);

    assert.ok($ordinary_selection.hasClass("selected_message"));
    assert.ok(!$ordinary_selection.hasClass("notification-highlighted-message"));

    $.reset_selector(".selected_message");
    $.set_results(".selected_message", [$ordinary_selection.get(0)]);
    const $notification_selection = $("<notification-selection>");
    message_selection_ui.update_selected_message_row($notification_selection, true);

    assert.ok(!$ordinary_selection.hasClass("selected_message"));
    assert.ok($notification_selection.hasClass("selected_message"));
    assert.ok($notification_selection.hasClass("notification-highlighted-message"));

    $.reset_selector(".selected_message");
    $.set_results(".selected_message", [$notification_selection.get(0)]);
    $.reset_selector(".notification-highlighted-message");
    $.set_results(".notification-highlighted-message", [$notification_selection.get(0)]);
    const $next_ordinary_selection = $("<next-ordinary-selection>");
    message_selection_ui.update_selected_message_row($next_ordinary_selection, false);

    assert.ok(!$notification_selection.hasClass("selected_message"));
    assert.ok(!$notification_selection.hasClass("notification-highlighted-message"));
    assert.ok($next_ordinary_selection.hasClass("selected_message"));
    assert.ok(!$next_ordinary_selection.hasClass("notification-highlighted-message"));
});

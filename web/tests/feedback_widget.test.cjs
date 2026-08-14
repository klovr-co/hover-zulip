"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const feedback_widget = zrequire("feedback_widget");

run_test("uses the Cofounder toast lifecycle for transient feedback", () => {
    let undo_count = 0;
    const $container = $("#feedback_container");
    const $title = $.create(".feedback-title-stub");
    const $content = $.create(".feedback-content-stub");
    const $undo_label = $.create(".feedback-undo-label-stub");
    $container.set_find_results(".cf-toast__title", $title);
    $container.set_find_results(".cf-toast__content", $content);
    $container.set_find_results(".cf-toast__undo .cf-button__label", $undo_label);

    feedback_widget.show({
        hide_delay: 60_000,
        on_undo() {
            undo_count += 1;
        },
        populate($content) {
            $content.text("The message was moved to Product updates.");
        },
        title_text: "Message moved",
        undo_button_text: "Undo",
    });

    assert.equal(feedback_widget.is_open(), true);
    assert.equal($container.hasClass("cf-toast-host--visible"), true);
    assert.match($container.html(), /cf-toast cf-toast--neutral/);
    assert.equal($title.text(), "Message moved");
    assert.equal($content.text(), "The message was moved to Product updates.");
    assert.equal($undo_label.text(), "Undo");

    $container.get_on_handler("click", ".cf-toast__undo")();
    assert.equal(undo_count, 1);
    assert.equal(feedback_widget.is_open(), false);
    assert.equal($container.hasClass("cf-toast-host--leaving"), true);

    feedback_widget.show({
        hide_delay: 60_000,
        populate($content) {
            $content.text("The reminder was scheduled.");
        },
        title_text: "Reminder scheduled",
    });

    assert.equal(feedback_widget.is_open(), true);
    assert.doesNotMatch($container.html(), /cf-toast__undo/);
    $container.get_on_handler("click", ".cf-toast__close")();
    assert.equal(feedback_widget.is_open(), false);
});

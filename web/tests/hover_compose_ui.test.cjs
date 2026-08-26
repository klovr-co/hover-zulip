"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const insertions = [];

mock_esm("../src/compose_ui", {
    insert_and_scroll_into_view(content, $textarea) {
        insertions.push({content, $textarea});
    },
});

const hover_compose_ui = zrequire("hover_compose_ui");

function initialize_dom() {
    const $compose = $("#compose");
    const $messagebox = $("#messagebox-for-test").addClass("hover-formatting-expanded");
    const $format_button = $("#format-button-for-test")
        .attr("data-hover-compose-action", "format")
        .attr("aria-expanded", "true");
    const $mention_button = $("#mention-button-for-test").attr(
        "data-hover-compose-action",
        "mention",
    );
    const $textarea = $("#compose-textarea");

    $("#send_message_form .messagebox").set_find_results(".messagebox", $messagebox);
    $("[data-hover-compose-action='format']").set_find_results(
        "[data-hover-compose-action='format']",
        $format_button,
    );

    hover_compose_ui.initialize();

    return {$compose, $format_button, $mention_button, $messagebox, $textarea};
}

run_test("toggles progressive formatting controls", () => {
    const {$compose, $format_button, $messagebox} = initialize_dom();
    const handler = $compose.get_on_handler("click", "[data-hover-compose-action='format']");

    handler({currentTarget: $format_button, preventDefault() {}});
    assert.equal($messagebox.hasClass("hover-formatting-expanded"), false);
    assert.equal($format_button.attr("aria-expanded"), "false");

    handler({currentTarget: $format_button, preventDefault() {}});
    assert.equal($messagebox.hasClass("hover-formatting-expanded"), true);
    assert.equal($format_button.attr("aria-expanded"), "true");
});

run_test("inserts a mention trigger at the caret", () => {
    insertions.length = 0;
    const {$compose, $mention_button, $textarea} = initialize_dom();
    const handler = $compose.get_on_handler("click", "[data-hover-compose-action='mention']");

    handler({currentTarget: $mention_button, preventDefault() {}});

    assert.equal(insertions.length, 1);
    assert.equal(insertions[0].content, "@");
    assert.equal(insertions[0].$textarea, $textarea);
});

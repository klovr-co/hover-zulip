"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

mock_esm("../src/channel", {});
mock_esm("../src/inbox_ui", {});
mock_esm("../src/left_sidebar_navigation_area", {});
mock_esm("../src/recent_view_ui", {});
mock_esm("../src/stream_data", {});
mock_esm("../src/stream_topic_history", {});
mock_esm("../src/timerender", {});
mock_esm("../src/state_data", {
    realm: {
        realm_incoming_webhook_bots: [
            {
                display_name: "GitHub",
                name: "github",
                logo_url: "/github.svg",
                description: "Repository activity",
                all_event_types: ["push"],
            },
            {
                display_name: "GitLab",
                name: "gitlab",
                logo_url: "/gitlab.svg",
                description: "Projects and pipelines",
                all_event_types: ["push"],
            },
        ],
    },
});

const view = zrequire("hover_data_sources_view");

run_test("connector catalogue stays in the data source flow", () => {
    assert.deepEqual(view.catalogue_context_for_testing("git"), {
        has_results: true,
        provider_keys: ["github", "gitlab"],
    });
    assert.deepEqual(view.catalogue_context_for_testing(""), {
        has_results: false,
        provider_keys: [],
    });
});

run_test("event selection toggle follows checkbox state", () => {
    view.initialize();

    const $options = $.create("event options");
    const $toggle = $.create("event selection toggle");
    const $push = $.create("push event checkbox").prop("checked", true);
    const $issues = $.create("issues event checkbox").prop("checked", true);
    const $events = $.create("event checkboxes", {elements: [$push[0], $issues[0]]});

    $toggle.set_closest_results(".hover-pipeline-event-options", $options);
    $push.set_closest_results(".hover-pipeline-event-options", $options);
    $options.set_find_results("input[type='checkbox']", $events);
    $options.set_find_results(".hover-pipeline-event-selection-toggle", $toggle);

    const click = $("body").get_on_handler("click", ".hover-pipeline-event-selection-toggle");
    click({currentTarget: $toggle[0]});
    assert.equal($push.prop("checked"), false);
    assert.equal($issues.prop("checked"), false);
    assert.equal($toggle.text(), "translated: Select all");

    click({currentTarget: $toggle[0]});
    assert.equal($push.prop("checked"), true);
    assert.equal($issues.prop("checked"), true);
    assert.equal($toggle.text(), "translated: Deselect all");

    $push.prop("checked", false);
    const change = $("body").get_on_handler(
        "change",
        ".hover-pipeline-event-options input[type='checkbox']",
    );
    change({currentTarget: $push[0]});
    assert.equal($toggle.text(), "translated: Select all");
});

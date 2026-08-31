"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

set_global("HTMLInputElement", class HTMLInputElement {});

let get_request;
let post_request;
let patch_request;
mock_esm("../src/channel", {
    get(options) {
        get_request = options;
    },
    post(options) {
        post_request = options;
    },
    patch(options) {
        patch_request = options;
    },
});
mock_esm("../src/inbox_ui", {hide() {}});
mock_esm("../src/left_sidebar_navigation_area", {select_top_left_corner_item() {}});
mock_esm("../src/recent_view_ui", {hide() {}});
mock_esm("../src/stream_data", {
    subscribed_subs: () => [{name: "Engineering"}],
    can_post_messages_in_stream: () => true,
});
mock_esm("../src/user_settings", {user_settings: {timezone: "Asia/Kuala_Lumpur"}});

const view = zrequire("hover_pipelines_view");

function pipeline(overrides = {}) {
    return {
        id: 1,
        name: "Release brief",
        instruction: "Summarize release activity.",
        input_destination: "Engineering",
        input_topic: "Releases",
        input_availability: "available",
        run_health: "healthy",
        data_sources: [],
        source_warnings: [],
        cadence: "daily",
        weekday: null,
        local_time: "09:00",
        timezone: "Asia/Kuala_Lumpur",
        output_destination: "Engineering",
        output_topic: "Release brief",
        lifecycle_state: "active",
        status: "active",
        available_transitions: ["edit", "pause"],
        last_run_at: "2026-08-31T01:00:00Z",
        date_created: "2026-08-01T01:00:00Z",
        ...overrides,
    };
}

function topic(overrides = {}) {
    return {
        input_destination: "Engineering",
        input_topic: "Releases",
        input_availability: "available",
        data_sources: [],
        ...overrides,
    };
}

function load_view(pipelines, topics = [topic()]) {
    view.test.reset();
    get_request = undefined;
    post_request = undefined;
    patch_request = undefined;
    view.initialize();
    view.show();
    get_request.success({pipelines, topics, can_create: true});
}

function event_target(name, attributes) {
    const $element = $.create(name);
    for (const [key, value] of Object.entries(attributes)) {
        $element.attr(key, String(value));
    }
    return $element[0];
}

function set_configure_form() {
    $("#hover_pipeline_name").val("Release brief");
    $("#hover_pipeline_instruction").val("Summarize release activity.");
    $("#hover_pipeline_cadence").val("daily");
    $("#hover_pipeline_weekday").val("4");
    $("#hover_pipeline_time").val("09:00");
    $("#hover_pipeline_output_destination").val("Engineering");
    $("#hover_pipeline_output_topic").val("Release brief");
}

run_test("Topic selection deduplicates by normalized Space and Topic identity", () => {
    const github = {
        id: 1,
        name: "GitHub releases",
        provider_key: "github",
        provider_name: "GitHub",
        provider_logo_url: "/github.svg",
        state: "active",
        health_status: "healthy",
    };
    const gitlab = {...github, id: 2, name: "GitLab releases", provider_key: "gitlab"};
    const rows = view.deduplicate_topics_for_testing([
        {
            input_destination: "Engineering",
            input_topic: "Release activity",
            input_availability: "available",
            data_sources: [github],
        },
        {
            input_destination: "engineering",
            input_topic: " release ACTIVITY ",
            input_availability: "topic_unavailable",
            data_sources: [github, gitlab],
        },
        {
            input_destination: "Product",
            input_topic: "Release activity",
            input_availability: "available",
            data_sources: [],
        },
    ]);

    assert.equal(rows.length, 2);
    assert.deepEqual(
        rows[0].data_sources.map((source) => source.id),
        [1, 2],
    );
    assert.equal(rows[0].input_availability, "available");
    assert.equal(rows[1].input_destination, "Product");
});

run_test("schedule summary is natural language and omits timezone", () => {
    assert.equal(
        view.schedule_summary_for_testing("weekdays", null, "09:00"),
        "translated: translated: Every weekday at 9:00 AM",
    );
    assert.equal(
        view.schedule_summary_for_testing("weekly", 4, "16:30"),
        "translated: Every translated: Friday at 4:30 PM",
    );
});

run_test("repair submission targets the existing Pipeline", () => {
    assert.equal(view.pipeline_submission_target_for_testing(undefined), "/json/hover/pipelines");
    assert.equal(view.pipeline_submission_target_for_testing(42), "/json/hover/pipelines/42");
});

run_test("lifecycle actions keep permissions and Topic health orthogonal", () => {
    assert.deepEqual(view.lifecycle_actions_for_testing("active", "available", ["edit", "pause"]), {
        can_activate: false,
        can_continue_setup: false,
        can_show_pause: true,
        can_show_resume: false,
        can_pause: true,
        can_resume: false,
        topic_needs_repair: false,
    });
    assert.deepEqual(view.lifecycle_actions_for_testing("paused", "topic_unavailable", ["edit"]), {
        can_activate: false,
        can_continue_setup: false,
        can_show_pause: false,
        can_show_resume: true,
        can_pause: false,
        can_resume: false,
        topic_needs_repair: true,
    });
    assert.deepEqual(
        view.lifecycle_actions_for_testing("draft", "available", ["edit", "activate"]),
        {
            can_activate: true,
            can_continue_setup: true,
            can_show_pause: false,
            can_show_resume: false,
            can_pause: false,
            can_resume: false,
            topic_needs_repair: false,
        },
    );
    assert.equal(view.lifecycle_transition_target_for_testing("pause"), "paused");
    assert.equal(view.lifecycle_transition_target_for_testing("resume"), "active");
    assert.equal(view.lifecycle_transition_target_for_testing("activate"), "active");
});

run_test("filters All, Active, Drafts, and Paused by lifecycle and composes with search", () => {
    load_view([
        pipeline(),
        pipeline({
            id: 2,
            name: "Planning draft",
            lifecycle_state: "draft",
            status: "draft",
            available_transitions: ["edit", "activate"],
        }),
        pipeline({
            id: 3,
            name: "Customer pulse",
            lifecycle_state: "paused",
            status: "paused",
            available_transitions: ["edit", "resume"],
        }),
    ]);

    let html = $("#hover-pipelines-view").html();
    assert.match(html, /Release brief/);
    assert.match(html, /Planning draft/);
    assert.match(html, /Customer pulse/);
    assert.match(html, /data-pipeline-filter="paused"/);

    const filter = $("body").get_on_handler("click", "[data-pipeline-filter]");
    filter({currentTarget: event_target("paused filter", {"data-pipeline-filter": "paused"})});
    html = $("#hover-pipelines-view").html();
    assert.doesNotMatch(html, /Release brief/);
    assert.doesNotMatch(html, /Planning draft/);
    assert.match(html, /Customer pulse/);

    const $search = $.create("pipeline search").val("planning");
    $("body").get_on_handler(
        "input",
        ".hover-pipeline-index-search",
    )({
        currentTarget: $search[0],
    });
    html = $("#hover-pipelines-view").html();
    assert.doesNotMatch(html, /Planning draft/);
    assert.match(html, /No pipelines match this view/);
});

run_test("Pause and Resume render pending, success, and error feedback", () => {
    load_view([pipeline()]);
    const toggle = $("body").get_on_handler("click", ".hover-pipeline-row-toggle");
    toggle({currentTarget: event_target("row toggle", {"data-pipeline-id": 1})});
    let html = $("#hover-pipelines-view").html();
    assert.match(html, /class="button rounded hover-pipeline-pause"/);

    const pause = $("body").get_on_handler("click", ".hover-pipeline-pause");
    pause({currentTarget: event_target("pause", {"data-pipeline-id": 1})});
    assert.equal(patch_request.url, "/json/hover/pipelines/1");
    assert.equal(patch_request.data.lifecycle_state, '"paused"');
    html = $("#hover-pipelines-view").html();
    assert.match(html, /Pausing/);
    assert.match(html, /hover-pipeline-pause[^>]*disabled/);

    patch_request.success({
        pipeline: pipeline({
            lifecycle_state: "paused",
            status: "paused",
            available_transitions: ["edit", "resume"],
        }),
    });
    html = $("#hover-pipelines-view").html();
    assert.match(html, /Pipeline paused/);
    assert.match(html, /hover-pipeline-resume/);

    const resume = $("body").get_on_handler("click", ".hover-pipeline-resume");
    resume({currentTarget: event_target("resume", {"data-pipeline-id": 1})});
    assert.equal(patch_request.data.lifecycle_state, '"active"');
    assert.match($("#hover-pipelines-view").html(), /Resuming/);
    patch_request.error();
    html = $("#hover-pipelines-view").html();
    assert.match(html, /Could not resume this Pipeline/);
    assert.match(html, /hover-pipeline-resume/);
});

run_test("lifecycle actions remain visible but disabled without permission", () => {
    load_view([
        pipeline({available_transitions: []}),
        pipeline({
            id: 2,
            lifecycle_state: "paused",
            status: "paused",
            available_transitions: [],
        }),
    ]);
    const toggle = $("body").get_on_handler("click", ".hover-pipeline-row-toggle");
    toggle({currentTarget: event_target("active toggle", {"data-pipeline-id": 1})});
    toggle({currentTarget: event_target("paused toggle", {"data-pipeline-id": 2})});
    const html = $("#hover-pipelines-view").html();
    assert.match(html, /hover-pipeline-pause[^>]*disabled/);
    assert.match(html, /hover-pipeline-resume[^>]*disabled/);
    assert.match(html, /Only the creator or a workspace administrator/);
});

run_test("Pause returns focus to the selected filter when the row leaves the result set", () => {
    load_view([pipeline()]);
    $("body").get_on_handler(
        "click",
        "[data-pipeline-filter]",
    )({
        currentTarget: event_target("active filter", {"data-pipeline-filter": "active"}),
    });
    $("body").get_on_handler(
        "click",
        ".hover-pipeline-row-toggle",
    )({
        currentTarget: event_target("active row", {"data-pipeline-id": 1}),
    });
    $("body").get_on_handler(
        "click",
        ".hover-pipeline-pause",
    )({
        currentTarget: event_target("pause active", {"data-pipeline-id": 1}),
    });
    patch_request.success({
        pipeline: pipeline({
            lifecycle_state: "paused",
            status: "paused",
            available_transitions: ["edit", "resume"],
        }),
    });

    assert.doesNotMatch($("#hover-pipelines-view").html(), /Release brief/);
    assert.equal($('[data-pipeline-filter="active"]').is_focused(), true);
});

run_test("creates a Draft from Configure with the canonical POST", () => {
    load_view([]);
    $("body").get_on_handler("click", ".hover-pipeline-create")();
    $("body").get_on_handler(
        "click",
        ".hover-pipeline-topic-choice",
    )({
        currentTarget: event_target("topic", {
            "data-space": "Engineering",
            "data-topic": "Releases",
        }),
    });
    $("body").get_on_handler("click", ".hover-pipeline-topic-continue")();
    set_configure_form();
    assert.match($("#hover-pipelines-view").html(), /hover-pipeline-save-draft/);
    $("body").get_on_handler("click", ".hover-pipeline-save-draft")();
    assert.equal(post_request.url, "/json/hover/pipelines");
    assert.equal(post_request.data.lifecycle_state, '"draft"');
    assert.equal($(".hover-pipeline-submit, .hover-pipeline-save-draft").prop("disabled"), true);
    assert.match($(".hover-pipeline-save-draft").text(), /Saving/);

    post_request.error();
    assert.equal($(".hover-pipeline-submit, .hover-pipeline-save-draft").prop("disabled"), false);
    assert.match($(".hover-pipeline-request-status").text(), /Could not save the pipeline/);

    $("body").get_on_handler("click", ".hover-pipeline-save-draft")();
    post_request.success({
        pipeline: pipeline({
            lifecycle_state: "draft",
            status: "draft",
            available_transitions: ["edit", "activate"],
            last_run_at: null,
        }),
    });
    const html = $("#hover-pipelines-view").html();
    assert.match(html, /Draft saved/);
    assert.match(html, /hover-pipeline-continue-setup/);
});

run_test("continues and activates the same Draft Pipeline ID", () => {
    const saved_draft = pipeline({
        id: 9,
        lifecycle_state: "draft",
        status: "draft",
        available_transitions: ["edit", "activate"],
        last_run_at: null,
    });
    load_view([saved_draft]);
    $("body").get_on_handler(
        "click",
        ".hover-pipeline-continue-setup",
    )({
        currentTarget: event_target("continue setup", {"data-pipeline-id": 9}),
    });
    assert.match($("#hover-pipelines-view").html(), /Configure pipeline/);
    set_configure_form();
    $("body").get_on_handler(
        "submit",
        "#hover_pipeline_configure_form",
    )({
        preventDefault() {},
    });
    const html = $("#hover-pipelines-view").html();
    assert.match(html, /Activate pipeline/);
    assert.match(html, /hover-pipeline-save-draft/);

    $("body").get_on_handler("click", ".hover-pipeline-submit")();
    assert.equal(patch_request.url, "/json/hover/pipelines/9");
    assert.equal(patch_request.data.lifecycle_state, '"active"');
});

run_test("paused plus unavailable stays Paused after repair-oriented rendering", () => {
    load_view([
        pipeline({
            lifecycle_state: "paused",
            status: "needs_attention",
            input_availability: "topic_unavailable",
            available_transitions: ["edit"],
        }),
    ]);
    $("body").get_on_handler(
        "click",
        ".hover-pipeline-row-toggle",
    )({
        currentTarget: event_target("paused unavailable toggle", {"data-pipeline-id": 1}),
    });
    const html = $("#hover-pipelines-view").html();
    assert.match(html, /Needs attention/);
    assert.match(html, /leave this Pipeline paused/);
    assert.match(html, /Repair the input Topic before resuming/);
    assert.doesNotMatch(html, /Only the creator or a workspace administrator/);
    assert.match(html, /hover-pipeline-resume[^>]*disabled/);
    assert.doesNotMatch(html, /hover-pipeline-status--active/);
});

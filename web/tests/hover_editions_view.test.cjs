"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

let request;
let selected_row;
mock_esm("../src/channel", {
    get(options) {
        request = options;
        return {abort() {}};
    },
});
mock_esm("../src/inbox_ui", {hide() {}});
mock_esm("../src/recent_view_ui", {hide() {}});
mock_esm("../src/left_sidebar_navigation_area", {
    select_top_left_corner_item(selector) {
        selected_row = selector;
    },
});

const hover_editions_view = zrequire("hover_editions_view");

function edition_response() {
    const first = {
        title: "The venue handoff is ready",
        detail: "Start with the confirmed access plan, then share the arrival window.",
        update: {
            message_id: 42,
            space_name: "AIMTO Events",
            topic: "Venue readiness",
            url: "#narrow/channel/4/topic/Venue%20readiness/near/42",
            evidence_url: "/json/hover/spaces/4/generated-items/7/evidence",
        },
    };
    const second = {
        title: "Volunteer coverage is settled",
        detail: "The remaining shifts now have confirmed owners.",
        update: {
            message_id: 43,
            space_name: "AIMTO Events",
            topic: "Volunteer coverage",
            url: "#narrow/channel/4/topic/Volunteer%20coverage/near/43",
            evidence_url: null,
        },
    };
    return {
        sync_status: "current",
        editions: {
            morning: {
                edition: "morning",
                title: "A good place to start",
                covered_end: "2026-08-11T10:00:00Z",
                published_at: "2026-08-11T10:01:00Z",
                sections: {
                    urgency: [first],
                    unresolved_carryover: [second],
                    guidance: [],
                },
                all_clear: true,
            },
            end_of_day: {
                edition: "end_of_day",
                title: "Your day in motion",
                covered_end: "2026-08-11T18:00:00Z",
                published_at: "2026-08-11T18:01:00Z",
                sections: {
                    meaningful_movement: [first],
                    completed_work: [],
                    carryover: [],
                    delegated_dependencies: [],
                    tomorrow_preview: [],
                },
                all_clear: false,
            },
        },
    };
}

run_test("renders a prose-first full edition and a manual accessible focus view", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();

    assert.equal(request.url, "/json/hover/personal-editions");
    assert.equal(request.data, undefined);
    assert.equal(selected_row, ".top_left_daily_brief");
    request.success(edition_response());

    let html = $("#hover-editions-view").html();
    assert.match(html, /A good place to start/);
    assert.match(html, /Everything else is moving well/);
    assert.match(html, /Open update/);
    assert.match(html, /View sources/);
    assert.match(html, /aria-haspopup="dialog"/);
    assert.match(html, /\/json\/hover\/spaces\/4\/generated-items\/7\/evidence/);
    assert.match(html, /AIMTO Events\s+·\s+Venue readiness/);
    assert.doesNotMatch(html, /Add Todo|Create Todo/);
    assert.ok(
        html.indexOf("The venue handoff is ready") < html.indexOf("Volunteer coverage is settled"),
    );

    const focus_handler = $("body").get_on_handler("click", "#hover-edition-focus-view");
    focus_handler();
    html = $("#hover-editions-view").html();
    assert.match(html, /aria-roledescription="carousel"/);
    assert.match(html, /View all/);
    assert.match(html, /Item 1 of 2/);
    assert.doesNotMatch(html, /Volunteer coverage is settled/);
    assert.equal($(".hover-edition-carousel").is_focused(), true);

    let prevented = false;
    const key_handler = $("body").get_on_handler("keydown", ".hover-edition-carousel");
    $(".hover-edition-carousel").trigger("blur");
    key_handler({
        key: "ArrowRight",
        preventDefault() {
            prevented = true;
        },
    });
    html = $("#hover-editions-view").html();
    assert.equal(prevented, true);
    assert.match(html, /Item 2 of 2/);
    assert.match(html, /Volunteer coverage is settled/);
    assert.equal($(".hover-edition-carousel").is_focused(), true);

    $(".hover-edition-carousel").trigger("blur");
    key_handler({
        key: "ArrowLeft",
        preventDefault() {},
    });
    html = $("#hover-editions-view").html();
    assert.match(html, /Item 1 of 2/);
    assert.match(html, /The venue handoff is ready/);
    assert.equal($(".hover-edition-carousel").is_focused(), true);

    const all_handler = $("body").get_on_handler("click", "#hover-edition-view-all");
    all_handler();
    assert.match($("#hover-editions-view").html(), /Full edition/);
});

run_test("shows cached degradation and reloads when confirmed access changes", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();
    const degraded = edition_response();
    degraded.sync_status = "degraded";
    request.success(degraded);

    assert.match($("#hover-editions-view").html(), /latest available edition/);
    assert.match($("#hover-editions-view").html(), /Retry/);

    const previous_request = request;
    hover_editions_view.handle_access_change();
    assert.notEqual(request, previous_request);
    assert.equal(request.url, "/json/hover/personal-editions");
});

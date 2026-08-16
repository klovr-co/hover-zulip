"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

let request;
let selected_row;
mock_esm("../src/channel", {
    get(options) {
        request = options;
        return {
            abort() {
                options.aborted = true;
            },
        };
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

function opening_button_tag(html, id) {
    const match = html.match(new RegExp(`<button[^>]*id="${id}"[^>]*>`));
    assert.notEqual(match, null);
    return match[0];
}

function opening_tab_tag(html, edition) {
    const match = html.match(new RegExp(`<button[^>]*data-edition="${edition}"[^>]*>`));
    assert.notEqual(match, null);
    return match[0];
}

function opening_panel_tag(html, panel) {
    const match = html.match(new RegExp(`<div[^>]*id="hover-edition-panel-${panel}"[^>]*>`));
    assert.notEqual(match, null);
    return match[0];
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
    assert.match(opening_button_tag(html, "hover-edition-previous"), / disabled/);
    assert.doesNotMatch(opening_button_tag(html, "hover-edition-next"), / disabled/);

    clock.tick(60_000);
    assert.match($("#hover-editions-view").html(), /Item 1 of 2/);

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
    assert.doesNotMatch(opening_button_tag(html, "hover-edition-previous"), / disabled/);
    assert.match(opening_button_tag(html, "hover-edition-next"), / disabled/);

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
    clock.reset();
});

run_test("renders the first-edition empty state", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();

    assert.match($("#hover-editions-view").html(), /Preparing your latest edition/);
    assert.match($("#hover-editions-view").html(), /hover-edition-loading/);
    request.success({
        sync_status: "empty",
        editions: {morning: null, end_of_day: null},
    });

    const html = $("#hover-editions-view").html();
    assert.match(html, /Your first edition will appear after confirmed Space updates arrive/);
    assert.match(html, /Your Daily Brief/);
    assert.doesNotMatch(html, /hover-edition-loading/);
    assert.doesNotMatch(html, /id="hover-edition-retry"/);
    assert.doesNotMatch(html, /id="hover-edition-focus-view"/);
});

run_test("renders a hard error and retries from loading state", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();
    const failed_request = request;

    failed_request.error({}, "error");
    let html = $("#hover-editions-view").html();
    assert.match(html, /Your edition could not be loaded/);
    assert.match(html, /id="hover-edition-retry"/);
    assert.doesNotMatch(html, /hover-edition-loading/);

    $("body").get_on_handler("click", "#hover-edition-retry")();
    assert.notEqual(request, failed_request);
    assert.equal(failed_request.aborted, true);
    assert.equal(request.url, "/json/hover/personal-editions");
    html = $("#hover-editions-view").html();
    assert.match(html, /Preparing your latest edition/);
    assert.match(html, /hover-edition-loading/);
    assert.doesNotMatch(html, /id="hover-edition-retry"/);

    request.success(edition_response());
    assert.match($("#hover-editions-view").html(), /A good place to start/);
});

run_test("switches Morning and End of day tabs with selected semantics", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();
    request.success(edition_response());
    const tab_handler = $("body").get_on_handler("click", ".hover-edition-tab");

    let html = $("#hover-editions-view").html();
    let morning_tab = opening_tab_tag(html, "morning");
    let end_of_day_tab = opening_tab_tag(html, "end_of_day");
    assert.match(morning_tab, /id="hover-edition-tab-morning"/);
    assert.match(morning_tab, /aria-controls="hover-edition-panel-morning"/);
    assert.match(morning_tab, /aria-selected="true"/);
    assert.match(morning_tab, /tabindex="0"/);
    assert.match(end_of_day_tab, /id="hover-edition-tab-end-of-day"/);
    assert.match(end_of_day_tab, /aria-controls="hover-edition-panel-end-of-day"/);
    assert.match(end_of_day_tab, /aria-selected="false"/);
    assert.match(end_of_day_tab, /tabindex="-1"/);
    for (const id of [
        "hover-edition-tab-morning",
        "hover-edition-tab-end-of-day",
        "hover-edition-panel-morning",
        "hover-edition-panel-end-of-day",
    ]) {
        assert.equal((html.match(new RegExp(`id="${id}"`, "g")) ?? []).length, 1);
    }
    assert.match(opening_panel_tag(html, "morning"), /role="tabpanel"/);
    assert.match(opening_panel_tag(html, "morning"), /aria-labelledby="hover-edition-tab-morning"/);
    assert.doesNotMatch(opening_panel_tag(html, "morning"), / hidden/);
    assert.match(opening_panel_tag(html, "end-of-day"), / hidden/);
    assert.match(html, /A good place to start/);

    const $end_of_day_tab = $(".end-of-day-tab").attr("data-edition", "end_of_day");
    tab_handler({currentTarget: $end_of_day_tab[0]});
    html = $("#hover-editions-view").html();
    morning_tab = opening_tab_tag(html, "morning");
    end_of_day_tab = opening_tab_tag(html, "end_of_day");
    assert.match(morning_tab, /aria-selected="false"/);
    assert.match(morning_tab, /tabindex="-1"/);
    assert.match(end_of_day_tab, /aria-selected="true"/);
    assert.match(end_of_day_tab, /tabindex="0"/);
    assert.match(opening_panel_tag(html, "morning"), / hidden/);
    assert.match(
        opening_panel_tag(html, "end-of-day"),
        /aria-labelledby="hover-edition-tab-end-of-day"/,
    );
    assert.doesNotMatch(opening_panel_tag(html, "end-of-day"), / hidden/);
    assert.equal($("#hover-edition-tab-end-of-day").is_focused(), true);
    assert.match(html, /Your day in motion/);
    assert.match(html, /A thoughtful close to what moved/);
    assert.doesNotMatch(html, /Everything else is moving well/);

    const $morning_tab = $(".morning-tab").attr("data-edition", "morning");
    tab_handler({currentTarget: $morning_tab[0]});
    html = $("#hover-editions-view").html();
    assert.match(opening_tab_tag(html, "morning"), /aria-selected="true"/);
    assert.match(opening_tab_tag(html, "end_of_day"), /aria-selected="false"/);
    assert.match(html, /A good place to start/);
    assert.match(html, /Everything else is moving well/);
    assert.equal($("#hover-edition-tab-morning").is_focused(), true);
});

run_test("supports roving keyboard navigation for edition tabs", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();
    request.success(edition_response());
    const key_handler = $("body").get_on_handler("keydown", ".hover-edition-tab");
    let prevented = 0;

    function press(key, edition) {
        const $tab = $(`.keyboard-${edition}-${key}`).attr("data-edition", edition);
        key_handler({
            currentTarget: $tab[0],
            key,
            preventDefault() {
                prevented += 1;
            },
        });
    }

    press("ArrowRight", "morning");
    let html = $("#hover-editions-view").html();
    assert.match(opening_tab_tag(html, "end_of_day"), /aria-selected="true"/);
    assert.match(opening_tab_tag(html, "end_of_day"), /tabindex="0"/);
    assert.equal($("#hover-edition-tab-end-of-day").is_focused(), true);

    press("ArrowLeft", "end_of_day");
    html = $("#hover-editions-view").html();
    assert.match(opening_tab_tag(html, "morning"), /aria-selected="true"/);
    assert.equal($("#hover-edition-tab-morning").is_focused(), true);

    press("End", "morning");
    html = $("#hover-editions-view").html();
    assert.match(opening_tab_tag(html, "end_of_day"), /aria-selected="true"/);
    assert.equal($("#hover-edition-tab-end-of-day").is_focused(), true);

    press("Home", "end_of_day");
    html = $("#hover-editions-view").html();
    assert.match(opening_tab_tag(html, "morning"), /aria-selected="true"/);
    assert.equal($("#hover-edition-tab-morning").is_focused(), true);
    assert.equal(prevented, 4);
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

run_test("selects the available edition when Morning is unavailable", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();
    const response = edition_response();
    response.editions.morning = null;
    request.success(response);

    const html = $("#hover-editions-view").html();
    assert.match(opening_tab_tag(html, "end_of_day"), /aria-selected="true"/);
    assert.match(html, /Your day in motion/);
});

run_test("ignores callbacks from stale and aborted requests", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();
    const stale_request = request;

    hover_editions_view.hide();
    assert.equal(stale_request.aborted, true);
    stale_request.success(edition_response());
    stale_request.error({}, "error");
    assert.equal($("#hover-editions-view").visible(), false);

    hover_editions_view.show();
    const current_request = request;
    current_request.error({}, "abort");
    assert.doesNotMatch($("#hover-editions-view").html(), /could not be loaded/);
});

run_test("reuses loaded data and defers hidden access refresh", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();
    hover_editions_view.show();
    request.success(edition_response());
    const loaded_request = request;

    hover_editions_view.hide();
    hover_editions_view.hide();
    hover_editions_view.show();
    assert.equal(request, loaded_request);
    assert.match($("#hover-editions-view").html(), /A good place to start/);

    hover_editions_view.hide();
    hover_editions_view.handle_access_change();
    assert.equal(request, loaded_request);
    hover_editions_view.show();
    assert.notEqual(request, loaded_request);
});

run_test("ignores invalid controls and supports button carousel navigation", () => {
    hover_editions_view.test.reset();
    hover_editions_view.initialize();

    $("body").get_on_handler("click", "#hover-edition-view-all")();
    $("body").get_on_handler("click", "#hover-edition-next")();

    const tab_handler = $("body").get_on_handler("click", ".hover-edition-tab");
    const $invalid_tab = $(".invalid-edition-tab").attr("data-edition", "weekly");
    tab_handler({currentTarget: $invalid_tab[0]});

    const key_handler = $("body").get_on_handler("keydown", ".hover-edition-tab");
    let prevented = false;
    key_handler({
        currentTarget: $invalid_tab[0],
        key: "ArrowRight",
        preventDefault() {
            prevented = true;
        },
    });
    const $morning_tab = $(".unhandled-key-tab").attr("data-edition", "morning");
    key_handler({
        currentTarget: $morning_tab[0],
        key: "PageDown",
        preventDefault() {
            prevented = true;
        },
    });
    assert.equal(prevented, false);

    hover_editions_view.show();
    request.success(edition_response());
    $("body").get_on_handler("click", "#hover-edition-focus-view")();
    $("body").get_on_handler("click", "#hover-edition-next")();
    assert.match($("#hover-editions-view").html(), /Item 2 of 2/);
    $("body").get_on_handler("click", "#hover-edition-previous")();
    assert.match($("#hover-editions-view").html(), /Item 1 of 2/);
});

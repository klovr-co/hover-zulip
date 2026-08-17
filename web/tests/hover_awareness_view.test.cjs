"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
const inbox_ui = mock_esm("../src/inbox_ui");
mock_esm("../src/message_view_header", {render_title_area() {}});
mock_esm("../src/people", {small_avatar_url_for_user_id: (user_id) => `/avatar/${user_id}`});
const recent_view_ui = mock_esm("../src/recent_view_ui");

const hover_awareness_view = zrequire("hover_awareness_view");

function generated_item() {
    return {
        id: 7,
        output_type: "progress_update",
        module: {key: "progress", name: "Progress", version: "v1"},
        source_summary: "From project updates",
        presentation: {
            label: "Progress update",
            importance: "high",
            state: "active",
            occurred_at: "2026-08-11T09:00:00+00:00",
            generated_at: "2026-08-11T09:01:00+00:00",
            published_at: "2026-08-11T09:02:00+00:00",
            run_reference: "run-18",
        },
        lineage: {
            is_latest: true,
            history_count: 2,
            history: [
                {
                    message_id: 42,
                    title: "Current plan",
                    state: "active",
                    occurred_at: "2026-08-11T09:00:00+00:00",
                    is_current: true,
                },
                {
                    message_id: 41,
                    title: "Earlier plan",
                    state: "active",
                    occurred_at: "2026-08-10T09:00:00+00:00",
                    is_current: false,
                },
            ],
        },
        evidence_available: true,
        evidence_url: "/json/hover/spaces/3/generated-items/7/evidence",
        sources: [],
        reviewed_payload: {summary: "Confirmed current plan"},
        revisions: [
            {
                id: 1,
                field_path: "summary",
                previous_value: "Likely plan",
                new_value: "Confirmed current plan",
                actor: {id: 9, full_name: "Reviewer"},
                timestamp: "2026-08-11T09:03:00+00:00",
                reason: "Confirmed",
                review_message_id: 43,
            },
        ],
        disputed_details: [],
        suggested_action: null,
    };
}

function awareness_item() {
    return {
        message_id: 42,
        generated_item_id: 7,
        space_id: 3,
        space_name: "AIMTO Events",
        stream_id: 4,
        topic: "Project updates",
        rendered_content: "<p>Current plan</p>",
        sender_id: 9,
        sender_name: "Hover",
        timestamp: "2026-08-11T09:02:00+00:00",
        is_unread: true,
        rank: 780,
        reasons: ["mention", "important"],
        hover_generated_item: generated_item(),
    };
}

run_test("For You loads ranked canonical items with accessible actions", ({override}) => {
    hover_awareness_view.test.reset();
    let request;
    let inbox_hidden = false;
    let recent_hidden = false;
    override(inbox_ui, "hide", () => {
        inbox_hidden = true;
    });
    override(recent_view_ui, "hide", () => {
        recent_hidden = true;
    });
    override(channel, "get", (options) => {
        request = options;
        return {abort() {}};
    });

    hover_awareness_view.show("for_you");

    assert.equal(inbox_hidden, true);
    assert.equal(recent_hidden, true);
    assert.equal(request.url, "/json/hover/awareness");
    assert.deepEqual(request.data, {surface: '"for_you"'});
    request.success({
        surface: "for_you",
        items: [awareness_item()],
    });

    const html = $("#hover-awareness-view").html();
    assert.match(html, /For You/);
    assert.match(html, /role="feed"/);
    assert.match(html, /role="article"/);
    assert.match(html, /src="\/avatar\/9"/);
    assert.match(html, /Mentioned you/);
    assert.match(html, /Latest state/);
    assert.match(html, /Confirmed current plan/);
    assert.match(html, /View history \(2\)/);
    assert.match(html, /near\/41/);
    assert.match(html, /View sources/);
    assert.match(html, /aria-label="translated: Unread"/);
});

run_test("Team Pulse exposes an empty state and retryable loading error", ({override}) => {
    hover_awareness_view.test.reset();
    const requests = [];
    override(inbox_ui, "hide", () => {});
    override(recent_view_ui, "hide", () => {});
    override(channel, "get", (options) => {
        requests.push(options);
        return {abort() {}};
    });

    hover_awareness_view.show("team_pulse");
    requests.at(-1).success({surface: "team_pulse", items: []});
    assert.match($("#hover-awareness-view").html(), /No important team developments yet/);

    hover_awareness_view.hide();
    hover_awareness_view.show("team_pulse");
    requests.at(-1).error({}, "error");
    const html = $("#hover-awareness-view").html();
    assert.match(html, /Live awareness could not be loaded/);
    assert.match(html, /id="hover-awareness-retry"/);
});

run_test("renders review fallbacks and suppresses unknown reasons", ({override}) => {
    hover_awareness_view.test.reset();
    let request;
    override(inbox_ui, "hide", () => {});
    override(recent_view_ui, "hide", () => {});
    override(channel, "get", (options) => {
        request = options;
        return {abort() {}};
    });

    hover_awareness_view.show("for_you");
    const without_review = awareness_item();
    without_review.message_id = 43;
    without_review.hover_generated_item.revisions = [];
    without_review.hover_generated_item.lineage.history = [];
    without_review.hover_generated_item.lineage.history_count = 1;
    without_review.reasons = ["unknown_reason"];

    const reviewed_without_summary = awareness_item();
    reviewed_without_summary.message_id = 44;
    reviewed_without_summary.is_unread = false;
    reviewed_without_summary.reasons = ["unknown_reason"];
    reviewed_without_summary.hover_generated_item.reviewed_payload = {};

    request.success({
        surface: "for_you",
        items: [without_review, reviewed_without_summary],
    });

    const html = $("#hover-awareness-view").html();
    assert.doesNotMatch(html, /Why this is here/);
    assert.match(html, /Updated through Review/);
    assert.match(html, /near\/43/);
});

run_test("ignores stale, mismatched, and aborted responses", ({override}) => {
    hover_awareness_view.test.reset();
    const requests = [];
    let abort_count = 0;
    override(inbox_ui, "hide", () => {});
    override(recent_view_ui, "hide", () => {});
    override(channel, "get", (options) => {
        requests.push(options);
        return {
            abort() {
                abort_count += 1;
            },
        };
    });

    hover_awareness_view.show("for_you");
    hover_awareness_view.show("team_pulse");
    assert.equal(abort_count, 1);

    requests[0].success({surface: "for_you", items: [awareness_item()]});
    requests[0].error({}, "error");
    requests[1].success({surface: "for_you", items: [awareness_item()]});
    assert.doesNotMatch($("#hover-awareness-view").html(), /Current plan/);

    requests[1].error({}, "abort");
    requests[1].success({surface: "team_pulse", items: []});
    assert.match($("#hover-awareness-view").html(), /No important team developments yet/);

    const request_count = requests.length;
    hover_awareness_view.show("team_pulse");
    assert.equal(requests.length, request_count);

    hover_awareness_view.hide();
    requests[1].success({surface: "team_pulse", items: [awareness_item()]});
    hover_awareness_view.hide();
    assert.equal($("#hover-awareness-view").html(), "");
});

run_test("retries and refreshes only while visible", ({override}) => {
    hover_awareness_view.test.reset();
    const requests = [];
    override(inbox_ui, "hide", () => {});
    override(recent_view_ui, "hide", () => {});
    override(channel, "get", (options) => {
        requests.push(options);
        return {abort() {}};
    });

    hover_awareness_view.initialize();
    hover_awareness_view.test.render();
    $("body").get_on_handler("click", "#hover-awareness-retry")();
    assert.equal(requests.length, 0);

    hover_awareness_view.show("for_you");
    hover_awareness_view.handle_realtime_change();
    hover_awareness_view.handle_realtime_change();
    clock.tick(100);
    assert.equal(requests.length, 2);

    $("body").get_on_handler("click", "#hover-awareness-retry")();
    assert.equal(requests.length, 3);

    hover_awareness_view.hide();
    hover_awareness_view.handle_realtime_change();
    clock.tick(100);
    assert.equal(requests.length, 3);
});

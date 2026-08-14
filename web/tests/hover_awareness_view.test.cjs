"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
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

run_test("For You loads ranked canonical items with accessible actions", ({override}) => {
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
        items: [
            {
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
            },
        ],
    });

    const html = $("#cf-awareness-view").html();
    assert.match(html, /For You/);
    assert.match(html, /cf-awareness-card[^"]*cf-awareness-card--unread/);
    assert.match(html, /class="cf-awareness-card__content rendered_markdown"/);
    assert.match(html, /class="cf-source-action cf-source-action--evidence"/);
    assert.match(html, /data-cf-evidence-url=/);
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
    assert.doesNotMatch(
        html,
        /hover-awareness|hover-source-pill|hover-view-evidence|message_content/,
    );
});

run_test("Team Pulse exposes an empty state and retryable loading error", ({override}) => {
    const requests = [];
    override(inbox_ui, "hide", () => {});
    override(recent_view_ui, "hide", () => {});
    override(channel, "get", (options) => {
        requests.push(options);
        return {abort() {}};
    });

    hover_awareness_view.show("team_pulse");
    requests.at(-1).success({surface: "team_pulse", items: []});
    assert.match($("#cf-awareness-view").html(), /No important team developments yet/);

    hover_awareness_view.hide();
    hover_awareness_view.show("team_pulse");
    requests.at(-1).error({}, "error");
    const html = $("#cf-awareness-view").html();
    assert.match(html, /Live awareness could not be loaded/);
    assert.match(html, /id="cf-awareness-retry"/);
    assert.match(html, /class="cf-button cf-button--secondary"/);
    assert.doesNotMatch(html, /class="button rounded small"/);
});

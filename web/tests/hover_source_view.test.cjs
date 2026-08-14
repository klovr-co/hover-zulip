"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

let space;
let requests;

mock_esm("../src/channel", {
    post(options) {
        requests.push(options);
        return {
            abort() {
                options.aborted = true;
            },
        };
    },
});
mock_esm("../src/hover_spaces", {get_by_id: () => space});
mock_esm("../src/inbox_ui", {hide() {}});
mock_esm("../src/recent_view_ui", {hide() {}});

const hover_source_view = zrequire("hover_source_view");

function make_attachment() {
    return {
        id: 8,
        state: "active",
        can_browse_records: true,
        source: {
            display_name: "Venue team",
            provider_key: "whatsapp",
            source_type: "group",
            account_display_name: "AIMTO conversations",
        },
    };
}

function reset_view() {
    hover_source_view.clear();
    requests = [];
    space = {id: 3, name: "AIMTO Events", attachments: [make_attachment()]};
    hover_source_view.initialize();
    window.location.hash = "#hover/space/3/source/8";
}

function make_record(id, timestamp, text) {
    return {
        id,
        sender_display_name: id === "record-1" ? "Alex <Admin>" : "Priya",
        timestamp,
        content: {
            text,
            voice_transcript: id === "record-1" ? "The handoff is recorded." : null,
            media_description: id === "record-1" ? "A venue floor plan" : null,
        },
        media:
            id === "record-1"
                ? {
                      type: "document",
                      mime_type: "application/pdf",
                      byte_size: 2048,
                      available: false,
                  }
                : null,
        reply_context:
            id === "record-1"
                ? {
                      sender_display_name: "Morgan",
                      timestamp: "2026-08-10T08:55:00Z",
                      excerpt: "Use <main> entrance",
                  }
                : null,
    };
}

function response(records, {next_cursor = "", has_more = false} = {}) {
    return {
        source: {
            attachment_id: 8,
            display_name: "Venue team",
            provider_key: "whatsapp",
            source_type: "group",
            account_display_name: "AIMTO conversations",
            state: "active",
        },
        records,
        next_cursor,
        has_more,
    };
}

run_test("renders loading and first-page empty states", () => {
    reset_view();

    assert.equal(hover_source_view.show(3, 8), true);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, "/json/hover/spaces/3/sources/8/records/browse");
    assert.deepEqual(requests[0].data, {
        cursor: "null",
        limit: "30",
        query: '""',
    });
    assert.match($("#cf-source-view").html(), /Loading Source records/);
    assert.match($("#cf-source-view").html(), /Source records · Read-only/);

    requests[0].success(response([]));
    const html = $("#cf-source-view").html();
    assert.match(html, /This Source has no records in its confirmed history/);
    assert.doesNotMatch(html, /class="cf-source-record"/);
});

run_test("renders records and searches with a no-match state", () => {
    reset_view();
    hover_source_view.show(3, 8);
    requests[0].success(
        response(
            [
                make_record(
                    "record-1",
                    "2026-08-10T09:00:00Z",
                    "Venue <script>alert(1)</script> ready",
                ),
            ],
            {next_cursor: "next-page", has_more: true},
        ),
    );

    const populated_html = $("#cf-source-view").html();
    assert.match(populated_html, /data-record-id="record-1"/);
    assert.match(populated_html, /Alex &lt;Admin&gt;/);
    assert.match(populated_html, /Venue &lt;script&gt;alert\(1\)&lt;\/script&gt; ready/);
    assert.match(populated_html, /Use &lt;main&gt; entrance/);
    assert.match(populated_html, /Voice transcript/);
    assert.match(populated_html, /The handoff is recorded/);
    assert.match(populated_html, /application\/pdf/);
    assert.match(populated_html, /2\.0 KB/);
    assert.match(populated_html, /Unavailable/);
    assert.match(populated_html, /id="cf-source-load-older"/);
    assert.doesNotMatch(populated_html, /hover-source-|fa fa-|zulip-icon/);

    $("#cf-source-search").val("  venue   handoff  ");
    let default_prevented = false;
    $("body").get_on_handler(
        "submit",
        "#cf-source-search-form",
    )({
        preventDefault() {
            default_prevented = true;
        },
    });
    assert.equal(default_prevented, true);
    assert.equal(requests.length, 2);
    assert.equal(requests[0].aborted, true);
    assert.deepEqual(requests[1].data, {
        cursor: "null",
        limit: "30",
        query: '"venue handoff"',
    });
    assert.doesNotMatch($("#cf-source-view").html(), /record-1/);

    requests[1].success(response([]));
    assert.match($("#cf-source-view").html(), /No records match this search/);
});

run_test("retries a retryable first-page error", () => {
    reset_view();
    hover_source_view.show(3, 8);

    requests[0].error(
        {
            responseJSON: {
                retryable: true,
                error_code: "rate_limited",
                retry_after_seconds: 5,
            },
        },
        "error",
    );
    const error_html = $("#cf-source-view").html();
    assert.match(error_html, /rate limited/);
    assert.match(error_html, /5 seconds/);
    assert.match(error_html, /id="cf-source-retry"/);

    $("body").get_on_handler("click", "#cf-source-retry")();
    assert.equal(requests.length, 2);
    assert.equal(requests[0].aborted, true);
    assert.deepEqual(requests[1].data, {
        cursor: "null",
        limit: "30",
        query: '""',
    });
    assert.match($("#cf-source-view").html(), /Loading Source records/);
});

run_test("loads older records and preserves the reading position", () => {
    reset_view();
    const $view = $("#cf-source-view");
    $view[0].scrollHeight = 100;
    $view.scrollTop(25);
    hover_source_view.show(3, 8);
    requests[0].success(
        response([make_record("record-1", "2026-08-10T09:00:00Z", "First page")], {
            next_cursor: "next-page",
            has_more: true,
        }),
    );

    $("body").get_on_handler("click", "#cf-source-load-older")();
    assert.equal(requests.length, 2);
    assert.deepEqual(requests[1].data, {
        cursor: '"next-page"',
        limit: "30",
        query: '""',
    });
    assert.match($("#cf-source-view").html(), /Loading older records/);
    assert.doesNotMatch($("#cf-source-view").html(), /id="cf-source-load-older"/);

    $view[0].scrollHeight = 180;
    requests[1].success(response([make_record("record-2", "2026-08-09T09:00:00Z", "Older page")]));
    const html = $view.html();
    assert.ok(html.indexOf("Older page") < html.indexOf("First page"));
    assert.equal($view.scrollTop(), 105);
    assert.doesNotMatch(html, /id="cf-source-load-older"/);
});

run_test("closes the active Source view when browse permission is revoked", () => {
    reset_view();
    hover_source_view.show(3, 8);
    requests[0].success(
        response([make_record("record-1", "2026-08-10T09:00:00Z", "Visible record")]),
    );
    assert.match($("#cf-source-view").html(), /Visible record/);

    space = {...space, attachments: [{...space.attachments[0], can_browse_records: false}]};
    hover_source_view.handle_space_event();

    assert.equal(window.location.hash, "");
    assert.equal($("#cf-source-view").html(), "");
    assert.equal(requests[0].aborted, true);
    assert.equal(hover_source_view.show(3, 8), false);
    assert.equal(requests.length, 1);
});

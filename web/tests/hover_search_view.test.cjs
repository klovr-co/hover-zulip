"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

let request;
let abort_count = 0;
const flag_updates = [];
const starred_adds = [];
const starred_removes = [];
let authorized_spaces = [{id: 3, state: "launched"}];
mock_esm("../src/channel", {
    post(options) {
        request = options;
        return {
            abort() {
                abort_count += 1;
            },
        };
    },
});
mock_esm("../src/inbox_ui", {hide() {}});
mock_esm("../src/hover_spaces", {get_all: () => authorized_spaces});
mock_esm("../src/recent_view_ui", {hide() {}});
mock_esm("../src/left_sidebar_navigation_area", {select_top_left_corner_item() {}});
mock_esm("../src/message_flags", {
    send_flag_update_for_messages(...args) {
        flag_updates.push(args);
    },
});
mock_esm("../src/starred_messages", {
    add(ids) {
        starred_adds.push(ids);
    },
    remove(ids) {
        starred_removes.push(ids);
    },
});
mock_esm("../src/starred_messages_ui", {rerender_ui() {}, update_starred_flag() {}});

const hover_search_view = zrequire("hover_search_view");

function response() {
    return {
        query: "venue handoff",
        knowledge: [
            {
                kind: "generated",
                message_id: 42,
                space: {id: 3, name: "AIMTO Events"},
                topic: "Progress",
                sender_name: "Hover Bot",
                timestamp: "2026-08-11T10:00:00Z",
                rendered_content: "<p>Venue handoff is ready.</p>",
                module_name: "Progress Tracker",
                output_type: "progress_update",
                saved: false,
                saveable: true,
                url: "/#narrow/channel/4/topic/Progress/near/42",
            },
        ],
        sources: [
            {
                kind: "source",
                space: {id: 3, name: "AIMTO Events"},
                source: {
                    attachment_id: 8,
                    display_name: "Venue team",
                    provider_key: "whatsapp",
                    source_type: "group",
                    account_display_name: "AIMTO conversations",
                    state: "active",
                },
                record: {
                    id: "record_11111111111111111111111111111111",
                    sender_display_name: "Alex",
                    timestamp: "2026-08-11T09:00:00Z",
                    content: {
                        text: "<img src=x onerror=alert(1)>",
                        voice_transcript: null,
                        media_description: null,
                    },
                    media: null,
                    reply_context: null,
                },
                saveable: false,
            },
        ],
        source_unavailable_count: 0,
    };
}

run_test("empty searches reset state without rendering a hidden view", () => {
    hover_search_view.test.search(" ".repeat(3));
    assert.equal(request, undefined);
    assert.equal($("#hover-search-view").html(), "never-been-set");
});

run_test("knowledge ranks before read-only Sources and uses native starred state", () => {
    hover_search_view.initialize();
    hover_search_view.show();
    hover_search_view.test.search("  venue   handoff ");
    assert.equal(request.url, "/json/hover/search");
    assert.deepEqual(request.data, {query: JSON.stringify("venue handoff")});
    request.success(response());

    const html = $("#hover-search-view").html();
    assert.ok(
        html.indexOf('id="hover-search-knowledge-heading"') <
            html.indexOf('id="hover-search-sources-heading"'),
    );
    assert.match(html, /Generated update/);
    assert.match(html, /Source evidence cannot be saved/);
    assert.match(html, /&lt;img/);
    assert.doesNotMatch(html, /<img src=x onerror=alert\(1\)>/);
    assert.match(html, /data-message-id="42"/);
    assert.equal((html.match(/hover-search-save-button/g) ?? []).length, 1);

    const $button = $(".hover-search-save-button").attr("data-message-id", "42");
    const handler = $("body").get_on_handler("click", ".hover-search-save-button");
    handler({currentTarget: $button[0]});
    assert.deepEqual(flag_updates, [[[42], "starred", "add"]]);
    assert.deepEqual(starred_adds, [[42]]);
    assert.match($("#hover-search-view").html(), /Remove from Saved/);
    handler({currentTarget: $button[0]});
    assert.deepEqual(flag_updates.at(-1), [[42], "starred", "remove"]);
    assert.deepEqual(starred_removes, [[42]]);
    assert.match($("#hover-search-view").html(), /aria-pressed="false"/);
    const $unknown_button = $("#unknown-search-result").attr("data-message-id", "404");
    handler({currentTarget: $unknown_button[0]});

    authorized_spaces = [];
    hover_search_view.handle_space_event();
    assert.doesNotMatch($("#hover-search-view").html(), /Venue handoff is ready/);
    assert.match($("#hover-search-view").html(), /Space access changed/);

    // A response that was already in flight cannot reintroduce revoked results.
    hover_search_view.test.search("venue handoff");
    request.success(response());
    assert.doesNotMatch($("#hover-search-view").html(), /Venue handoff is ready/);
});

run_test("later searches replace stale requests", () => {
    hover_search_view.test.search("first");
    const first_request = request;
    const previous_abort_count = abort_count;
    hover_search_view.test.search("second");
    assert.equal(abort_count, previous_abort_count + 1);
    assert.equal(JSON.parse(request.data.query), "second");
    // An old success is ignored by the request generation guard.
    first_request.success(response());
    assert.match($("#hover-search-view").html(), /value="second"/);
});

run_test("submit and request errors preserve request ordering", () => {
    hover_search_view.initialize();
    hover_search_view.show();
    $("#hover-global-search-input").val("  network   issue ");
    const submit_handler = $("body").get_on_handler("submit", "#hover-global-search-form");
    let prevented = false;
    submit_handler({
        preventDefault() {
            prevented = true;
        },
    });
    assert.equal(prevented, true);
    assert.equal(JSON.parse(request.data.query), "network issue");

    request.error({}, "abort");
    request.error({}, "error");
    assert.match($("#hover-search-view").html(), /Search could not be completed/);

    const stale_request = request;
    hover_search_view.test.search("replacement");
    stale_request.error({}, "error");
    assert.match($("#hover-search-view").html(), /value="replacement"/);
});

run_test("hide aborts active searches and is idempotent", () => {
    hover_search_view.show();
    hover_search_view.test.search("hide me");
    const previous_abort_count = abort_count;
    hover_search_view.hide();
    assert.equal(abort_count, previous_abort_count + 1);
    hover_search_view.hide();
});

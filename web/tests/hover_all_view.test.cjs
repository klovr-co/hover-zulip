"use strict";

const assert = require("node:assert/strict");

const {run_test} = require("./lib/test.cjs");

run_test("renders stable Module and Source filter keys", () => {
    const html = require("../templates/hover_all_view_filters.hbs")({
        space_name: "AIMTO Events",
        modules: [
            {
                key: "conversation_digest",
                name: "Conversation Digest",
                icon_name: "file-text",
                count: 3,
            },
        ],
        sources: [
            {
                source_key: "42",
                name: "Mentors & Volunteers",
                icon_name: "phone",
                count: 7,
            },
        ],
    });

    assert.match(html, /data-cf-feed-controls="all"/);
    assert.match(html, /data-cf-feed-filter-key="conversation_digest"/);
    assert.match(html, /data-cf-feed-filter-key="42"/);
    assert.match(html, /cf-feed-filter__label">Conversation Digest/);
    assert.match(html, /cf-feed-filter__count">7<\/span>/);
    assert.match(html, /class="cf-feed-controls__status" role="status" aria-live="polite"/);
    assert.doesNotMatch(html, /class="[^"]*hover-/);
});

run_test("renders latest and full-history controls for a Module topic", () => {
    const html = require("../templates/hover_module_view_filters.hbs")({
        space_name: "AIMTO Events",
        module_name: "Progress Tracker",
    });

    assert.match(html, /data-cf-feed-controls="module"/);
    assert.match(html, /data-cf-feed-history="latest"/);
    assert.match(html, /data-cf-feed-history="all"/);
    assert.match(html, />Progress Tracker<\/strong>/);
    assert.match(html, /Earlier updates remain in Full history/);
    assert.match(html, /class="cf-feed-controls__status" role="status" aria-live="polite"/);
    assert.doesNotMatch(html, /class="[^"]*hover-/);
});

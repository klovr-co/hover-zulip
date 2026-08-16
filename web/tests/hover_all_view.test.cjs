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
                icon: "zulip-icon-align-left",
                count: 3,
            },
        ],
        sources: [
            {
                source_key: "42",
                name: "Mentors & Volunteers",
                icon_class: "fa fa-whatsapp",
                count: 7,
            },
        ],
    });

    assert.match(html, /data-hover-filter-key="conversation_digest"/);
    assert.match(html, /data-hover-filter-key="42"/);
    assert.match(html, />Conversation Digest<span>3<\/span>/);
    assert.match(html, />Mentors &amp; Volunteers<span\s*>7<\/span>/);
});

run_test("renders latest and full-history controls for a Module topic", () => {
    const html = require("../templates/hover_module_view_filters.hbs")({
        space_name: "AIMTO Events",
        module_name: "Progress Tracker",
    });

    assert.match(html, /data-hover-history="latest"/);
    assert.match(html, /data-hover-history="all"/);
    assert.match(html, />Progress Tracker<\/strong>/);
    assert.match(html, /Earlier updates remain in Full history/);
});

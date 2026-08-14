"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_revision_trail = require("../templates/hover_revision_history.hbs");

const {run_test} = require("./lib/test.cjs");

const project_root = path.resolve(__dirname, "../..");
const behavior = fs.readFileSync(path.join(project_root, "web/src/hover_all_view.ts"), "utf8");
const component_css = fs.readFileSync(
    path.join(project_root, "web/styles/cofounder/components/feed-controls.css"),
    "utf8",
);
const message_template = fs.readFileSync(
    path.join(project_root, "web/templates/single_message.hbs"),
    "utf8",
);

run_test("revision history renders the Cofounder disclosure trail", () => {
    const html = render_revision_trail({
        revisions: [
            {
                actor: {full_name: "Priya Shah"},
                field_path: "venue.access_gate",
                new_value_display: '"East gate"',
                previous_value_display: '"South gate"',
                reason: "Confirmed against the final site plan.",
                timestamp: "2026-08-14T10:30:00+08:00",
            },
        ],
    });

    assert.match(html, /class="cf-revision-trail"/);
    assert.match(html, /class="cf-revision-trail__change"/);
    assert.match(html, /<del>&quot;South gate&quot;<\/del>/);
    assert.match(html, /<ins>&quot;East gate&quot;<\/ins>/);
    assert.doesNotMatch(html, /class="[^"]*hover-/);
});

run_test("feed filtering uses data state without a legacy class bridge", () => {
    assert.match(behavior, /data-cf-feed-filter/);
    assert.match(behavior, /dataset\["cfModuleKey"\]/);
    assert.match(behavior, /dataset\["cfFilterSourceIds"\]/);
    assert.match(message_template, /data-cf-lineage/);
    assert.match(message_template, /data-cf-filter-source-ids/);
    assert.doesNotMatch(
        behavior,
        /hover-(?:all-filter|lineage|raw-source-record|module--|source-id--)/,
    );
    assert.doesNotMatch(
        message_template,
        /hover-(?:lineage|raw-source-record|module--|source-id--)/,
    );
    assert.doesNotMatch(component_css, /var\(--(?:ds|hover)-|#[0-9a-f]{3,8}\b|hsl\(/i);
});

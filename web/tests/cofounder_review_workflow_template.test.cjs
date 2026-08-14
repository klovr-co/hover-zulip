"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_disputed_details = require("../templates/hover_disputed_details.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("review workflow uses production-owned Cofounder contracts", () => {
    const html = render_disputed_details({
        details: [
            {
                evidence_count: 2,
                evidence_url: "#evidence",
                field_label: "Venue access",
                field_path: "venue_access",
                resolution_label: null,
                show_review_action: true,
                state_label: "Needs review",
                state_tone: "warning",
                summary: "Two credible sources disagree about the delivery entrance.",
                target_label: "Review requested from you",
            },
        ],
        message_id: 42,
    });
    const message_template = fs.readFileSync(
        path.join(__dirname, "../templates/message_body.hbs"),
        "utf8",
    );
    const behavior_source = fs.readFileSync(
        path.join(__dirname, "../src/hover_review_request.ts"),
        "utf8",
    );
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/review-workflow.css"),
        "utf8",
    );
    const app_css = fs.readFileSync(path.join(__dirname, "../styles/cofounder/app.css"), "utf8");

    assert.match(html, /class="cf-review-details"/);
    assert.match(html, /class="cf-review-detail cf-review-detail--warning"/);
    assert.match(html, /cf-status--warning/);
    assert.match(html, /data-cf-evidence-url="#evidence"/);
    assert.match(html, /data-cf-review-message-id="42"/);
    assert.match(html, /data-cf-review-field-path="venue_access"/);
    assert.match(message_template, /class="cf-review-response/);
    assert.match(message_template, /class="cf-review-clarification"/);
    assert.match(message_template, /class="cf-review-request"/);
    assert.match(message_template, /hover_review_request_state_tone/);
    assert.match(behavior_source, /\.cf-review-detail__review/);
    assert.match(component_css, /\.cf-review-detail--success/);
    assert.doesNotMatch(
        html + behavior_source + app_css,
        /hover-disputed-detail|hover-dispute-review-button|hover-review-request-label|hover-response-label|hover-review-clarification|data-hover-(?:message-id|field-path)/,
    );
    assert.doesNotMatch(
        message_template + app_css,
        /hover-disputed-detail|hover-dispute-review-button|hover-review-request-label|hover-response-label|hover-review-clarification/,
    );
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/);
    assert.doesNotMatch(component_css, /var\(--(?:ds|hover)-|#[0-9a-f]{3,8}\b|hsl\(/i);
});

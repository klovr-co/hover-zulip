"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_details = require("../templates/hover_generated_details_modal.hbs");
const render_message = require("../templates/single_message.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("generated updates use production-owned Cofounder contracts", () => {
    const html = render_message({
        has_hover_disputed_details: false,
        has_hover_revisions: false,
        has_hover_source_integrations: false,
        hover_has_history: true,
        hover_history_count: 3,
        hover_importance: "high",
        hover_importance_tone: "danger",
        hover_is_earlier: false,
        hover_module_name: "Operations brief",
        hover_output_label: "Venue plan",
        hover_source_context: "Across 3 sources",
        hover_state: "active",
        hover_state_tone: "success",
        include_sender: true,
        is_hidden: false,
        is_hover_generated_update: true,
        is_hover_response: false,
        is_hover_suggested_action: false,
        message_list_id: 1,
        sender_is_bot: true,
        small_avatar_url: "/avatar.png",
        timestr: "10:38 AM",
        msg: {
            content: "<p>Venue plan ready for review.</p>",
            failed_request: false,
            id: 42,
            is_stream: true,
            locally_echoed: false,
            message_reactions: [],
            reminders: [],
            sender_full_name: "Hover Bot",
            sender_id: 10,
            sent_by_me: false,
            starred: false,
            url: "#message-42",
        },
    });
    const behavior_source = fs.readFileSync(
        path.join(__dirname, "../src/hover_generated_details.ts"),
        "utf8",
    );
    const details_context = {
        history: [
            {
                display_time: "August 13, 2026 at 10:38 AM",
                is_current: true,
                state: "active",
                title: "Approved venue plan",
                url: "#message-42",
            },
        ],
        module: {name: "Operations brief", version: "v6"},
        presentation: {
            display_generated_at: "August 13, 2026 at 10:37 AM",
            display_occurred_at: "August 13, 2026 at 10:32 AM",
            display_published_at: "August 13, 2026 at 10:38 AM",
            importance: "high",
            label: "Venue plan",
            run_reference: "run-42",
            state: "active",
            state_tone: "success",
        },
    };
    const details_html = render_details({...details_context, show_history: false});
    const history_html = render_details({...details_context, show_history: true});
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/generated-update.css"),
        "utf8",
    );

    assert.match(html, /cf-message-item--generated-update/);
    assert.match(html, /class="cf-generated-update__label"/);
    assert.match(html, /cf-status--success/);
    assert.match(html, /cf-status--danger/);
    assert.match(html, /class="[^"]*cf-generated-update__details/);
    assert.match(html, /class="[^"]*cf-generated-update__history/);
    assert.match(html, /data-cf-generated-message-id="42"/);
    assert.match(behavior_source, /\.cf-generated-update__details/);
    assert.match(behavior_source, /cfGeneratedMessageId/);
    assert.match(component_css, /grid-area: update-actions/);
    assert.match(details_html, /class="cf-generated-details"/);
    assert.match(details_html, /class="cf-generated-details__technical"/);
    assert.match(details_html, /data-cf-generated-details/);
    assert.match(history_html, /class="cf-generated-history"/);
    assert.match(history_html, /class="cf-generated-history__entry"/);
    assert.match(history_html, /aria-current="true"/);
    assert.match(history_html, /class="cf-generated-history__meta"/);
    assert.match(history_html, /class="cf-generated-history__state">active/);
    assert.match(history_html, /class="cf-generated-history__current"/);
    assert.doesNotMatch(
        html + details_html + history_html + behavior_source,
        /hover-generated-update|hover-generated-details|hover-generated-technical-details|hover-generated-history|data-hover-generated-details|data-hover-message-id/,
    );
    assert.doesNotMatch(component_css, /var\(--(?:ds|hover)-|#[0-9a-f]{3,8}\b|hsl\(/i);
});

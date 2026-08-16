"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_card = require("../templates/settings/connected_account_card.hbs");
const render_section = require("../templates/settings/connected_accounts_admin.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("connected account settings use standalone Cofounder contracts", () => {
    const section_html = render_section({is_admin: true, realm_hover_enabled: true});
    const card_html = render_card({
        account: {
            approval_label: "Approved",
            approval_state: "approved",
            approval_tone: "success",
            creator_name: "Maxine Tan",
            display_name: "AIMTO conversations",
            external_account_id: "acct_7B3F9D8C2A",
            health_checked_label: "August 13, 2026 at 10:18 AM",
            health_icon: "check",
            health_label: "Healthy",
            health_tone: "success",
            id: 18,
            is_approved: true,
            is_pending: false,
            is_revoked: false,
            owner_name: "Aisha Rahman",
            provider_name: "WhatsApp Business",
        },
        grants: [
            {
                action_label: "Restrict",
                id: 91,
                is_revoked: false,
                scope_label: "Leadership group",
                user_name: "Priya Shah",
            },
        ],
        has_grants: true,
    });
    const behavior_source = fs.readFileSync(
        path.join(__dirname, "../src/settings_connected_accounts.ts"),
        "utf8",
    );
    const event_source = fs.readFileSync(
        path.join(__dirname, "../src/server_events_dispatch.js"),
        "utf8",
    );

    assert.match(section_html, /id="cf-connected-accounts-list"/);
    assert.match(section_html, /cf-connected-accounts__privacy-status/);
    assert.match(card_html, /class="cf-connected-account"/);
    assert.match(card_html, /cf-status--success/);
    assert.match(card_html, /cf-connected-account__assign/);
    assert.match(card_html, /cf-button--danger[^>]*cf-connected-account__revoke/);
    assert.match(card_html, /cf-connected-account__edit-grant/);
    assert.match(behavior_source, /\.cf-connected-account__approve/);
    assert.match(event_source, /\.cf-connected-account-settings-entry/);
    assert.doesNotMatch(
        section_html + card_html,
        /hover-connected-account|hover-account-(?:state|health)|hover-secret-safe|\bbutton rounded\b|zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/,
    );
    assert.doesNotMatch(
        behavior_source,
        /#hover-connected-accounts-list|\.approve-connected-account|\.restore-connected-account|\.revoke-connected-account|\.add-connected-account-grant|\.edit-connected-account-grant|\.revoke-connected-account-grant/,
    );
});

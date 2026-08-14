"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_source_results = require("../templates/hover_source_discovery_results.hbs");
const render_space_setup = require("../templates/hover_space_setup_modal.hbs");

const {run_test} = require("./lib/test.cjs");

const project_root = path.resolve(__dirname, "../..");
const component_css = fs.readFileSync(
    path.join(project_root, "web/styles/cofounder/components/space-workbench.css"),
    "utf8",
);
const behavior_source = fs.readFileSync(
    path.join(project_root, "web/src/hover_spaces_ui.ts"),
    "utf8",
);
const production_bundle = fs.readFileSync(
    path.join(project_root, "web/src/bundles/app.ts"),
    "utf8",
);
const storybook_preview = fs.readFileSync(path.join(project_root, ".storybook/preview.js"), "utf8");

const legacy_contract =
    /hover-(?:space-setup|source-(?:attachment|discovery|candidate|preview|window|empty)|module-|member-)|button rounded|modal_select|zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/;

run_test("Space setup renders the standalone Cofounder workbench contract", () => {
    const attachment = {
        icon_name: "phone",
        id: 41,
        source: {
            account_display_name: "Operations",
            display_name: "Mentors & Volunteers",
            source_type: "group",
        },
    };
    const html = render_space_setup({
        accounts: [{display_name: "Operations", id: 3, provider_name: "WhatsApp"}],
        eligible_users: [{full_name: "Amina Niyonkuru", user_id: 14}],
        has_accounts: true,
        has_attachments: true,
        has_eligible_users: true,
        has_module_catalog: true,
        has_module_installations: true,
        module_catalog: [
            {
                attachments: [attachment],
                description: "Creates a concise daily view.",
                destination_topic: "Daily brief",
                icon_name: "file-text",
                id: 22,
                is_installed: false,
                name: "Conversation Digest",
                supports_manual: true,
                supports_new_source: true,
                supports_schedule: true,
                version: "1.4",
            },
        ],
        space: {
            attachments: [attachment],
            category: {name: "Community"},
            description: "Coordinate the next launch.",
            membership_suggestions: [
                {full_name: "Maya Chen", suggested_role: "subscriber", user_id: 10},
            ],
            memberships: [
                {
                    full_name: "Ava Rodriguez",
                    is_administrator: true,
                    role: "contributor",
                    user_id: 7,
                },
            ],
            module_installations: [
                {id: 19, name: "Suggested Actions", state: "enabled", version: "2.1"},
            ],
            name: "Community launch",
        },
        launch_ready: false,
        launch_requirements: [
            {icon_name: "check", label: "At least one active Source", met: true},
            {icon_name: "warning", label: "No pending teammate suggestions", met: false},
        ],
    });

    assert.match(html, /id="cf-space-setup-form" class="cf-space-workbench"/);
    assert.match(html, /data-cf-space-panel="modules"/);
    assert.match(html, /data-cf-space-panel="members"/);
    assert.match(html, /data-cf-space-panel="source"/);
    assert.match(html, /data-cf-space-action="install-module"/);
    assert.match(html, /data-cf-membership-action="confirm-suggestion"/);
    assert.match(html, /class="cf-field__control"/);
    assert.match(html, /class="cf-status cf-status--accent"/);
    assert.match(html, /id="cf-space-launch-requirements"/);
    assert.match(html, /data-state="open"/);
    assert.match(html, /data-cf-space-action="launch-space"[\s\S]*disabled/);
    assert.doesNotMatch(html, legacy_contract);
});

run_test("Source discovery results use typed icons and Cofounder action hooks", () => {
    const html = render_source_results({
        has_more: true,
        has_sources: true,
        sources: [
            {
                account_display_name: "Operations",
                display_name: "Mentors & Volunteers",
                icon_name: "phone",
                source_ref: "wa-community",
                source_type: "group",
            },
        ],
    });

    assert.match(html, /data-cf-source-results="available"/);
    assert.match(html, /name="cf_source_candidate"/);
    assert.match(html, /for="cf-source-candidate-0"/);
    assert.match(html, /data-cf-space-action="preview-source"/);
    assert.match(html, /data-cf-space-action="more-sources"/);
    assert.match(html, /class="cf-icon cf-icon--compact"/);
    assert.doesNotMatch(html, /<label[^>]*>[\s\S]*<button[\s\S]*<\/label>/);
    assert.doesNotMatch(html, legacy_contract);
});

run_test("Space workbench behavior and styles have no legacy compatibility bridge", () => {
    assert.match(behavior_source, /data-cf-space-action/);
    assert.match(behavior_source, /data-cf-member-role/);
    assert.match(behavior_source, /#cf-source-discovery-status/);
    assert.match(behavior_source, /discovery_request_id/);
    assert.match(behavior_source, /preview_request_id/);
    assert.match(behavior_source, /set_region_pending/);
    assert.doesNotMatch(behavior_source, legacy_contract);
    assert.doesNotMatch(component_css, /var\(--(?:ds|hover)-|#[0-9a-f]{3,8}\b|hsl\(/i);
    assert.match(production_bundle, /components\/space-workbench\.css/);
    assert.match(storybook_preview, /components\/space-workbench\.css/);
});

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_channel_list_item = require("../templates/channel_list_item.hbs");
const render_channel_row = require("../templates/stream_settings/browse_streams_list_item.hbs");
const render_copy_email = require("../templates/stream_settings/copy_email_address_modal.hbs");
const render_edit_folder = require("../templates/stream_settings/edit_channel_folder_modal.hbs");
const render_channels = require("../templates/stream_settings/stream_settings_overlay.hbs");
const render_sort_label = require("../templates/stream_settings/stream_sorter_toggle_label.hbs");
const render_group_row = require("../templates/user_group_settings/browse_user_groups_list_item.hbs");
const render_group_title = require("../templates/user_group_settings/selected_group_title.hbs");
const render_groups = require("../templates/user_group_settings/user_group_settings_overlay.hbs");

const {run_test} = require("./lib/test.cjs");

run_test(
    "Channel and user-group overlays share the Cofounder two-pane shell",
    ({mock_template}) => {
        mock_template("stream_settings/stream_creation_form.hbs", false, () => "");
        mock_template("user_group_settings/user_group_creation_form.hbs", false, () => "");

        const html = `${render_channels({
            can_create_streams: true,
            can_view_all_streams: true,
            realm_has_archived_channels: true,
        })}${render_groups({})}`;
        const shell_source = [
            "../templates/cofounder/components/two_pane_header.hbs",
            "../templates/stream_settings/stream_settings_overlay.hbs",
            "../templates/user_group_settings/user_group_settings_overlay.hbs",
        ]
            .map((file) => fs.readFileSync(path.join(__dirname, file), "utf8"))
            .join("");

        assert.match(html, /cf-two-pane-shell/);
        assert.match(html, /cf-two-pane-shell__back/);
        assert.match(html, /cf-two-pane-shell__filter-input/);
        assert.match(html, /cf-two-pane-shell__pane--detail/);
        assert.match(html, /cf-dropdown-trigger/);
        assert.match(html, /cf-button--primary/);
        assert.doesNotMatch(shell_source, /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/);
    },
);

run_test("Operational channel and group rows use typed Cofounder actions", () => {
    const channel_html = render_channel_row({
        can_access_subscribers: true,
        color: "#0878e8",
        name: "Design",
        rendered_description: "Design reviews and product decisions",
        should_display_subscription_button: true,
        stream_id: 7,
        subscriber_count: 24,
        subscribed: true,
    });
    const group_html = render_group_row({
        associated_subgroup_names: "Design leadership",
        can_leave: true,
        description: "Product design team",
        id: 3,
        is_direct_member: true,
        is_member: true,
        name: "Design",
    });

    assert.match(channel_html, /cf-two-pane-shell__row/);
    assert.match(channel_html, /cf-two-pane-shell__membership-action/);
    assert.match(channel_html, /cf-two-pane-shell__channel-icon/);
    assert.match(channel_html, /aria-label="translated: Unsubscribe from channel: Design"/);
    assert.match(
        channel_html,
        /class="sub-info-box cf-two-pane-shell__row-main" role="button" tabindex="0"/,
    );
    assert.match(channel_html, /aria-label="translated: Open channel settings: Design"/);
    assert.match(channel_html, /aria-controls="stream_settings"/);
    assert.match(group_html, /cf-two-pane-shell__membership-action/);
    assert.match(group_html, /aria-label="translated: Leave group: Design"/);
    assert.match(
        group_html,
        /class="group-info-box cf-two-pane-shell__row-main" role="button" tabindex="0"/,
    );
    assert.match(group_html, /aria-label="translated: Open user group settings: Design"/);
    assert.match(group_html, /aria-controls="user_group_settings"/);
    assert.match(`${channel_html}${group_html}`, /class="cf-icon/);
    assert.doesNotMatch(`${channel_html}${group_html}`, /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/);
});

run_test("Channel shell story demonstrates complete keyboard and state behavior", () => {
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_two_pane_settings.stories.ts"),
        "utf8",
    );
    const controller_source = fs.readFileSync(
        path.join(__dirname, "../src/stream_edit.ts"),
        "utf8",
    );
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/two-pane-shell.css"),
        "utf8",
    );
    const storybook_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");

    assert.match(story_source, /structuredClone\(channel_fixtures\)/);
    assert.match(story_source, /cf-tabs__tab--selected/);
    assert.match(story_source, /aria-selected/);
    assert.match(story_source, /setAttribute\("aria-current", String\(selected\)\)/);
    assert.match(story_source, /tabindex="\$\{index === 0 \? "0" : "-1"\}"/);
    assert.match(story_source, /function setup_channel_scene/);
    assert.match(story_source, /const select_channel/);
    assert.match(story_source, /const apply_sort/);
    assert.match(story_source, /const filter_rows/);
    assert.match(story_source, /replace_channel_row/);
    assert.match(story_source, /setAttribute\("aria-atomic", "true"\)/);
    assert.match(story_source, /no_stream_match_filter_empty_text/);
    assert.match(story_source, /globalThis\.matchMedia\("\(width < 700px\)"\)/);
    assert.match(story_source, /reveal_detail && uses_mobile_panes\(\)/);
    assert.match(story_source, /select_channel\(first_row, false, "", false\)/);
    assert.match(story_source, /detail_pane\.classList\.remove\("show"\)/);
    assert.match(story_source, /shell_header\.classList\.remove\("slide-left"\)/);
    assert.match(story_source, /data-storybook-open-channels/);
    assert.match(story_source, /event\.key === "Enter" \|\| event\.key === " "/);
    assert.match(
        controller_source,
        /"keydown",[\s\S]*"\.cf-two-pane-shell__row-main"[\s\S]*event\.key !== "Enter"[\s\S]*event\.key !== " "/,
    );
    assert.match(
        component_css,
        /\.cf-two-pane-shell__row-main:is\(\.sub-info-box, \.group-info-box\):focus-visible \{[\s\S]*outline: 2px solid var\(--cf-focus\);/,
    );
    assert.match(
        component_css,
        /\.cf-two-pane-shell__row-main:is\(\.sub-info-box, \.group-info-box\) \{[\s\S]*min-height: var\(--cf-control-height-touch\);/,
    );
    assert.match(component_css, /\.cf-two-pane-shell__empty\[hidden\] \{[\s\S]*display: none;/);
    assert.match(
        storybook_css,
        /\.storybook-two-pane-settings__summary \{[\s\S]*width: min\(100%, 680px\);/,
    );
    assert.match(
        storybook_css,
        /\.storybook-two-pane-settings__facts > div \{[\s\S]*grid-template-columns:/,
    );
});

run_test("User-group shell story demonstrates complete keyboard and state behavior", () => {
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_two_pane_settings.stories.ts"),
        "utf8",
    );
    const controller_source = fs.readFileSync(
        path.join(__dirname, "../src/user_group_edit.ts"),
        "utf8",
    );

    assert.match(story_source, /structuredClone\(group_fixtures\)/);
    assert.match(story_source, /function setup_group_scene/);
    assert.match(story_source, /const select_group/);
    assert.match(story_source, /const toggle_membership/);
    assert.match(story_source, /const replace_group_row/);
    assert.match(story_source, /No user groups match your filter\./);
    assert.match(story_source, /data-storybook-open-groups/);
    assert.match(story_source, /select_group\(first_row, false, "", false\)/);
    assert.match(story_source, /Joined/);
    assert.match(story_source, /System managed/);
    assert.match(
        controller_source,
        /"keydown",[\s\S]*"\.cf-two-pane-shell__row-main"[\s\S]*event\.key !== "Enter"[\s\S]*event\.key !== " "/,
    );
});

run_test("Settings detail controls use standalone Cofounder primitives", () => {
    const html = `${render_sort_label({icon: "sort-ascending", tooltip: "Sort by name"})}${render_group_title(
        {
            group_id: 3,
            group_name: "Design",
            is_direct_member: true,
            is_system_group: false,
        },
    )}${render_copy_email({email_address: "design@example.com", tags: []})}${render_edit_folder({
        can_manage_folder: true,
        description: "Product work",
        folder_id: 4,
        max_channel_folder_description_length: 100,
        max_channel_folder_name_length: 40,
        name: "Product",
    })}`;

    assert.match(html, /cf-two-pane-shell__sort-icon/);
    assert.match(html, /cf-search-field/);
    assert.match(html, /cf-copy-field/);
    assert.match(html, /cf-field__control/);
    assert.match(html, /data-clipboard-text="design@example.com"/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/);
});

run_test("Channel email dialog exposes grouped options and deterministic story behavior", () => {
    const html = render_copy_email({
        email_address: "design@example.com",
        tags: [
            {description: "Include sender", name: "show-sender"},
            {description: "Prefer HTML", name: "prefer-html"},
        ],
    });
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_settings_dialogs.stories.ts"),
        "utf8",
    );
    const dialog_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/dialog.css"),
        "utf8",
    );
    const story_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");

    assert.match(html, /<fieldset class="cf-email-options">/);
    assert.match(html, /<legend class="cf-email-options__legend question-which-parts">/);
    assert.match(html, /class="checkbox cf-email-options__option"/);
    assert.match(html, /class="tag-checkbox" id="show-sender"/);
    assert.match(html, /class="cf-email-options__label">Include sender<\/span>/);
    assert.match(html, /<h2 class="stream-email-header">/);
    assert.doesNotMatch(html, /<label class="inline"/);
    assert.match(story_source, /setup_channel_email_dialog/);
    assert.match(story_source, /storybook-dialog-story storybook-settings-dialog/);
    assert.match(story_source, /storybook-channel-email-sender-menu/);
    assert.match(story_source, /#show-sender/);
    assert.match(story_source, /Generated a new channel email address\./);
    assert.match(story_source, /Copy requested for/);
    assert.match(story_source, /event\.key === "Escape"/);
    assert.match(dialog_css, /\.cf-dialog#copy_email_address_modal/);
    assert.match(dialog_css, /width: min\(560px, 100%\)/);
    assert.match(dialog_css, /\.cf-email-options__option\.checkbox[\s\S]*?min-height/);
    assert.match(story_css, /\.storybook-settings-dialog__sender-menu/);
});

run_test("Manage channel folder dialog exposes named lists and complete story behavior", () => {
    const html = render_edit_folder({
        can_manage_folder: true,
        description: "Planning channels",
        folder_id: 4,
        max_channel_folder_description_length: 200,
        max_channel_folder_name_length: 60,
        name: "Product",
    });
    const channel_html = render_channel_list_item({
        can_manage_folder: true,
        remove_channel_label: "Remove Product planning from folder",
        stream: {
            color: "#3974d9",
            invite_only: false,
            is_archived: false,
            is_web_public: false,
            name: "Product planning",
            stream_id: 41,
        },
        view_channel_label: "View details for Product planning",
    });
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_settings_dialogs.stories.ts"),
        "utf8",
    );
    const controller_source = fs.readFileSync(
        path.join(__dirname, "../src/channel_folders_ui.ts"),
        "utf8",
    );
    const dialog_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/dialog.css"),
        "utf8",
    );
    const story_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");

    assert.match(html, /id="edit_channel_folder_name"[^>]* required/);
    assert.match(html, /<h2 id="edit_channel_folder_channels_heading"/);
    assert.match(html, /<h2 id="edit_channel_folder_add_heading"/);
    assert.match(
        html,
        /class="folder-stream-list modal-item-list" aria-labelledby="edit_channel_folder_channels_heading" aria-live="polite"/,
    );
    assert.match(html, /Select a channel/);
    assert.match(html, /aria-label="[^"]*Add selected channel to folder" disabled/);
    assert.match(channel_html, /role="button" aria-label="View details for Product planning"/);
    assert.match(channel_html, /aria-label="Remove Product planning from folder"/);
    assert.match(controller_source, /Remove \{channel_name\} from folder/);
    assert.match(controller_source, /View details for \{channel_name\}/);
    assert.match(story_source, /setup_channel_folder_dialog/);
    assert.match(story_source, /render_channel_list_item/);
    assert.match(story_source, /storybook-channel-folder-menu/);
    assert.match(story_source, /Channel folder name is required\./);
    assert.match(story_source, /initialFocus: "#edit_channel_folder_name"/);
    assert.match(dialog_css, /\.cf-dialog#edit_channel_folder/);
    assert.match(dialog_css, /height: min\(30vh, 240px\)/);
    assert.match(
        dialog_css,
        /\.modal-channel-list-row \.list-row-content \{[\s\S]*min-height: var\(--cf-control-height-touch\);/,
    );
    assert.match(story_css, /\.storybook-settings-dialog__menu-option/);
    assert.match(story_css, /\.storybook-settings-dialog__empty-list/);
});

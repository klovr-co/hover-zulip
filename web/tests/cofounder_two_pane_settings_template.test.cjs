"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

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
    assert.match(group_html, /cf-two-pane-shell__membership-action/);
    assert.match(`${channel_html}${group_html}`, /class="cf-icon/);
    assert.doesNotMatch(`${channel_html}${group_html}`, /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/);
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

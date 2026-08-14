"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_message_actions = require("../templates/popovers/message_actions_popover.hbs");
const render_user_group = require("../templates/popovers/user_group_info_popover.hbs");

const {run_test} = require("./lib/test.cjs");

function handlebars_files(directory) {
    return fs.readdirSync(directory, {withFileTypes: true}).flatMap((entry) => {
        const target = path.join(directory, entry.name);
        if (entry.isDirectory()) {
            return handlebars_files(target);
        }
        return entry.name.endsWith(".hbs") ? [target] : [];
    });
}

run_test("Utility popovers use Cofounder components without legacy icon markup", () => {
    const directory = path.join(__dirname, "../templates/popovers");
    const source = handlebars_files(directory)
        .map((file) => fs.readFileSync(file, "utf8"))
        .join("");
    const message_html = render_message_actions({
        conversation_time_url: "#message/42",
        editability_menu_item: "Edit message",
        message_id: 42,
        move_message_menu_item: "Move message",
        should_display_add_reaction_option: true,
        should_display_delete_option: true,
        should_display_mark_as_unread: true,
        should_display_message_report_option: true,
        should_display_quote_message: true,
        should_display_read_receipts_option: true,
        should_display_remind_me_option: true,
        view_source_menu_item: "View source",
    });
    const group_html = render_user_group({
        display_all_subgroups_and_members: true,
        displayed_members: [
            {
                full_name: "Ava Rodriguez",
                is_bot: false,
                user_circle_class: "user_circle_green",
                user_id: 7,
                user_last_seen_time_status: "Active now",
            },
        ],
        displayed_subgroups: [{name: "Design systems"}],
        group_edit_url: "#groups/design",
        group_name: "Product design",
        is_guest: false,
        members_count: 2,
        user_can_access_all_other_users: true,
    });

    assert.match(message_html, /cf-menu/);
    assert.match(message_html, /cf-icon/);
    assert.match(group_html, /cf-presence-dot--user_circle_green/);
    assert.match(group_html, /data-tippy-content="Active now"/);
    assert.doesNotMatch(source, /zulip-icon|\bfa(?:\s|-)|icon_class|\bicon-button\b/);
    assert.doesNotMatch(message_html + group_html, /zulip-icon|\bfa(?:\s|-)|icon_class/);
});

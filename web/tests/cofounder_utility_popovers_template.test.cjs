"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_message_actions = require("../templates/popovers/message_actions_popover.hbs");
const render_send_later = require("../templates/popovers/send_later_popover.hbs");
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
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_utility_popovers.stories.ts"),
        "utf8",
    );
    const story_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");
    const menu_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/menu.css"),
        "utf8",
    );
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
    const send_later_html = render_send_later({
        enter_sends_true: true,
        formatted_send_later_time: "Tomorrow at 9:00 AM",
        show_compose_new_message: true,
    });

    assert.match(message_html, /cf-menu/);
    assert.match(message_html, /cf-icon/);
    assert.match(message_html, /role="menu" aria-label="(?:translated: )?Message actions"/);
    assert.match(send_later_html, /role="menu" aria-label="(?:translated: )?Send options"/);
    assert.match(send_later_html, /role="menuitemradio" aria-checked="true"/);
    assert.match(send_later_html, /role="menuitemradio" aria-checked="false"/);
    assert.match(group_html, /cf-presence-dot--user_circle_green/);
    assert.match(group_html, /data-tippy-content="Active now"/);
    assert.match(group_html, /role="menu" aria-labelledby="user-group-info-name"/);
    assert.match(group_html, /<h2 class="popover-group-menu-name" id="user-group-info-name">/);
    assert.match(group_html, /translated: Subgroups/);
    assert.match(group_html, /translated: Members/);
    assert.match(group_html, /class="group-member-count /);
    assert.match(story_source, /view_source_menu_item: false/);
    assert.match(story_source, /should_display_collapse: true/);
    assert.match(story_source, /setup_message_actions_scene/);
    assert.match(story_source, /setup_send_later_scene/);
    assert.match(story_source, /setup_user_group_scene/);
    assert.match(story_source, /member_count\.textContent = "8 members"/);
    assert.match(story_source, /Ctrl\+Enter now sends messages/);
    assert.match(story_source, /case "ArrowDown":/);
    assert.match(story_source, /case "Home":/);
    assert.match(story_source, /requested for message 42/);
    assert.match(story_source, /#narrow\/channel\/7-design\/topic\/Homepage-redesign\/near\/42/);
    assert.match(story_source, /#groups\/3\/Product-design\/general/);
    assert.match(story_source, /#groups\/3\/Product-design\/members/);
    assert.match(story_css, /\.storybook-message-actions__feedback:empty/);
    assert.match(story_css, /\.storybook-send-later__feedback:empty/);
    assert.match(story_css, /\.storybook-user-group__feedback:empty/);
    assert.doesNotMatch(
        story_css,
        /storybook-send-later[\s\S]{0,120}\.cf-menu__list > li:first-child/,
    );
    assert.match(menu_css, /\.cf-menu \.enter_sends_choice:has/);
    assert.match(menu_css, /background: var\(--cf-surface-selected\)/);
    assert.match(menu_css, /\.cf-menu \.enter_sends_choice:focus-visible/);
    assert.match(menu_css, /min-height: 64px/);
    assert.match(menu_css, /\.user-group-info-popover \.popover-group-menu-section-label/);
    assert.match(menu_css, /ul\.popover-group-menu-member-list/);
    assert.match(menu_css, /grid-template-columns: 16px minmax\(0, 1fr\)/);
    assert.match(menu_css, /grid-area: auto/);
    assert.doesNotMatch(source, /zulip-icon|\bfa(?:\s|-)|icon_class|\bicon-button\b/);
    assert.doesNotMatch(message_html + group_html, /zulip-icon|\bfa(?:\s|-)|icon_class/);
});

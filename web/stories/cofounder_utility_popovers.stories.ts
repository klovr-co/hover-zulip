import type {Meta, StoryObj} from "@storybook/html";

import render_message_actions from "../templates/popovers/message_actions_popover.hbs";
import render_send_later from "../templates/popovers/send_later_popover.hbs";
import render_user_group from "../templates/popovers/user_group_info_popover.hbs";

import {render_template_story} from "./template_story_utils.ts";

const meta = {
    title: "Cofounder/Utility Popovers",
    parameters: {layout: "fullscreen"},
} satisfies Meta;

export default meta;
type Story = StoryObj;

function frame(host: HTMLElement, custom_class?: string): HTMLElement {
    host.classList.add("cf-theme", "storybook-utility-popover");
    if (custom_class !== undefined) {
        host.classList.add(custom_class);
    }
    return host;
}

export const MessageActions: Story = {
    render() {
        return frame(
            render_template_story("popovers/message_actions_popover.hbs", render_message_actions, {
                conversation_time_url: "#message/42",
                editability_menu_item: "Edit message",
                message_id: 42,
                move_message_menu_item: "Move message",
                should_display_add_reaction_option: true,
                should_display_collapse: false,
                should_display_delete_option: true,
                should_display_mark_as_unread: true,
                should_display_message_report_option: true,
                should_display_quote_message: true,
                should_display_read_receipts_option: true,
                should_display_remind_me_option: true,
                should_display_uncollapse: false,
                view_source_menu_item: "View source",
            }),
        );
    },
};

export const SendLater: Story = {
    render() {
        return frame(
            render_template_story("popovers/send_later_popover.hbs", render_send_later, {
                enter_sends_true: true,
                formatted_send_later_time: "Tomorrow at 9:00 AM",
                show_compose_new_message: true,
            }),
            "storybook-send-later",
        );
    },
};

export const UserGroup: Story = {
    render() {
        return frame(
            render_template_story("popovers/user_group_info_popover.hbs", render_user_group, {
                deactivated: false,
                display_all_subgroups_and_members: true,
                displayed_members: [
                    {
                        full_name: "Ava Rodriguez",
                        is_bot: false,
                        user_circle_class: "user_circle_green",
                        user_id: 7,
                        user_last_seen_time_status: "Active now",
                    },
                    {full_name: "Design review bot", is_bot: true},
                ],
                displayed_subgroups: [{name: "Design systems"}],
                group_description: "People shaping the Cofounder product experience.",
                group_edit_url: "#groups/design",
                group_name: "Product design",
                is_guest: false,
                is_system_group: false,
                members_count: 3,
                user_can_access_all_other_users: false,
            }),
        );
    },
};

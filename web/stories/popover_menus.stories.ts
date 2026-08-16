import type {Meta, StoryObj} from "@storybook/html";

import render_message_actions from "../templates/popovers/message_actions_popover.hbs";
import render_help_menu from "../templates/popovers/navbar/navbar_help_menu_popover.hbs";
import render_playground_links from "../templates/popovers/playground_links_popover.hbs";

type PopoverArgs = {
    corporate_enabled: boolean;
};

const meta = {
    title: "Overlays/Popovers/Menus",
    tags: ["autodocs"],
    args: {
        corporate_enabled: true,
    },
    render: (args) => `<div class="storybook-popover-menu">${render_help_menu(args)}</div>`,
} satisfies Meta<PopoverArgs>;

export default meta;
type Story = StoryObj<PopoverArgs>;

export const HelpMenu: Story = {};

export const MessageActions: Story = {
    render: () =>
        `<div class="storybook-popover-menu">${render_message_actions({
            conversation_time_url: "#narrow/near/42",
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
        })}</div>`,
};

export const PlaygroundLinks: Story = {
    render: () =>
        `<div class="storybook-popover-menu">${render_playground_links({
            playground_info: [
                {name: "playground", playground_url: "#playground"},
                {name: "documentation", playground_url: "#documentation"},
            ],
        })}</div>`,
};

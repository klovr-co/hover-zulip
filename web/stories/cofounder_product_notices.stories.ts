import type {Meta, StoryObj} from "@storybook/html";

import render_message_sent_banner from "../templates/compose_banner/message_sent_banner.hbs";
import render_upload_banner from "../templates/compose_banner/upload_banner.hbs";
import render_modal_banner from "../templates/modal_banner/modal_banner.hbs";
import render_mark_as_read_disabled_banner from "../templates/unread_banner/mark_as_read_disabled_banner.hbs";
import render_cannot_deactivate_group_banner from "../templates/user_group_settings/cannot_deactivate_group_banner.hbs";

import {component_story} from "./story_utils.ts";

type NoticeArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Patterns/Product Notices",
    parameters: {layout: "padded"},
} satisfies Meta<NoticeArgs>;

export default meta;
type Story = StoryObj<NoticeArgs>;

export const MessageSent: Story = {
    render: () =>
        component_story(
            render_message_sent_banner({
                action_button_text: "View message",
                banner_text: "Your message was sent.",
                classname: "sent_scroll_to_view",
                link_msg_id: 42,
            }),
            true,
        ),
};

export const UploadProgress: Story = {
    render: () =>
        component_story(
            render_upload_banner({
                banner_text: "Uploading product-brief.pdf…",
                banner_type: "info",
                file_id: "product-brief",
                is_upload_process_tracker: true,
            }),
            true,
        ),
};

export const ModalWarning: Story = {
    render: () =>
        component_story(
            render_modal_banner({
                banner_text: "Some participants are not subscribed to this channel.",
                banner_type: "warning",
                button_text: "Review participants",
                classname: "unsubscribed-participants-warning",
            }),
            true,
        ),
};

export const ReadingState: Story = {
    render: () => component_story(render_mark_as_read_disabled_banner(), true),
};

export const PermissionsError: Story = {
    render: () =>
        component_story(
            render_cannot_deactivate_group_banner({group_used_for_permissions: true}),
            true,
        ),
};

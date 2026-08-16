import type {Meta, StoryObj} from "@storybook/html";

import render_header from "../templates/cofounder/components/conversation_header.hbs";

const channel = {
    all_visibility_policies: {FOLLOWED: "FOLLOWED", MUTED: "MUTED", UNMUTED: "UNMUTED"},
    date_html: "Today",
    display_recipient: "design",
    is_archived: false,
    is_empty_string_topic: false,
    is_stream: true,
    is_subscribed: true,
    is_topic_editable: true,
    recipient_bar_color: "#4f8394",
    stream_id: 7,
    stream_privacy_icon_color: "#ffffff",
    stream_url: "#channel",
    topic: "Homepage redesign",
    topic_display_name: "Homepage redesign",
    topic_is_resolved: false,
    topic_links: [{text: "design spec", url: "#spec"}],
    topic_url: "#topic",
    user_can_resolve_topic: true,
    visibility_policy: "INHERIT",
};

const meta = {
    title: "Cofounder/Components/Conversation header",
    render: () => `<div class="storybook-conversation-header-frame">${render_header(channel)}</div>`,
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const Channel: Story = {};

export const DirectMessage: Story = {
    render: () =>
        `<div class="storybook-conversation-header-frame">${render_header({date_html: "Today", display_reply_to_for_tooltip: "Ava and Helper", is_dm_with_self: false, is_stream: false, pm_with_url: "#dm", recipient_users: [{full_name: "Ava Rodriguez"}, {full_name: "Helper", is_bot: true}]})}</div>`,
};

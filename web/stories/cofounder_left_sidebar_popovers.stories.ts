import type {Meta, StoryObj} from "@storybook/html";

import render_stream_actions from "../templates/popovers/left_sidebar/left_sidebar_stream_actions_popover.hbs";
import render_topic_actions from "../templates/popovers/left_sidebar/left_sidebar_topic_actions_popover.hbs";
import render_views from "../templates/popovers/left_sidebar/left_sidebar_views_popover.hbs";

import {render_template_story} from "./template_story_utils.ts";

const meta = {
    title: "Cofounder/Left Sidebar Popovers",
    parameters: {layout: "fullscreen"},
} satisfies Meta;

export default meta;
type Story = StoryObj;

function frame(host: HTMLElement): HTMLElement {
    host.classList.add("cf-theme", "storybook-left-sidebar-popover");
    return host;
}

export const Views: Story = {
    render() {
        return frame(
            render_template_story(
                "popovers/left_sidebar/left_sidebar_views_popover.hbs",
                render_views,
                {
                    is_home_view_active: false,
                    show_unread_count: true,
                    unread_messages_present: true,
                    views: [
                        {
                            cf_icon: "inbox",
                            css_class_suffix: "inbox",
                            fragment: "inbox",
                            has_unread_count: true,
                            name: "Inbox",
                            supports_masked_unread: true,
                            tooltip_template_id: "inbox-tooltip-template",
                            unread_count: 18,
                            unread_count_type: "normal-count",
                        },
                        {
                            cf_icon: "clock",
                            css_class_suffix: "recent_view",
                            fragment: "recent",
                            has_unread_count: true,
                            name: "Recent conversations",
                            supports_masked_unread: false,
                            tooltip_template_id: "recent-tooltip-template",
                            unread_count: 4,
                            unread_count_type: "quiet-count",
                        },
                        {
                            cf_icon: "star",
                            css_class_suffix: "starred_messages",
                            fragment: "narrow/is/starred",
                            has_unread_count: false,
                            name: "Starred messages",
                            supports_masked_unread: false,
                            tooltip_template_id: "starred-tooltip-template",
                            unread_count: 0,
                            unread_count_type: "",
                        },
                    ],
                },
            ),
        );
    },
};

export const ChannelActions: Story = {
    render() {
        return frame(
            render_template_story(
                "popovers/left_sidebar/left_sidebar_stream_actions_popover.hbs",
                render_stream_actions,
                {
                    has_unread_messages: true,
                    popover_hotkey_hints: "Y",
                    show_go_to_channel_feed: true,
                    show_go_to_list_of_topics: true,
                    stream: {
                        color: "#4f8394",
                        invite_only: false,
                        is_archived: false,
                        is_muted: false,
                        is_web_public: false,
                        list_of_topics_view_url: "#topics",
                        name: "Product design",
                        pin_to_top: true,
                        stream_id: 7,
                        url: "#channel/product-design",
                    },
                    stream_edit_hash: "#channels/7",
                },
            ),
        );
    },
};

export const TopicActions: Story = {
    render() {
        return frame(
            render_template_story(
                "popovers/left_sidebar/left_sidebar_topic_actions_popover.hbs",
                render_topic_actions,
                {
                    all_visibility_policies: {
                        FOLLOWED: 3,
                        INHERIT: 0,
                        MUTED: 1,
                        UNMUTED: 2,
                    },
                    can_move_topic: true,
                    can_rename_topic: true,
                    can_resolve_topic: true,
                    can_summarize_topics: true,
                    has_starred_messages: true,
                    has_unread_messages: true,
                    is_empty_string_topic: false,
                    is_realm_admin: true,
                    is_spectator: false,
                    is_topic_empty: false,
                    show_ai_features: true,
                    stream_archived: false,
                    stream_muted: false,
                    topic_display_name: "Research synthesis",
                    topic_is_resolved: false,
                    topic_unmuted: false,
                    url: "#topic/research-synthesis",
                    visibility_policy: 0,
                },
            ),
        );
    },
};

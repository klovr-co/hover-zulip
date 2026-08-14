import type {Meta, StoryObj} from "@storybook/html";

import render_space_setup_row from "../templates/hover_space_setup_sidebar_row.hbs";
import render_stream_sidebar_row from "../templates/stream_sidebar_row.hbs";

import {component_story} from "./story_utils.ts";

type ChannelNavItemArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Channel navigation item",
    parameters: {layout: "padded"},
} satisfies Meta<ChannelNavItemArgs>;

export default meta;
type Story = StoryObj<ChannelNavItemArgs>;

function channel({
    color,
    custom_classes = "",
    id,
    invite_only = false,
    is_muted = false,
    is_web_public = false,
    mention_label,
    name,
    selected = false,
    unread_count,
}: {
    color: string;
    custom_classes?: string;
    id: number;
    invite_only?: boolean;
    is_muted?: boolean;
    is_web_public?: boolean;
    mention_label?: string;
    name: string;
    selected?: boolean;
    unread_count?: number;
}): string {
    return render_stream_sidebar_row({
        badge_visible: unread_count !== undefined,
        can_post_messages: true,
        color,
        custom_classes,
        id,
        invite_only,
        is_archived: false,
        is_empty_topic_only_channel: false,
        is_muted,
        is_web_public,
        mention_label,
        name,
        selected,
        unread_count,
        url: `#narrow/channel/${id}-${name.toLowerCase().replaceAll(" ", "-")}`,
    });
}

export const States: Story = {
    render: () =>
        component_story(`
            <nav aria-label="Channels" style="width: 280px">
                <p style="margin: 0 0 8px 8px; color: var(--cf-text-secondary); font-size: 11px; font-weight: 650; letter-spacing: 0.1em; text-transform: uppercase">Channels</p>
                <ul id="stream_filters" class="filters" style="display: grid; gap: 2px; margin: 0; padding: 0; list-style: none">
                    ${channel({
                        color: "#0878e8",
                        custom_classes: "active-filter stream-expanded",
                        id: 7,
                        name: "Product design",
                        selected: true,
                        unread_count: 12,
                    })}
                    ${channel({
                        color: "#c94a55",
                        id: 9,
                        invite_only: true,
                        mention_label: "@3",
                        name: "Leadership",
                    })}
                    ${channel({
                        color: "#5f6f52",
                        id: 12,
                        is_web_public: true,
                        name: "Community updates",
                        unread_count: 4,
                    })}
                    ${channel({
                        color: "#696b66",
                        id: 14,
                        is_muted: true,
                        name: "Release archive",
                    })}
                </ul>
            </nav>
        `),
};

export const SpaceNavigation: Story = {
    render: () =>
        component_story(`
            <nav class="storybook-space-navigation" aria-label="Space navigation">
                <ul id="stream_filters" class="filters">
                    ${render_stream_sidebar_row({
                        can_post_messages: true,
                        color: "#57745d",
                        custom_classes: "active-filter stream-expanded",
                        has_hover_ai_modules: true,
                        hover_ai_modules: [
                            {
                                count: 4,
                                has_count: true,
                                icon_name: "file-text",
                                key: "conversation_digest",
                                name: "Conversation Digest",
                                url: "#digest",
                            },
                            {
                                count: 2,
                                has_count: true,
                                icon_name: "sparkles",
                                key: "suggested_actions",
                                name: "Suggested Actions",
                                url: "#actions",
                            },
                        ],
                        hover_attached_sources: [
                            {
                                detail: "WhatsApp · Live since 8/11/2026",
                                icon_name: "phone",
                                is_external: false,
                                key: "whatsapp",
                                name: "Mentors & Volunteers",
                                source_key: "41",
                                url: "#source-41",
                            },
                            {
                                detail: "Operations · workspace",
                                icon_name: "link-alt",
                                is_external: true,
                                key: "workspace",
                                name: "Operations workspace",
                                source_key: "42",
                                url: "https://example.com/operations",
                            },
                        ],
                        id: 7,
                        invite_only: true,
                        is_archived: false,
                        is_empty_topic_only_channel: false,
                        is_hover_space: true,
                        is_muted: false,
                        is_web_public: false,
                        name: "AIMTO Events",
                        url: "#aimto-events",
                    })}
                    ${render_space_setup_row({
                        has_hover_attached_sources: true,
                        hover_attached_sources: [
                            {
                                detail: "Community · group",
                                icon_name: "phone",
                                key: "whatsapp",
                                name: "Community planning",
                                source_key: "43",
                                url: "#setup-source",
                            },
                        ],
                        id: 8,
                        name: "Community launch",
                    })}
                </ul>
            </nav>
        `),
};

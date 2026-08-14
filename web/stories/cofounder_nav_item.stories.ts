import type {Meta, StoryObj} from "@storybook/html";

import render_nav_item from "../templates/cofounder/components/nav_item.hbs";
import render_left_sidebar from "../templates/left_sidebar.hbs";

import {component_story} from "./story_utils.ts";
import {render_template_story} from "./template_story_utils.ts";

type NavItemArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Navigation item",
    parameters: {layout: "padded"},
} satisfies Meta<NavItemArgs>;

export default meta;
type Story = StoryObj<NavItemArgs>;

export const States: Story = {
    render: () =>
        component_story(`
            <nav aria-label="Workspace" style="width: 280px">
                <ul style="display: grid; gap: 2px; margin: 0; padding: 0; list-style: none">
                    ${render_nav_item({
                        href: "#for-you",
                        icon: "inbox",
                        label: "For You",
                        selected: true,
                        reserve_badge: true,
                        badge_visible: true,
                        badge: 12,
                        action_label: "For You options",
                    })}
                    ${render_nav_item({
                        href: "#team-pulse",
                        icon: "activity",
                        label: "Team Pulse",
                        reserve_badge: true,
                        badge_visible: true,
                        badge: 3,
                    })}
                    ${render_nav_item({
                        href: "#daily-brief",
                        icon: "sun",
                        label: "Daily Brief",
                        reserve_badge: true,
                        badge_visible: false,
                    })}
                    ${render_nav_item({
                        href: "#permissions",
                        icon: "file",
                        label: "Permissions",
                        disabled: true,
                    })}
                </ul>
            </nav>
        `),
};

function production_view({
    badge,
    icon,
    key,
    label,
    selected = false,
}: {
    badge?: number;
    icon: string;
    key: string;
    label: string;
    selected?: boolean;
}): Record<string, unknown> {
    return {
        action_label: `${label} options`,
        action_classes: selected
            ? "arrow sidebar-menu-icon inbox-sidebar-menu-icon hidden-for-spectators"
            : "",
        badge,
        badge_classes: "unread_count normal-count",
        badge_visible: badge !== undefined && badge !== 0,
        cf_icon: icon,
        fragment: key,
        has_unread_count: true,
        href: `#${key}`,
        item_classes: `top_left_${key} top_left_row${
            selected ? " selected-home-view top-left-active-filter" : ""
        }`,
        main_classes: "left-sidebar-navigation-label-container tippy-left-sidebar-tooltip",
        menu_aria_label: `${label} options`,
        menu_icon_class: selected ? "inbox-sidebar-menu-icon" : "",
        name: label,
        selected,
        supports_masked_unread: true,
        tooltip_template_id: `${key}-tooltip-template`,
        unread_count: badge,
    };
}

export const ProductionViews: Story = {
    parameters: {layout: "fullscreen"},
    render() {
        const template_story = render_template_story("left_sidebar.hbs", render_left_sidebar, {
            can_create_spaces: true,
            expanded_views: [
                production_view({
                    badge: 12,
                    icon: "inbox",
                    key: "inbox",
                    label: "For You",
                    selected: true,
                }),
                production_view({icon: "activity", key: "recent_view", label: "Team Pulse"}),
                production_view({icon: "sun", key: "daily_brief", label: "Daily Brief"}),
                production_view({icon: "alarm", key: "reminders", label: "Todos"}),
                production_view({icon: "search", key: "hover_search", label: "Search"}),
                production_view({icon: "star", key: "starred_messages", label: "Saved"}),
            ],
            hover_enabled: true,
            is_guest: false,
            is_spectator: false,
            LEFT_SIDEBAR_DIRECT_MESSAGES_TITLE: "Direct messages",
            LEFT_SIDEBAR_NAVIGATION_AREA_TITLE: "Views",
            primary_condensed_views: [],
        });
        const frame = globalThis.document.createElement("main");
        frame.className = "app-main";
        const column = globalThis.document.createElement("aside");
        column.className = "column-left";
        column.append(template_story);
        frame.append(column);
        return frame;
    },
};

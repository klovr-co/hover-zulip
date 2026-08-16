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
    render() {
        const canvas = globalThis.document.createElement("div");
        canvas.innerHTML = component_story(`
            <nav class="storybook-cf-nav-states" aria-label="Workspace">
                <ul class="storybook-cf-nav-states__list">
                    ${render_nav_item({
                        href: "#for-you",
                        icon: "inbox",
                        label: "For You",
                        selected: true,
                        reserve_badge: true,
                        badge_visible: true,
                        badge: 12,
                        badge_label: "Unread messages",
                        action_label: "For You options",
                        action_classes: "left_sidebar_menu_icon_visible",
                    })}
                    ${render_nav_item({
                        href: "#team-pulse",
                        icon: "activity",
                        label: "Team Pulse",
                        reserve_badge: true,
                        badge_visible: true,
                        badge: 3,
                        badge_label: "Unread messages",
                    })}
                    ${render_nav_item({
                        href: "#daily-brief",
                        icon: "sun",
                        label: "Daily Brief",
                        reserve_badge: true,
                        badge_visible: false,
                    })}
                    ${render_nav_item({
                        href: "#mentions",
                        icon: "at-sign",
                        label: "Mentions",
                        masked_classes: "storybook-cf-nav-item__masked--visible",
                        supports_masked_unread: true,
                        masked_unread_label: "Some unread messages are hidden",
                    })}
                    ${render_nav_item({
                        href: "#permissions",
                        icon: "file",
                        label: "Permissions",
                        disabled: true,
                    })}
                </ul>
                <p class="storybook-cf-nav-states__feedback" role="status" aria-live="polite"></p>
            </nav>
        `);
        const feedback = canvas.querySelector<HTMLElement>(".storybook-cf-nav-states__feedback");
        canvas.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }
            const action = event.target.closest<HTMLButtonElement>(".cf-nav-item__action");
            if (action && feedback) {
                feedback.textContent = `${action.getAttribute("aria-label") ?? "Options"} selected.`;
            }
        });
        return canvas;
    },
};

type ProductionViewKey =
    "hover_editions" | "hover_search" | "inbox" | "recent_view" | "reminders" | "starred_messages";

type ProductionViewFixture = {
    cf_icon: string;
    css_class_suffix: string;
    fragment: string;
    has_unread_count: boolean;
    hidden_for_spectators: boolean;
    menu_aria_label: string;
    menu_icon_class: string;
    name: string;
    supports_masked_unread: boolean;
    tooltip_template_id: string;
    unread_count_type: "normal-count" | "quiet-count" | "";
};

// Keep this focused projection aligned with built_in_views_meta_data in
// navigation_views.ts without importing its application-level i18n bootstrap.
const production_view_metadata: Record<ProductionViewKey, ProductionViewFixture> = {
    hover_editions: {
        cf_icon: "sun",
        css_class_suffix: "daily_brief",
        fragment: "hover/editions",
        has_unread_count: false,
        hidden_for_spectators: true,
        menu_aria_label: "",
        menu_icon_class: "",
        name: "Daily Brief",
        supports_masked_unread: false,
        tooltip_template_id: "daily-brief-tooltip-template",
        unread_count_type: "",
    },
    hover_search: {
        cf_icon: "search",
        css_class_suffix: "hover_search",
        fragment: "hover/search",
        has_unread_count: false,
        hidden_for_spectators: true,
        menu_aria_label: "",
        menu_icon_class: "",
        name: "Search",
        supports_masked_unread: false,
        tooltip_template_id: "hover-search-tooltip-template",
        unread_count_type: "",
    },
    inbox: {
        cf_icon: "inbox",
        css_class_suffix: "inbox",
        fragment: "inbox",
        has_unread_count: true,
        hidden_for_spectators: true,
        menu_aria_label: "For You options",
        menu_icon_class: "inbox-sidebar-menu-icon",
        name: "For You",
        supports_masked_unread: true,
        tooltip_template_id: "hover-inbox-tooltip-template",
        unread_count_type: "normal-count",
    },
    recent_view: {
        cf_icon: "clock",
        css_class_suffix: "recent_view",
        fragment: "recent",
        has_unread_count: true,
        hidden_for_spectators: false,
        menu_aria_label: "Team Pulse options",
        menu_icon_class: "recent-view-sidebar-menu-icon",
        name: "Team Pulse",
        supports_masked_unread: true,
        tooltip_template_id: "hover-recent-conversations-tooltip-template",
        unread_count_type: "normal-count",
    },
    reminders: {
        cf_icon: "alarm",
        css_class_suffix: "reminders",
        fragment: "reminders",
        has_unread_count: true,
        hidden_for_spectators: true,
        menu_aria_label: "",
        menu_icon_class: "",
        name: "Todos",
        supports_masked_unread: false,
        tooltip_template_id: "hover-reminders-tooltip-template",
        unread_count_type: "quiet-count",
    },
    starred_messages: {
        cf_icon: "star",
        css_class_suffix: "starred_messages",
        fragment: "narrow/is/starred",
        has_unread_count: true,
        hidden_for_spectators: true,
        menu_aria_label: "Saved options",
        menu_icon_class: "starred-messages-sidebar-menu-icon",
        name: "Saved",
        supports_masked_unread: true,
        tooltip_template_id: "hover-starred-message-tooltip-template",
        unread_count_type: "quiet-count",
    },
};

function production_view({
    badge,
    key,
    selected = false,
}: {
    badge?: number;
    key: ProductionViewKey;
    selected?: boolean;
}): Record<string, unknown> {
    const view = production_view_metadata[key];

    return {
        ...view,
        action_classes: `arrow sidebar-menu-icon ${view.menu_icon_class} hidden-for-spectators`,
        badge,
        badge_classes: `unread_count ${view.unread_count_type}`.trim(),
        badge_visible: badge !== undefined && badge !== 0,
        href: `#${view.fragment}`,
        item_classes: `top_left_${view.css_class_suffix} top_left_row${
            view.hidden_for_spectators ? " hidden-for-spectators" : ""
        }${selected ? " selected-home-view top-left-active-filter" : ""}`,
        main_classes: "left-sidebar-navigation-label-container tippy-left-sidebar-tooltip",
        selected,
        unread_count: badge,
    };
}

export const ProductionViews: Story = {
    parameters: {layout: "fullscreen"},
    render() {
        const template_story = render_template_story("left_sidebar.hbs", render_left_sidebar, {
            can_create_spaces: true,
            expanded_views: [
                production_view({badge: 12, key: "inbox", selected: true}),
                production_view({key: "recent_view"}),
                production_view({key: "hover_editions"}),
                production_view({key: "reminders"}),
                production_view({key: "hover_search"}),
                production_view({badge: 4, key: "starred_messages"}),
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
        column.setAttribute("aria-label", "Workspace sidebar");
        column.append(template_story);
        const feedback = globalThis.document.createElement("p");
        feedback.className = "storybook-cf-production-nav__feedback";
        feedback.setAttribute("role", "status");
        feedback.setAttribute("aria-live", "polite");
        column.append(feedback);
        column.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }
            const action = event.target.closest<HTMLButtonElement>(".cf-nav-item__action");
            if (action) {
                feedback.textContent = `${action.getAttribute("aria-label") ?? "Options"} opened.`;
                return;
            }
            const link = event.target.closest<HTMLAnchorElement>(".cf-nav-item__main");
            if (link) {
                event.preventDefault();
                const label = link.querySelector(".cf-nav-item__label")?.textContent ?? "View";
                feedback.textContent = `${label} selected.`;
            }
        });
        frame.append(column);
        return frame;
    },
};

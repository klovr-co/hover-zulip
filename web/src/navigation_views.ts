import * as blueslip from "./blueslip.ts";
import type {CofounderIconName} from "./cofounder/components/icon.ts";
import {$t} from "./i18n.ts";
import type {NavigationView, StateData} from "./state_data.ts";
import {user_settings} from "./user_settings.ts";

export type BuiltInViewBasicMetadata = {
    fragment: string;
    name: string;
    is_pinned: boolean;
    cf_icon: CofounderIconName;
    css_class_suffix: string;
    tooltip_template_id: string;
    has_unread_count: boolean;
    unread_count_type: "normal-count" | "quiet-count" | "";
    supports_masked_unread: boolean;
    hidden_for_spectators: boolean;
    menu_icon_class: string;
    menu_aria_label: string;
    home_view_code: string;
    prioritize_in_condensed_view: boolean;
};

export const built_in_views_meta_data: Record<string, BuiltInViewBasicMetadata> = {
    inbox: {
        fragment: "inbox",
        name: $t({defaultMessage: "Inbox"}),
        is_pinned: true,
        cf_icon: "inbox",
        css_class_suffix: "inbox",
        tooltip_template_id: "inbox-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        supports_masked_unread: true,
        hidden_for_spectators: true,
        menu_icon_class: "inbox-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Inbox options"}),
        home_view_code: "inbox",
        prioritize_in_condensed_view: true,
    },
    recent_view: {
        fragment: "recent",
        name: $t({defaultMessage: "Recent conversations"}),
        is_pinned: true,
        cf_icon: "clock",
        css_class_suffix: "recent_view",
        tooltip_template_id: "recent-conversations-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        supports_masked_unread: true,
        hidden_for_spectators: false,
        menu_icon_class: "recent-view-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Recent conversations options"}),
        home_view_code: "recent",
        prioritize_in_condensed_view: true,
    },
    all_messages: {
        fragment: "feed",
        name: $t({defaultMessage: "Combined feed"}),
        is_pinned: true,
        cf_icon: "activity",
        css_class_suffix: "all_messages",
        tooltip_template_id: "all-message-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        supports_masked_unread: true,
        hidden_for_spectators: false,
        menu_icon_class: "all-messages-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Combined feed options"}),
        home_view_code: "all_messages",
        prioritize_in_condensed_view: true,
    },
    mentions: {
        fragment: "narrow/is/mentioned",
        name: $t({defaultMessage: "Mentions"}),
        is_pinned: true,
        cf_icon: "at-sign",
        css_class_suffix: "mentions",
        tooltip_template_id: "mentions-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: true,
    },
    my_reactions: {
        fragment: "narrow/has/reaction/sender/me",
        name: $t({defaultMessage: "Reactions"}),
        is_pinned: true,
        cf_icon: "smile",
        css_class_suffix: "my_reactions",
        tooltip_template_id: "my-reactions-tooltip-template",
        has_unread_count: false,
        unread_count_type: "",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: false,
    },
    starred_messages: {
        fragment: "narrow/is/starred",
        name: $t({defaultMessage: "Starred messages"}),
        is_pinned: true,
        cf_icon: "star",
        css_class_suffix: "starred_messages",
        tooltip_template_id: "starred-message-tooltip-template",
        has_unread_count: true,
        unread_count_type: "quiet-count",
        supports_masked_unread: true,
        hidden_for_spectators: true,
        menu_icon_class: "starred-messages-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Starred messages options"}),
        home_view_code: "",
        prioritize_in_condensed_view: true,
    },
    hover_search: {
        fragment: "hover/search",
        name: $t({defaultMessage: "Search"}),
        is_pinned: true,
        cf_icon: "search",
        css_class_suffix: "hover_search",
        tooltip_template_id: "hover-search-tooltip-template",
        has_unread_count: false,
        unread_count_type: "",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: false,
    },
    hover_editions: {
        fragment: "hover/editions",
        name: $t({defaultMessage: "Daily Brief"}),
        is_pinned: true,
        cf_icon: "sun",
        css_class_suffix: "daily_brief",
        tooltip_template_id: "daily-brief-tooltip-template",
        has_unread_count: false,
        unread_count_type: "",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: true,
    },
    drafts: {
        fragment: "drafts",
        name: $t({defaultMessage: "Drafts"}),
        is_pinned: true,
        cf_icon: "file",
        css_class_suffix: "drafts",
        tooltip_template_id: "drafts-tooltip-template",
        has_unread_count: true,
        unread_count_type: "quiet-count",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "drafts-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Drafts options"}),
        home_view_code: "",
        prioritize_in_condensed_view: false,
    },
    scheduled_messages: {
        fragment: "scheduled",
        name: $t({defaultMessage: "Scheduled messages"}),
        is_pinned: true,
        cf_icon: "calendar",
        css_class_suffix: "scheduled_messages",
        tooltip_template_id: "scheduled-tooltip-template",
        has_unread_count: true,
        unread_count_type: "quiet-count",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: false,
    },
    reminders: {
        fragment: "reminders",
        name: $t({defaultMessage: "Reminders"}),
        is_pinned: true,
        cf_icon: "alarm",
        css_class_suffix: "reminders",
        tooltip_template_id: "reminders-tooltip-template",
        has_unread_count: true,
        unread_count_type: "quiet-count",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: false,
    },
};

let hover_enabled = false;

export function set_hover_enabled(enabled: boolean): void {
    hover_enabled = enabled;
    Object.assign(built_in_views_meta_data["inbox"]!, {
        name: enabled ? $t({defaultMessage: "For You"}) : $t({defaultMessage: "Inbox"}),
        tooltip_template_id: enabled ? "hover-inbox-tooltip-template" : "inbox-tooltip-template",
        menu_aria_label: enabled
            ? $t({defaultMessage: "For You options"})
            : $t({defaultMessage: "Inbox options"}),
    });
    Object.assign(built_in_views_meta_data["recent_view"]!, {
        name: enabled
            ? $t({defaultMessage: "Team Pulse"})
            : $t({defaultMessage: "Recent conversations"}),
        menu_aria_label: enabled
            ? $t({defaultMessage: "Team Pulse options"})
            : $t({defaultMessage: "Recent conversations options"}),
        tooltip_template_id: enabled
            ? "hover-recent-conversations-tooltip-template"
            : "recent-conversations-tooltip-template",
    });
    Object.assign(built_in_views_meta_data["all_messages"]!, {
        name: enabled
            ? $t({defaultMessage: "All activity"})
            : $t({defaultMessage: "Combined feed"}),
        tooltip_template_id: enabled
            ? "hover-all-message-tooltip-template"
            : "all-message-tooltip-template",
        menu_aria_label: enabled
            ? $t({defaultMessage: "All activity options"})
            : $t({defaultMessage: "Combined feed options"}),
    });
    Object.assign(built_in_views_meta_data["starred_messages"]!, {
        name: enabled ? $t({defaultMessage: "Saved"}) : $t({defaultMessage: "Starred messages"}),
        tooltip_template_id: enabled
            ? "hover-starred-message-tooltip-template"
            : "starred-message-tooltip-template",
        menu_aria_label: enabled
            ? $t({defaultMessage: "Saved options"})
            : $t({defaultMessage: "Starred messages options"}),
    });
    Object.assign(built_in_views_meta_data["reminders"]!, {
        name: enabled ? $t({defaultMessage: "Todos"}) : $t({defaultMessage: "Reminders"}),
        tooltip_template_id: enabled
            ? "hover-reminders-tooltip-template"
            : "reminders-tooltip-template",
    });
}

let navigation_views_dict: Map<string, NavigationView>;

export function add_navigation_view(navigation_view: NavigationView): void {
    navigation_views_dict.set(navigation_view.fragment, navigation_view);
}

export function update_navigation_view(fragment: string, data: Partial<NavigationView>): void {
    const view = get_navigation_view_by_fragment(fragment);
    if (view) {
        navigation_views_dict.set(fragment, {
            ...view,
            ...data,
        });
    } else {
        blueslip.error("Cannot find navigation view to update");
    }
}

export function remove_navigation_view(fragment: string): void {
    navigation_views_dict.delete(fragment);
}

export function get_navigation_view_by_fragment(fragment: string): NavigationView | undefined {
    return navigation_views_dict.get(fragment);
}

export type BuiltInViewMetadata = BuiltInViewBasicMetadata & {
    is_home_view: boolean;
    unread_count?: number;
    href: string;
    item_classes: string;
    main_classes: string;
    action_classes: string;
    badge_classes: string;
    badge_visible: boolean;
    selected: boolean;
};

export function get_built_in_views(): BuiltInViewMetadata[] {
    return Object.values(built_in_views_meta_data)
        .filter((view) => {
            if (hover_enabled) {
                return view.fragment !== "narrow/is/mentioned";
            }
            return view.fragment !== "hover/search" && view.fragment !== "hover/editions";
        })
        .map((view) => {
            const view_current_data = get_navigation_view_by_fragment(view.fragment);
            const is_home_view = view.home_view_code === user_settings.web_home_view;
            return {
                ...view,
                href: `#${view.fragment}`,
                is_pinned: view_current_data?.is_pinned ?? view.is_pinned,
                is_home_view,
                item_classes: `top_left_${view.css_class_suffix} top_left_row${
                    view.hidden_for_spectators ? " hidden-for-spectators" : ""
                }${is_home_view ? " selected-home-view" : ""}`,
                main_classes: "left-sidebar-navigation-label-container tippy-left-sidebar-tooltip",
                action_classes: `arrow sidebar-menu-icon ${view.menu_icon_class} hidden-for-spectators`,
                badge_classes: `unread_count ${view.unread_count_type}`.trim(),
                badge_visible: false,
                selected: false,
            };
        });
}

export function get_all_navigation_views(): NavigationView[] {
    const built_in_views = get_built_in_views().map((view) => ({
        fragment: view.fragment,
        is_pinned: view.is_pinned,
        name: view.name,
    }));
    const built_in_fragments = new Set(built_in_views.map((view) => view.fragment));
    const custom_views = navigation_views_dict
        .values()
        .filter((view) => !built_in_fragments.has(view.fragment));
    return [...built_in_views, ...custom_views];
}

export const initialize = (params: StateData["navigation_views"]): void => {
    navigation_views_dict = new Map<string, NavigationView>(
        params.navigation_views.map((view) => [view.fragment, view]),
    );
};

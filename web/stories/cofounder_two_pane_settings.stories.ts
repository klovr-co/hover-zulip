import type {Meta, StoryObj} from "@storybook/html";

import render_channel_row from "../templates/stream_settings/browse_streams_list_item.hbs";
import render_channels from "../templates/stream_settings/stream_settings_overlay.hbs";
import render_sort_label from "../templates/stream_settings/stream_sorter_toggle_label.hbs";
import render_group_row from "../templates/user_group_settings/browse_user_groups_list_item.hbs";
import render_group_title from "../templates/user_group_settings/selected_group_title.hbs";
import render_groups from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import {render_template_story} from "./template_story_utils.ts";

type Surface = "channels" | "groups";

function populate_channel_rows(host: HTMLElement): void {
    const list = host.querySelector<HTMLElement>(".streams-list");
    if (!list) {
        return;
    }
    list.innerHTML = [
        {
            color: "#0878e8",
            name: "Design",
            rendered_description: "Design reviews and product decisions",
            stream_id: 7,
            subscriber_count: 24,
            subscribed: true,
        },
        {
            color: "#278642",
            name: "Product",
            rendered_description: "Roadmap, research, and launch planning",
            stream_id: 8,
            subscriber_count: 41,
            subscribed: true,
        },
        {
            color: "#9a6500",
            name: "Customer feedback",
            rendered_description: "Patterns gathered from customer conversations",
            stream_id: 9,
            subscriber_count: 18,
            subscribed: false,
        },
    ]
        .map((channel) =>
            render_channel_row({
                ...channel,
                can_access_subscribers: true,
                should_display_subscription_button: true,
            }),
        )
        .join("");
    list.querySelector(".stream-row")?.classList.add("active");
}

function populate_group_rows(host: HTMLElement): void {
    const list = host.querySelector<HTMLElement>(".user-groups-list");
    if (!list) {
        return;
    }
    list.innerHTML = [
        {description: "Product design team", id: 3, is_member: true, name: "Design"},
        {description: "Research planning and synthesis", id: 4, name: "Research"},
        {description: "Organization administrators", id: 5, is_system_group: true, name: "Admins"},
    ]
        .map((group) =>
            render_group_row({
                ...group,
                can_join: true,
                can_leave: true,
                is_direct_member: true,
            }),
        )
        .join("");
    list.querySelector(".group-row")?.classList.add("active");
}

function populate_channel_sorter(host: HTMLElement): void {
    const container = host.querySelector<HTMLElement>(".list-toggler-container");
    if (!container) {
        return;
    }
    const options = [
        {icon: "sort-ascending", label: "Sort by name"},
        {icon: "users", label: "Sort by number of subscribers"},
        {icon: "activity", label: "Sort by estimated weekly traffic"},
    ];
    container.innerHTML = `<div class="cf-tabs stream_sorter_toggle" role="tablist">${options
        .map(
            (option, index) =>
                `<button type="button" class="cf-tabs__tab${index === 0 ? " cf-tabs__tab--active" : ""}" role="tab" aria-label="${option.label}" aria-selected="${index === 0}">${render_sort_label({icon: option.icon, tooltip: option.label})}</button>`,
        )
        .join("")}</div>`;
}

function populate_group_title(host: HTMLElement): void {
    const title = host.querySelector<HTMLElement>(".user-group-info-title");
    if (!title) {
        return;
    }
    title.innerHTML = render_group_title({
        group_id: 3,
        group_name: "Design",
        is_direct_member: true,
        is_system_group: false,
    });
    title
        .querySelector<HTMLElement>(".deactivated-user-group-icon")
        ?.style.setProperty("display", "none");
    title
        .querySelector<HTMLElement>(".reactivate-group-button")
        ?.style.setProperty("display", "none");
}

function render_scene(surface: Surface, mobileDetail = false): HTMLElement {
    const host =
        surface === "channels"
            ? render_template_story(
                  "stream_settings/stream_settings_overlay.hbs",
                  render_channels,
                  {
                      can_create_streams: true,
                      can_view_all_streams: true,
                      realm_has_archived_channels: true,
                  },
              )
            : render_template_story(
                  "user_group_settings/user_group_settings_overlay.hbs",
                  render_groups,
                  {},
              );
    host.classList.add("cf-theme", "storybook-two-pane-settings");

    if (surface === "channels") {
        populate_channel_rows(host);
        populate_channel_sorter(host);
        const value = host.querySelector(
            ":scope #stream_settings_filter_widget .dropdown_widget_value",
        );
        value?.append("Active");
    } else {
        populate_group_rows(host);
        populate_group_title(host);
        const value = host.querySelector(
            ":scope #user_group_visibility_settings_widget .dropdown_widget_value",
        );
        value?.append("All groups");
    }

    host.querySelectorAll<HTMLElement>(
        ":scope .no-streams-to-show, :scope .no-groups-to-show",
    ).forEach((element) => {
        element.hidden = true;
    });

    if (mobileDetail) {
        host.querySelector(":scope .cf-two-pane-shell__pane--detail")?.classList.add("show");
        host.querySelector(":scope .cf-two-pane-shell__header")?.classList.add("slide-left");
        if (surface === "channels") {
            const title = host.querySelector(".cf-two-pane-shell__pane-title");
            if (title) {
                title.textContent = "Design";
            }
        }
    }
    return host;
}

const meta = {
    title: "Cofounder/Settings/Two Pane Shell",
    parameters: {layout: "fullscreen"},
    render: () => render_scene("channels"),
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const Channels: Story = {};

export const UserGroups: Story = {
    render: () => render_scene("groups"),
};

export const MobileChannelDetail: Story = {
    render: () => render_scene("channels", true),
};

export const MobileUserGroupDetail: Story = {
    render: () => render_scene("groups", true),
};

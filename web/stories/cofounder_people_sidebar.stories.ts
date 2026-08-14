import type {Meta, StoryObj} from "@storybook/html";

import render_section_header from "../templates/buddy_list/section_header.hbs";
import render_presence_rows from "../templates/presence_rows.hbs";
import render_right_sidebar from "../templates/right_sidebar.hbs";

import {render_template_story} from "./template_story_utils.ts";

type DisplayStyle = "avatar" | "compact" | "status";

type PeopleSidebarArgs = {
    display_style: DisplayStyle;
};

const avatar = (initials: string, color: string): string =>
    `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="100%" height="100%" rx="40" fill="${color}"/><text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle" fill="white" font-family="sans-serif" font-size="29" font-weight="600">${initials}</text></svg>`)}`;

function people(display_style: DisplayStyle): object[] {
    const style = {
        WITH_AVATAR: display_style === "avatar",
        WITH_STATUS: display_style === "status",
    };
    return [
        {
            has_status_text: display_style === "status",
            href: "#dm/ava",
            is_current_user: false,
            name: "Ava Rodriguez",
            num_unread: 3,
            profile_picture: avatar("AR", "#7584b5"),
            status_text: "Reviewing the launch brief",
            user_circle_class: "user-circle-active",
            user_id: 7,
            user_list_style: style,
        },
        {
            has_status_text: display_style === "status",
            href: "#dm/jamie",
            is_current_user: false,
            name: "Jamie Morris",
            num_unread: 0,
            profile_picture: avatar("JM", "#d4a95f"),
            status_text: "In a design review",
            user_circle_class: "user-circle-idle",
            user_id: 8,
            user_list_style: style,
        },
        {
            has_status_text: display_style === "status",
            href: "#dm/taylor",
            is_current_user: false,
            name: "Taylor Smith",
            num_unread: 0,
            profile_picture: avatar("TS", "#79ad82"),
            status_text: "Available",
            user_circle_class: "user-circle-active",
            user_id: 9,
            user_list_style: style,
        },
        {
            has_status_text: display_style === "status",
            href: "#dm/riley",
            is_current_user: false,
            name: "Riley Wong",
            num_unread: 0,
            profile_picture: avatar("RW", "#d68173"),
            status_text: "Offline",
            user_circle_class: "user-circle-offline",
            user_id: 10,
            user_list_style: style,
        },
    ];
}

function render_people_sidebar(args: PeopleSidebarArgs): HTMLElement {
    const host = render_template_story("right_sidebar.hbs", render_right_sidebar, {});
    host.classList.add("cf-theme", "storybook-people-sidebar");

    const sidebar = host.querySelector<HTMLElement>(":scope #right-sidebar");
    if (sidebar === null) {
        return host;
    }

    const participants = sidebar.querySelector<HTMLElement>(
        ":scope #buddy-list-participants-container",
    );
    participants?.remove();

    const header = sidebar.querySelector<HTMLElement>(
        ":scope #buddy-list-users-matching-view-container .cf-people-sidebar__section-header",
    );
    if (header !== null) {
        header.innerHTML = render_section_header({
            header_text: "Members",
            id: "storybook-people-heading",
            is_collapsed: false,
        });
    }

    const list = sidebar.querySelector<HTMLElement>(":scope #buddy-list-users-matching-view");
    if (list !== null) {
        list.innerHTML = render_presence_rows({presence_rows: people(args.display_style)});
    }

    sidebar.querySelector<HTMLElement>(":scope #buddy-list-other-users-container")?.remove();
    sidebar.querySelector<HTMLElement>(":scope .cf-people-sidebar__invite")?.remove();
    return host;
}

const meta = {
    title: "Cofounder/People Sidebar",
    parameters: {layout: "fullscreen"},
    args: {display_style: "avatar"},
    render: render_people_sidebar,
} satisfies Meta<PeopleSidebarArgs>;

export default meta;
type Story = StoryObj<PeopleSidebarArgs>;

export const Avatars: Story = {};

export const Status: Story = {
    args: {display_style: "status"},
};

export const Compact: Story = {
    args: {display_style: "compact"},
};

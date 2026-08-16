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
            presence_label: "Active now",
            profile_picture: avatar("AR", "#7584b5"),
            status_text: "Reviewing the launch brief",
            user_actions_label: "User actions for Ava Rodriguez",
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
            presence_label: "Idle",
            profile_picture: avatar("JM", "#d4a95f"),
            status_text: "In a design review",
            user_actions_label: "User actions for Jamie Morris",
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
            presence_label: "Active now",
            profile_picture: avatar("TS", "#79ad82"),
            status_text: "Available",
            user_actions_label: "User actions for Taylor Smith",
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
            presence_label: "Offline",
            profile_picture: avatar("RW", "#d68173"),
            status_text: "Offline",
            user_actions_label: "User actions for Riley Wong",
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
            controls_id: "buddy-list-users-matching-view",
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

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-people-sidebar__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    host.append(feedback);

    const announce = (message: string): void => {
        feedback.textContent = message;
    };
    const filter = sidebar.querySelector<HTMLInputElement>(".user-list-filter");
    const apply_filter = (): void => {
        const query = filter?.value.trim().toLocaleLowerCase() ?? "";
        let visible_count = 0;
        for (const row of sidebar.querySelectorAll<HTMLElement>(".cf-member-row")) {
            const matches = row.dataset["name"]?.toLocaleLowerCase().includes(query) ?? false;
            row.hidden = !matches;
            if (matches) {
                visible_count += 1;
            }
        }
        announce(`${visible_count} ${visible_count === 1 ? "person" : "people"} shown.`);
    };
    filter?.addEventListener("input", apply_filter);

    sidebar.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const clear = event.target.closest<HTMLButtonElement>(".input-close-filter-button");
        if (clear && filter) {
            filter.value = "";
            apply_filter();
            filter.focus();
            return;
        }
        const toggle = event.target.closest<HTMLButtonElement>(
            ".cf-people-sidebar__section-toggle",
        );
        if (toggle && list) {
            const expanded = toggle.getAttribute("aria-expanded") === "true";
            toggle.setAttribute("aria-expanded", String(!expanded));
            list.hidden = expanded;
            announce(`Members ${expanded ? "collapsed" : "expanded"}.`);
            return;
        }
        if (event.target.closest(".cf-people-sidebar__menu")) {
            announce("People list options opened.");
            return;
        }
        const user_actions = event.target.closest<HTMLButtonElement>(".cf-member-row__actions");
        if (user_actions) {
            const name = user_actions.closest<HTMLElement>(".cf-member-row")?.dataset["name"];
            announce(`${name ?? "Member"} actions opened.`);
            return;
        }
        const member_link = event.target.closest<HTMLAnchorElement>(".cf-member-row__link");
        if (member_link) {
            event.preventDefault();
            const name = member_link.closest<HTMLElement>(".cf-member-row")?.dataset["name"];
            announce(`${name ?? "Member"} conversation selected.`);
        }
    });
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

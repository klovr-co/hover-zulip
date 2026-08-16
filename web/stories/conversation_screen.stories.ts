import type {Meta, StoryObj} from "@storybook/html";

import render_composer from "../templates/cofounder/components/composer.hbs";
import render_icon from "../templates/cofounder/components/icon.hbs";
import render_message from "../templates/cofounder/components/message.hbs";
import render_left_sidebar from "../templates/left_sidebar.hbs";
import render_navbar from "../templates/navbar.hbs";
import render_presence_rows from "../templates/presence_rows.hbs";
import render_recipient_row from "../templates/recipient_row.hbs";

type ConversationArgs = {focused: boolean; narrow: boolean; show_right_sidebar: boolean};

const avatar = (initials: string, color: string): string =>
    `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="100%" height="100%" rx="14" fill="${color}"/><text x="50%" y="56%" dominant-baseline="middle" text-anchor="middle" fill="white" font-family="sans-serif" font-size="30">${initials}</text></svg>`)}`;

function stream_row(name: string, count?: number): string {
    return `<li class="stream-list-subscription"><a class="stream-name" href="#narrow/channel/${name}">${render_icon({compact: true, name: "hash"})}<span>${name}</span></a>${count === undefined ? "" : `<span class="unread_count normal-count">${count}</span>`}</li>`;
}

function message(
    sender: string,
    time: string,
    content_html: string,
    avatar_url: string,
    reactions: {count: number; emoji: string; label: string; selected?: boolean}[],
    is_own = false,
): string {
    return render_message({
        avatar_url,
        content_html,
        has_reactions: reactions.length > 0,
        is_own,
        reactions,
        sender,
        time,
    });
}

function presence_row(
    name: string,
    user_id: number,
    presence: "active" | "idle",
    num_unread = 0,
    unread_id = `conversation-unread-${user_id}`,
): object {
    return {
        href: `#user/${user_id}`,
        name,
        num_unread,
        presence_label: presence === "active" ? "Active now" : "Idle",
        unread_id,
        user_actions_label: `User actions for ${name}`,
        user_circle_class: `user-circle-${presence}`,
        user_id,
        user_list_style: {WITH_AVATAR: false, WITH_STATUS: false},
    };
}

function escape_html(value: string): string {
    const container = globalThis.document.createElement("span");
    container.textContent = value;
    return container.innerHTML;
}

function initialize_conversation(screen: HTMLElement): void {
    const feedback = screen.querySelector<HTMLElement>(".storybook-conversation-feedback");
    const filter = screen.querySelector<HTMLInputElement>(".left-sidebar-search-input");
    const message_list = screen.querySelector<HTMLElement>(".message-list");
    if (feedback === null || filter === null || message_list === null) {
        return;
    }

    filter.addEventListener("input", () => {
        const query = filter.value.trim().toLocaleLowerCase();
        let visible = 0;
        for (const row of screen.querySelectorAll<HTMLElement>(
            ":scope #direct-messages-list .cf-member-row, :scope .stream-list-subscription",
        )) {
            const matches = row.textContent?.toLocaleLowerCase().includes(query) ?? false;
            row.hidden = !matches;
            if (matches) {
                visible += 1;
            }
        }
        feedback.textContent =
            query === ""
                ? "Navigation filter cleared."
                : `${visible} navigation ${visible === 1 ? "result" : "results"}.`;
    });

    screen.addEventListener("submit", (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.classList.contains("cf-composer")) {
            return;
        }
        event.preventDefault();
        const textarea = form.querySelector<HTMLTextAreaElement>(".cf-composer__textarea");
        const value = textarea?.value.trim() ?? "";
        if (textarea === null || value === "") {
            feedback.textContent = "Write a message before sending.";
            textarea?.focus();
            return;
        }
        message_list.insertAdjacentHTML(
            "beforeend",
            message("Maxine", "Now", escape_html(value), avatar("MA", "#5d7fa3"), [], true),
        );
        textarea.value = "";
        textarea.focus();
        message_list.lastElementChild?.scrollIntoView({block: "nearest"});
        feedback.textContent = "Message sent to design / Homepage redesign.";
    });

    screen.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        if (target.closest(".input-close-filter-button") !== null) {
            filter.value = "";
            filter.dispatchEvent(new Event("input", {bubbles: true}));
            filter.focus();
            return;
        }

        const reaction = target.closest<HTMLButtonElement>(".cf-message-item__reaction");
        if (reaction !== null) {
            const selected = reaction.getAttribute("aria-pressed") !== "true";
            const count = reaction.querySelector<HTMLElement>("span:last-child");
            const current_count = Number.parseInt(count?.textContent ?? "0", 10);
            const next_count = Math.max(0, current_count + (selected ? 1 : -1));
            reaction.classList.toggle("cf-message-item__reaction--selected", selected);
            reaction.setAttribute("aria-pressed", String(selected));
            reaction.setAttribute(
                "aria-label",
                (reaction.getAttribute("aria-label") ?? "Reaction").replace(/\d+$/, () =>
                    String(next_count),
                ),
            );
            if (count !== null) {
                count.textContent = String(next_count);
            }
            feedback.textContent = selected ? "Reaction added." : "Reaction removed.";
            return;
        }

        const link = target.closest<HTMLAnchorElement>("a[href]");
        if (link !== null) {
            event.preventDefault();
            const label =
                link.getAttribute("aria-label") ?? link.textContent?.trim() ?? "Destination";
            feedback.textContent = `${label} opened.`;
            return;
        }

        const button = target.closest<HTMLButtonElement>("button");
        if (button !== null && !button.disabled) {
            const label =
                button.getAttribute("aria-label") ?? button.textContent?.trim() ?? "Action";
            feedback.textContent = `${label} requested.`;
        }
    });
}

function render_conversation(args: ConversationArgs): HTMLElement {
    const screen = globalThis.document.createElement("div");
    screen.className = "cf-theme storybook-conversation-screen";
    screen.classList.toggle("storybook-conversation-screen--focused", args.focused);
    screen.classList.toggle("storybook-conversation-screen--narrow", args.narrow);
    screen.innerHTML = render_navbar({
        embedded: false,
        realm_logo_url: avatar("H", "#0878e8"),
        user_avatar: avatar("MA", "#5d7fa3"),
    });

    const body = globalThis.document.createElement("div");
    body.className = "storybook-conversation-body";
    body.innerHTML = render_left_sidebar({
        LEFT_SIDEBAR_DIRECT_MESSAGES_TITLE: "DIRECT MESSAGES",
        LEFT_SIDEBAR_NAVIGATION_AREA_TITLE: "VIEWS",
        expanded_views: [],
        is_guest: false,
        is_spectator: false,
        primary_condensed_views: [],
    });
    const sidebar = body.querySelector<HTMLElement>(".left-sidebar");
    if (sidebar !== null) {
        const direct_messages = sidebar.querySelector<HTMLElement>("#direct-messages-list");
        if (direct_messages !== null) {
            direct_messages.innerHTML = `<ul class="user-list">${render_presence_rows({presence_rows: [presence_row("Ava Rodriguez", 1, "active", 3, "conversation-dm-unread-1"), presence_row("Sam Lee", 2, "idle", 0, "conversation-dm-unread-2")]})}</ul>`;
        }
        const streams = sidebar.querySelector<HTMLElement>("#streams_list");
        if (streams !== null) {
            streams.insertAdjacentHTML(
                "beforeend",
                `<div class="left-sidebar-section-header"><h4 class="left-sidebar-title">CHANNELS</h4></div><ul class="stream-list">${stream_row("design", 7)}${stream_row("engineering", 2)}${stream_row("announcements")}</ul>`,
            );
        }
    }

    const main = globalThis.document.createElement("main");
    main.className = "storybook-message-pane";
    main.setAttribute("aria-label", "Conversation: design / Homepage redesign");
    main.innerHTML = `<div class="message-view-header">${render_recipient_row({all_visibility_policies: {FOLLOWED: "FOLLOWED", MUTED: "MUTED", UNMUTED: "UNMUTED"}, date_html: "Today", date_unchanged: false, display_recipient: "design", is_archived: false, is_empty_string_topic: false, is_stream: true, is_subscribed: true, is_topic_editable: true, recipient_bar_color: "#4f8394", stream_id: 7, stream_privacy_icon_color: "#ffffff", stream_url: "#narrow/channel/design", topic: "Homepage redesign", topic_display_name: "Homepage redesign", topic_is_resolved: false, topic_links: [], topic_url: "#narrow/channel/design/topic/Homepage%20redesign", user_can_resolve_topic: true, visibility_policy: "INHERIT"})}</div><div class="message-list" role="list" aria-label="Messages in design / Homepage redesign"></div><div class="storybook-compose">${render_composer({channel: "design", disabled: false, placeholder: "Compose a message", recipient: "Homepage redesign", value: ""})}</div>`;
    const message_list = main.querySelector<HTMLElement>(".message-list");
    if (message_list !== null) {
        const reactions = [
            {count: 4, emoji: "👍", label: "thumbs up, 4", selected: true},
            {count: 2, emoji: "💡", label: "bulb, 2"},
        ];
        message_list.innerHTML =
            message(
                "Ava Rodriguez",
                "10:32 AM",
                "I’ve put the latest homepage direction in the shared file. The calmer visual hierarchy should make the next step more obvious.",
                avatar("AR", "#a06a91"),
                reactions,
            ) +
            message(
                "Sam Lee",
                "10:41 AM",
                "The grouped sections look much easier to scan. I’ll add the empty and loading states before our review.",
                avatar("SL", "#5c9b72"),
                [],
            ) +
            message(
                "Maxine",
                "10:45 AM",
                "Perfect — let’s use this view to compare component states as we redesign.",
                avatar("MA", "#5d7fa3"),
                [],
                true,
            );
    }
    body.append(main);
    if (args.show_right_sidebar) {
        body.insertAdjacentHTML(
            "beforeend",
            `<aside class="storybook-right-sidebar right-sidebar" aria-label="People"><div class="right-sidebar-header"><h2>People</h2><span>3 online</span></div><ul class="user-list">${render_presence_rows({presence_rows: [presence_row("Ava Rodriguez", 1, "active", 0, "conversation-people-unread-1"), presence_row("Sam Lee", 2, "active", 0, "conversation-people-unread-2"), presence_row("Maxine", 3, "idle", 0, "conversation-people-unread-3")]})}</ul></aside>`,
        );
    }
    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-conversation-feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    screen.append(body, feedback);
    initialize_conversation(screen);
    return screen;
}

const meta = {
    title: "Cofounder/Screens/Conversation",
    tags: ["autodocs"],
    args: {focused: false, narrow: false, show_right_sidebar: true},
    render: render_conversation,
} satisfies Meta<ConversationArgs>;

export default meta;
type Story = StoryObj<ConversationArgs>;

export const Default: Story = {};
export const Focused: Story = {args: {focused: true, show_right_sidebar: false}};
export const Narrow: Story = {
    args: {narrow: true, show_right_sidebar: false},
    parameters: {viewport: {defaultViewport: "mobile1"}},
};

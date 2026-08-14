import type {Meta, StoryObj} from "@storybook/html";

import render_composer from "../templates/cofounder/components/composer.hbs";
import render_message from "../templates/cofounder/components/message.hbs";
import render_left_sidebar from "../templates/left_sidebar.hbs";
import render_navbar from "../templates/navbar.hbs";
import render_presence_rows from "../templates/presence_rows.hbs";
import render_recipient_row from "../templates/recipient_row.hbs";

type ConversationArgs = {show_right_sidebar: boolean};

const avatar = (initials: string, color: string): string =>
    `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="100%" height="100%" rx="14" fill="${color}"/><text x="50%" y="56%" dominant-baseline="middle" text-anchor="middle" fill="white" font-family="sans-serif" font-size="30">${initials}</text></svg>`)}`;

function stream_row(name: string, count?: number): string {
    return `<li class="stream-list-subscription"><a class="stream-name" href="#narrow/channel/${name}"><i class="zulip-icon zulip-icon-hash" aria-hidden="true"></i>${name}</a>${count === undefined ? "" : `<span class="unread_count normal-count">${count}</span>`}</li>`;
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
    user_circle_class: string,
    num_unread = 0,
): object {
    return {
        href: `#user/${user_id}`,
        name,
        num_unread,
        user_circle_class,
        user_id,
        user_list_style: {WITH_AVATAR: false, WITH_STATUS: false},
    };
}

function render_conversation(args: ConversationArgs): HTMLElement {
    const screen = globalThis.document.createElement("div");
    screen.className = "storybook-conversation-screen";
    screen.innerHTML = render_navbar({embedded: false, user_avatar: avatar("MA", "#5d7fa3")});

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
            direct_messages.innerHTML = `<ul class="user-list">${render_presence_rows({presence_rows: [presence_row("Ava Rodriguez", 1, "active", 3), presence_row("Sam Lee", 2, "idle")]})}</ul>`;
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
    main.innerHTML = `<div class="message-view-header">${render_recipient_row({all_visibility_policies: {FOLLOWED: "FOLLOWED", MUTED: "MUTED", UNMUTED: "UNMUTED"}, date_html: "Today", date_unchanged: false, display_recipient: "design", is_archived: false, is_empty_string_topic: false, is_stream: true, is_subscribed: true, is_topic_editable: true, recipient_bar_color: "#4f8394", stream_id: 7, stream_privacy_icon_color: "#ffffff", stream_url: "#narrow/channel/design", topic: "Homepage redesign", topic_display_name: "Homepage redesign", topic_is_resolved: false, topic_links: [], topic_url: "#narrow/channel/design/topic/Homepage%20redesign", user_can_resolve_topic: true, visibility_policy: "INHERIT"})}</div><div class="message-list" role="list"></div><div class="storybook-compose">${render_composer({channel: "design", disabled: false, placeholder: "Compose a message", recipient: "Homepage redesign", value: ""})}</div>`;
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
            `<aside class="storybook-right-sidebar right-sidebar"><div class="right-sidebar-header"><strong>People</strong><span>3 online</span></div><ul class="user-list">${render_presence_rows({presence_rows: [presence_row("Ava Rodriguez", 1, "active"), presence_row("Sam Lee", 2, "active"), presence_row("Maxine", 3, "idle")]})}</ul></aside>`,
        );
    }
    screen.append(body);
    return screen;
}

const meta = {
    title: "Cofounder/Screens/Conversation",
    tags: ["autodocs"],
    args: {show_right_sidebar: true},
    render: render_conversation,
} satisfies Meta<ConversationArgs>;

export default meta;
type Story = StoryObj<ConversationArgs>;

export const Default: Story = {};
export const Focused: Story = {args: {show_right_sidebar: false}};
export const Narrow: Story = {args: {show_right_sidebar: false}};

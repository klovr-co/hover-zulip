import type {Meta, StoryObj} from "@storybook/html";

import render_inbox from "../templates/inbox_view/inbox_view.hbs";

const policies = {FOLLOWED: "FOLLOWED", INHERIT: "INHERIT", MUTED: "MUTED", UNMUTED: "UNMUTED"};
const columns = {ACTION_MENU: 3, FULL_ROW: 0, TOPIC_VISIBILITY: 2, UNREAD_COUNT: 1};

function topic(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return {
        all_visibility_policies: policies,
        column_indexes: columns,
        conversation_key: "design:homepage",
        is_direct: false,
        is_empty_string_topic: false,
        is_hidden: false,
        is_stream: false,
        is_topic: true,
        mention_in_unread: false,
        stream_archived: false,
        stream_id: 7,
        topic_display_name: "Homepage redesign",
        topic_name: "Homepage redesign",
        topic_url: "#topic",
        unread_count: 4,
        visibility_policy: policies.FOLLOWED,
        ...overrides,
    };
}

function stream(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return {
        column_indexes: columns,
        invite_only: false,
        is_archived: false,
        is_collapsed: false,
        is_hidden: false,
        is_muted: false,
        is_stream: true,
        mention_in_unread: false,
        stream_color: "#4f8394",
        stream_header_color: "#f5f8fa",
        stream_id: 7,
        stream_name: "design",
        unread_count: 6,
        ...overrides,
    };
}

function dm(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return {
        column_indexes: columns,
        conversation_key: "1,2",
        dm_url: "#dm",
        has_unread_mention: false,
        is_bot: false,
        is_direct: true,
        is_group: false,
        is_hidden: false,
        is_stream: false,
        is_topic: false,
        rendered_dm_with_html: "Ava Rodriguez",
        unread_count: 2,
        user_circle_class: "user-circle-active",
        user_ids_string: "1",
        ...overrides,
    };
}

function render_scene({empty = false} = {}): HTMLElement {
    const host = globalThis.document.createElement("section");
    host.className = "cf-theme storybook-inbox";
    host.setAttribute("aria-label", "Inbox");

    const pane = globalThis.document.createElement("div");
    pane.id = "inbox-pane";
    pane.innerHTML = render_inbox({
        INBOX_SEARCH_ID: "inbox-search",
        dms_dict: new Map([
            ["1", dm()],
            [
                "2,3,4",
                dm({
                    conversation_key: "2,3,4",
                    has_unread_mention: true,
                    is_group: true,
                    rendered_dm_with_html: "Research working group",
                    unread_count: 7,
                    user_circle_class: undefined,
                    user_ids_string: "2,3,4",
                }),
            ],
            [
                "5",
                dm({
                    conversation_key: "5",
                    is_bot: true,
                    rendered_dm_with_html: "Release bot",
                    unread_count: 0,
                    user_circle_class: undefined,
                    user_ids_string: "5",
                }),
            ],
        ]),
        folders_with_stream_rows: [
            {
                has_unread_mention: true,
                header_id: "inbox-folder-product",
                is_collapsed: false,
                is_header_visible: true,
                name: "Product",
                stream_rows: [
                    {
                        stream_key: "stream-design",
                        stream_row: stream(),
                        topic_rows: [
                            topic(),
                            topic({
                                conversation_key: "design:research",
                                topic_display_name: "Customer interview synthesis",
                                topic_name: "Customer interview synthesis",
                                unread_count: 2,
                                visibility_policy: policies.UNMUTED,
                            }),
                            topic({
                                conversation_key: "design:archive",
                                topic_display_name: "Design archive",
                                topic_name: "Design archive",
                                unread_count: 0,
                                visibility_policy: policies.INHERIT,
                            }),
                        ],
                    },
                    {
                        stream_key: "stream-engineering",
                        stream_row: stream({
                            stream_color: "#c17d11",
                            stream_id: 9,
                            stream_name: "engineering",
                            unread_count: 3,
                        }),
                        topic_rows: [
                            topic({
                                conversation_key: "engineering:release",
                                mention_in_unread: true,
                                stream_id: 9,
                                topic_display_name: "August release",
                                topic_name: "August release",
                                unread_count: 3,
                                visibility_policy: policies.MUTED,
                            }),
                        ],
                    },
                ],
                unread_count: 11,
            },
            {
                has_unread_mention: false,
                header_id: "inbox-folder-company",
                is_collapsed: false,
                is_header_visible: true,
                name: "Company",
                stream_rows: [
                    {
                        stream_key: "stream-announcements",
                        stream_row: stream({
                            stream_color: "#278642",
                            stream_id: 14,
                            stream_name: "announcements",
                            unread_count: 1,
                        }),
                        topic_rows: [
                            topic({
                                conversation_key: "announcements:planning",
                                stream_id: 14,
                                topic_display_name: "Quarterly planning",
                                topic_name: "Quarterly planning",
                                unread_count: 1,
                                visibility_policy: policies.FOLLOWED,
                            }),
                        ],
                    },
                ],
                unread_count: 1,
            },
        ],
        has_dms_post_filter: true,
        has_unread_mention: true,
        is_dms_collapsed: false,
        normal_view: true,
        search_val: "",
        show_channel_folder_toggle: true,
        unread_dms_count: 9,
    });

    const dropdownValue = pane.querySelector(".dropdown_widget_value");
    if (dropdownValue) {
        dropdownValue.textContent = "All conversations";
    }
    if (empty) {
        pane.querySelector("#inbox-list")?.remove();
        const emptyState = pane.querySelector<HTMLElement>("#inbox-empty-without-search");
        emptyState?.style.setProperty("display", "flex");
    }
    host.append(pane);

    function toggle_header(header: HTMLElement): void {
        const collapsed = header.classList.toggle("inbox-collapsed-state");
        header
            .querySelector<HTMLElement>(".cf-conversation-list__collapse")
            ?.setAttribute("aria-expanded", String(!collapsed));
    }

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const button = event.target.closest(".cf-conversation-list__collapse");
        const header = button?.closest<HTMLElement>(".inbox-header");
        if (header !== null && header !== undefined) {
            toggle_header(header);
        }
    });
    host.addEventListener("keydown", (event) => {
        if (!(event.target instanceof HTMLElement) || !event.target.matches(".inbox-header")) {
            return;
        }
        if (event.key !== "Enter" && event.key !== " ") {
            return;
        }
        event.preventDefault();
        toggle_header(event.target);
    });
    return host;
}

const meta = {
    title: "Cofounder/Conversation list/Inbox",
    render: () => render_scene(),
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const Default: Story = {};

export const Empty: Story = {
    render: () => render_scene({empty: true}),
};

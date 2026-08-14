import type {Meta, StoryObj} from "@storybook/html";

import render_empty from "../templates/recent_view_empty_list_widget_for_table.hbs";
import render_row from "../templates/recent_view_row.hbs";
import render_table_header from "../templates/recent_view_table.hbs";

const policies = {FOLLOWED: "FOLLOWED", MUTED: "MUTED", UNMUTED: "UNMUTED"};

function row(overrides: Record<string, unknown> = {}): string {
    return render_row({
        all_visibility_policies: policies,
        column_indexes: {mute: 2, read: 1, topic: 0},
        conversation_key: "design:homepage",
        full_last_msg_date_time: "Today at 10:45 AM",
        is_archived: false,
        is_empty_string_topic: false,
        is_private: false,
        last_msg_time: "10:45 AM",
        last_msg_url: "#message",
        mention_in_unread: false,
        other_sender_names_html: "Ava Rodriguez and Noah Williams",
        other_senders_count: 0,
        senders: [
            {
                avatar_url_small: "/static/images/jdenticon-1.png",
                full_name: "Ava Rodriguez",
                is_muted: false,
                user_id: 1,
            },
            {
                avatar_url_small: "/static/images/jdenticon-2.png",
                full_name: "Noah Williams",
                is_muted: false,
                user_id: 2,
            },
        ],
        stream_color: "#4f8394",
        stream_id: 7,
        stream_name: "design",
        topic: "Homepage redesign",
        topic_display_name: "Homepage redesign",
        topic_url: "#topic",
        unread_count: 4,
        visibility_policy: policies.FOLLOWED,
        ...overrides,
    });
}

function render_recent_view({empty = false, loading = false} = {}): HTMLElement {
    const host = globalThis.document.createElement("section");
    host.id = "recent_view";
    host.className = "cf-theme storybook-recent-view no-visible-focus-outlines";
    host.setAttribute("aria-label", "Recent conversations");

    const header = globalThis.document.createElement("div");
    header.className = "recent_view_container";
    const headerContent = globalThis.document.createElement("div");
    headerContent.id = "recent_view_table";
    headerContent.innerHTML = render_table_header({
        filter_participated: false,
        filter_pm: true,
        filter_unread: false,
        folder_filter_tooltip: "Filter by folder",
        is_spectator: false,
        search_val: "",
        show_folder_filter: true,
    });
    const dropdownValue = headerContent.querySelector(".dropdown_widget_value");
    if (dropdownValue) {
        dropdownValue.textContent = "All conversations";
    }
    header.append(headerContent);

    const table = globalThis.document.createElement("table");
    table.id = "recent-view-content-table";
    table.className = "cf-data-table cf-data-table--body";
    const body = globalThis.document.createElement("tbody");
    body.id = "recent-view-content-tbody";
    body.innerHTML = empty
        ? render_empty({
              column_count: 3,
              empty_list_message: "No conversations match your filters.",
              load_more_button_text: "Load more",
          })
        : [
              row(),
              row({
                  conversation_key: "engineering:release",
                  last_msg_time: "9:28 AM",
                  other_senders_count: 3,
                  stream_color: "#c17d11",
                  stream_id: 9,
                  stream_name: "engineering",
                  topic: "August release",
                  topic_display_name: "August release",
                  unread_count: 0,
                  visibility_policy: policies.UNMUTED,
              }),
              row({
                  conversation_key: "customers:research",
                  last_msg_time: "Yesterday",
                  senders: [
                      {
                          avatar_url_small: "/static/images/jdenticon-3.png",
                          full_name: "Priya Shah",
                          is_muted: false,
                          user_id: 3,
                      },
                  ],
                  stream_color: "#8f5cb4",
                  stream_id: 12,
                  stream_name: "customer research",
                  topic: "Onboarding interviews",
                  topic_display_name: "Onboarding interviews",
                  unread_count: 2,
                  visibility_policy: policies.MUTED,
              }),
              row({
                  conversation_key: "announcements:planning",
                  last_msg_time: "Mon",
                  stream_color: "#278642",
                  stream_id: 14,
                  stream_name: "announcements",
                  topic: "Quarterly planning",
                  topic_display_name: "Quarterly planning",
                  unread_count: 0,
                  visibility_policy: "INHERIT",
              }),
          ].join("");
    table.append(body);

    host.append(header, table);
    if (loading) {
        host.insertAdjacentHTML(
            "beforeend",
            '<div class="cf-load-more recent-view-load-more-container"><p class="cf-load-more__message">Showing messages since Monday.</p><button class="cf-button cf-button--secondary"><span class="cf-button__label">Load more</span></button></div>',
        );
    }
    return host;
}

const meta = {
    title: "Cofounder/Data table/Recent conversations",
    render: () => render_recent_view(),
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const Default: Story = {};

export const LoadingMore: Story = {
    render: () => render_recent_view({loading: true}),
};

export const Empty: Story = {
    render: () => render_recent_view({empty: true}),
};

import type {Meta, StoryObj} from "@storybook/html";

import render_icon from "../templates/cofounder/components/icon.hbs";
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
    host.className = "cf-theme storybook-recent-view";
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
    table.setAttribute("aria-label", "Recent conversations");
    table.innerHTML = `
        <thead class="cf-data-table__sr-only-head">
            <tr>
                <th>Channel and conversation</th>
                <th>Participants</th>
                <th>Time</th>
            </tr>
        </thead>`;
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

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-recent-view__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");

    const rows = [...body.querySelectorAll<HTMLTableRowElement>(".recent-view-body-row")];
    for (const [index, conversation_row] of rows.entries()) {
        conversation_row.dataset["participated"] = index === 0 || index === 2 ? "true" : "false";
        conversation_row.dataset["timeOrder"] = String(rows.length - index);
    }

    const filter_rows = (): void => {
        const search =
            headerContent
                .querySelector<HTMLInputElement>("#recent_view_search")
                ?.value.trim()
                .toLocaleLowerCase() ?? "";
        const unread_only =
            headerContent
                .querySelector<HTMLElement>('[data-filter="unread"]')
                ?.getAttribute("aria-checked") === "true";
        const participated_only =
            headerContent
                .querySelector<HTMLElement>('[data-filter="participated"]')
                ?.getAttribute("aria-checked") === "true";
        let visible_count = 0;
        for (const conversation_row of rows) {
            const unread_count = Number(
                conversation_row.querySelector<HTMLElement>(".unread_count")?.textContent ?? "0",
            );
            const matches_search =
                conversation_row.textContent?.toLocaleLowerCase().includes(search) ?? false;
            const matches =
                matches_search &&
                (!unread_only || unread_count > 0) &&
                (!participated_only || conversation_row.dataset["participated"] === "true");
            conversation_row.hidden = !matches;
            visible_count += Number(matches);
        }
        feedback.textContent = `${visible_count} conversation${visible_count === 1 ? "" : "s"} shown.`;
    };

    const sync_sort_state = (active: HTMLButtonElement): void => {
        const controls = [
            ...headerContent.querySelectorAll<HTMLButtonElement>(".cf-data-table__sort"),
        ];
        for (const control of controls) {
            control.classList.toggle("active", control === active);
            if (control !== active) {
                control.classList.remove("descend");
            }
            control.setAttribute("aria-pressed", String(control === active));
        }
        const semantic_headers = [...table.querySelectorAll("th")];
        for (const semantic_header of semantic_headers) {
            semantic_header.setAttribute("aria-sort", "none");
        }
        const semantic_header =
            active.dataset["sort"] === "numeric" ? semantic_headers[2] : semantic_headers[0];
        semantic_header?.setAttribute(
            "aria-sort",
            active.classList.contains("descend") ? "descending" : "ascending",
        );
    };

    const sort_rows = (control: HTMLButtonElement): void => {
        if (control.classList.contains("active")) {
            control.classList.toggle("descend");
        }
        sync_sort_state(control);
        const sort = control.dataset["sort"];
        const sorted = rows.toSorted((left, right) => {
            const value = (candidate: HTMLTableRowElement): string | number => {
                if (sort === "unread_sort") {
                    return Number(candidate.querySelector(".unread_count")?.textContent ?? "0");
                }
                if (sort === "numeric") {
                    return Number(candidate.dataset["timeOrder"] ?? "0");
                }
                const selector =
                    sort === "channel_sort"
                        ? ".recent-view-channel-name"
                        : ".recent-view-conversation-link";
                return candidate.querySelector(selector)?.textContent?.trim() ?? "";
            };
            return String(value(left)).localeCompare(String(value(right)), undefined, {
                numeric: true,
                sensitivity: "base",
            });
        });
        if (control.classList.contains("descend")) {
            sorted.reverse();
        }
        body.append(...sorted);
        const sort_label = (
            control.getAttribute("aria-label") ??
            control.textContent?.trim() ??
            "column"
        ).replace(/^sort by /i, "");
        feedback.textContent = `Sorted by ${sort_label.toLocaleLowerCase()}, ${
            control.classList.contains("descend") ? "descending" : "ascending"
        }.`;
    };

    const initial_sort = headerContent.querySelector<HTMLButtonElement>(
        ".recent-view-last-msg-time-sort",
    );
    if (initial_sort) {
        sync_sort_state(initial_sort);
    }

    headerContent.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const sort = event.target.closest<HTMLButtonElement>(".cf-data-table__sort");
        if (sort) {
            sort_rows(sort);
            return;
        }
        const filter = event.target.closest<HTMLElement>(".button-recent-filters");
        if (filter) {
            const selected = filter.getAttribute("aria-checked") === "true";
            filter.setAttribute("aria-checked", String(!selected));
            filter.classList.toggle("button-recent-selected", !selected);
            filter_rows();
            return;
        }
        if (event.target.closest(".input-close-filter-button")) {
            const search = headerContent.querySelector<HTMLInputElement>("#recent_view_search");
            if (search) {
                search.value = "";
                search.focus();
                filter_rows();
            }
        }
    });
    headerContent
        .querySelector<HTMLInputElement>("#recent_view_search")
        ?.addEventListener("input", filter_rows);

    body.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const conversation_row = event.target.closest<HTMLTableRowElement>(".recent-view-body-row");
        if (!conversation_row) {
            return;
        }
        const topic =
            conversation_row.querySelector(".recent-view-conversation-link")?.textContent?.trim() ??
            "conversation";
        const unread = event.target.closest<HTMLElement>(".on_hover_topic_read");
        if (unread) {
            unread.textContent = "0";
            unread.classList.add("unread_hidden");
            conversation_row.classList.remove("cf-data-table__row--unread", "unread_topic");
            filter_rows();
            feedback.textContent = `${topic} marked as read.`;
            conversation_row.focus();
            return;
        }
        if (event.target.closest(".recent-view-topic-visibility")) {
            feedback.textContent = `Opened topic actions for ${topic}.`;
            return;
        }
        event.preventDefault();
        feedback.textContent = `Opened ${topic}.`;
    });
    body.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") {
            return;
        }
        if (!(event.target instanceof HTMLElement)) {
            return;
        }
        const interactive = event.target.closest<HTMLElement>(
            ".recent-view-body-row, .on_hover_topic_read, .recent-view-topic-visibility",
        );
        if (!interactive) {
            return;
        }
        event.preventDefault();
        interactive.click();
    });

    host.append(header, table, feedback);
    if (loading) {
        host.insertAdjacentHTML(
            "beforeend",
            `<div class="cf-load-more recent-view-load-more-container" aria-label="Older conversations">
                <p class="cf-load-more__message last-fetched-message" role="status" aria-live="polite">Showing messages since Monday.</p>
                <button type="button" class="cf-button cf-button--secondary fetch-messages-button" aria-busy="false">
                    <span class="storybook-recent-view__load-spinner" hidden>${render_icon({compact: true, name: "loader-circle"})}</span>
                    <span class="cf-button__label button-label">Load more</span>
                </button>
            </div>`,
        );
        const load_more = host.querySelector<HTMLElement>(".recent-view-load-more-container");
        const load_button = load_more?.querySelector<HTMLButtonElement>(".fetch-messages-button");
        const load_message = load_more?.querySelector<HTMLElement>(".last-fetched-message");
        const load_label = load_button?.querySelector<HTMLElement>(".button-label");
        const load_spinner = load_button?.querySelector<HTMLElement>(
            ".storybook-recent-view__load-spinner",
        );
        load_button?.addEventListener("click", () => {
            if (load_button.getAttribute("aria-busy") === "true") {
                return;
            }
            load_button.disabled = true;
            load_button.setAttribute("aria-busy", "true");
            if (load_label) {
                load_label.textContent = "Loading older conversations…";
            }
            if (load_spinner) {
                load_spinner.hidden = false;
            }
            feedback.textContent = "Loading older conversations…";
            setTimeout(() => {
                body.insertAdjacentHTML(
                    "beforeend",
                    row({
                        conversation_key: "operations:retrospective",
                        last_msg_time: "Fri",
                        stream_color: "#8a6331",
                        stream_id: 18,
                        stream_name: "operations",
                        topic: "Launch retrospective",
                        topic_display_name: "Launch retrospective",
                        unread_count: 0,
                        visibility_policy: policies.UNMUTED,
                    }),
                );
                const loaded_row = body.lastElementChild;
                if (loaded_row instanceof HTMLTableRowElement) {
                    loaded_row.dataset["participated"] = "true";
                    loaded_row.dataset["timeOrder"] = "0";
                    rows.push(loaded_row);
                    loaded_row.focus();
                }
                if (load_message) {
                    load_message.textContent = "All available conversations are loaded.";
                }
                load_button.disabled = false;
                load_button.setAttribute("aria-busy", "false");
                if (load_label) {
                    load_label.textContent = "Load more";
                }
                if (load_spinner) {
                    load_spinner.hidden = true;
                }
                if (load_more) {
                    load_more.hidden = true;
                }
                feedback.textContent =
                    "1 older conversation loaded. All conversations are available.";
            }, 300);
        });
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

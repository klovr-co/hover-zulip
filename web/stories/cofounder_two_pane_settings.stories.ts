import type {Meta, StoryObj} from "@storybook/html";

import render_channel_row from "../templates/stream_settings/browse_streams_list_item.hbs";
import render_channels from "../templates/stream_settings/stream_settings_overlay.hbs";
import render_sort_label from "../templates/stream_settings/stream_sorter_toggle_label.hbs";
import render_group_row from "../templates/user_group_settings/browse_user_groups_list_item.hbs";
import render_group_title from "../templates/user_group_settings/selected_group_title.hbs";
import render_groups from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import {render_template_story} from "./template_story_utils.ts";

type Surface = "channels" | "groups";

type ChannelFixture = {
    color: string;
    name: string;
    rendered_description: string;
    stream_id: number;
    stream_weekly_traffic: number;
    subscriber_count: number;
    subscribed: boolean;
};

type GroupFixture = {
    description: string;
    id: number;
    is_member: boolean;
    is_system_group: boolean;
    member_count: number;
    name: string;
};

const channel_fixtures: ChannelFixture[] = [
    {
        color: "#0878e8",
        name: "Design",
        rendered_description: "Design reviews and product decisions",
        stream_id: 7,
        stream_weekly_traffic: 37,
        subscriber_count: 24,
        subscribed: true,
    },
    {
        color: "#278642",
        name: "Product",
        rendered_description: "Roadmap, research, and launch planning",
        stream_id: 8,
        stream_weekly_traffic: 64,
        subscriber_count: 41,
        subscribed: true,
    },
    {
        color: "#9a6500",
        name: "Customer feedback",
        rendered_description: "Patterns gathered from customer conversations",
        stream_id: 9,
        stream_weekly_traffic: 18,
        subscriber_count: 18,
        subscribed: false,
    },
];

const group_fixtures: GroupFixture[] = [
    {
        description: "Product design team",
        id: 3,
        is_member: true,
        is_system_group: false,
        member_count: 12,
        name: "Design",
    },
    {
        description: "Research planning and synthesis",
        id: 4,
        is_member: false,
        is_system_group: false,
        member_count: 8,
        name: "Research",
    },
    {
        description: "Organization administrators",
        id: 5,
        is_member: true,
        is_system_group: true,
        member_count: 4,
        name: "Admins",
    },
];

function render_channel_fixture(channel: ChannelFixture): string {
    return render_channel_row({
        ...channel,
        can_access_subscribers: true,
        is_old_stream: true,
        should_display_subscription_button: true,
    });
}

function populate_channel_rows(host: HTMLElement, channels: ChannelFixture[]): void {
    const list = host.querySelector<HTMLElement>(".streams-list");
    if (!list) {
        return;
    }
    list.innerHTML = channels.map((channel) => render_channel_fixture(channel)).join("");
}

function render_group_fixture(group: GroupFixture): string {
    return render_group_row({
        ...group,
        can_join: true,
        can_leave: true,
        is_direct_member: true,
    });
}

function populate_group_rows(host: HTMLElement, groups: GroupFixture[]): void {
    const list = host.querySelector<HTMLElement>(".user-groups-list");
    if (!list) {
        return;
    }
    list.innerHTML = groups.map((group) => render_group_fixture(group)).join("");
}

function populate_channel_sorter(host: HTMLElement): void {
    const container = host.querySelector<HTMLElement>(".list-toggler-container");
    if (!container) {
        return;
    }
    const options = [
        {icon: "sort-ascending", key: "name", label: "Sort by name"},
        {icon: "users", key: "subscribers", label: "Sort by number of subscribers"},
        {icon: "activity", key: "traffic", label: "Sort by estimated weekly traffic"},
    ];
    container.innerHTML = `<div class="cf-tabs stream_sorter_toggle" role="tablist">${options
        .map(
            (option, index) =>
                `<button type="button" class="cf-tabs__tab${index === 0 ? " cf-tabs__tab--selected" : ""}" role="tab" data-sort-key="${option.key}" aria-label="${option.label}" aria-selected="${index === 0}" tabindex="${index === 0 ? "0" : "-1"}">${render_sort_label({icon: option.icon, tooltip: option.label})}</button>`,
        )
        .join("")}</div>`;
}

function populate_group_title(host: HTMLElement, group: GroupFixture): void {
    const title = host.querySelector<HTMLElement>(".user-group-info-title");
    if (!title) {
        return;
    }
    title.innerHTML = render_group_title({
        group_id: group.id,
        group_name: group.name,
        is_direct_member: group.is_member,
        is_system_group: group.is_system_group,
    });
    title
        .querySelector<HTMLElement>(".deactivated-user-group-icon")
        ?.style.setProperty("display", "none");
    title
        .querySelector<HTMLElement>(".reactivate-group-button")
        ?.style.setProperty("display", "none");
}

type SummaryFact = {
    label: string;
    value: string;
};

function render_detail_summary(
    detail: HTMLElement,
    heading_id: string,
    heading_text: string,
    description: string,
    facts: SummaryFact[],
    announcement: string,
): void {
    const document = detail.ownerDocument;
    const summary = document.createElement("section");
    summary.className = "storybook-two-pane-settings__summary";
    summary.setAttribute("aria-labelledby", heading_id);

    const heading = document.createElement("h2");
    heading.id = heading_id;
    heading.textContent = heading_text;

    const description_element = document.createElement("p");
    description_element.className = "storybook-two-pane-settings__description";
    description_element.textContent = description;

    const facts_list = document.createElement("dl");
    facts_list.className = "storybook-two-pane-settings__facts";
    for (const fact of facts) {
        const fact_element = document.createElement("div");
        const label = document.createElement("dt");
        label.textContent = fact.label;
        const value = document.createElement("dd");
        value.textContent = fact.value;
        fact_element.append(label, value);
        facts_list.append(fact_element);
    }

    const feedback = document.createElement("p");
    feedback.className = "storybook-two-pane-settings__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    feedback.textContent = announcement;

    summary.append(heading, description_element, facts_list, feedback);
    detail.replaceChildren(summary);
}

function setup_channel_scene(
    host: HTMLElement,
    channels: ChannelFixture[],
    mobile_detail: boolean,
): void {
    const list = host.querySelector<HTMLElement>(".streams-list");
    const detail = host.querySelector<HTMLElement>("#stream_settings");
    const empty = host.querySelector<HTMLElement>(".cf-two-pane-shell__empty");
    const pane_title = host.querySelector<HTMLElement>(".cf-two-pane-shell__pane-title");
    const detail_pane = host.querySelector<HTMLElement>(".cf-two-pane-shell__pane--detail");
    const shell_header = host.querySelector<HTMLElement>(".cf-two-pane-shell__header");
    if (
        list === null ||
        detail === null ||
        empty === null ||
        pane_title === null ||
        detail_pane === null ||
        shell_header === null
    ) {
        return;
    }

    let selected_stream_id = 7;
    const no_results = host.querySelector<HTMLElement>(".no-streams-to-show");
    const empty_states = no_results?.children ?? [];
    for (const state of empty_states) {
        if (state instanceof HTMLElement) {
            state.hidden = !state.classList.contains("no_stream_match_filter_empty_text");
        }
    }

    const uses_mobile_panes = (): boolean =>
        mobile_detail || globalThis.matchMedia("(width < 700px)").matches;

    const render_detail = (channel: ChannelFixture, announcement = ""): void => {
        pane_title.textContent = channel.name;
        empty.hidden = true;
        detail.hidden = false;
        render_detail_summary(
            detail,
            `storybook-channel-heading-${channel.stream_id}`,
            channel.name,
            channel.rendered_description,
            [
                {label: "Subscribers", value: String(channel.subscriber_count)},
                {label: "Weekly activity", value: `${channel.stream_weekly_traffic} messages`},
                {label: "Membership", value: channel.subscribed ? "Subscribed" : "Not subscribed"},
            ],
            announcement,
        );
    };

    const select_channel = (
        row: HTMLElement,
        move_focus = false,
        announcement?: string,
        reveal_detail = true,
    ): void => {
        const stream_id = Number(row.dataset["streamId"]);
        const channel = channels.find((candidate) => candidate.stream_id === stream_id);
        if (channel === undefined) {
            return;
        }
        selected_stream_id = stream_id;
        for (const candidate of list.querySelectorAll<HTMLElement>(".stream-row")) {
            const selected = candidate === row;
            candidate.classList.toggle("active", selected);
            const row_control = candidate.querySelector<HTMLElement>(
                ".cf-two-pane-shell__row-main",
            );
            row_control?.setAttribute("aria-current", String(selected));
        }
        render_detail(channel, announcement ?? `${channel.name} settings selected.`);
        if (reveal_detail && uses_mobile_panes()) {
            detail_pane.classList.add("show");
            shell_header.classList.add("slide-left");
        }
        if (move_focus) {
            row.querySelector<HTMLElement>(".cf-two-pane-shell__row-main")?.focus();
        }
    };

    const replace_channel_row = (row: HTMLElement, channel: ChannelFixture): HTMLElement => {
        const holder = globalThis.document.createElement("div");
        holder.innerHTML = render_channel_fixture(channel);
        const replacement = holder.firstElementChild;
        if (!(replacement instanceof HTMLElement)) {
            return row;
        }
        row.replaceWith(replacement);
        return replacement;
    };

    const apply_sort = (tab: HTMLButtonElement, move_focus = false): void => {
        const key = tab.dataset["sortKey"];
        if (key !== "name" && key !== "subscribers" && key !== "traffic") {
            return;
        }
        for (const candidate of host.querySelectorAll<HTMLButtonElement>(
            ":scope .stream_sorter_toggle .cf-tabs__tab",
        )) {
            const selected = candidate === tab;
            candidate.classList.toggle("cf-tabs__tab--selected", selected);
            candidate.setAttribute("aria-selected", String(selected));
            candidate.tabIndex = selected ? 0 : -1;
        }
        channels.sort((first, second) => {
            if (key === "name") {
                return first.name.localeCompare(second.name);
            }
            return key === "subscribers"
                ? second.subscriber_count - first.subscriber_count
                : second.stream_weekly_traffic - first.stream_weekly_traffic;
        });
        populate_channel_rows(host, channels);
        const selected_row = list.querySelector<HTMLElement>(
            `.stream-row[data-stream-id="${CSS.escape(String(selected_stream_id))}"]`,
        );
        if (selected_row !== null) {
            select_channel(
                selected_row,
                false,
                `${tab.getAttribute("aria-label")} applied.`,
                false,
            );
        }
        if (move_focus) {
            tab.focus();
        }
    };

    const filter_rows = (query: string): void => {
        let visible_count = 0;
        for (const row of list.querySelectorAll<HTMLElement>(".stream-row")) {
            const visible = (row.dataset["streamName"] ?? "")
                .toLocaleLowerCase()
                .includes(query.trim().toLocaleLowerCase());
            row.hidden = !visible;
            visible_count += Number(visible);
        }
        if (no_results !== null) {
            no_results.hidden = visible_count !== 0;
        }
        list.hidden = visible_count === 0;
        const feedback = detail.querySelector<HTMLElement>(
            ".storybook-two-pane-settings__feedback",
        );
        if (feedback !== null) {
            feedback.textContent = `${visible_count} channel${visible_count === 1 ? "" : "s"} shown.`;
        }
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const back = event.target.closest<HTMLButtonElement>(".cf-two-pane-shell__back");
        if (back !== null) {
            detail_pane.classList.remove("show");
            shell_header.classList.remove("slide-left");
            list.querySelector<HTMLElement>(
                ":scope > .stream-row.active .cf-two-pane-shell__row-main",
            )?.focus();
            return;
        }
        const launcher = event.target.closest<HTMLButtonElement>("[data-storybook-open-channels]");
        if (launcher !== null) {
            launcher.remove();
            const overlay = host.querySelector<HTMLElement>(".two-pane-settings-overlay");
            if (overlay !== null) {
                overlay.hidden = false;
                list.querySelector<HTMLElement>(
                    ":scope > .stream-row.active .cf-two-pane-shell__row-main",
                )?.focus();
            }
            return;
        }
        const close = event.target.closest<HTMLButtonElement>(".cf-two-pane-shell__close");
        if (close !== null) {
            const overlay = host.querySelector<HTMLElement>(".two-pane-settings-overlay");
            if (overlay !== null) {
                overlay.hidden = true;
                const open = globalThis.document.createElement("button");
                open.type = "button";
                open.className = "cf-button cf-button--primary storybook-two-pane-settings__open";
                open.dataset["storybookOpenChannels"] = "";
                open.textContent = "Open channel settings";
                host.prepend(open);
                open.focus();
            }
            return;
        }
        const tab = event.target.closest<HTMLButtonElement>(".stream_sorter_toggle .cf-tabs__tab");
        if (tab !== null) {
            apply_sort(tab);
            return;
        }
        const membership = event.target.closest<HTMLButtonElement>(
            ".cf-two-pane-shell__membership-action",
        );
        if (membership !== null) {
            const row = membership.closest<HTMLElement>(".stream-row");
            const channel = channels.find(
                (candidate) => candidate.stream_id === Number(row?.dataset["streamId"]),
            );
            if (row === null || channel === undefined) {
                return;
            }
            channel.subscribed = !channel.subscribed;
            const replacement = replace_channel_row(row, channel);
            select_channel(
                replacement,
                false,
                `${channel.subscribed ? "Subscribed to" : "Unsubscribed from"} ${channel.name}.`,
                false,
            );
            replacement
                .querySelector<HTMLButtonElement>(".cf-two-pane-shell__membership-action")
                ?.focus();
            return;
        }
        const row_main = event.target.closest<HTMLElement>(".cf-two-pane-shell__row-main");
        const row = row_main?.closest<HTMLElement>(".stream-row");
        if (row_main !== null && row_main !== undefined && row !== null && row !== undefined) {
            select_channel(row);
            return;
        }
        if (event.target.closest(".create_stream_button") !== null) {
            const feedback = detail.querySelector<HTMLElement>(
                ".storybook-two-pane-settings__feedback",
            );
            if (feedback !== null) {
                feedback.textContent = "Create channel requested.";
            }
            return;
        }
        if (event.target.closest("#clear_search_stream_name") !== null) {
            const input = host.querySelector<HTMLInputElement>("#search_stream_name");
            if (input !== null) {
                input.value = "";
                filter_rows("");
                input.focus();
            }
        }
    });

    host.addEventListener("input", (event) => {
        if (event.target instanceof HTMLInputElement && event.target.id === "search_stream_name") {
            filter_rows(event.target.value);
        }
    });

    host.addEventListener("keydown", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const row_main = event.target.closest<HTMLElement>(".cf-two-pane-shell__row-main");
        if (row_main !== null && (event.key === "Enter" || event.key === " ")) {
            event.preventDefault();
            row_main.click();
            return;
        }
        const tab = event.target.closest<HTMLButtonElement>(".stream_sorter_toggle .cf-tabs__tab");
        if (tab !== null && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
            const tabs = [
                ...host.querySelectorAll<HTMLButtonElement>(
                    ":scope .stream_sorter_toggle .cf-tabs__tab",
                ),
            ];
            const offset = event.key === "ArrowRight" ? 1 : -1;
            const next = tabs[(tabs.indexOf(tab) + offset + tabs.length) % tabs.length];
            if (next !== undefined) {
                event.preventDefault();
                apply_sort(next, true);
            }
        }
    });

    const first_row =
        list.querySelector<HTMLElement>(
            `.stream-row[data-stream-id="${CSS.escape(String(selected_stream_id))}"]`,
        ) ?? list.querySelector<HTMLElement>(".stream-row");
    if (first_row !== null) {
        select_channel(first_row, false, "", false);
    }
}

function setup_group_scene(
    host: HTMLElement,
    groups: GroupFixture[],
    mobile_detail: boolean,
): void {
    const list = host.querySelector<HTMLElement>(".user-groups-list");
    const detail = host.querySelector<HTMLElement>("#user_group_settings");
    const empty = host.querySelector<HTMLElement>(".cf-two-pane-shell__empty");
    const detail_pane = host.querySelector<HTMLElement>(".cf-two-pane-shell__pane--detail");
    const shell_header = host.querySelector<HTMLElement>(".cf-two-pane-shell__header");
    const no_results = host.querySelector<HTMLElement>(".no-groups-to-show");
    if (
        list === null ||
        detail === null ||
        empty === null ||
        detail_pane === null ||
        shell_header === null ||
        no_results === null
    ) {
        return;
    }

    no_results.textContent = "No user groups match your filter.";
    no_results.setAttribute("role", "status");
    no_results.hidden = true;
    let selected_group_id = 3;
    const uses_mobile_panes = (): boolean =>
        mobile_detail || globalThis.matchMedia("(width < 700px)").matches;

    const render_detail = (group: GroupFixture, announcement = ""): void => {
        populate_group_title(host, group);
        empty.hidden = true;
        detail.hidden = false;
        render_detail_summary(
            detail,
            `storybook-group-heading-${group.id}`,
            group.name,
            group.description,
            [
                {label: "Members", value: String(group.member_count)},
                {
                    label: "Membership",
                    value: group.is_system_group
                        ? "System managed"
                        : group.is_member
                          ? "Joined"
                          : "Not joined",
                },
                {
                    label: "Group type",
                    value: group.is_system_group ? "System group" : "Custom group",
                },
            ],
            announcement,
        );
    };

    const select_group = (
        row: HTMLElement,
        move_focus = false,
        announcement?: string,
        reveal_detail = true,
    ): void => {
        const group = groups.find((candidate) => candidate.id === Number(row.dataset["groupId"]));
        if (group === undefined) {
            return;
        }
        selected_group_id = group.id;
        for (const candidate of list.querySelectorAll<HTMLElement>(".group-row")) {
            const selected = candidate === row;
            candidate.classList.toggle("active", selected);
            candidate
                .querySelector<HTMLElement>(".cf-two-pane-shell__row-main")
                ?.setAttribute("aria-current", String(selected));
        }
        render_detail(group, announcement ?? `${group.name} settings selected.`);
        if (reveal_detail && uses_mobile_panes()) {
            detail_pane.classList.add("show");
            shell_header.classList.add("slide-left");
        }
        if (move_focus) {
            row.querySelector<HTMLElement>(".cf-two-pane-shell__row-main")?.focus();
        }
    };

    const replace_group_row = (row: HTMLElement, group: GroupFixture): HTMLElement => {
        const holder = globalThis.document.createElement("div");
        holder.innerHTML = render_group_fixture(group);
        const replacement = holder.firstElementChild;
        if (!(replacement instanceof HTMLElement)) {
            return row;
        }
        row.replaceWith(replacement);
        return replacement;
    };

    const toggle_membership = (group: GroupFixture, row: HTMLElement): void => {
        group.is_member = !group.is_member;
        const replacement = replace_group_row(row, group);
        select_group(
            replacement,
            false,
            `${group.is_member ? "Joined" : "Left"} ${group.name}.`,
            false,
        );
    };

    const filter_rows = (query: string): void => {
        let visible_count = 0;
        for (const row of list.querySelectorAll<HTMLElement>(".group-row")) {
            const visible = (row.dataset["groupName"] ?? "")
                .toLocaleLowerCase()
                .includes(query.trim().toLocaleLowerCase());
            row.hidden = !visible;
            visible_count += Number(visible);
        }
        no_results.hidden = visible_count !== 0;
        list.parentElement?.toggleAttribute("hidden", visible_count === 0);
        const feedback = detail.querySelector<HTMLElement>(
            ".storybook-two-pane-settings__feedback",
        );
        if (feedback !== null) {
            feedback.textContent = `${visible_count} user group${visible_count === 1 ? "" : "s"} shown.`;
        }
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const back = event.target.closest<HTMLButtonElement>(".cf-two-pane-shell__back");
        if (back !== null) {
            detail_pane.classList.remove("show");
            shell_header.classList.remove("slide-left");
            list.querySelector<HTMLElement>(
                ":scope > .group-row.active .cf-two-pane-shell__row-main",
            )?.focus();
            return;
        }
        const launcher = event.target.closest<HTMLButtonElement>("[data-storybook-open-groups]");
        if (launcher !== null) {
            launcher.remove();
            const overlay = host.querySelector<HTMLElement>(".two-pane-settings-overlay");
            if (overlay !== null) {
                overlay.hidden = false;
                list.querySelector<HTMLElement>(
                    ":scope > .group-row.active .cf-two-pane-shell__row-main",
                )?.focus();
            }
            return;
        }
        if (event.target.closest(".cf-two-pane-shell__close") !== null) {
            const overlay = host.querySelector<HTMLElement>(".two-pane-settings-overlay");
            if (overlay !== null) {
                overlay.hidden = true;
                const open = globalThis.document.createElement("button");
                open.type = "button";
                open.className = "cf-button cf-button--primary storybook-two-pane-settings__open";
                open.dataset["storybookOpenGroups"] = "";
                open.textContent = "Open user group settings";
                host.prepend(open);
                open.focus();
            }
            return;
        }
        const row_membership = event.target.closest<HTMLButtonElement>(
            ".group-row .cf-two-pane-shell__membership-action",
        );
        if (row_membership !== null) {
            const row = row_membership.closest<HTMLElement>(".group-row");
            const group = groups.find(
                (candidate) => candidate.id === Number(row?.dataset["groupId"]),
            );
            if (row !== null && group !== undefined) {
                toggle_membership(group, row);
                list.querySelector<HTMLButtonElement>(
                    `.group-row[data-group-id="${CSS.escape(String(group.id))}"] .cf-two-pane-shell__membership-action`,
                )?.focus();
            }
            return;
        }
        const title_membership = event.target.closest<HTMLButtonElement>(
            ".selected-group-buttons .join_leave_button",
        );
        if (title_membership !== null) {
            const row = list.querySelector<HTMLElement>(
                `.group-row[data-group-id="${CSS.escape(String(selected_group_id))}"]`,
            );
            const group = groups.find((candidate) => candidate.id === selected_group_id);
            if (row !== null && group !== undefined) {
                toggle_membership(group, row);
                host.querySelector<HTMLButtonElement>(
                    ":scope .selected-group-buttons .join_leave_button",
                )?.focus();
            }
            return;
        }
        const row_main = event.target.closest<HTMLElement>(".cf-two-pane-shell__row-main");
        const row = row_main?.closest<HTMLElement>(".group-row");
        if (row_main !== null && row_main !== undefined && row !== null && row !== undefined) {
            select_group(row);
            return;
        }
        if (event.target.closest(".open-group-info-button") !== null) {
            const feedback = detail.querySelector<HTMLElement>(
                ".storybook-two-pane-settings__feedback",
            );
            if (feedback !== null) {
                feedback.textContent = "Change group information requested.";
            }
            return;
        }
        if (event.target.closest(".deactivate-group-button") !== null) {
            const feedback = detail.querySelector<HTMLElement>(
                ".storybook-two-pane-settings__feedback",
            );
            if (feedback !== null) {
                feedback.textContent = "Deactivate group requested.";
            }
            return;
        }
        if (event.target.closest(".create_user_group_button") !== null) {
            const feedback = detail.querySelector<HTMLElement>(
                ".storybook-two-pane-settings__feedback",
            );
            if (feedback !== null) {
                feedback.textContent = "Create user group requested.";
            }
            return;
        }
        if (event.target.closest("#clear_search_group_name") !== null) {
            const input = host.querySelector<HTMLInputElement>("#search_group_name");
            if (input !== null) {
                input.value = "";
                filter_rows("");
                input.focus();
            }
        }
    });

    host.addEventListener("input", (event) => {
        if (event.target instanceof HTMLInputElement && event.target.id === "search_group_name") {
            filter_rows(event.target.value);
        }
    });

    host.addEventListener("keydown", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const row_main = event.target.closest<HTMLElement>(".cf-two-pane-shell__row-main");
        if (row_main !== null && (event.key === "Enter" || event.key === " ")) {
            event.preventDefault();
            row_main.click();
        }
    });

    const first_row = list.querySelector<HTMLElement>(
        `.group-row[data-group-id="${CSS.escape(String(selected_group_id))}"]`,
    );
    if (first_row !== null) {
        select_group(first_row, false, "", false);
    }
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
    const scene_channels = structuredClone(channel_fixtures);

    if (surface === "channels") {
        scene_channels.sort((first, second) => first.name.localeCompare(second.name));
        populate_channel_rows(host, scene_channels);
        populate_channel_sorter(host);
        const value = host.querySelector(
            ":scope #stream_settings_filter_widget .dropdown_widget_value",
        );
        value?.append("Active");
        setup_channel_scene(host, scene_channels, mobileDetail);
    } else {
        const scene_groups = structuredClone(group_fixtures);
        populate_group_rows(host, scene_groups);
        const value = host.querySelector(
            ":scope #user_group_visibility_settings_widget .dropdown_widget_value",
        );
        value?.append("All groups");
        setup_group_scene(host, scene_groups, mobileDetail);
    }

    host.querySelectorAll<HTMLElement>(
        ":scope .no-streams-to-show, :scope .no-groups-to-show",
    ).forEach((element) => {
        element.hidden = true;
    });

    if (mobileDetail) {
        host.querySelector(":scope .cf-two-pane-shell__pane--detail")?.classList.add("show");
        host.querySelector(":scope .cf-two-pane-shell__header")?.classList.add("slide-left");
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

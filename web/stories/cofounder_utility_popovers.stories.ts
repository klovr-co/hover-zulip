import type {Meta, StoryObj} from "@storybook/html";

import render_message_actions from "../templates/popovers/message_actions_popover.hbs";
import render_send_later from "../templates/popovers/send_later_popover.hbs";
import render_user_group from "../templates/popovers/user_group_info_popover.hbs";

import {render_template_story} from "./template_story_utils.ts";

const meta = {
    title: "Cofounder/Utility Popovers",
    parameters: {layout: "fullscreen"},
} satisfies Meta;

export default meta;
type Story = StoryObj;

function frame(host: HTMLElement, custom_class?: string): HTMLElement {
    host.classList.add("cf-theme", "storybook-utility-popover");
    if (custom_class !== undefined) {
        host.classList.add(custom_class);
    }
    return host;
}

function setup_message_actions_scene(host: HTMLElement): void {
    const menu = host.querySelector<HTMLElement>('[role="menu"]');
    if (menu === null) {
        return;
    }

    const items = [...menu.querySelectorAll<HTMLElement>('[role="menuitem"]')];
    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-message-actions__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    host.append(feedback);

    function focus_item(index: number): void {
        for (const [item_index, item] of items.entries()) {
            item.tabIndex = item_index === index ? 0 : -1;
        }
        items[index]?.focus();
    }

    for (const [index, item] of items.entries()) {
        item.tabIndex = index === 0 ? 0 : -1;
    }

    menu.addEventListener("keydown", (event) => {
        const active_element = globalThis.document.activeElement;
        const current_index =
            active_element instanceof HTMLElement ? items.indexOf(active_element) : -1;
        if (current_index === -1) {
            return;
        }

        let next_index: number | undefined;
        switch (event.key) {
            case "ArrowDown":
                next_index = Math.min(current_index + 1, items.length - 1);
                break;
            case "ArrowUp":
                next_index = Math.max(current_index - 1, 0);
                break;
            case "Home":
                next_index = 0;
                break;
            case "End":
                next_index = items.length - 1;
                break;
            case "Enter":
            case " ":
                event.preventDefault();
                items[current_index]?.click();
                return;
        }

        if (next_index !== undefined) {
            event.preventDefault();
            focus_item(next_index);
        }
    });

    menu.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const item = target.closest<HTMLElement>('[role="menuitem"]');
        if (item === null || !menu.contains(item)) {
            return;
        }

        event.preventDefault();
        const index = items.indexOf(item);
        if (index !== -1) {
            focus_item(index);
        }
        const label = item.querySelector(".cf-menu__label")?.textContent?.trim() ?? "Action";
        feedback.textContent = `${label} requested for message 42.`;
    });
}

function setup_send_later_scene(host: HTMLElement): void {
    const menu = host.querySelector<HTMLElement>('[role="menu"]');
    if (menu === null) {
        return;
    }

    const items = [
        ...menu.querySelectorAll<HTMLElement>('[role="menuitemradio"], [role="menuitem"]'),
    ];
    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-send-later__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    host.append(feedback);

    function visible_items(): HTMLElement[] {
        return items.filter((item) => item.getClientRects().length > 0);
    }

    function focus_item(next_item: HTMLElement): void {
        for (const item of items) {
            item.tabIndex = item === next_item ? 0 : -1;
        }
        next_item.focus();
    }

    for (const [index, item] of items.entries()) {
        item.tabIndex = index === 0 ? 0 : -1;
    }

    menu.addEventListener("keydown", (event) => {
        const active_element = globalThis.document.activeElement;
        const navigable_items = visible_items();
        const current_index =
            active_element instanceof HTMLElement ? navigable_items.indexOf(active_element) : -1;
        if (current_index === -1) {
            return;
        }

        let next_index: number | undefined;
        switch (event.key) {
            case "ArrowDown":
                next_index = Math.min(current_index + 1, navigable_items.length - 1);
                break;
            case "ArrowUp":
                next_index = Math.max(current_index - 1, 0);
                break;
            case "Home":
                next_index = 0;
                break;
            case "End":
                next_index = navigable_items.length - 1;
                break;
            case "Enter":
            case " ":
                event.preventDefault();
                navigable_items[current_index]?.click();
                return;
        }

        if (next_index !== undefined) {
            event.preventDefault();
            const next_item = navigable_items[next_index];
            if (next_item !== undefined) {
                focus_item(next_item);
            }
        }
    });

    menu.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const item = target.closest<HTMLElement>('[role="menuitemradio"], [role="menuitem"]');
        if (item === null || !menu.contains(item)) {
            return;
        }

        event.preventDefault();
        focus_item(item);
        const radio = item.querySelector<HTMLInputElement>('input[type="radio"]');
        if (radio !== null) {
            for (const choice of menu.querySelectorAll<HTMLElement>('[role="menuitemradio"]')) {
                const choice_radio = choice.querySelector<HTMLInputElement>('input[type="radio"]');
                const selected = choice_radio === radio;
                choice.setAttribute("aria-checked", String(selected));
                if (choice_radio !== null) {
                    choice_radio.checked = selected;
                }
            }
            feedback.textContent =
                radio.value === "true"
                    ? "Enter now sends messages."
                    : "Ctrl+Enter now sends messages.";
            return;
        }

        const label = item.querySelector(".cf-menu__label")?.textContent?.trim() ?? "Action";
        feedback.textContent = `${label} requested.`;
    });
}

function setup_user_group_scene(host: HTMLElement): void {
    const member_count = host.querySelector<HTMLElement>(".group-member-count");
    if (member_count !== null) {
        member_count.textContent = "8 members";
    }

    const menu = host.querySelector<HTMLElement>('[role="menu"]');
    if (menu === null) {
        return;
    }

    const items = [...menu.querySelectorAll<HTMLElement>('[role="menuitem"]')];
    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-user-group__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    host.append(feedback);

    function focus_item(index: number): void {
        for (const [item_index, item] of items.entries()) {
            item.tabIndex = item_index === index ? 0 : -1;
        }
        items[index]?.focus();
    }

    for (const [index, item] of items.entries()) {
        item.tabIndex = index === 0 ? 0 : -1;
    }

    menu.addEventListener("keydown", (event) => {
        const active_element = globalThis.document.activeElement;
        const current_index =
            active_element instanceof HTMLElement ? items.indexOf(active_element) : -1;
        if (current_index === -1) {
            return;
        }

        let next_index: number | undefined;
        switch (event.key) {
            case "ArrowDown":
                next_index = Math.min(current_index + 1, items.length - 1);
                break;
            case "ArrowUp":
                next_index = Math.max(current_index - 1, 0);
                break;
            case "Home":
                next_index = 0;
                break;
            case "End":
                next_index = items.length - 1;
                break;
            case "Enter":
            case " ":
                event.preventDefault();
                items[current_index]?.click();
                return;
        }

        if (next_index !== undefined) {
            event.preventDefault();
            focus_item(next_index);
        }
    });

    menu.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const item = target.closest<HTMLElement>('[role="menuitem"]');
        if (item === null || !menu.contains(item)) {
            return;
        }

        event.preventDefault();
        const index = items.indexOf(item);
        if (index !== -1) {
            focus_item(index);
        }
        const label = item.querySelector(".cf-menu__label")?.textContent?.trim() ?? "Action";
        feedback.textContent = `${label} requested for Product design.`;
    });
}

export const MessageActions: Story = {
    render() {
        const host = frame(
            render_template_story("popovers/message_actions_popover.hbs", render_message_actions, {
                conversation_time_url: "#narrow/channel/7-design/topic/Homepage-redesign/near/42",
                editability_menu_item: "Edit message",
                message_id: 42,
                move_message_menu_item: "Move message",
                should_display_add_reaction_option: true,
                should_display_collapse: true,
                should_display_delete_option: true,
                should_display_mark_as_unread: true,
                should_display_message_report_option: true,
                should_display_quote_message: true,
                should_display_read_receipts_option: true,
                should_display_remind_me_option: true,
                should_display_uncollapse: false,
                view_source_menu_item: false,
            }),
            "storybook-message-actions",
        );
        setup_message_actions_scene(host);
        return host;
    },
};

export const SendLater: Story = {
    render() {
        const host = frame(
            render_template_story("popovers/send_later_popover.hbs", render_send_later, {
                enter_sends_true: true,
                formatted_send_later_time: "Tomorrow at 9:00 AM",
                show_compose_new_message: true,
            }),
            "storybook-send-later",
        );
        setup_send_later_scene(host);
        return host;
    },
};

export const UserGroup: Story = {
    render() {
        const host = frame(
            render_template_story("popovers/user_group_info_popover.hbs", render_user_group, {
                deactivated: false,
                display_all_subgroups_and_members: false,
                displayed_members: [
                    {
                        full_name: "Ava Rodriguez",
                        is_bot: false,
                        user_circle_class: "user_circle_green",
                        user_id: 7,
                        user_last_seen_time_status: "Active now",
                    },
                    {full_name: "Design review bot", is_bot: true},
                ],
                displayed_subgroups: [{name: "Design systems"}],
                group_description: "People shaping the Cofounder product experience.",
                group_edit_url: "#groups/3/Product-design/general",
                group_members_url: "#groups/3/Product-design/members",
                group_name: "Product design",
                has_bots: false,
                is_guest: false,
                is_system_group: false,
                members_count: 8,
                user_can_access_all_other_users: true,
            }),
            "storybook-user-group",
        );
        setup_user_group_scene(host);
        return host;
    },
};

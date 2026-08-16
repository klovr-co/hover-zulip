import type {Meta, StoryObj} from "@storybook/html";

import render_tabs from "../templates/cofounder/components/tabs.hbs";
import render_user_card from "../templates/popovers/user_card/user_card_popover.hbs";
import render_user_profile from "../templates/user_profile_modal.hbs";

import {render_template_story} from "./template_story_utils.ts";

const avatar = "/static/images/test-images/avatars/example_profile_picture.png";

const user = {
    can_manage_profile: true,
    can_manage_user: true,
    can_mute: true,
    can_send_private_message: true,
    can_unmute: false,
    date_joined: "August 8, 2026",
    display_profile_fields: [
        {
            id: 1,
            is_external_account: false,
            is_link: false,
            is_long_text: false,
            name: "Role",
            rendered_value: false,
            type: 1,
            value: "Product designer",
        },
        {
            id: 2,
            is_external_account: false,
            is_link: true,
            is_long_text: false,
            name: "Portfolio",
            rendered_value: false,
            type: 1,
            value: "https://example.com/ava",
        },
    ],
    email: "ava@example.com",
    full_name: "Ava Rodriguez",
    has_message_context: true,
    is_active: true,
    is_bot: false,
    is_imported_stub: false,
    is_me: false,
    is_sender_popover: true,
    last_seen: "Active now",
    pm_with_url: "#narrow/dm/7",
    private_message_class: "send_private_message",
    profile_data: [
        {
            id: 1,
            is_external_account: false,
            is_link: false,
            is_user_field: false,
            name: "Team",
            rendered_value: false,
            type: 1,
            value: "Product design",
        },
        {
            id: 2,
            is_external_account: false,
            is_link: true,
            is_user_field: false,
            name: "Portfolio",
            rendered_value: false,
            type: 1,
            value: "https://example.com/ava",
        },
    ],
    sent_by_url: "#narrow/sender/7",
    show_placeholder_for_status_text: false,
    show_last_active_status: true,
    show_manage_section: true,
    spectator_view: false,
    status_emoji_info: false,
    status_content_available: true,
    status_text: "Reviewing the new component library",
    user_avatar: avatar,
    user_circle_class: "user-circle-active",
    user_email: "ava@example.com",
    user_full_name: "Ava Rodriguez",
    user_id: 7,
    user_last_seen_time_status: "Active now",
    user_mention_syntax: "@**Ava Rodriguez|7**",
    user_time: "7:48 PM",
    user_type: "Member",
};

function setup_user_card_scene(host: HTMLElement): void {
    const card = host.querySelector<HTMLElement>(".cf-user-card");
    if (card === null) {
        return;
    }
    const menu = card.querySelector<HTMLElement>("[role='menu']");
    if (menu === null) {
        return;
    }
    card.querySelector("#popover-menu-copy-email")?.classList.remove("hide_copy_icon");
    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-user-card__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    card.append(feedback);

    const visible_items = (): HTMLElement[] =>
        [...menu.querySelectorAll<HTMLElement>("[role='menuitem']")].filter(
            (item) => item.getClientRects().length > 0,
        );

    card.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const action = event.target.closest<HTMLElement>("[role='menuitem']");
        if (action === null) {
            return;
        }
        event.preventDefault();
        const label =
            action.getAttribute("aria-label") ??
            action.querySelector<HTMLElement>(".cf-menu__label")?.textContent.trim() ??
            action.textContent.trim();
        feedback.textContent = `${label} requested.`;
    });

    card.addEventListener("keydown", (event) => {
        const items = visible_items();
        const current = event.target instanceof HTMLElement ? items.indexOf(event.target) : -1;
        if (current === -1) {
            return;
        }
        let next: number;
        switch (event.key) {
            case "ArrowDown": {
                next = (current + 1) % items.length;
                break;
            }
            case "ArrowUp": {
                next = (current - 1 + items.length) % items.length;
                break;
            }
            case "Home": {
                next = 0;
                break;
            }
            case "End": {
                next = items.length - 1;
                break;
            }
            default: {
                return;
            }
        }
        event.preventDefault();
        items[next]?.focus();
    });
}

function setup_user_profile_scene(host: HTMLElement): void {
    const modal = host.querySelector<HTMLElement>("#user-profile-modal");
    if (modal === null) {
        return;
    }
    const dialog = modal.querySelector<HTMLElement>(".cf-dialog");
    if (dialog === null) {
        return;
    }
    const tabs = [...dialog.querySelectorAll<HTMLButtonElement>("[role='tab']")];
    const footer = dialog.querySelector<HTMLElement>(".manage-profile-tab-footer");
    if (footer === null) {
        return;
    }

    for (const tab of tabs) {
        const panel_id = tab.dataset["tabKey"];
        const panel = panel_id
            ? dialog.querySelector<HTMLElement>(`#${CSS.escape(panel_id)}`)
            : null;
        if (panel === null || panel_id === undefined) {
            continue;
        }
        const control_id = `${panel_id}-control`;
        tab.id = control_id;
        tab.setAttribute("aria-controls", panel_id);
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", control_id);
    }

    const stream_list = dialog.querySelector<HTMLElement>(".user-stream-list");
    if (stream_list !== null) {
        stream_list.innerHTML = `
            <li class="storybook-user-profile__list-item"><span>Design</span><span>Subscribed</span></li>
            <li class="storybook-user-profile__list-item"><span>Product</span><span>Subscribed</span></li>`;
    }
    const group_list = dialog.querySelector<HTMLElement>(".user-group-list");
    if (group_list !== null) {
        group_list.innerHTML = `
            <li class="storybook-user-profile__list-item"><span>Design</span><span>Member</span></li>
            <li class="storybook-user-profile__list-item"><span>Research</span><span>Not joined</span></li>`;
    }
    const manage_panel = dialog.querySelector<HTMLElement>("#manage-profile-tab");
    if (manage_panel !== null) {
        manage_panel.innerHTML = `
            <section class="storybook-user-profile__manage" aria-labelledby="storybook-user-profile-manage-heading">
                <h2 id="storybook-user-profile-manage-heading">Manage Ava Rodriguez</h2>
                <p>Review account access before saving administrative changes.</p>
                <dl>
                    <div><dt>Account state</dt><dd>Active</dd></div>
                    <div><dt>Role</dt><dd>Member</dd></div>
                </dl>
            </section>`;
    }
    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-user-profile__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    dialog.querySelector<HTMLElement>(".cf-dialog__body")?.append(feedback);

    const activate_tab = (tab: HTMLButtonElement, move_focus = false): void => {
        const panel_id = tab.dataset["tabKey"];
        if (!panel_id) {
            return;
        }
        for (const candidate of tabs) {
            const selected = candidate === tab;
            candidate.classList.toggle("cf-tabs__tab--selected", selected);
            candidate.setAttribute("aria-selected", String(selected));
            candidate.tabIndex = selected ? 0 : -1;
            const candidate_panel_id = candidate.dataset["tabKey"];
            const panel = candidate_panel_id
                ? dialog.querySelector<HTMLElement>(`#${CSS.escape(candidate_panel_id)}`)
                : null;
            if (panel !== null) {
                panel.hidden = !selected;
                panel.style.display = selected ? "block" : "none";
            }
        }
        footer.hidden = panel_id !== "manage-profile-tab";
        footer.style.display = panel_id === "manage-profile-tab" ? "flex" : "none";
        feedback.textContent = `${tab.textContent.trim()} section selected.`;
        if (move_focus) {
            tab.focus();
        }
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const launcher = event.target.closest<HTMLButtonElement>("[data-storybook-open-profile]");
        if (launcher !== null) {
            launcher.remove();
            modal.classList.add("modal--open");
            modal.setAttribute("aria-hidden", "false");
            tabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.focus();
            return;
        }
        const close = event.target.closest<HTMLButtonElement>(".modal__close, .dialog_exit_button");
        if (close !== null) {
            modal.classList.remove("modal--open");
            modal.setAttribute("aria-hidden", "true");
            const open = globalThis.document.createElement("button");
            open.type = "button";
            open.className = "cf-button cf-button--primary storybook-user-profile__open";
            open.dataset["storybookOpenProfile"] = "";
            open.textContent = "Open user profile";
            host.prepend(open);
            open.focus();
            return;
        }
        const tab = event.target.closest<HTMLButtonElement>("[role='tab']");
        if (tab !== null) {
            activate_tab(tab);
            return;
        }
        if (event.target.closest(".user-profile-update-user-tab-button") !== null) {
            const manage_tab = tabs.find(
                (candidate) => candidate.dataset["tabKey"] === "manage-profile-tab",
            );
            if (manage_tab !== undefined) {
                activate_tab(manage_tab, true);
            }
            return;
        }
        const action = event.target.closest<HTMLElement>(
            ".copy-link-to-user-profile, .copy-custom-field-url, .dialog_submit_button",
        );
        if (action !== null) {
            event.preventDefault();
            feedback.textContent = `${action.getAttribute("aria-label") ?? action.textContent.trim()} requested.`;
        }
    });

    dialog.addEventListener("keydown", (event) => {
        const tab =
            event.target instanceof Element
                ? event.target.closest<HTMLButtonElement>("[role='tab']")
                : null;
        if (tab === null || (event.key !== "ArrowLeft" && event.key !== "ArrowRight")) {
            return;
        }
        event.preventDefault();
        const offset = event.key === "ArrowRight" ? 1 : -1;
        const next = tabs[(tabs.indexOf(tab) + offset + tabs.length) % tabs.length];
        if (next !== undefined) {
            activate_tab(next, true);
        }
    });

    const initial_tab = tabs.find((tab) => tab.getAttribute("aria-selected") === "true");
    if (initial_tab !== undefined) {
        activate_tab(initial_tab);
        feedback.textContent = "";
    }
}

const meta = {
    title: "Cofounder/User Identity",
    parameters: {layout: "fullscreen"},
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const UserCard: Story = {
    render() {
        const host = render_template_story(
            "popovers/user_card/user_card_popover.hbs",
            render_user_card,
            {...user, user_time: undefined},
        );
        host.classList.add("cf-theme", "storybook-user-card");
        setup_user_card_scene(host);
        return host;
    },
};

export const UserProfile: Story = {
    render() {
        const host = render_template_story("user_profile_modal.hbs", render_user_profile, user);
        host.classList.add("cf-theme", "storybook-user-profile");
        const modal = host.querySelector<HTMLElement>("#user-profile-modal");
        modal?.classList.add("modal--open");
        modal?.setAttribute("aria-hidden", "false");
        const tabSwitcher = host.querySelector<HTMLElement>(".modal__tab-switcher-container");
        if (tabSwitcher) {
            tabSwitcher.innerHTML = render_tabs({
                aria_label: "Profile sections",
                custom_classes: "cf-tabs--fill cf-tabs--wrap",
                tabs: [
                    {id: "profile", key: "profile-tab", label: "Profile", selected: true},
                    {id: "channels", key: "user-profile-streams-tab", label: "Channels"},
                    {id: "groups", key: "user-profile-groups-tab", label: "User groups"},
                    {id: "manage", key: "manage-profile-tab", label: "Manage"},
                ],
            });
        }
        host.querySelectorAll<HTMLElement>(".tabcontent").forEach((tab) => {
            tab.hidden = tab.id !== "profile-tab";
            tab.style.display = tab.id === "profile-tab" ? "block" : "none";
        });
        setup_user_profile_scene(host);
        return host;
    },
};

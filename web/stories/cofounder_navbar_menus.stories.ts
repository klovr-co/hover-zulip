import type {Meta, StoryObj} from "@storybook/html";

import {sync_menuitemradio_checked_state} from "../src/cofounder/components/menu.ts";
import render_gear_menu from "../templates/popovers/navbar/navbar_gear_menu_popover.hbs";
import render_help_menu from "../templates/popovers/navbar/navbar_help_menu_popover.hbs";
import render_personal_menu from "../templates/popovers/navbar/navbar_personal_menu_popover.hbs";

import {render_template_story} from "./template_story_utils.ts";

const theme = {
    color_scheme_values: {
        automatic: {code: 0},
        dark: {code: 2},
        light: {code: 1},
    },
    user_color_scheme: 1,
    web_font_size_px: 14,
    web_line_height_percent: 120,
};

const meta = {
    title: "Cofounder/Navbar Menus",
    parameters: {layout: "fullscreen"},
} satisfies Meta;

export default meta;
type Story = StoryObj;

function frame(host: HTMLElement): HTMLElement {
    host.classList.add("cf-theme", "storybook-navbar-menu");
    return host;
}

function personal_menu_story(host: HTMLElement): HTMLElement {
    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-navbar-menu__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    host.append(feedback);

    const announce = (message: string): void => {
        feedback.textContent = message;
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }

        const theme_choice = event.target.closest<HTMLLabelElement>("[role='menuitemradio']");
        if (theme_choice) {
            event.preventDefault();
            const input = host.querySelector<HTMLInputElement>(`#${theme_choice.htmlFor}`);
            if (input) {
                input.checked = true;
                sync_menuitemradio_checked_state(host);
                announce(`${theme_choice.getAttribute("aria-label") ?? "Theme"} selected.`);
            }
            return;
        }

        const density_button = event.target.closest<HTMLButtonElement>(".info-density-button");
        if (density_button) {
            announce(`${density_button.getAttribute("aria-label") ?? "Display setting"} selected.`);
            return;
        }

        const action = event.target.closest<HTMLElement>(".cf-menu__action");
        if (!action) {
            return;
        }
        event.preventDefault();
        if (action.classList.contains("personal-menu-clear-status")) {
            const status = host.querySelector<HTMLElement>(".personal-menu-status-text");
            if (status) {
                status.textContent = "No status set";
            }
            action.hidden = true;
            announce("Status cleared.");
            return;
        }
        const label =
            action.querySelector(".cf-menu__label")?.textContent?.trim() ??
            action.getAttribute("aria-label") ??
            "Menu action";
        announce(`${label} selected.`);
    });

    host.addEventListener("keydown", (event) => {
        if (!(event.target instanceof HTMLElement)) {
            return;
        }
        if (
            (event.key === "Enter" || event.key === " ") &&
            event.target.matches("a[role='menuitem'], label[role='menuitemradio']")
        ) {
            event.preventDefault();
            event.target.click();
        }
    });

    return host;
}

function workspace_menu_story(host: HTMLElement): HTMLElement {
    const menu = host.querySelector<HTMLElement>("#gear-menu-dropdown");
    if (!menu) {
        return host;
    }

    const trigger = globalThis.document.createElement("button");
    trigger.type = "button";
    trigger.className = "storybook-navbar-menu__trigger";
    trigger.textContent = "Main menu";
    trigger.setAttribute("aria-expanded", "true");
    trigger.setAttribute("aria-controls", "gear-menu-dropdown");
    host.prepend(trigger);

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-navbar-menu__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    host.append(feedback);

    const set_open = (open: boolean): void => {
        menu.hidden = !open;
        trigger.setAttribute("aria-expanded", String(open));
        feedback.textContent = `Workspace menu ${open ? "opened" : "closed"}.`;
    };

    trigger.addEventListener("click", () => {
        set_open(menu.hasAttribute("hidden"));
    });

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const action = event.target.closest<HTMLElement>(".cf-menu__action");
        if (!action) {
            return;
        }
        event.preventDefault();
        const label = action.querySelector(".cf-menu__label")?.textContent?.trim() ?? "Menu action";
        feedback.textContent = action.classList.contains("invite-user-link")
            ? "Invite users dialog opened."
            : `${label} selected.`;
    });

    host.addEventListener("keydown", (event) => {
        if (!(event.target instanceof HTMLElement) || menu.hidden) {
            return;
        }
        if (
            (event.key === "Enter" || event.key === " ") &&
            event.target.matches("a[role='menuitem']")
        ) {
            event.preventDefault();
            event.target.click();
            return;
        }
        if (event.key === "Escape") {
            event.preventDefault();
            set_open(false);
            trigger.focus();
            return;
        }
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
            return;
        }
        const items = [...menu.querySelectorAll<HTMLElement>(".cf-menu__action")].filter(
            (item) => item.getClientRects().length > 0,
        );
        const current_index = items.indexOf(event.target);
        if (current_index === -1 || items.length === 0) {
            return;
        }
        event.preventDefault();
        const offset = event.key === "ArrowDown" ? 1 : -1;
        items[(current_index + offset + items.length) % items.length]?.focus();
    });

    return host;
}

function help_menu_story(host: HTMLElement): HTMLElement {
    const menu = host.querySelector<HTMLElement>("#help-menu-dropdown");
    if (!menu) {
        return host;
    }

    host.classList.add("storybook-navbar-menu--help");
    const trigger = globalThis.document.createElement("button");
    trigger.type = "button";
    trigger.className = "storybook-navbar-menu__trigger";
    trigger.textContent = "Help menu";
    trigger.setAttribute("aria-expanded", "true");
    trigger.setAttribute("aria-controls", "help-menu-dropdown");
    host.prepend(trigger);

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-navbar-menu__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    host.append(feedback);

    const set_open = (open: boolean): void => {
        menu.hidden = !open;
        trigger.setAttribute("aria-expanded", String(open));
        feedback.textContent = `Help menu ${open ? "opened" : "closed"}.`;
    };

    trigger.addEventListener("click", () => {
        set_open(menu.hasAttribute("hidden"));
    });

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const action = event.target.closest<HTMLElement>(".cf-menu__action");
        if (!action) {
            return;
        }
        event.preventDefault();
        const label = action.querySelector(".cf-menu__label")?.textContent?.trim() ?? "Help";
        feedback.textContent = action.dataset["overlayTrigger"]
            ? `${label} opened.`
            : `${label} selected.`;
    });

    host.addEventListener("keydown", (event) => {
        if (!(event.target instanceof HTMLElement) || menu.hidden) {
            return;
        }
        if (
            (event.key === "Enter" || event.key === " ") &&
            event.target.matches("a[role='menuitem']")
        ) {
            event.preventDefault();
            event.target.click();
            return;
        }
        if (event.key === "Escape") {
            event.preventDefault();
            set_open(false);
            trigger.focus();
            return;
        }
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
            return;
        }
        const items = [...menu.querySelectorAll<HTMLElement>(".cf-menu__action")].filter(
            (item) => item.getClientRects().length > 0,
        );
        const current_index = items.indexOf(event.target);
        if (current_index === -1 || items.length === 0) {
            return;
        }
        event.preventDefault();
        const offset = event.key === "ArrowDown" ? 1 : -1;
        items[(current_index + offset + items.length) % items.length]?.focus();
    });

    return host;
}

export const Personal: Story = {
    render() {
        return personal_menu_story(
            frame(
                render_template_story(
                    "popovers/navbar/navbar_personal_menu_popover.hbs",
                    render_personal_menu,
                    {
                        ...theme,
                        invisible_mode: false,
                        is_active: true,
                        popover_hotkey_hints: "Shift Y",
                        show_placeholder_for_status_text: false,
                        status_content_available: true,
                        status_emoji_info: undefined,
                        status_text: "Reviewing the Cofounder library",
                        user_avatar:
                            "/static/images/test-images/avatars/example_profile_picture.png",
                        user_circle_class: "user-circle-active",
                        user_full_name: "Ava Rodriguez",
                        user_id: 7,
                        user_is_guest: false,
                        user_last_seen_time_status: "Active now",
                        user_type: "Member",
                    },
                ),
            ),
        );
    },
};

export const Workspace: Story = {
    render() {
        return workspace_menu_story(
            frame(
                render_template_story(
                    "popovers/navbar/navbar_gear_menu_popover.hbs",
                    render_gear_menu,
                    {
                        ...theme,
                        apps_page_url: "/apps/",
                        can_create_multiuse_invite: true,
                        can_invite_users_by_email: true,
                        is_business_org: true,
                        is_demo_organization: false,
                        is_education_org: false,
                        is_guest: false,
                        is_org_on_paid_plan: true,
                        is_owner: true,
                        is_plan_limited: false,
                        is_plan_plus: true,
                        is_plan_standard: false,
                        is_plan_standard_sponsored_for_free: false,
                        is_self_hosted: false,
                        is_spectator: false,
                        login_link: "/login/",
                        promote_sponsoring_zulip: false,
                        realm_name: "Cofounder Studio",
                        realm_url: "cofounder.example.com",
                        show_billing: true,
                        show_plans: true,
                        show_remote_billing: false,
                        sponsorship_pending: false,
                        user_has_billing_access: true,
                    },
                ),
            ),
        );
    },
};

export const Help: Story = {
    render() {
        return help_menu_story(
            frame(
                render_template_story(
                    "popovers/navbar/navbar_help_menu_popover.hbs",
                    render_help_menu,
                    {
                        corporate_enabled: true,
                        is_admin: true,
                        is_owner: true,
                        popover_hotkey_hints: "?",
                    },
                ),
            ),
        );
    },
};

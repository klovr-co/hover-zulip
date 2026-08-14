import type {Meta, StoryObj} from "@storybook/html";

import render_connected_account_card from "../templates/settings/connected_account_card.hbs";
import render_connected_accounts_admin from "../templates/settings/connected_accounts_admin.hbs";
import render_settings_overlay from "../templates/settings_overlay.hbs";

type ConnectedAccountsArgs = {
    mobileContent: boolean;
    mode: "approved" | "pending" | "revoked" | "empty";
};

const grants = [
    {
        action_label: "Restrict",
        id: 91,
        is_revoked: false,
        scope_label: "Leadership group, Venue team",
        user_name: "Priya Shah",
    },
    {
        action_label: "Restore",
        id: 92,
        is_revoked: true,
        scope_label: "Marketing announcements",
        user_name: "Morgan Lee",
    },
];

function card_context(mode: Exclude<ConnectedAccountsArgs["mode"], "empty">): object {
    const is_pending = mode === "pending";
    const is_approved = mode === "approved";
    const is_revoked = mode === "revoked";
    return {
        account: {
            approval_label: is_pending ? "Pending approval" : is_approved ? "Approved" : "Revoked",
            approval_state: mode,
            approval_tone: is_pending ? "warning" : is_approved ? "success" : "danger",
            creator_name: "Maxine Tan",
            display_name: "AIMTO conversations",
            external_account_id: "acct_7B3F9D8C2A",
            health_checked_label: "August 13, 2026 at 10:18 AM",
            health_icon: is_pending ? "warning" : is_approved ? "check" : "circle-x",
            health_label: is_pending ? "Degraded" : is_approved ? "Healthy" : "Unavailable",
            health_tone: is_pending ? "warning" : is_approved ? "success" : "danger",
            id: 18,
            is_approved,
            is_pending,
            is_revoked,
            owner_name: "Aisha Rahman",
            provider_name: "WhatsApp Business",
        },
        grants: is_pending ? [] : grants,
        has_grants: !is_pending,
    };
}

function render_story(args: ConnectedAccountsArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme cf-connected-accounts-story";
    canvas.innerHTML = render_settings_overlay({
        can_create_new_bots: true,
        can_edit_user_panel: true,
        can_manage_bot: true,
        is_admin: true,
        is_guest: false,
        is_owner: true,
        realm_hover_enabled: true,
        show_emoji_settings_lock: false,
        show_uploaded_files_section: true,
    });
    const settingsBox = canvas.querySelector<HTMLElement>(".settings-box");
    if (settingsBox === null) {
        throw new Error("Settings content host did not render");
    }
    settingsBox.innerHTML = render_connected_accounts_admin({
        is_admin: true,
        realm_hover_enabled: true,
    });
    canvas
        .querySelector<HTMLElement>('[data-section="connected-account-settings"]')
        ?.classList.add("active");
    canvas
        .querySelector<HTMLElement>('[data-section="connected-account-settings"]')
        ?.setAttribute("aria-current", "page");
    canvas.querySelector(".header-prefix")?.append("Organization settings");
    canvas
        .querySelector(":scope .settings-header:not(.mobile) .section")
        ?.append(" / Connected Accounts");
    canvas
        .querySelector(":scope .settings-header.mobile .section")
        ?.append(" / Connected Accounts");
    if (args.mobileContent) {
        canvas.querySelector(".content-wrapper")?.classList.add("show");
        canvas.querySelector(".settings-header.mobile")?.classList.add("slide-left");
    }
    const list = canvas.querySelector<HTMLElement>("#cf-connected-accounts-list");
    if (list === null) {
        throw new Error("Connected Accounts list did not render");
    }
    if (args.mode === "empty") {
        const empty = globalThis.document.createElement("p");
        empty.className = "cf-connected-accounts__empty";
        empty.textContent = "No Connected Accounts are available.";
        list.append(empty);
    } else {
        list.innerHTML = render_connected_account_card(card_context(args.mode));
    }
    return canvas;
}

const meta = {
    title: "Cofounder/Settings/Connected accounts",
    parameters: {layout: "fullscreen"},
    args: {mobileContent: false, mode: "approved"},
    render: render_story,
} satisfies Meta<ConnectedAccountsArgs>;

export default meta;
type Story = StoryObj<ConnectedAccountsArgs>;

export const Approved: Story = {};
export const Pending: Story = {args: {mode: "pending"}};
export const Revoked: Story = {args: {mode: "revoked"}};
export const Empty: Story = {args: {mode: "empty"}};
export const NarrowTouch: Story = {
    args: {mobileContent: true},
    parameters: {viewport: {defaultViewport: "mobile1"}},
};

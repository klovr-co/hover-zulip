import type {Meta, StoryObj} from "@storybook/html";

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

export const Personal: Story = {
    render() {
        return frame(
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
                    status_text: "Reviewing the Cofounder library",
                    user_avatar: "/static/images/test-images/avatars/example_profile_picture.png",
                    user_circle_class: "user-circle-active",
                    user_full_name: "Ava Rodriguez",
                    user_id: 7,
                    user_is_guest: false,
                    user_last_seen_time_status: "Active now",
                    user_type: "Member",
                },
            ),
        );
    },
};

export const Workspace: Story = {
    render() {
        return frame(
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
        );
    },
};

export const Help: Story = {
    render() {
        return frame(
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
        );
    },
};

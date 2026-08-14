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
    date_joined: "August 8, 2026",
    display_profile_fields: [
        {id: 1, name: "Role", type: 1, value: "Product designer"},
        {id: 2, is_link: true, name: "Portfolio", type: 1, value: "https://example.com/ava"},
    ],
    email: "ava@example.com",
    full_name: "Ava Rodriguez",
    has_message_context: true,
    is_active: true,
    is_bot: false,
    is_me: false,
    is_sender_popover: true,
    last_seen: "Active now",
    pm_with_url: "#narrow/dm/7",
    private_message_class: "send_private_message",
    profile_data: [
        {id: 1, name: "Team", type: 1, value: "Product design"},
        {id: 2, is_link: true, name: "Portfolio", type: 1, value: "https://example.com/ava"},
    ],
    sent_by_url: "#narrow/sender/7",
    show_placeholder_for_status_text: false,
    show_last_active_status: true,
    show_manage_section: true,
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
        return host;
    },
};

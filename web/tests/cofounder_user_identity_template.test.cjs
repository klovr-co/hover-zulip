"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_user_card = require("../templates/popovers/user_card/user_card_popover.hbs");
const render_user_profile = require("../templates/user_profile_modal.hbs");

const {run_test} = require("./lib/test.cjs");

const user = {
    can_manage_profile: true,
    can_manage_user: true,
    can_mute: true,
    can_send_private_message: true,
    date_joined: "August 8, 2026",
    display_profile_fields: [],
    email: "ava@example.com",
    full_name: "Ava Rodriguez",
    has_message_context: true,
    is_active: true,
    is_bot: false,
    is_me: false,
    is_sender_popover: true,
    last_seen: "Active now",
    pm_with_url: "#narrow/dm/7",
    profile_data: [
        {
            id: 2,
            is_link: true,
            name: "Portfolio",
            type: 1,
            value: "https://example.com/ava",
        },
    ],
    private_message_class: "send_private_message",
    sent_by_url: "#narrow/sender/7",
    show_last_active_status: true,
    show_manage_section: true,
    status_content_available: true,
    status_text: "Reviewing the new component library",
    user_avatar: "/static/images/avatar.png",
    user_circle_class: "user-circle-active",
    user_email: "ava@example.com",
    user_full_name: "Ava Rodriguez",
    user_id: 7,
    user_last_seen_time_status: "Active now",
    user_mention_syntax: "@**Ava Rodriguez|7**",
    user_time: "7:48 PM",
    user_type: "Member",
};

run_test("User identity surfaces use Cofounder primitives", ({mock_template}) => {
    mock_template("user_profile_subscribe_widget.hbs", false, () => "");

    const html = `${render_user_card(user)}${render_user_profile(user)}`;
    const source = [
        "../templates/user_profile_modal.hbs",
        "../templates/popovers/user_card/user_card_popover.hbs",
        "../templates/popovers/user_card/user_card_popover_custom_fields.hbs",
        "../templates/popovers/user_card/user_card_popover_for_deleted_user.hbs",
        "../templates/popovers/user_card/user_card_popover_for_unknown_user.hbs",
        "../templates/user_profile_subscribe_widget.hbs",
        "../templates/user_custom_profile_fields.hbs",
        "../templates/default_external_account_icon.hbs",
    ]
        .map((file) => fs.readFileSync(path.join(__dirname, file), "utf8"))
        .join("");

    assert.match(html, /cf-presence-dot--user-circle-active/);
    assert.match(html, /cf-dialog-root/);
    assert.match(html, /cf-search-field/);
    assert.match(html, /cf-menu__icon/);
    assert.match(html, /data-clipboard-text="ava@example.com"/);
    assert.match(html, /role="heading" aria-level="2"/);
    assert.match(html, /role="menu" aria-label="translated: User actions: Ava Rodriguez"/);
    assert.match(html, /id="popover-menu-copy-email"[^>]*role="menuitem"/);
    assert.doesNotMatch(source, /zulip-icon|\bfa(?:\s|-)|icon_class/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|icon_class/);
    assert.match(source, /cofounder=true/);
    assert.match(source, /add-subscription-button/);
});

run_test("User card story provides truthful fixture state and deterministic behavior", () => {
    const source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_user_identity.stories.ts"),
        "utf8",
    );
    const fixture_source = fs.readFileSync(
        path.join(__dirname, "../stories/template_story_utils.ts"),
        "utf8",
    );
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/user-identity.css"),
        "utf8",
    );

    assert.match(source, /can_unmute: false/);
    assert.match(source, /is_imported_stub: false/);
    assert.match(source, /spectator_view: false/);
    assert.match(source, /status_emoji_info: false/);
    assert.match(source, /is_long_text: false/);
    assert.match(source, /function setup_user_card_scene/);
    assert.match(source, /classList\.remove\("hide_copy_icon"\)/);
    assert.match(source, /aria-atomic/);
    assert.match(source, /case "ArrowDown"/);
    assert.match(source, /case "ArrowUp"/);
    assert.match(source, /case "Home"/);
    assert.match(source, /case "End"/);
    const storybook_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");
    assert.match(storybook_css, /\.storybook-user-card__feedback:empty \{[\s\S]*display: none;/);
    assert.match(
        fixture_source,
        /"popovers\/user_card\/user_card_popover\.hbs": \{[\s\S]*pm_with_url: "#narrow\/dm\/7"/,
    );
    assert.match(
        component_css,
        /\.cf-user-card \.custom-profile-field-link \{[\s\S]*min-height: var\(--cf-control-height\);/,
    );
    assert.match(component_css, /min-height: var\(--cf-control-height-touch\);/);
});

run_test("Cofounder presence dots keep semantic runtime state classes", () => {
    const source = fs.readFileSync(path.join(__dirname, "../src/buddy_list_presence.ts"), "utf8");

    assert.match(source, /hasClass\("cf-presence-dot"\)/);
    assert.match(source, /addClass\(user_circle_class\)/);
    assert.match(source, /addClass\(`zulip-icon-\$\{user_circle_class\}`\)/);
});

run_test("User profile story provides truthful tabs and dialog behavior", () => {
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_user_identity.stories.ts"),
        "utf8",
    );
    const css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/user-identity.css"),
        "utf8",
    );

    assert.match(story, /is_user_field: false/);
    assert.match(story, /function setup_user_profile_scene/);
    assert.match(story, /setAttribute\("aria-controls", panel_id\)/);
    assert.match(story, /setAttribute\("role", "tabpanel"\)/);
    assert.match(story, /const activate_tab/);
    assert.match(story, /data-storybook-open-profile/);
    assert.match(story, /event\.key !== "ArrowLeft"/);
    assert.match(story, /event\.key !== "ArrowRight"/);
    assert.match(story, /storybook-user-profile__list-item/);
    assert.match(css, /\.cf-user-profile \.custom-profile-fields-link/);
    assert.match(css, /min-height: var\(--cf-control-height-touch\);/);
});

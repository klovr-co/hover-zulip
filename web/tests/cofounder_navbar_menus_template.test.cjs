"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_gear = require("../templates/popovers/navbar/navbar_gear_menu_popover.hbs");
const render_help = require("../templates/popovers/navbar/navbar_help_menu_popover.hbs");
const render_personal = require("../templates/popovers/navbar/navbar_personal_menu_popover.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("Navbar menus use typed Cofounder icons", () => {
    const directory = path.join(__dirname, "../templates/popovers/navbar");
    const source = fs
        .readdirSync(directory)
        .map((file) => fs.readFileSync(path.join(directory, file), "utf8"))
        .join("");
    const html = render_help({
        corporate_enabled: true,
        is_admin: true,
        is_owner: true,
        popover_hotkey_hints: "?",
    });

    assert.match(html, /cf-menu/);
    assert.match(html, /cf-icon/);
    assert.doesNotMatch(source, /zulip-icon|\bfa(?:\s|-)|icon_class/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|icon_class/);
});

run_test("Help menu owns its name, native commands, trigger context, and shortcut bounds", () => {
    const html = render_help({
        corporate_enabled: true,
        is_admin: true,
        is_owner: true,
        popover_hotkey_hints: "?",
    });
    const menu_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/menu.css"),
        "utf8",
    );
    const story_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_navbar_menus.stories.ts"),
        "utf8",
    );

    assert.match(html, /role="menu" aria-label="[^"]*Help menu/);
    assert.equal((html.match(/<button type="button" role="menuitem"/g) ?? []).length, 3);
    assert.equal((html.match(/data-overlay-trigger=/g) ?? []).length, 3);
    assert.doesNotMatch(html, /aria-labelledby="help-menu"/);
    assert.match(menu_css, /\.cf-menu \.popover-menu-hotkey-hints[\s\S]*max-width: 45%/);
    assert.match(story_css, /storybook-navbar-menu--help #help-menu-dropdown/);
    assert.match(story, /function help_menu_story/);
    assert.match(story, /aria-controls/);
    assert.match(story, /ArrowDown/);
    assert.match(story, /Help menu.*closed/);
});

run_test("Personal menu owns named, synchronized Cofounder controls", () => {
    const html = render_personal({
        color_scheme_values: {
            automatic: {code: 0},
            dark: {code: 2},
            light: {code: 1},
        },
        invisible_mode: false,
        is_active: true,
        popover_hotkey_hints: "Shift Y",
        show_placeholder_for_status_text: false,
        status_content_available: true,
        status_emoji_info: undefined,
        status_text: "Reviewing the Cofounder library",
        user_color_scheme: 1,
        user_avatar: "/avatar/7",
        user_circle_class: "user-circle-active",
        user_full_name: "Ava Rodriguez",
        user_id: 7,
        user_is_guest: false,
        user_type: "Member",
        web_font_size_px: 14,
        web_line_height_percent: 120,
    });
    const app_css = fs.readFileSync(path.join(__dirname, "../styles/cofounder/app.css"), "utf8");
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_navbar_menus.stories.ts"),
        "utf8",
    );

    assert.match(html, /role="menu" aria-label="[^"]*Personal menu/);
    assert.match(html, /class="theme-switcher cf-menu__choice-group/);
    assert.equal((html.match(/role="menuitemradio"/g) ?? []).length, 3);
    assert.equal((html.match(/aria-checked="true"/g) ?? []).length, 1);
    assert.equal((html.match(/aria-checked="false"/g) ?? []).length, 2);
    assert.equal((html.match(/tabindex="-1" aria-hidden="true"/g) ?? []).length, 3);
    assert.doesNotMatch(html, /\btab-picker\b|\btab-option\b|class="slider"|::/);
    assert.match(app_css, /personal-menu-status-text[\s\S]*text-overflow: ellipsis/);
    assert.match(app_css, /info-density-button:focus-visible/);
    assert.match(story, /status_emoji_info: undefined/);
    assert.match(story, /Status cleared\./);
    assert.match(story, /sync_menuitemradio_checked_state/);
});

run_test("Workspace menu owns native commands, context, and hostile-copy boundaries", () => {
    const html = render_gear({
        apps_page_url: "/apps/",
        can_create_multiuse_invite: true,
        can_invite_users_by_email: true,
        color_scheme_values: {
            automatic: {code: 0},
            dark: {code: 2},
            light: {code: 1},
        },
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
        user_color_scheme: 1,
        web_font_size_px: 14,
        web_line_height_percent: 120,
    });
    const app_css = fs.readFileSync(path.join(__dirname, "../styles/cofounder/app.css"), "utf8");
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_navbar_menus.stories.ts"),
        "utf8",
    );

    assert.match(html, /role="menu" aria-label="[^"]*Workspace menu/);
    assert.match(
        html,
        /<button type="button" role="menuitem" class="invite-user-link cf-menu__action/,
    );
    assert.doesNotMatch(html, /aria-labelledby="settings-dropdown"/);
    assert.match(app_css, /#gear-menu-dropdown :is\(\.org-name, \.org-url\)/);
    assert.match(app_css, /#gear-menu-dropdown \.org-info \.popover-menu-link/);
    assert.match(story, /function workspace_menu_story/);
    assert.match(story, /aria-controls/);
    assert.match(story, /ArrowDown/);
    assert.match(story, /Invite users dialog opened\./);
});

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_info_density = require("../templates/settings/info_density_control_button_group.hbs");
const render_preferences = require("../templates/settings/preferences_general.hbs");
const render_settings = require("../templates/settings_overlay.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("Settings overlay uses the Cofounder shell and navigation contract", () => {
    const html = render_settings({
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

    assert.match(html, /cf-settings-shell/);
    assert.match(html, /cf-settings-nav__item/);
    assert.match(html, /cf-settings-shell__back/);
    assert.match(html, /cf-settings-shell__close/);
    assert.match(
        html,
        /role="link" tabindex="-1" data-section="preferences" aria-controls="settings_content"/,
    );
    const behavior_source = fs.readFileSync(
        path.join(__dirname, "../src/settings_panel_menu.ts"),
        "utf8",
    );
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_settings.stories.ts"),
        "utf8",
    );
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/settings-shell.css"),
        "utf8",
    );
    assert.match(behavior_source, /children\("li"\)\.attr\("tabindex", "-1"\)/);
    assert.match(behavior_source, /\{"aria-current": "page", tabindex: "0"\}/);
    assert.match(
        behavior_source,
        /mobile_deactivate_section[\s\S]*?\.cf-settings-nav__item\[aria-current='page'\][\s\S]*?getClientRects[\s\S]*?\.focus\(\)/,
    );
    assert.match(story_source, /select_section/);
    assert.match(story_source, /select_scope/);
    assert.match(story_source, /update_density/);
    assert.match(story_source, /\.current-value/);
    assert.match(story_source, /\.display-value/);
    assert.match(story_source, /Font size|web_font_size_px/);
    assert.match(story_source, /Line spacing|web_line_height_percent/);
    assert.match(story_source, /addEventListener\("change"/);
    assert.match(story_source, /Back to settings\./);
    assert.match(story_source, /Close settings requested\./);
    assert.match(component_css, /\.cf-settings-nav__list\[hidden\]/);
    assert.match(
        component_css,
        /\.cf-settings-shell__content\.content-wrapper[\s\S]*?visibility: hidden;[\s\S]*?transform: translateX\(100%\)/,
    );
    assert.match(
        component_css,
        /\.cf-settings-shell__content\.content-wrapper\.show[\s\S]*?visibility: visible;[\s\S]*?transform: translateX\(0\)/,
    );
    assert.match(component_css, /:not\(:has\(\.cf-settings-shell__content\.show\)\)/);
    assert.match(component_css, /@media \(width <= 700px\)[\s\S]*?contain: paint/);
    assert.match(
        component_css,
        /:has\(\.cf-settings-shell__content\.show\)[\s\S]*?\.cf-settings-shell__sidebar[\s\S]*?visibility: hidden/,
    );
    assert.match(component_css, /overflow-wrap: anywhere/);
    assert.match(component_css, /grid-template-columns: minmax\(0, 1fr\)/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-) |<i(?:\s|>)/);
});

run_test("General preferences use Cofounder fields, choices, and typed icons", () => {
    const html = render_preferences({
        color_scheme_values: {
            automatic: {code: 0},
            dark: {code: 2},
            light: {code: 1},
        },
        for_realm_settings: false,
        prefix: "user_",
        settings_label: {
            default_language_settings_label: "Language",
            enter_sends: "Press Enter to send messages",
            twenty_four_hour_time: "Time format",
        },
        settings_object: {enter_sends: true, web_font_size_px: 15},
        twenty_four_hour_time_values: {
            twelve: {description: "12-hour", value: false},
            twentyFour: {description: "24-hour", value: true},
        },
        web_line_height_percent_display_value: "1.2×",
    });

    assert.match(html, /cf-settings-section/);
    assert.match(html, /cf-settings-field-row/);
    assert.match(html, /cf-settings-choice-group/);
    assert.match(html, /cf-settings-stepper/);
    assert.match(html, /cf-help-link/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)/);
});

run_test("Information-density controls expose button semantics without icon fonts", () => {
    const html = render_info_density({
        default_icon_name: "type",
        display_value: 15,
        for_settings_ui: true,
        prefix: "user_",
        property: "web_font_size_px",
        property_value: 15,
    });

    assert.match(html, /cf-settings-stepper__button/);
    assert.match(html, /type="button"/);
    assert.match(html, /cf-icon/);
    assert.doesNotMatch(html, /zulip-icon|<i(?:\s|>)/);
});

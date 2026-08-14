"use strict";

const assert = require("node:assert/strict");

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
    assert.match(html, /data-section="preferences"/);
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

import type {Meta, StoryObj} from "@storybook/html";

import render_tabs from "../templates/cofounder/components/tabs.hbs";
import render_preferences_general from "../templates/settings/preferences_general.hbs";
import render_settings_overlay from "../templates/settings_overlay.hbs";

function render_scene({mobileContent = false} = {}): HTMLElement {
    const host = globalThis.document.createElement("div");
    host.className = "cf-theme storybook-settings";
    host.innerHTML = render_settings_overlay({
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

    const tabContainer = host.querySelector(".tab-container");
    if (tabContainer) {
        tabContainer.innerHTML = render_tabs({
            aria_label: "Settings scope",
            custom_classes: "cf-tabs--fill",
            tabs: [
                {id: 0, key: "settings", label: "Personal", selected: true},
                {id: 1, key: "organization", label: "Organization"},
            ],
        });
    }

    const preferencesNav = host.querySelector<HTMLElement>('[data-section="preferences"]');
    preferencesNav?.classList.add("active");
    preferencesNav?.setAttribute("aria-current", "page");

    const settingsBox = host.querySelector(".settings-box");
    if (settingsBox) {
        settingsBox.innerHTML = `
            <section id="user-preferences" class="settings-section show" data-name="preferences">
                <h2 class="settings-section-title">Preferences</h2>
                <p class="settings-section-description">Choose how Cofounder looks and responds while you work.</p>
                <form class="preferences-settings-form">
                    ${render_preferences_general({
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
                        settings_object: {
                            enter_sends: true,
                            web_font_size_px: 15,
                            web_line_height_percent: 120,
                        },
                        twenty_four_hour_time_values: {
                            twelve: {description: "12-hour (10:45 AM)", value: false},
                            twentyFour: {description: "24-hour (22:45)", value: true},
                        },
                        web_line_height_percent_display_value: "1.2×",
                    })}
                </form>
            </section>`;
    }

    const languageValue = host.querySelector(
        ":scope #default_language_widget .dropdown_widget_value",
    );
    if (languageValue) {
        languageValue.textContent = "English";
    }
    const automaticTheme = host.querySelector<HTMLInputElement>(
        ":scope #user_theme_select_automatic",
    );
    if (automaticTheme) {
        automaticTheme.checked = true;
    }

    host.querySelector(".header-prefix")?.append("Personal settings");
    host.querySelector(":scope .settings-header:not(.mobile) .section")?.append(" / Preferences");
    host.querySelector(":scope .settings-header.mobile .section")?.append(" / Preferences");

    if (mobileContent) {
        host.querySelector(".content-wrapper")?.classList.add("show");
        host.querySelector(".settings-header.mobile")?.classList.add("slide-left");
    }
    return host;
}

const meta = {
    title: "Cofounder/Settings/Shell",
    parameters: {layout: "fullscreen"},
    render: () => render_scene(),
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const Navigation: Story = {};

export const MobilePreferencePanel: Story = {
    render: () => render_scene({mobileContent: true}),
};

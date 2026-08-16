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
    preferencesNav?.setAttribute("tabindex", "0");
    host.querySelector<HTMLElement>(".org-settings-list")?.toggleAttribute("hidden", true);

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

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-settings__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    host.append(feedback);

    const select_section = (item: HTMLElement, move_focus = false): void => {
        const list = item.closest<HTMLElement>(".cf-settings-nav__list");
        if (list === null) {
            return;
        }
        for (const candidate of list.querySelectorAll<HTMLElement>(".cf-settings-nav__item")) {
            const selected = candidate === item;
            candidate.classList.toggle("active", selected);
            candidate.setAttribute("tabindex", selected ? "0" : "-1");
            candidate.toggleAttribute("aria-current", selected);
            if (selected) {
                candidate.setAttribute("aria-current", "page");
            }
        }
        const label = item
            .querySelector<HTMLElement>(".cf-settings-nav__label")
            ?.textContent?.trim();
        if (label) {
            for (const section of host.querySelectorAll<HTMLElement>(
                ":scope .settings-header .section",
            )) {
                section.textContent = ` / ${label}`;
            }
            feedback.textContent = `${label} settings selected.`;
        }
        if (move_focus) {
            item.focus();
        }
    };

    const select_scope = (tab: HTMLButtonElement, move_focus = false): void => {
        const scope = tab.dataset["tabKey"];
        if (scope !== "settings" && scope !== "organization") {
            return;
        }
        for (const candidate of host.querySelectorAll<HTMLButtonElement>(".cf-tabs__tab")) {
            const selected = candidate === tab;
            candidate.classList.toggle("cf-tabs__tab--selected", selected);
            candidate.setAttribute("aria-selected", String(selected));
            candidate.setAttribute("tabindex", selected ? "0" : "-1");
        }
        const personal = host.querySelector<HTMLElement>(".normal-settings-list");
        const organization = host.querySelector<HTMLElement>(".org-settings-list");
        personal?.toggleAttribute("hidden", scope !== "settings");
        organization?.toggleAttribute("hidden", scope !== "organization");
        const visible_list = scope === "settings" ? personal : organization;
        const current =
            visible_list?.querySelector<HTMLElement>('[aria-current="page"]') ??
            visible_list?.querySelector<HTMLElement>(".cf-settings-nav__item");
        if (current) {
            select_section(current);
        }
        const prefix = scope === "settings" ? "Personal settings" : "Organization settings";
        host.querySelector<HTMLElement>(".header-prefix")!.textContent = prefix;
        feedback.textContent = `${prefix} shown.`;
        if (move_focus) {
            tab.focus();
        }
    };

    const update_density = (button: HTMLButtonElement): void => {
        const group = button.closest<HTMLElement>(".cf-settings-stepper");
        if (group === null) {
            return;
        }
        const property = group.dataset["property"];
        const input = group.querySelector<HTMLInputElement>(".current-value");
        const value = group.querySelector<HTMLElement>(".display-value");
        if (
            input === null ||
            value === null ||
            (property !== "web_font_size_px" && property !== "web_line_height_percent")
        ) {
            return;
        }
        const font_size = property === "web_font_size_px";
        const minimum = font_size ? 12 : 100;
        const maximum = font_size ? 20 : 200;
        const step = font_size ? 1 : 10;
        const default_value = font_size ? 15 : 120;
        const current = Number.parseInt(input.value, 10);
        const next = button.classList.contains("default-button")
            ? default_value
            : Math.min(
                  maximum,
                  Math.max(
                      minimum,
                      current + (button.classList.contains("increase-button") ? step : -step),
                  ),
              );
        input.value = String(next);
        value.textContent = font_size ? String(next) : `${(next / 100).toFixed(1)}×`;
        group.querySelector<HTMLButtonElement>(".decrease-button")!.disabled = next <= minimum;
        group.querySelector<HTMLButtonElement>(".increase-button")!.disabled = next >= maximum;
        group.querySelector<HTMLButtonElement>(".default-button")!.disabled =
            next === default_value;
        feedback.textContent = `${group.getAttribute("aria-label")} set to ${value.textContent}.`;
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const tab = event.target.closest<HTMLButtonElement>(".cf-tabs__tab");
        if (tab) {
            select_scope(tab);
            return;
        }
        const density_button = event.target.closest<HTMLButtonElement>(".info-density-button");
        if (density_button) {
            update_density(density_button);
            return;
        }
        const item = event.target.closest<HTMLElement>(".cf-settings-nav__item");
        if (item) {
            select_section(item);
            return;
        }
        if (event.target.closest(".cf-settings-shell__back")) {
            host.querySelector(":scope .content-wrapper")?.classList.remove("show");
            host.querySelector(":scope .settings-header.mobile")?.classList.remove("slide-left");
            host.querySelector<HTMLElement>(
                ':scope .cf-settings-nav__list:not([hidden]) [aria-current="page"]',
            )?.focus();
            feedback.textContent = "Back to settings.";
            return;
        }
        if (event.target.closest(".cf-settings-shell__close")) {
            feedback.textContent = "Close settings requested.";
        }
    });

    host.addEventListener("change", (event) => {
        if (!(
            event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement
        )) {
            return;
        }
        if (event.target instanceof HTMLSelectElement) {
            const label = host
                .querySelector<HTMLLabelElement>(
                    `:scope label[for="${CSS.escape(event.target.id)}"]`,
                )
                ?.textContent?.trim();
            feedback.textContent = `${label ?? "Setting"} set to ${event.target.selectedOptions[0]?.text ?? event.target.value}.`;
            return;
        }
        if (event.target.type === "radio") {
            const label = host
                .querySelector<HTMLLabelElement>(
                    `:scope label[for="${CSS.escape(event.target.id)}"]`,
                )
                ?.getAttribute("aria-label");
            feedback.textContent = `${label ?? "Theme"} selected.`;
            return;
        }
        if (event.target.type === "checkbox") {
            const label = host
                .querySelector<HTMLLabelElement>(
                    `:scope label[for="${CSS.escape(event.target.id)}"]`,
                )
                ?.textContent?.trim();
            feedback.textContent = `${label ?? "Setting"} ${event.target.checked ? "enabled" : "disabled"}.`;
        }
    });

    host.addEventListener("keydown", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const item = event.target.closest<HTMLElement>(".cf-settings-nav__item");
        if (item && ["ArrowDown", "ArrowUp"].includes(event.key)) {
            const list = item.closest<HTMLElement>(".cf-settings-nav__list");
            const items = [
                ...(list?.querySelectorAll<HTMLElement>(".cf-settings-nav__item") ?? []),
            ].filter((candidate) => candidate.getClientRects().length > 0);
            const offset = event.key === "ArrowDown" ? 1 : -1;
            const next = items[(items.indexOf(item) + offset + items.length) % items.length];
            if (next) {
                event.preventDefault();
                select_section(next, true);
            }
            return;
        }
        const tab = event.target.closest<HTMLButtonElement>(".cf-tabs__tab");
        if (tab && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
            const tabs = [...host.querySelectorAll<HTMLButtonElement>(".cf-tabs__tab")];
            const offset = event.key === "ArrowRight" ? 1 : -1;
            const next = tabs[(tabs.indexOf(tab) + offset + tabs.length) % tabs.length];
            if (next) {
                event.preventDefault();
                select_scope(next, true);
            }
        }
    });
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

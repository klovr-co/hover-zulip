import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";
import {test_credentials} from "./lib/common.ts";

const zuliprc_regex =
    /^data:application\/octet-stream;charset=utf-8,\[api\]\nemail=.+\nkey=.+\nsite=.+\n$/;

async function get_decoded_url_in_selector(page: Page, selector: string): Promise<string> {
    const anchor = await page.$(`a:is(${selector})`);
    return decodeURIComponent(await (await anchor!.getProperty("href")).jsonValue());
}

async function open_settings(page: Page): Promise<void> {
    await common.open_personal_menu(page);

    const settings_selector = "#personal-menu-dropdown a[href^='#settings']";
    await page.waitForSelector(settings_selector, {visible: true});
    await page.click(settings_selector);

    await page.waitForSelector("#settings_content .profile-settings-form", {visible: true});
    const page_url = await common.page_url_with_fragment(page);
    assert.ok(
        page_url.includes("/#settings/"),
        `Page url: ${page_url} does not contain /#settings/`,
    );
    await page.waitForSelector("#settings_overlay_container", {visible: true});
}

async function close_settings_and_date_picker(page: Page): Promise<void> {
    const date_picker_selector = ".date-field-alt-input";
    await page.$eval(date_picker_selector, (element) => {
        if (!(element instanceof HTMLElement)) {
            throw new TypeError("Expected the date picker control to be an HTML element.");
        }
        element.click();
    });
    await page.waitForSelector(".flatpickr-calendar", {visible: true});
    await page.keyboard.press("Escape");
    await page.waitForSelector(".flatpickr-calendar", {hidden: true});
    await page.waitForSelector("#settings_overlay_container", {hidden: true});
}

async function test_change_full_name(page: Page): Promise<void> {
    await page.waitForSelector("#full_name", {visible: true});
    await page.click("#full_name");
    const full_name_input_selector = 'input[name="full_name"]';
    await common.clear_and_type(page, full_name_input_selector, "New name");
    await page.click("#settings_content .profile-settings-form");
    await page.waitForSelector(".full-name-change-container .alert-success", {visible: true});
    await page.waitForFunction(
        () => document.querySelector<HTMLInputElement>("#full_name")?.value === "New name",
    );
}

async function test_change_password(page: Page): Promise<void> {
    await page.click("#change_password");
    const change_password_button_selector = "#change_password_modal .dialog_submit_button";
    await page.waitForSelector(change_password_button_selector, {visible: true});
    await common.wait_for_micromodal_to_open(page);
    await page.type("#old_password", test_credentials.default_user.password);
    test_credentials.default_user.password = "new_password";
    await page.type("#new_password", test_credentials.default_user.password);
    await page.waitForSelector("#pw_strength .bar", {visible: true});
    await page.click(change_password_button_selector);
    await common.wait_for_micromodal_to_close(page);
}

async function test_get_api_key(page: Page): Promise<void> {
    await page.click('[data-section="account-and-privacy"]');
    const show_change_api_key_selector = "#api_key_button";
    await page.waitForSelector(show_change_api_key_selector, {visible: true});
    await page.click(show_change_api_key_selector);

    const get_api_key_button_selector = "#get_api_key_button";
    await page.waitForSelector(get_api_key_button_selector, {visible: true});
    await common.wait_for_micromodal_to_open(page);
    await common.fill_form(page, "#api_key_form", {
        password: test_credentials.default_user.password,
    });
    await page.focus(get_api_key_button_selector);
    await page.click(get_api_key_button_selector);

    await page.waitForSelector("#show_api_key", {visible: true});
    const api_key = await common.get_text_from_selector(page, "#api_key_value");
    assert.match(api_key, /[\dA-Za-z]{32}/, "Incorrect API key format.");

    const download_zuliprc_selector = "#download_zuliprc";
    await page.click(download_zuliprc_selector);
    const zuliprc_decoded_url = await get_decoded_url_in_selector(page, download_zuliprc_selector);
    assert.match(zuliprc_decoded_url, zuliprc_regex, "Incorrect zuliprc file");
    await page.click("#api_key_modal .modal__close");
    await common.wait_for_micromodal_to_close(page);
}

async function test_connectors_section(page: Page): Promise<void> {
    await page.click('.normal-settings-list [data-section="connectors"]');
    await page.waitForSelector("#personal-connector-list.show", {visible: true});
    await page.waitForSelector("#personal-connector-list .connector-rows tr", {visible: true});

    await page.click("#personal-connector-list .add-connector");
    await common.wait_for_micromodal_to_open(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Add integration",
    );

    await page.waitForSelector(".connector-fallback[data-provider='slack_incoming']", {
        visible: true,
    });
    assert.deepEqual(
        await page.$$eval(".connector-fallback", (elements) =>
            elements.map((element) => element.getAttribute("data-provider")),
        ),
        ["slack_incoming", "rest_api"],
    );
    await page.click(".connector-fallback[data-provider='slack_incoming']");
    await page.waitForSelector("#connector_setup_form", {visible: true});
    assert.strictEqual(await page.$(".connector-events"), null);
    await page.click(".connector-back");
    await page.waitForSelector(".connector-provider-search", {visible: true});

    await page.type(".connector-provider-search", "GitHub");
    await page.waitForSelector(".connector-provider-choice[data-provider='github']", {
        visible: true,
    });
    await page.click(".connector-provider-choice[data-provider='github']");

    await page.waitForSelector("#connector_setup_form", {visible: true});
    await page.waitForSelector(".connector-events", {visible: true});
    assert.ok(
        (await page.$$eval(".connector-event-options input", (elements) => elements.length)) > 0,
    );
    await common.clear_and_type(page, ".connector-topic", "Connector browser test");
    await page.click(".connector-save");

    await page.waitForSelector(".connector-handoff #connector_webhook_url", {visible: true});
    const webhook_url = await common.get_text_from_selector(page, "#connector_webhook_url");
    assert.match(webhook_url, /\/api\/v1\/external\/github\?api_key=/);
    assert.strictEqual(await common.get_text_from_selector(page, ".dialog_heading"), "GitHub");

    await page.evaluate(() => {
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: {
                async writeText(value: string) {
                    await Promise.resolve();
                    document.body.dataset["copiedConnectorUrl"] = value;
                },
            },
        });
    });
    await page.click(".connector-copy-primary");
    await page.waitForFunction(
        (expected_url) => document.body.dataset["copiedConnectorUrl"] === expected_url,
        {},
        webhook_url,
    );

    await page.click(".connector-handoff .rotate-connector");
    await page.waitForFunction(
        (original_url) =>
            document.querySelector("#connector_webhook_url")?.textContent !== original_url,
        {},
        webhook_url,
    );
    const rotated_webhook_url = await common.get_text_from_selector(page, "#connector_webhook_url");
    assert.notStrictEqual(rotated_webhook_url, webhook_url);

    await page.click(".edit-connector");
    await page.waitForSelector("#connector_setup_form", {visible: true});
    await common.clear_and_type(page, ".connector-topic", "Updated connector browser test");
    await page.click(".connector-save");
    await page.waitForSelector(".connector-handoff #connector_webhook_url", {visible: true});

    await page.click("#connector-dialog .modal__close");
    await common.wait_for_micromodal_to_close(page);
    await page.waitForSelector(
        "#personal-connector-list .connector-row-actions .copy-connector-url",
        {visible: true},
    );

    await page.click("#personal-connector-list .connector-actions-menu summary");
    await page.click("#personal-connector-list .connector-actions-menu .view-connector");
    await common.wait_for_micromodal_to_open(page);
    await page.waitForSelector(".connector-handoff .disable-connector", {visible: true});
    await page.click(".connector-handoff .disable-connector");
    await page.click(".connector-handoff .disable-connector");
    await page.waitForSelector(".connector-disabled-state", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, ".connector-disabled-state h2"),
        "Connector disabled",
    );
    await page.click("#connector-dialog .modal__close");
    await common.wait_for_micromodal_to_close(page);
}

const alert_word_status_banner_selector = ".alert-word-status-banner";

async function add_alert_word(page: Page, word: string): Promise<void> {
    await page.click("#open-add-alert-word-modal");
    await common.wait_for_micromodal_to_open(page);

    await page.type("#add-alert-word-name", word);
    await page.click("#add-alert-word .dialog_submit_button");

    await common.wait_for_micromodal_to_close(page);
}

async function check_alert_word_added(page: Page, word: string): Promise<void> {
    const added_alert_word_selector = `.alert-word-item[data-word='${CSS.escape(word)}']`;
    await page.waitForSelector(added_alert_word_selector, {visible: true});
}

async function get_alert_words_status_text(page: Page): Promise<string> {
    await page.waitForSelector(alert_word_status_banner_selector, {visible: true});
    const status_text = await common.get_text_from_selector(
        page,
        ".alert-word-status-banner .banner-label",
    );
    return status_text;
}

async function close_alert_words_status(page: Page): Promise<void> {
    const status_close_button = ".alert-word-status-banner .banner-close-button";
    await page.click(status_close_button);
    await page.waitForSelector(alert_word_status_banner_selector, {hidden: true});
}

async function test_duplicate_alert_words_cannot_be_added(
    page: Page,
    duplicate_word: string,
): Promise<void> {
    await page.click("#open-add-alert-word-modal");
    await common.wait_for_micromodal_to_open(page);

    await page.type("#add-alert-word-name", duplicate_word);
    await page.click("#add-alert-word .dialog_submit_button");

    const alert_word_status_selector = "#dialog_error";
    await page.waitForSelector(alert_word_status_selector, {visible: true});
    const status_text = await common.get_text_from_selector(page, alert_word_status_selector);
    assert.strictEqual(status_text, "Alert word already exists!");

    await page.click("#add-alert-word .dialog_exit_button");
    await common.wait_for_micromodal_to_close(page);
}

async function delete_alert_word(page: Page, word: string): Promise<void> {
    const delete_button_selector = `tr[data-word="${CSS.escape(word)}"] .remove-alert-word`;
    await page.click(delete_button_selector);
    await page.waitForSelector(delete_button_selector, {hidden: true});
}

async function test_alert_word_deletion(page: Page, word: string): Promise<void> {
    await delete_alert_word(page, word);
    const status_text = await get_alert_words_status_text(page);
    assert.strictEqual(status_text, `Alert word ${word} removed successfully!`);
    await close_alert_words_status(page);
}

async function test_alert_words_section(page: Page): Promise<void> {
    await page.click('[data-section="alert-words"]');
    const word = "puppeteer";
    await add_alert_word(page, word);
    await check_alert_word_added(page, word);
    await test_duplicate_alert_words_cannot_be_added(page, word);
    await test_alert_word_deletion(page, word);
}

async function change_language(page: Page, language_data_code: string): Promise<void> {
    await page.waitForSelector("#default_language_widget", {
        visible: true,
    });
    await page.click("#default_language_widget");
    await page.waitForSelector(".dropdown-list", {visible: true});
    const language_selector = `li[data-unique-id="${CSS.escape(language_data_code)}"]`;
    await page.click(language_selector);
}

async function check_language_setting_status(page: Page): Promise<void> {
    await page.waitForSelector("#user-preferences .general-settings-status .reload_link", {
        visible: true,
    });
}

async function assert_language_changed_to_chinese(page: Page): Promise<void> {
    await page.waitForSelector("#default_language_widget", {
        visible: true,
    });
    const default_language = await common.get_text_from_selector(page, ".dropdown_widget_value");
    assert.match(
        default_language,
        /^中文（简体）/v,
        "Default language has not been changed to Chinese.",
    );
}

async function test_i18n_language_precedence(page: Page): Promise<void> {
    const settings_url_for_german = "http://zulip.zulipdev.com:9981/de/#settings";
    await page.goto(settings_url_for_german);
    await page.waitForSelector("#settings-change-box", {visible: true});
    const page_language_code = await page.evaluate(() => document.documentElement.lang);
    assert.strictEqual(page_language_code, "de");
}

async function test_default_language_setting(page: Page): Promise<void> {
    // The personal Connectors section opens the current user's connector inventory by default.
    // we need to switch back to the Personal Settings tab to proceed with further testing.
    await page.waitForSelector('.tab-switcher .ind-tab[data-tab-key="settings"]', {visible: true});
    await page.click('.tab-switcher .ind-tab[data-tab-key="settings"]');
    await page.waitForSelector("#settings_overlay_container", {visible: true});

    const preferences_section = '[data-section="preferences"]';
    await page.click(preferences_section);

    const chinese_language_data_code = "zh-hans";
    await change_language(page, chinese_language_data_code);
    // Check that the saved indicator appears
    await check_language_setting_status(page);
    await page.click(".reload_link");
    await page.waitForSelector("#default_language_widget", {
        visible: true,
    });
    await assert_language_changed_to_chinese(page);
    await test_i18n_language_precedence(page);
    await page.waitForSelector(preferences_section, {visible: true});
    await page.click(preferences_section);

    // Change the language back to English so that subsequent tests pass.
    await change_language(page, "en");

    // Check that the saved indicator appears
    await check_language_setting_status(page);
    await page.goto("http://zulip.zulipdev.com:9981/#settings"); // get back to normal language.
    await page.waitForSelector(preferences_section, {visible: true});
    await page.click(preferences_section);
    await page.waitForSelector("#user-preferences .general-settings-status", {
        visible: true,
    });
    await page.waitForSelector("#default_language_widget", {
        visible: true,
    });
}

async function test_notifications_section(page: Page): Promise<void> {
    await page.click('[data-section="notifications"]');
    // At the beginning, "DMs, mentions, and alerts"(checkbox name=enable_sounds) audio will be on
    // and "Streams"(checkbox name=enable_stream_audible_notifications) audio will be off by default.

    const notification_sound_enabled =
        "#user-notification-settings .setting_notification_sound:enabled";
    await page.waitForSelector(notification_sound_enabled, {visible: true});

    await common.fill_form(page, "#user-notification-settings .notification-settings-form", {
        enable_stream_audible_notifications: true,
        enable_sounds: false,
    });
    await page.waitForSelector(notification_sound_enabled, {visible: true});

    await common.fill_form(page, "#user-notification-settings .notification-settings-form", {
        enable_stream_audible_notifications: true,
    });
    /*
    Usually notifications sound dropdown gets disabled on disabling
    all audio notifications. But this seems flaky in tests.
    TODO: Find the right fix and enable this.

    const notification_sound_disabled = ".setting_notification_sound:disabled";
    await page.waitForSelector(notification_sound_disabled);
    */
}

async function settings_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await open_settings(page);
    await close_settings_and_date_picker(page);
    await open_settings(page);
    await test_change_full_name(page);
    await test_alert_words_section(page);
    await test_connectors_section(page);
    await test_default_language_setting(page);
    await test_notifications_section(page);
    await test_get_api_key(page);
    await test_change_password(page);
    // test_change_password should be the very last test, because it
    // replaces your session, which can lead to some nondeterministic
    // failures in test code after it, involving `GET /events`
    // returning a 401. (We reset the test database after each file).
}

await common.run_test(settings_tests);

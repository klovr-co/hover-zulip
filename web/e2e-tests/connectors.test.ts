import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function open_settings(page: Page): Promise<void> {
    await common.open_personal_menu(page);

    const settings_selector = "#personal-menu-dropdown a[href^='#settings']";
    await page.waitForSelector(settings_selector, {visible: true});
    await page.click(settings_selector);

    await page.waitForSelector("#settings_content .profile-settings-form", {visible: true});
    await page.waitForSelector("#settings_overlay_container", {visible: true});
}

async function test_connector_lifecycle(page: Page): Promise<void> {
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
    await page.waitForFunction(
        () =>
            document.querySelector<HTMLInputElement>(".connector-provider-search")?.value ===
            "GitHub",
    );
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
}

async function connector_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await open_settings(page);
    await test_connector_lifecycle(page);
}

await common.run_test(connector_tests);

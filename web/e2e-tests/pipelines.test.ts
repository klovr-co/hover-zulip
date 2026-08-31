import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function pipeline_creation_test(page: Page): Promise<void> {
    await common.log_in(page);

    await page.click("#left-sidebar-navigation-list .top_left_pipelines");
    await page.waitForSelector("#hover-pipelines-view .hover-pipelines-shell", {visible: true});
    assert.ok((await common.page_url_with_fragment(page)).endsWith("#hover/pipelines"));
    assert.strictEqual(
        await common.get_text_from_selector(page, ".hover-pipelines-index-header h1"),
        "Pipelines",
    );

    await page.click(".hover-pipeline-create");
    await page.waitForSelector(".hover-pipeline-provider-search", {visible: true});
    assert.deepEqual(
        await page.$$eval(".hover-pipeline-fallbacks .hover-pipeline-provider-choice", (items) =>
            items.map((item) => item.getAttribute("data-provider-key")),
        ),
        ["slack_incoming", "rest_api"],
    );

    await page.type(".hover-pipeline-provider-search", "GitHub");
    await page.waitForSelector(
        '.hover-pipeline-provider-choice[data-provider-key="github"]',
        {visible: true},
    );
    await page.click('.hover-pipeline-provider-choice[data-provider-key="github"]');

    await page.waitForSelector("#hover_pipeline_source_form", {visible: true});
    assert.ok(
        (await page.$$eval(".hover-pipeline-event-options input", (items) => items.length)) > 0,
    );
    await page.$$eval(".hover-pipeline-event-options input", (items) => {
        for (const item of items) {
            (item as HTMLInputElement).click();
        }
    });
    await page.click('#hover_pipeline_source_form button[type="submit"]');
    assert.strictEqual(
        await common.get_text_from_selector(page, ".hover-pipeline-request-status"),
        "Choose at least one event.",
    );
    await page.$$eval(".hover-pipeline-event-options input", (items) => {
        for (const item of items) {
            (item as HTMLInputElement).click();
        }
    });
    await common.clear_and_type(page, ".hover-pipeline-source-topic", "Pipeline browser test");
    await page.click('#hover_pipeline_source_form button[type="submit"]');

    await page.waitForSelector(".hover-pipeline-handoff .hover-pipeline-webhook-url", {
        visible: true,
    });
    const webhook_url = await page.$eval(
        ".hover-pipeline-webhook-url",
        (input) => (input as HTMLInputElement).value,
    );
    assert.match(webhook_url, /\/api\/v1\/external\/github\?api_key=/);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".hover-pipeline-ready"),
        "Webhook ready",
    );

    await page.click('.hover-pipeline-back[data-pipeline-back="setup"]');
    await page.waitForSelector("#hover_pipeline_source_form", {visible: true});
    assert.strictEqual(
        await page.$eval(".hover-pipeline-source-setup > .hover-pipeline-back", (item) =>
            item.getAttribute("data-pipeline-back"),
        ),
        "handoff",
    );
    assert.ok(
        (await page.$$eval(
            ".hover-pipeline-event-options input:checked",
            (items) => items.length,
        )) > 0,
    );
    await common.clear_and_type(page, ".hover-pipeline-source-topic", "Pipeline browser test edited");
    await page.click('#hover_pipeline_source_form button[type="submit"]');
    await page.waitForSelector(".hover-pipeline-handoff .hover-pipeline-webhook-url", {
        visible: true,
    });
    assert.strictEqual(
        await page.$eval(
            ".hover-pipeline-webhook-url",
            (input) => (input as HTMLInputElement).value,
        ),
        webhook_url,
    );

    await page.click(".hover-pipeline-to-configure");
    await page.waitForSelector("#hover_pipeline_configure_form", {visible: true});
    await common.clear_and_type(page, "#hover_pipeline_name", "GitHub browser brief");
    await common.clear_and_type(
        page,
        "#hover_pipeline_instruction",
        "Summarize release progress and deployment blockers.",
    );

    await page.setViewport({width: 900, height: 900});
    assert.strictEqual(
        await page.evaluate(
            () => {
                const view = document.querySelector<HTMLElement>("#hover-pipelines-view")!;
                return view.scrollWidth <= view.clientWidth;
            },
        ),
        true,
    );
    await page.click('#hover_pipeline_configure_form button[type="submit"]');

    await page.waitForSelector(".hover-pipeline-review", {visible: true});
    assert.match(
        await common.get_text_from_selector(page, ".hover-pipeline-review"),
        /GitHub browser brief/,
    );
    assert.match(
        await common.get_text_from_selector(page, ".hover-pipeline-review"),
        /Every day at 9:00 AM/,
    );

    await page.click(".hover-pipeline-submit");
    await page.waitForSelector(".hover-pipeline-table tbody tr:not(.hover-pipeline-empty)", {
        visible: true,
    });
    assert.match(
        await common.get_text_from_selector(
            page,
            ".hover-pipeline-table tbody tr:not(.hover-pipeline-empty)",
        ),
        /GitHub browser brief/,
    );
}

await common.run_test(pipeline_creation_test);

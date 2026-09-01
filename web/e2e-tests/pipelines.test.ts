import assert from "node:assert/strict";

import type {HTTPRequest, Page} from "puppeteer";
import * as z from "zod/mini";

import * as common from "./lib/common.ts";

const desktop_viewport = {width: 1400, height: 1024};
const compact_viewport = {width: 900, height: 900};

const permission_fixture_schema = z.object({
    pipelines: z.array(
        z.object({
            id: z.number(),
            lifecycle_state: z.enum(["active", "draft", "paused"]),
            status: z.enum(["active", "draft", "paused", "needs_attention"]),
            available_transitions: z.array(z.string()),
        }),
    ),
});
type PermissionFixture = z.infer<typeof permission_fixture_schema>;

function assert_permission_fixture(value: unknown): asserts value is PermissionFixture {
    permission_fixture_schema.parse(value);
}

const lifecycle_fixture_schema = z.object({
    pipelines: z.array(z.object({id: z.number(), lifecycle_state: z.string()})),
});

async function capture_audit(
    page: Page,
    name: string,
    viewport: {width: number; height: number} = desktop_viewport,
    preserve_feedback = false,
    focus_selector?: string,
): Promise<void> {
    await page.setViewport(viewport);
    await page.evaluate((keep_feedback) => {
        if (!keep_feedback) {
            document
                .querySelector<HTMLElement>("#feedback_container.show-feedback-container .exit-me")
                ?.click();
        }
        window.scrollTo(0, 0);
        for (const view of document.querySelectorAll<HTMLElement>(".hover-pipelines-view")) {
            view.scrollTop = 0;
        }
    }, preserve_feedback);
    if (focus_selector !== undefined) {
        await page.$eval(focus_selector, (element) => {
            element.scrollIntoView({block: "center", inline: "nearest"});
        });
    }
    await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise<void>((resolve) => {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    resolve();
                });
            });
        });
    });
    if (!preserve_feedback) {
        await page.evaluate(() => {
            document
                .querySelector<HTMLButtonElement>(
                    "#feedback_container.show-feedback-container .exit-me",
                )
                ?.click();
        });
    }
    assert.strictEqual(
        await page.evaluate(
            () =>
                document.documentElement.scrollWidth <= document.documentElement.clientWidth &&
                document.body.scrollWidth <= document.body.clientWidth,
        ),
        true,
        `Horizontal overflow in audit state ${name}`,
    );
    await common.screenshot(
        page,
        `topic-first-pipelines__${name}__${viewport.width}x${viewport.height}`,
    );
}

async function select_topic(page: Page, space: string, topic: string): Promise<void> {
    const selected = await page.$$eval(
        ".hover-pipeline-topic-choice",
        (choices, expected) => {
            const choice = choices.find(
                (item) =>
                    item.getAttribute("data-space") === expected.space &&
                    item.getAttribute("data-topic") === expected.topic,
            );
            if (!(choice instanceof HTMLButtonElement) || choice.disabled) {
                return false;
            }
            choice.click();
            return true;
        },
        {space, topic},
    );
    assert.ok(selected, `Could not select ${space} > ${topic}`);
    await page.waitForFunction(
        (expected) =>
            [...document.querySelectorAll(".hover-pipeline-topic-choice.is-selected")].some(
                (choice) =>
                    choice.getAttribute("data-space") === expected.space &&
                    choice.getAttribute("data-topic") === expected.topic,
            ),
        {},
        {space, topic},
    );
}

async function open_pipelines(page: Page): Promise<void> {
    await page.click("#left-sidebar-navigation-list .top_left_pipelines");
    await page.waitForSelector("#hover-pipelines-view .hover-pipelines-shell", {visible: true});
    await page.waitForSelector(".hover-pipeline-create", {visible: true});
    assert.ok((await common.page_url_with_fragment(page)).endsWith("#hover/pipelines"));
}

async function reload_pipelines(page: Page): Promise<void> {
    await page.reload();
    await page.waitForSelector("#hover-pipelines-view .hover-pipelines-shell", {visible: true});
    await page.waitForSelector(".hover-pipeline-overview-table", {visible: true});
    await page.waitForFunction(
        () =>
            !document
                .querySelector(".hover-pipeline-empty")
                ?.textContent?.includes("Loading pipelines"),
    );
}

async function create_audit_space(page: Page): Promise<number> {
    const result = await page.evaluate(async () => {
        const csrf_token = document.querySelector<HTMLInputElement>(
            'input[name="csrfmiddlewaretoken"]',
        )?.value;
        if (csrf_token === undefined) {
            throw new Error("Missing CSRF token");
        }
        const response = await fetch("/json/users/me/subscriptions", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-CSRFToken": csrf_token,
            },
            body: new URLSearchParams({
                subscriptions: JSON.stringify([
                    {
                        name: "Pipeline archive audit",
                        description: "Temporary Space for the Topic unavailable browser audit.",
                    },
                ]),
                invite_only: "false",
                is_web_public: "false",
            }),
        });
        return {status: response.status, body: await response.text()};
    });
    assert.strictEqual(result.status, 200, result.body);
    await page.waitForFunction(() => zulip_test.get_sub("Pipeline archive audit") !== undefined);
    const stream_id = await page.evaluate(
        () => zulip_test.get_sub("Pipeline archive audit")?.stream_id,
    );
    assert.ok(stream_id !== undefined);
    return stream_id;
}

async function send_topic_message(
    page: Page,
    destination: string,
    topic: string,
    content: string,
): Promise<number> {
    const result = await page.evaluate(
        async (message) => {
            const csrf_token = document.querySelector<HTMLInputElement>(
                'input[name="csrfmiddlewaretoken"]',
            )?.value;
            if (csrf_token === undefined) {
                throw new Error("Missing CSRF token");
            }
            const response = await fetch("/json/messages", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "X-CSRFToken": csrf_token,
                },
                body: new URLSearchParams({
                    type: "stream",
                    to: message.destination,
                    topic: message.topic,
                    content: message.content,
                }),
            });
            return {status: response.status, body: await response.text()};
        },
        {destination, topic, content},
    );
    assert.strictEqual(result.status, 200, result.body);
    const body = z.object({id: z.number()}).parse(JSON.parse(result.body));
    return body.id;
}

async function archive_space(page: Page, stream_id: number): Promise<void> {
    const result = await page.evaluate(async (id) => {
        const csrf_token = document.querySelector<HTMLInputElement>(
            'input[name="csrfmiddlewaretoken"]',
        )?.value;
        if (csrf_token === undefined) {
            throw new Error("Missing CSRF token");
        }
        const response = await fetch(`/json/streams/${id}`, {
            method: "DELETE",
            headers: {"X-CSRFToken": csrf_token},
        });
        return {status: response.status, body: await response.text()};
    }, stream_id);
    assert.strictEqual(result.status, 200, result.body);
}

async function create_data_source(page: Page): Promise<string> {
    await page.click("#left-sidebar-navigation-list .top_left_data_sources");
    await page.waitForSelector("#hover-data-sources-view .hover-data-sources-shell", {
        visible: true,
    });
    await page.evaluate(() => {
        const button = document.querySelector<HTMLButtonElement>(".hover-data-source-create");
        if (button === null) {
            throw new Error("Data Source create button is missing");
        }
        button.click();
    });
    await page.waitForSelector(".hover-data-source-provider-search", {visible: true});
    await page.click('.hover-data-source-provider-choice[data-provider-key="rest_api"]');
    await page.waitForSelector("#hover_data_source_form", {visible: true});

    await page.select(".hover-data-source-destination", "Verona");
    await page.click(".hover-data-source-topic");
    await page.waitForSelector(".hover-data-source-topic-menu", {visible: true});
    await capture_audit(page, "data-source-topic-dropdown-open");
    await capture_audit(page, "data-source-topic-dropdown-open", compact_viewport);
    await page.click('.hover-data-source-topic-option[data-topic="Release activity"]');
    await page.waitForSelector(".hover-data-source-destination-preview", {visible: true});
    assert.match(
        await common.get_text_from_selector(page, ".hover-data-source-destination-preview"),
        /Verona.*Release activity/s,
    );
    await capture_audit(page, "data-source-destination-selected");

    await page.$eval(".hover-data-source-topic", (input) => {
        if (!(input instanceof HTMLInputElement)) {
            throw new TypeError("Expected Topic input");
        }
        input.value = "";
        input.dispatchEvent(new InputEvent("input", {bubbles: true}));
    });
    await page.click('#hover_data_source_form button[type="submit"]');
    await page.waitForFunction(() =>
        [...document.querySelectorAll(".hover-pipeline-request-status")].some((element) =>
            element.textContent?.includes("Choose a destination Space and Topic"),
        ),
    );
    assert.strictEqual(
        await page.$eval(".hover-data-source-topic", (input) => input.matches(":invalid")),
        true,
    );
    await capture_audit(page, "data-source-validation-or-permission-disabled");

    await page.$eval(".hover-data-source-topic", (input) => {
        if (!(input instanceof HTMLInputElement)) {
            throw new TypeError("Expected Topic input");
        }
        input.value = "Release activity";
        input.dispatchEvent(new InputEvent("input", {bubbles: true}));
    });
    await page.click(".hover-data-source-topic");
    await page.waitForSelector(".hover-data-source-topic-menu", {visible: true});
    await page.click('.hover-data-source-topic-option[data-topic="Release activity"]');
    await page.waitForSelector(".hover-data-source-destination-preview", {visible: true});
    await capture_audit(page, "data-source-final-sync-preview");
    await page.click('#hover_data_source_form button[type="submit"]');

    await page.waitForSelector(".hover-pipeline-handoff .hover-data-source-webhook-url", {
        visible: true,
    });
    await capture_audit(page, "data-source-webhook-ready");
    return await page.$eval(".hover-data-source-webhook-url", (input) =>
        input instanceof HTMLInputElement ? input.value : "",
    );
}

async function begin_pipeline_creation(page: Page): Promise<void> {
    await page.evaluate(() => {
        const button = document.querySelector<HTMLButtonElement>(".hover-pipeline-create");
        if (button === null) {
            throw new Error("Pipeline create button is missing");
        }
        button.click();
    });
    await page.waitForSelector(".hover-pipeline-topic-select", {visible: true});
}

async function configure_pipeline(
    page: Page,
    input_topic: string,
    name: string,
    output_topic: string,
): Promise<void> {
    await select_topic(page, "Verona", input_topic);
    await page.click(".hover-pipeline-topic-continue");
    await page.waitForSelector("#hover_pipeline_configure_form", {visible: true});
    await common.clear_and_type(page, "#hover_pipeline_name", name);
    await common.clear_and_type(
        page,
        "#hover_pipeline_instruction",
        "Summarize release progress, decisions, and deployment blockers.",
    );
    await page.select("#hover_pipeline_output_destination", "Verona");
    await common.clear_and_type(page, "#hover_pipeline_output_topic", output_topic);
}

async function submit_review(page: Page): Promise<void> {
    await page.click('#hover_pipeline_configure_form button[type="submit"]');
    await page.waitForSelector(".hover-pipeline-review", {visible: true});
    assert.match(
        await common.get_text_from_selector(page, ".hover-pipeline-flow"),
        /Topic input.*Processing.*Output Topic/is,
    );
    await page.click(".hover-pipeline-submit");
    await page.waitForSelector(".hover-pipeline-overview-row", {visible: true});
}

async function pipeline_id_for_name(page: Page, name: string): Promise<string> {
    const pipeline_id = await page.$$eval(
        ".hover-pipeline-overview-row",
        (rows, expected_name) =>
            rows
                .find((row) => row.textContent?.includes(expected_name))
                ?.getAttribute("data-pipeline-row") ?? null,
        name,
    );
    assert.ok(pipeline_id !== null, `Could not find Pipeline row for ${name}`);
    return pipeline_id;
}

async function expand_pipeline(page: Page, pipeline_id: string): Promise<void> {
    const toggle = `.hover-pipeline-row-toggle[data-pipeline-id="${pipeline_id}"]`;
    if ((await page.$eval(toggle, (button) => button.getAttribute("aria-expanded"))) === "false") {
        await page.click(toggle);
    }
    await page.waitForSelector(
        `.hover-pipeline-detail-row[data-pipeline-detail="${pipeline_id}"]`,
        {
            visible: true,
        },
    );
}

async function pipeline_row_count(page: Page): Promise<number> {
    return (await page.$$(".hover-pipeline-overview-row")).length;
}

async function wait_for_pipeline_status(
    page: Page,
    pipeline_id: string,
    expected_status: string,
): Promise<void> {
    await page.waitForFunction(
        (id, status) =>
            document
                .querySelector(
                    `.hover-pipeline-overview-row[data-pipeline-row="${CSS.escape(id)}"]`,
                )
                ?.textContent?.includes(status) === true,
        {},
        pipeline_id,
        expected_status,
    );
}

async function transition_with_pending_audit(
    page: Page,
    pipeline_id: string,
    action: "pause" | "resume",
): Promise<URLSearchParams> {
    const selector = `.hover-pipeline-${action}[data-pipeline-id="${pipeline_id}"]`;
    let transition_request: HTTPRequest | undefined;
    const {promise: request_released, resolve: release_request} =
        Promise.withResolvers<undefined>();
    const request_handler = (request: HTTPRequest): void => {
        const url = new URL(request.url());
        if (
            request.method() === "PATCH" &&
            url.pathname === `/json/hover/pipelines/${pipeline_id}`
        ) {
            assert.strictEqual(
                transition_request,
                undefined,
                `${action} must not submit a duplicate transition request`,
            );
            transition_request = request;
            void (async () => {
                await request_released;
                await request.continue();
            })();
            return;
        }
        void request.continue();
    };

    await page.setRequestInterception(true);
    page.on("request", request_handler);
    await page.evaluate((button_selector) => {
        const button = document.querySelector<HTMLButtonElement>(button_selector);
        if (button === null) {
            throw new Error(`Missing lifecycle action ${button_selector}`);
        }
        button.click();
        button.click();
    }, selector);
    await page.waitForFunction(
        (button_selector) => {
            const button = document.querySelector<HTMLButtonElement>(button_selector);
            return button?.disabled === true || button?.getAttribute("aria-disabled") === "true";
        },
        {},
        selector,
    );
    await capture_audit(page, `overview-${action}-pending`, desktop_viewport, false, selector);
    assert.ok(transition_request !== undefined, `${action} did not send its PATCH request`);
    const transition_data = new URLSearchParams((await transition_request.fetchPostData()) ?? "");
    assert.deepStrictEqual(
        transition_data.keys().toArray(),
        ["lifecycle_state"],
        "Lifecycle transitions must not overwrite configuration or the input cursor",
    );
    const transition_response = page.waitForResponse(
        (response) =>
            response.request() === transition_request && response.request().method() === "PATCH",
    );
    release_request(undefined);
    await transition_response;
    page.off("request", request_handler);
    await page.setRequestInterception(false);
    return transition_data;
}

async function lifecycle_transition_error_audit(
    page: Page,
    pipeline_id: string,
    action: "pause" | "resume",
): Promise<void> {
    const selector = `.hover-pipeline-${action}[data-pipeline-id="${pipeline_id}"]`;
    const request_handler = (request: HTTPRequest): void => {
        const url = new URL(request.url());
        if (
            request.method() === "PATCH" &&
            url.pathname === `/json/hover/pipelines/${pipeline_id}`
        ) {
            void request.respond({
                status: 403,
                contentType: "application/json",
                body: JSON.stringify({result: "error", msg: "You cannot update this Pipeline."}),
            });
            return;
        }
        void request.continue();
    };
    await page.setRequestInterception(true);
    page.on("request", request_handler);
    await page.click(selector);
    const expected_error =
        action === "pause"
            ? "Could not pause this Pipeline. Try again."
            : "Could not resume this Pipeline. Try again.";
    await page.waitForFunction(
        (message) =>
            [...document.querySelectorAll(".hover-pipeline-request-status")].some((element) =>
                element.textContent?.includes(message),
            ),
        {},
        expected_error,
    );
    assert.strictEqual(
        await page.$eval(selector, (button) => !button.hasAttribute("disabled")),
        true,
    );
    await capture_audit(page, `overview-${action}-error`, desktop_viewport, false, selector);
    page.off("request", request_handler);
    await page.setRequestInterception(false);
}

async function degrade_data_source(page: Page, webhook_url: string): Promise<void> {
    const status = await page.evaluate(async (url) => {
        const webhook = new URL(url);
        webhook.searchParams.set("stream", "999999999");
        const response = await fetch(webhook, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({status: "missing destination"}),
        });
        return response.status;
    }, webhook_url);
    assert.ok(status >= 400);
}

async function rename_topic(page: Page, message_id: number): Promise<void> {
    const result = await page.evaluate(async (id) => {
        const csrf_token = document.querySelector<HTMLInputElement>(
            'input[name="csrfmiddlewaretoken"]',
        )?.value;
        if (csrf_token === undefined) {
            throw new Error("Missing CSRF token");
        }
        const response = await fetch(`/json/messages/${id}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-CSRFToken": csrf_token,
            },
            body: new URLSearchParams({
                topic: "Engineering notes moved",
                propagate_mode: "change_all",
                send_notification_to_old_thread: "false",
                send_notification_to_new_thread: "false",
            }),
        });
        return {status: response.status, body: await response.text()};
    }, message_id);
    assert.strictEqual(result.status, 200, result.body);
}

async function pipeline_creation_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.waitForSelector(".decline-time-zone-update", {visible: true});
    await page.click(".decline-time-zone-update");
    await page.waitForSelector(".navbar-alert-banner", {hidden: true});
    const archive_stream_id = await create_audit_space(page);
    await send_topic_message(
        page,
        "Verona",
        "Release activity",
        "Release candidate passed the browser smoke suite.",
    );
    const engineering_message_id = await send_topic_message(
        page,
        "Verona",
        "Engineering notes",
        "The Topic-first cursor design is ready for review.",
    );
    await send_topic_message(
        page,
        "Verona",
        "Customer pulse",
        "Customers want concise weekly delivery summaries.",
    );
    await send_topic_message(
        page,
        "Pipeline archive audit",
        "Lifecycle input",
        "Archiving this Space should pause, not hide, its Pipeline.",
    );

    const webhook_url = await create_data_source(page);
    await open_pipelines(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".hover-pipelines-index-header h1"),
        "Pipelines",
    );

    await begin_pipeline_creation(page);
    await page.waitForSelector(".hover-pipeline-topic-group", {visible: true});
    await capture_audit(page, "topic-selection-all-topics");
    await capture_audit(page, "topic-selection-all-topics", compact_viewport);

    await common.clear_and_type(page, ".hover-pipeline-topic-search", "Release activity");
    await page.waitForSelector('.hover-pipeline-topic-choice[data-topic="Release activity"]', {
        visible: true,
    });
    await capture_audit(page, "topic-selection-search-result");
    await select_topic(page, "Verona", "Release activity");
    await capture_audit(page, "topic-selection-source-backed-selected");

    await common.clear_and_type(page, ".hover-pipeline-topic-search", "Engineering notes");
    await select_topic(page, "Verona", "Engineering notes");
    await capture_audit(page, "topic-selection-ordinary-selected");

    await common.clear_and_type(page, ".hover-pipeline-topic-search", "No such Topic");
    await page.waitForSelector(".hover-pipeline-topic-empty", {visible: true});
    await capture_audit(page, "topic-selection-empty");

    await common.clear_and_type(page, ".hover-pipeline-topic-search", "Release activity");
    await configure_pipeline(
        page,
        "Release activity",
        "Release activity brief",
        "Release activity",
    );
    await page.waitForSelector(".hover-pipeline-same-topic-note", {visible: true});
    await capture_audit(page, "configuration-schedule-closed-same-topic");
    await page.click(".hover-pipeline-schedule-details > summary");
    await page.waitForSelector(".hover-pipeline-schedule-controls", {visible: true});
    await capture_audit(page, "configuration-schedule-options-open");
    await capture_audit(page, "configuration-schedule-options-open", compact_viewport);
    await submit_review(page);

    await begin_pipeline_creation(page);
    await configure_pipeline(page, "Customer pulse", "Customer pulse draft", "Customer pulse");
    await capture_audit(page, "draft-save-from-configuration");
    await page.click(".hover-pipeline-save-draft");
    await page.waitForFunction(() =>
        [...document.querySelectorAll(".hover-pipeline-overview-row")].some(
            (row) =>
                row.textContent?.includes("Customer pulse draft") &&
                row.textContent.includes("Draft"),
        ),
    );
    const draft_pipeline_id = await pipeline_id_for_name(page, "Customer pulse draft");
    const pipeline_count_with_draft = await pipeline_row_count(page);
    await capture_audit(page, "overview-draft-save-success", desktop_viewport, true);
    await capture_audit(page, "overview-active-and-draft");

    await reload_pipelines(page);
    assert.strictEqual(
        await pipeline_id_for_name(page, "Customer pulse draft"),
        draft_pipeline_id,
        "Reloading must preserve the persisted Draft ID",
    );
    assert.strictEqual(await pipeline_row_count(page), pipeline_count_with_draft);
    await expand_pipeline(page, draft_pipeline_id);
    await capture_audit(page, "overview-draft-continue-setup");
    await page.click(`.hover-pipeline-continue-setup[data-pipeline-id="${draft_pipeline_id}"]`);
    await page.waitForSelector("#hover_pipeline_configure_form", {visible: true});
    assert.strictEqual(
        await page.$eval("#hover_pipeline_name", (input) =>
            input instanceof HTMLInputElement ? input.value : "",
        ),
        "Customer pulse draft",
    );
    await capture_audit(page, "draft-continue-configuration");
    await page.click('#hover_pipeline_configure_form button[type="submit"]');
    await page.waitForSelector(".hover-pipeline-review", {visible: true});
    await page.waitForSelector(".hover-pipeline-save-draft", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, ".hover-pipeline-submit"),
        "Activate pipeline",
    );
    await capture_audit(page, "draft-activation-review");
    await page.click(".hover-pipeline-submit");
    await wait_for_pipeline_status(page, draft_pipeline_id, "Active");
    assert.strictEqual(
        await pipeline_id_for_name(page, "Customer pulse draft"),
        draft_pipeline_id,
        "Activation must update the Draft instead of creating a new Pipeline",
    );
    assert.strictEqual(await pipeline_row_count(page), pipeline_count_with_draft);
    await capture_audit(page, "overview-draft-activate-success", desktop_viewport, true);

    await begin_pipeline_creation(page);
    await configure_pipeline(
        page,
        "Customer pulse",
        "Persistent lifecycle draft",
        "Lifecycle drafts",
    );
    await page.click(".hover-pipeline-save-draft");
    await page.waitForFunction(() =>
        [...document.querySelectorAll(".hover-pipeline-overview-row")].some((row) =>
            row.textContent?.includes("Persistent lifecycle draft"),
        ),
    );

    await begin_pipeline_creation(page);
    await configure_pipeline(
        page,
        "Engineering notes",
        "Engineering decision brief",
        "Customer pulse",
    );
    await capture_audit(page, "configuration-different-output-topic");
    await page.click('#hover_pipeline_configure_form button[type="submit"]');
    await page.waitForSelector(".hover-pipeline-review", {visible: true});
    await capture_audit(page, "configuration-final-review");
    await page.click(".hover-pipeline-submit");
    await page.waitForSelector(".hover-pipeline-overview-row", {visible: true});

    await begin_pipeline_creation(page);
    await select_topic(page, "Pipeline archive audit", "Lifecycle input");
    await page.click(".hover-pipeline-topic-continue");
    await page.waitForSelector("#hover_pipeline_configure_form", {visible: true});
    await common.clear_and_type(page, "#hover_pipeline_name", "Lifecycle availability brief");
    await common.clear_and_type(
        page,
        "#hover_pipeline_instruction",
        "Summarize lifecycle signals without depending on a Data Source.",
    );
    await page.select("#hover_pipeline_output_destination", "Verona");
    await common.clear_and_type(page, "#hover_pipeline_output_topic", "Lifecycle summaries");
    await submit_review(page);

    const resumable_pipeline_id = await pipeline_id_for_name(page, "Release activity brief");
    const resumable_pipeline_count = await pipeline_row_count(page);
    const last_run_before_pause = await page.$eval(
        `.hover-pipeline-overview-row[data-pipeline-row="${resumable_pipeline_id}"] td[data-label="Last run"]`,
        (cell) => cell.textContent?.trim() ?? "",
    );
    await expand_pipeline(page, resumable_pipeline_id);
    const pause_data = await transition_with_pending_audit(page, resumable_pipeline_id, "pause");
    assert.strictEqual(JSON.parse(pause_data.get("lifecycle_state") ?? "null"), "paused");
    await wait_for_pipeline_status(page, resumable_pipeline_id, "Paused");
    assert.strictEqual(await pipeline_row_count(page), resumable_pipeline_count);
    assert.strictEqual(
        await page.$eval(
            `.hover-pipeline-overview-row[data-pipeline-row="${resumable_pipeline_id}"] td[data-label="Last run"]`,
            (cell) => cell.textContent?.trim() ?? "",
        ),
        last_run_before_pause,
        "Pause must preserve the Pipeline's Last run value",
    );
    assert.strictEqual(
        await page.evaluate(
            () =>
                document.activeElement
                    ?.closest(".hover-pipeline-overview-row")
                    ?.getAttribute("data-pipeline-row") ??
                document.activeElement
                    ?.closest(".hover-pipeline-detail-row")
                    ?.getAttribute("data-pipeline-detail"),
        ),
        resumable_pipeline_id,
        "Focus must return to the transitioned Pipeline row",
    );
    await capture_audit(
        page,
        "overview-pause-success",
        desktop_viewport,
        true,
        `.hover-pipeline-resume[data-pipeline-id="${resumable_pipeline_id}"]`,
    );
    await expand_pipeline(page, resumable_pipeline_id);
    await capture_audit(page, "overview-paused-row-expanded");
    await capture_audit(page, "overview-paused-row-expanded", compact_viewport);

    const resume_data = await transition_with_pending_audit(page, resumable_pipeline_id, "resume");
    assert.strictEqual(JSON.parse(resume_data.get("lifecycle_state") ?? "null"), "active");
    await wait_for_pipeline_status(page, resumable_pipeline_id, "Active");
    assert.strictEqual(await pipeline_row_count(page), resumable_pipeline_count);
    assert.strictEqual(
        await page.$eval(
            `.hover-pipeline-overview-row[data-pipeline-row="${resumable_pipeline_id}"] td[data-label="Last run"]`,
            (cell) => cell.textContent?.trim() ?? "",
        ),
        last_run_before_pause,
        "Resume must preserve the Pipeline's Last run value",
    );
    assert.strictEqual(
        await page.evaluate(
            () =>
                document.activeElement
                    ?.closest(".hover-pipeline-overview-row")
                    ?.getAttribute("data-pipeline-row") ??
                document.activeElement
                    ?.closest(".hover-pipeline-detail-row")
                    ?.getAttribute("data-pipeline-detail"),
        ),
        resumable_pipeline_id,
        "Focus must return to the resumed Pipeline row",
    );
    await capture_audit(
        page,
        "overview-resume-success",
        desktop_viewport,
        true,
        `.hover-pipeline-pause[data-pipeline-id="${resumable_pipeline_id}"]`,
    );
    await expand_pipeline(page, resumable_pipeline_id);
    await lifecycle_transition_error_audit(page, resumable_pipeline_id, "pause");
    await wait_for_pipeline_status(page, resumable_pipeline_id, "Active");

    const permission_fixture: unknown = JSON.parse(
        await page.evaluate(async () => {
            const response = await fetch("/json/hover/pipelines");
            if (!response.ok) {
                throw new Error(await response.text());
            }
            return await response.text();
        }),
    );
    assert_permission_fixture(permission_fixture);
    const permission_pipeline = permission_fixture.pipelines.find(
        (pipeline) => pipeline.id === Number(resumable_pipeline_id),
    );
    assert.ok(permission_pipeline !== undefined);
    permission_pipeline.available_transitions = [];
    const permission_handler = (request: HTTPRequest): void => {
        if (new URL(request.url()).pathname === "/json/hover/pipelines") {
            void request.respond({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify(permission_fixture),
            });
            return;
        }
        void request.continue();
    };
    await page.setRequestInterception(true);
    page.on("request", permission_handler);
    await reload_pipelines(page);
    await expand_pipeline(page, resumable_pipeline_id);
    const permission_disabled_selector = `.hover-pipeline-pause[data-pipeline-id="${resumable_pipeline_id}"][disabled]`;
    await page.waitForSelector(permission_disabled_selector, {visible: true});
    await capture_audit(
        page,
        "overview-pause-permission-disabled",
        desktop_viewport,
        false,
        permission_disabled_selector,
    );
    permission_pipeline.lifecycle_state = "paused";
    permission_pipeline.status = "paused";
    await reload_pipelines(page);
    await expand_pipeline(page, resumable_pipeline_id);
    await page.waitForSelector(
        `.hover-pipeline-resume[data-pipeline-id="${resumable_pipeline_id}"][disabled]`,
        {visible: true},
    );
    await capture_audit(
        page,
        "overview-resume-permission-disabled",
        desktop_viewport,
        false,
        `.hover-pipeline-resume[data-pipeline-id="${resumable_pipeline_id}"][disabled]`,
    );
    page.off("request", permission_handler);
    await page.setRequestInterception(false);
    await reload_pipelines(page);

    await capture_audit(page, "overview-default-list");
    await page.click('.hover-pipeline-row-toggle[aria-expanded="false"]');
    await page.waitForSelector(".hover-pipeline-detail-row", {visible: true});
    await capture_audit(page, "overview-active-row-expanded");
    await capture_audit(page, "overview-active-row-expanded", compact_viewport);
    assert.match(
        await common.get_text_from_selector(page, ".hover-pipeline-overview-table"),
        /Engineering notes.*Ordinary Topic/s,
    );
    await capture_audit(page, "overview-ordinary-topic-without-data-source");

    await degrade_data_source(page, webhook_url);
    await reload_pipelines(page);
    const source_pipeline_id = await page.$$eval(
        ".hover-pipeline-overview-row",
        (rows) =>
            rows
                .find((row) => row.textContent?.includes("Release activity brief"))
                ?.getAttribute("data-pipeline-row") ?? null,
    );
    assert.ok(source_pipeline_id !== null);
    await page.click(`.hover-pipeline-row-toggle[data-pipeline-id="${source_pipeline_id}"]`);
    await page.waitForSelector(".hover-pipeline-source-warning", {visible: true});
    assert.match(
        await common.get_text_from_selector(
            page,
            `.hover-pipeline-overview-row[data-pipeline-row="${source_pipeline_id}"]`,
        ),
        /Active/,
    );
    await capture_audit(page, "overview-source-warning-pipeline-active");

    await rename_topic(page, engineering_message_id);
    await reload_pipelines(page);
    const actual_pipeline_payload = z
        .object({
            pipelines: z.array(z.object({name: z.string(), input_topic: z.string()})),
            topics: z.array(z.record(z.string(), z.unknown())),
            can_create: z.boolean(),
        })
        .parse(
            JSON.parse(
                await page.evaluate(async () => {
                    const response = await fetch("/json/hover/pipelines");
                    if (!response.ok) {
                        throw new Error(await response.text());
                    }
                    return await response.text();
                }),
            ),
        );
    const renamed_pipeline = actual_pipeline_payload.pipelines.find(
        (pipeline) => pipeline.name === "Engineering decision brief",
    );
    assert.strictEqual(renamed_pipeline?.input_topic, "Engineering notes moved");

    const unavailable_pipeline_id_before_archive = await pipeline_id_for_name(
        page,
        "Lifecycle availability brief",
    );
    await expand_pipeline(page, unavailable_pipeline_id_before_archive);
    await page.click(
        `.hover-pipeline-pause[data-pipeline-id="${unavailable_pipeline_id_before_archive}"]`,
    );
    await wait_for_pipeline_status(page, unavailable_pipeline_id_before_archive, "Paused");
    await capture_audit(page, "overview-active-draft-and-paused");
    await page.click('[data-pipeline-filter="paused"]');
    await page.waitForFunction(() => {
        const rows = [...document.querySelectorAll(".hover-pipeline-overview-row")];
        return rows.length > 0 && rows.every((row) => row.textContent?.includes("Paused"));
    });
    await capture_audit(page, "overview-paused-filter");
    await page.click('[data-pipeline-filter="all"]');
    await archive_space(page, archive_stream_id);
    await reload_pipelines(page);
    const unavailable_pipeline_id = await page.$$eval(
        ".hover-pipeline-overview-row",
        (rows) =>
            rows
                .find((row) => row.textContent?.includes("Lifecycle availability brief"))
                ?.getAttribute("data-pipeline-row") ?? null,
    );
    assert.ok(unavailable_pipeline_id !== null);
    assert.strictEqual(unavailable_pipeline_id, unavailable_pipeline_id_before_archive);
    await page.click(`.hover-pipeline-row-toggle[data-pipeline-id="${unavailable_pipeline_id}"]`);
    await page.waitForSelector(".hover-pipeline-topic-unavailable", {visible: true});
    assert.match(
        await common.get_text_from_selector(
            page,
            `.hover-pipeline-overview-row[data-pipeline-row="${unavailable_pipeline_id}"]`,
        ),
        /Needs attention/,
    );
    const unavailable_payload = lifecycle_fixture_schema.parse(
        JSON.parse(
            await page.evaluate(async () => {
                const response = await fetch("/json/hover/pipelines");
                if (!response.ok) {
                    throw new Error(await response.text());
                }
                return await response.text();
            }),
        ),
    );
    assert.strictEqual(
        unavailable_payload.pipelines.find(
            (pipeline) => pipeline.id === Number(unavailable_pipeline_id),
        )?.lifecycle_state,
        "paused",
        "Topic unavailability must not overwrite the user's Paused intent",
    );
    await capture_audit(page, "overview-paused-topic-unavailable-recovery");
    const pipeline_count_before_repair = (await page.$$(".hover-pipeline-overview-row")).length;
    await page.click(".hover-pipeline-repair-topic");
    await page.waitForSelector(".hover-pipeline-topic-select", {visible: true});
    await page.waitForSelector(
        '.hover-pipeline-topic-choice.is-unavailable[aria-disabled="true"][data-topic="Lifecycle input"]',
    );
    await capture_audit(page, "topic-selection-unavailable");

    await select_topic(page, "Verona", "Customer pulse");
    await page.click(".hover-pipeline-topic-continue");
    await page.waitForSelector("#hover_pipeline_configure_form", {visible: true});
    assert.strictEqual(
        await page.$eval("#hover_pipeline_name", (input) =>
            input instanceof HTMLInputElement ? input.value : "",
        ),
        "Lifecycle availability brief",
    );
    assert.strictEqual(
        await page.$eval("#hover_pipeline_output_topic", (input) =>
            input instanceof HTMLInputElement ? input.value : "",
        ),
        "Lifecycle summaries",
    );
    await page.click('#hover_pipeline_configure_form button[type="submit"]');
    await page.waitForSelector(".hover-pipeline-review", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, ".hover-pipeline-submit"),
        "Repair pipeline",
    );
    assert.match(
        await common.get_text_from_selector(page, ".hover-pipeline-flow"),
        /Verona.*Customer pulse.*Lifecycle availability brief.*Lifecycle summaries/s,
    );
    await capture_audit(page, "topic-unavailable-repair-review");
    await page.click(".hover-pipeline-submit");
    await page.waitForFunction(
        (pipeline_id, expected_count) => {
            const rows = [
                ...document.querySelectorAll<HTMLElement>(".hover-pipeline-overview-row"),
            ];
            const repaired = rows.find(
                (row) => row.getAttribute("data-pipeline-row") === pipeline_id,
            );
            return (
                rows.length === expected_count &&
                repaired?.textContent?.includes("Customer pulse") === true &&
                repaired.textContent.includes("Paused")
            );
        },
        {},
        unavailable_pipeline_id,
        pipeline_count_before_repair,
    );
    assert.strictEqual(
        await page.$$eval(
            ".hover-pipeline-overview-row",
            (rows) =>
                rows.filter((row) => row.textContent?.includes("Lifecycle availability brief"))
                    .length,
        ),
        1,
        "Repair must update the original Pipeline instead of creating a duplicate row",
    );
    const repaired_payload = lifecycle_fixture_schema.parse(
        JSON.parse(
            await page.evaluate(async () => {
                const response = await fetch("/json/hover/pipelines");
                if (!response.ok) {
                    throw new Error(await response.text());
                }
                return await response.text();
            }),
        ),
    );
    assert.strictEqual(
        repaired_payload.pipelines.find(
            (pipeline) => pipeline.id === Number(unavailable_pipeline_id),
        )?.lifecycle_state,
        "paused",
        "Repair must restore Topic availability without implicitly resuming the Pipeline",
    );
    await capture_audit(page, "overview-repaired-original-row-remains-paused");

    await common.clear_and_type(page, ".hover-pipeline-index-search", "No matching pipeline");
    await page.waitForSelector(".hover-pipeline-empty", {visible: true});
    await capture_audit(page, "overview-empty-list");

    const pipeline_fixture = {pipelines: [], topics: [], can_create: false};
    const intercept_pipeline_api = async (request: HTTPRequest): Promise<void> => {
        if (new URL(request.url()).pathname === "/json/hover/pipelines") {
            await request.respond({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({result: "success", msg: "", ...pipeline_fixture}),
            });
            return;
        }
        await request.continue();
    };
    await page.setRequestInterception(true);
    const request_handler = (request: HTTPRequest): void => {
        void intercept_pipeline_api(request);
    };
    page.on("request", request_handler);
    await reload_pipelines(page);
    await page.waitForSelector(".hover-pipeline-permission-limited", {visible: true});
    await capture_audit(page, "overview-permission-limited");
    page.off("request", request_handler);
    await page.setRequestInterception(false);
}

await common.run_test(pipeline_creation_test);

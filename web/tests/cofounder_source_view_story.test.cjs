"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_source_view = require("../templates/hover_source_view.hbs");

const {run_test} = require("./lib/test.cjs");

const project_root = path.resolve(__dirname, "../..");
const component_css = fs.readFileSync(
    path.join(project_root, "web/styles/cofounder/components/source-view.css"),
    "utf8",
);
const story_source = fs.readFileSync(
    path.join(project_root, "web/stories/cofounder_source_view.stories.ts"),
    "utf8",
);

run_test("Source browser connects search, status, and record-list semantics", () => {
    const html = render_source_view({
        date_groups: [],
        empty_hint: "",
        empty_icon: "archive",
        has_error: false,
        is_empty: false,
        provider_icon: "phone",
        is_loading: false,
        query: "",
        show_load_older: false,
        show_retry: false,
        source: {
            account_display_name: "Operations",
            display_name: "Venue team",
            is_history_retained: true,
            source_type: "WhatsApp group",
        },
        space_name: "AIMTO Events",
        status: "2 Source records shown.",
    });

    assert.match(
        html,
        /id="cf-source-search"[\s\S]*aria-controls="cf-source-record-list"[\s\S]*aria-describedby="cf-source-view-status"/,
    );
    assert.match(
        html,
        /class="cf-source-view__status"[\s\S]*id="cf-source-view-status"[\s\S]*role="status"[\s\S]*aria-atomic="true"/,
    );
    assert.match(
        html,
        /id="cf-source-record-list"[\s\S]*role="list"[\s\S]*aria-label="(?:translated: )?Source records"[\s\S]*aria-busy="false"/,
    );
    assert.match(html, /Read-only records/);
});

run_test("Source browser exposes the record-list loading lifecycle", () => {
    const html = render_source_view({
        date_groups: [],
        empty_hint: "",
        empty_icon: "archive",
        has_error: false,
        is_loading: true,
        is_empty: false,
        provider_icon: "phone",
        query: "",
        show_load_older: false,
        show_retry: false,
        source: {
            account_display_name: "Operations",
            display_name: "Venue team",
            is_history_retained: false,
            source_type: "WhatsApp group",
        },
        space_name: "AIMTO Events",
        status: "Loading Source records…",
    });

    assert.match(html, /cf-icon--spinner cf-source-view__loading-indicator/);
    assert.match(html, /aria-busy="true"/);
    assert.match(story_source, /is_loading: mode === "loading"/);
});

run_test("Retry state is named, visually distinct, and recoverable in Storybook", () => {
    const html = render_source_view({
        date_groups: [],
        empty_hint: "",
        empty_icon: "archive",
        has_error: true,
        is_loading: false,
        is_empty: false,
        provider_icon: "phone",
        query: "",
        show_load_older: false,
        show_retry: true,
        source: {
            account_display_name: "Operations",
            display_name: "Venue team",
            is_history_retained: false,
            source_type: "WhatsApp group",
        },
        space_name: "AIMTO Events",
        status: "Source records are temporarily unavailable. Try again.",
    });

    assert.match(html, /cf-source-view__status cf-source-view__status--error/);
    assert.match(html, /cf-source-view__error-indicator/);
    assert.match(html, /aria-label="(?:translated: )?Retry loading Source records"/);
    assert.match(story_source, /setup_retry_story/);
    assert.match(story_source, /Source records restored\. 2 records shown\./);
    assert.match(story_source, /status\.classList\.remove\("cf-source-view__status--error"\)/);
    assert.match(story_source, /retry\.remove\(\)/);
    assert.match(story_source, /heading\.focus\(\)/);
});

run_test("Empty Source story distinguishes history from query no-results", () => {
    const html = render_source_view({
        date_groups: [],
        empty_hint: "Records will appear after history imports.",
        empty_icon: "archive",
        has_error: false,
        is_empty: true,
        is_loading: false,
        provider_icon: "phone",
        query: "",
        show_load_older: false,
        show_retry: false,
        source: {
            account_display_name: "Operations",
            display_name: "Venue team",
            is_history_retained: false,
            source_type: "WhatsApp group",
        },
        space_name: "AIMTO Events",
        status: "This Source has no records in its confirmed history.",
    });

    assert.match(html, /cf-source-view__status--empty/);
    assert.match(html, /cf-source-view__empty-indicator/);
    assert.match(html, /Records will appear after history imports\./);
    assert.match(
        component_css,
        /\.cf-source-view__status--empty \{[\s\S]*box-sizing: border-box;[\s\S]*min-height: 148px;/,
    );
    assert.match(story_source, /setup_empty_story/);
    assert.match(story_source, /No records match “\$\{query\}”\./);
    assert.match(story_source, /Press Search to check this Source\./);
    assert.match(story_source, /Try a different search phrase\./);
    assert.match(story_source, /This Source has no records in its confirmed history\./);
});

run_test("Populated Source browser story models search and pagination outcomes", () => {
    assert.match(story_source, /case "populated":[\s\S]*setup_populated_story\(canvas\)/);
    assert.match(story_source, /search\.value\.trim\(\)\.replaceAll\(\/\\s\+\/g, " "\)/);
    assert.match(story_source, /No records match this search\./);
    assert.match(story_source, /Source \$\{visible_count === 1 \? "record" : "records"\} shown\./);
    assert.match(story_source, /event\.key === "Enter"/);
    assert.match(story_source, /render_source_record\(older_record\)/);
    assert.match(story_source, /1 older Source record loaded\./);
    assert.match(story_source, /record_list\.prepend\(section\)/);
    assert.match(story_source, /heading\.focus\(\)/);
});

run_test("Source browser contains hostile imported text at each layout boundary", () => {
    assert.match(component_css, /\.cf-source-view__shell \{[\s\S]*min-width: 0;/);
    assert.match(component_css, /\.cf-source-view__breadcrumb \{[\s\S]*overflow-wrap: anywhere;/);
    assert.match(component_css, /\.cf-source-view__title-row h1 \{[\s\S]*overflow-wrap: anywhere;/);
    assert.match(component_css, /\.cf-source-view__metadata \{[\s\S]*flex-wrap: wrap;/);
    assert.match(component_css, /\.cf-source-record__header \{[\s\S]*flex-wrap: wrap;/);
    assert.match(component_css, /\.cf-source-record__reply span \{[\s\S]*overflow-wrap: anywhere;/);
    assert.match(component_css, /\.cf-source-record__media \{[\s\S]*flex-wrap: wrap;/);
    assert.match(
        component_css,
        /\.cf-source-record__media-unavailable \{[\s\S]*color: var\(--cf-color-danger-hover\);/,
    );
    assert.doesNotMatch(component_css, /var\(--(?:ds|hover)-|#[0-9a-f]{3,8}\b|hsl\(/i);
});

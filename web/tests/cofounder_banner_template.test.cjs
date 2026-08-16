"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_banner = require("../templates/components/banner.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("renders the standalone Cofounder banner contract", () => {
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/banner.stories.ts"),
        "utf8",
    );
    const story_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");
    const html = render_banner({
        buttons: [
            {label: "Review", variant: "secondary"},
            {custom_classes: "dismiss-example", label: "Dismiss", variant: "ghost"},
        ],
        close_button: true,
        intent: "warning",
        label: "A source needs review.",
        process: "source-review",
    });

    assert.match(html, /role="alert"/);
    assert.match(html, /aria-atomic="true"/);
    assert.match(html, /data-process="source-review"/);
    assert.match(html, /class="cf-banner cf-banner--warning"/);
    assert.match(html, /class="cf-banner__content"/);
    assert.match(html, /class="cf-banner__label"/);
    assert.match(html, /class="cf-banner__actions"/);
    assert.match(html, /cf-button--secondary/);
    assert.match(html, /cf-button--ghost dismiss-example/);
    assert.match(html, /cf-button--ghost cf-button--icon-only cf-banner__close/);
    assert.match(html, /<svg class="cf-icon"/);
    assert.doesNotMatch(html, /action-button/);
    assert.doesNotMatch(html, /icon-button/);
    assert.doesNotMatch(html, /zulip-icon/);
    assert.doesNotMatch(html, /class="(?:[^"]+ )?banner(?: |")/);
    assert.match(story_source, /render_banner_playground/);
    assert.match(story_source, /Banner dismissed/);
    assert.match(story_source, /Banner restored/);
    assert.match(story_source, /\.cf-banner__actions button/);
    assert.match(story_source, /render_banner_intents/);
    assert.match(story_source, /Cofounder has a new activity summary/);
    assert.match(story_source, /Review the activity summary before sharing it/);
    assert.match(story_source, /The activity summary could not be published/);
    assert.match(story_source, /storybook-banner-intent__heading/);
    assert.match(story_source, /Show \$\{intent\} banner/);
    assert.match(story_css, /\.storybook-banner-playground__feedback:empty/);
    assert.match(story_css, /\.storybook-banner-playground__restore\.cf-button/);
    assert.match(story_css, /\.storybook-banner-intent\s*{/);
    assert.match(story_css, /grid-template-columns: 72px minmax\(0, 1fr\)/);
    assert.match(story_css, /\.storybook-banner-intents__feedback:empty/);
    assert.match(story_source, /render_navbar_banner/);
    assert.match(story_source, /Workspace navigation banner example/);
    assert.match(story_source, /Review policy/);
    assert.match(story_source, /Navigation banner dismissed/);
    assert.match(story_source, /Navigation banner restored/);
    assert.match(story_css, /\.storybook-navbar-banner__surface\s*{/);
    assert.match(story_css, /\.storybook-navbar-banner__boundary\s*{/);
    assert.match(story_css, /container: banner \/ inline-size/);
    assert.match(story_css, /\.storybook-navbar-banner__feedback:empty/);
    assert.match(
        fs.readFileSync(path.join(__dirname, "../styles/cofounder/components/banner.css"), "utf8"),
        /\.cf-banner\[hidden\]\s*{\s*display: none/,
    );
    assert.match(story_source, /render_popup_banner/);
    assert.match(story_source, /Popup banner placement example/);
    assert.match(story_source, /buttons: \[\]/);
    assert.match(story_source, /process: "changes-saved"/);
    assert.match(story_source, /animationend/);
    assert.match(story_source, /animationDuration/);
    assert.match(story_source, /Popup banner dismissed/);
    assert.match(story_source, /Popup banner restored/);
    assert.match(story_css, /\.storybook-popup-banner__viewport\s*{/);
    assert.match(story_css, /\.storybook-popup-banner__workspace\s*{\s*box-sizing: border-box/);
    assert.match(story_css, /\.storybook-popup-banner__region\.cf-feedback-region/);
    assert.match(story_css, /\.storybook-popup-banner__feedback:empty/);
});

run_test("uses a polite status role for non-urgent feedback", () => {
    const html = render_banner({
        buttons: [],
        close_button: false,
        intent: "success",
        label: "Source saved.",
    });

    assert.match(html, /role="status"/);
    assert.match(html, /cf-banner--success/);
    assert.doesNotMatch(html, /cf-banner__close/);
});

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_toast = require("../templates/cofounder/components/toast.hbs");
const render_feedback_container = require("../templates/feedback_container.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("renders the standalone Cofounder toast contract", () => {
    const html = render_toast({
        has_undo_button: true,
        intent: "danger",
        message: "The reminder could not be scheduled.",
        title: "Something went wrong",
        undo_button_text: "Undo",
    });

    assert.match(html, /role="alert"/);
    assert.match(html, /aria-atomic="true"/);
    assert.match(html, /class="cf-toast cf-toast--danger"/);
    assert.match(html, /class="cf-toast__header"/);
    assert.match(html, /<div class="cf-toast__title">Something went wrong<\/div>/);
    assert.doesNotMatch(html, /<h2 class="cf-toast__title"/);
    assert.match(html, /class="cf-toast__actions"/);
    assert.match(html, /cf-button--secondary cf-toast__undo/);
    assert.match(html, /cf-button--ghost cf-button--icon-only cf-toast__close/);
    assert.match(html, /class="cf-toast__content"/);
    assert.match(html, /<svg class="cf-icon"/);
    assert.doesNotMatch(html, /action-button/);
    assert.doesNotMatch(html, /icon-button/);
    assert.doesNotMatch(html, /zulip-icon/);
    assert.doesNotMatch(html, /feedback_(?:title|content|undo)/);
});

run_test("keeps the Cofounder toast story actions demonstrable", () => {
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_toast.stories.ts"),
        "utf8",
    );

    assert.match(story_source, /Dismiss \$\{title\.textContent\?\.trim\(\)/);
    assert.match(story_source, /intent: "brand"/);
    assert.match(story_source, /intent: "info"/);
    assert.match(story_source, /\.cf-toast__close, \.cf-toast__undo/);
    assert.match(story_source, /toast\.classList\.add\("cf-toast--leaving"\)/);
    assert.match(story_source, /toast\.addEventListener\([\s\S]*"animationend"/);
    assert.match(story_source, /toast\.remove\(\)/);
    assert.match(story_source, /next_control\?\.focus\(\)/);
    const css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/toast.css"),
        "utf8",
    );
    assert.match(css, /\.cf-toast__close\.cf-button \{[\s\S]*align-self: start;/);
    assert.doesNotMatch(
        css,
        /\.cf-toast__close\.cf-button \{[\s\S]*margin: calc\(-1 \* var\(--cf-space-1\)\);/,
    );
});

run_test("adapts the feedback widget to a polite Cofounder toast", () => {
    const html = render_feedback_container({has_undo_button: true});

    assert.match(html, /role="status"/);
    assert.match(html, /class="cf-toast cf-toast--neutral"/);
    assert.match(html, /cf-toast__undo/);
    assert.match(html, /cf-toast__close/);
    assert.doesNotMatch(html, /feedback-container-content-wrapper/);
    assert.doesNotMatch(html, /exit-me/);
});

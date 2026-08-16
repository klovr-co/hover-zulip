"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {run_test} = require("./lib/test.cjs");

const story_source = fs.readFileSync(
    path.join(__dirname, "../stories/conversation_screen.stories.ts"),
    "utf8",
);
const story_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");
const left_sidebar_source = fs.readFileSync(
    path.join(__dirname, "../templates/left_sidebar.hbs"),
    "utf8",
);

run_test("Conversation screen composes a named legacy-free workspace", () => {
    assert.match(story_source, /import render_icon/);
    assert.match(story_source, /render_icon\(\{compact: true, name: "hash"\}\)/);
    assert.doesNotMatch(story_source, /zulip-icon|<i(?:\s|>)/);
    assert.match(story_source, /conversation-dm-unread-1/);
    assert.match(story_source, /conversation-people-unread-1/);
    assert.match(story_source, /user_actions_label: `User actions for \$\{name\}`/);
    assert.match(story_source, /presence_label: presence === "active"/);
    assert.match(story_source, /aria-label", "Conversation: design \/ Homepage redesign"/);
    assert.match(story_source, /role="list" aria-label="Messages in design \/ Homepage redesign"/);
    assert.match(
        story_source,
        /aside class="storybook-right-sidebar right-sidebar" aria-label="People"/,
    );
    assert.match(story_source, /<h2>People<\/h2>/);
    assert.match(left_sidebar_source, /input_button_aria_label=\(t "Clear navigation filter"\)/);
    assert.match(
        left_sidebar_source,
        /input_button_aria_label=\(t "Clear direct message filter"\)/,
    );
});

run_test("Conversation screen models filtering reactions and safe message sending", () => {
    assert.match(story_source, /initialize_conversation/);
    assert.match(story_source, /filter\.addEventListener\("input"/);
    assert.match(story_source, /Navigation filter cleared/);
    assert.match(story_source, /\.cf-message-item__reaction/);
    assert.match(story_source, /reaction\.setAttribute\("aria-pressed"/);
    assert.match(story_source, /Reaction added/);
    assert.match(story_source, /escape_html\(value\)/);
    assert.match(story_source, /Message sent to design \/ Homepage redesign/);
    assert.match(story_source, /Write a message before sending/);
    assert.match(story_source, /role", "status"/);
    assert.match(story_source, /aria-live", "polite"/);
    assert.match(story_source, /aria-atomic", "true"/);
});

run_test("Conversation screen bounds messages and composer in flex flow", () => {
    assert.match(story_css, /\.storybook-message-pane\s*{[^}]*display: flex/s);
    assert.match(story_css, /\.storybook-message-pane\s*{[^}]*flex-direction: column/s);
    assert.match(
        story_css,
        /\.storybook-message-pane \.message-list\s*{[^}]*box-sizing: border-box/s,
    );
    assert.match(story_css, /\.storybook-message-pane \.message-list\s*{[^}]*width: 100%/s);
    assert.match(story_css, /\.storybook-message-pane \.message-list\s*{[^}]*overflow-y: auto/s);
    assert.match(story_css, /\.storybook-compose\s*{[^}]*position: relative/s);
    assert.match(story_css, /\.storybook-compose\s*{[^}]*flex: none/s);
    assert.match(story_css, /\.storybook-conversation-feedback:empty/);
    assert.match(story_css, /\.storybook-conversation-feedback:not\(:empty\)/);
});

run_test("Conversation screen progressively releases sidebars at intermediate widths", () => {
    assert.match(
        story_css,
        /@media \(width <= 1000px\)\s*{[^}]*\.storybook-conversation-screen\s*{[^}]*min-width: 0/s,
    );
    assert.match(
        story_css,
        /@media \(width <= 900px\)\s*{[^}]*\.storybook-conversation-body > \.storybook-right-sidebar\s*{[^}]*display: none/s,
    );
    assert.match(
        story_css,
        /@media \(width <= 760px\)\s*{[^}]*\.storybook-conversation-body > \.left-sidebar\s*{[^}]*display: none/s,
    );
    assert.match(
        story_css,
        /@media \(width <= 760px\)[\s\S]*?\.storybook-message-pane\s*{[^}]*min-width: 0/s,
    );
});

run_test("Focused conversation keeps messages in a centered reading lane", () => {
    assert.match(story_source, /type ConversationArgs = {focused: boolean;/);
    assert.match(
        story_source,
        /classList\.toggle\("storybook-conversation-screen--focused", args\.focused\)/,
    );
    assert.match(
        story_source,
        /Focused: Story = {args: {focused: true, show_right_sidebar: false}}/,
    );
    assert.match(
        story_css,
        /\.storybook-conversation-screen--focused[\s\S]*?\.cf-message-item\s*{[^}]*width: min\(100%, var\(--cf-layout-content-width\)\)[^}]*margin-inline: auto/s,
    );
});

run_test("Narrow conversation is a self-contained viewport-safe composition", () => {
    assert.match(story_source, /narrow: boolean/);
    assert.match(
        story_source,
        /classList\.toggle\("storybook-conversation-screen--narrow", args\.narrow\)/,
    );
    assert.match(story_source, /args: {narrow: true, show_right_sidebar: false}/);
    assert.match(story_source, /defaultViewport: "mobile1"/);
    assert.match(
        story_css,
        /\.storybook-conversation-screen--narrow\s*{[^}]*width: min\(100%, 390px\)[^}]*min-width: 0/s,
    );
    assert.match(
        story_css,
        /\.storybook-conversation-screen--narrow > \.header,[\s\S]*?> \.storybook-right-sidebar\s*{[^}]*display: none/s,
    );
    assert.match(
        story_css,
        /height: min\(844px, calc\(100dvh - 2 \* var\(--cf-space-4\)\)\)[^}]*min-height: 0/s,
    );
    assert.match(
        story_css,
        /@media \(width <= 600px\)[\s\S]*?\.storybook-conversation-body\s*{[^}]*height: calc\(100dvh - 2 \* var\(--cf-space-4\)\)[^}]*min-height: 0/s,
    );
});

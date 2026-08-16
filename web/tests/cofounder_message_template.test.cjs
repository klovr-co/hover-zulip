"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_message = require("../templates/cofounder/components/message.hbs");
const render_single_message = require("../templates/single_message.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("message owns identity content actions and reactions", () => {
    const html = render_message({
        avatar_url: "/avatar.png",
        content_html: "A useful update.",
        has_reactions: true,
        reactions: [{count: 3, emoji: "👍", label: "thumbs up, 3", selected: true}],
        sender: "Ava",
        time: "10:32 AM",
    });

    assert.match(html, /class="cf-message-item(?:\s|")/);
    assert.match(html, /cf-message-item__sender[^>]*>Ava/);
    assert.match(html, /cf-message-item__content">A useful update/);
    assert.match(html, /cf-message-item__reaction--selected/);
    assert.match(html, /cf-message-item__reaction--selected[^>]*aria-pressed="true"/);
    assert.match(html, /cf-message-item__actions/);
    assert.match(html, /aria-label="translated: Message actions"/);
    assert.doesNotMatch(html, /message_row|zulip-icon|<i(?:\s|>)/);
});

run_test("production message row exposes the Cofounder message contract", () => {
    const html = render_single_message({
        include_sender: true,
        message_list_id: 1,
        sender_is_bot: true,
        small_avatar_url: "/avatar.png",
        timestr: "10:32 AM",
        msg: {
            content: "A production update.",
            failed_request: false,
            id: 42,
            is_stream: true,
            locally_echoed: false,
            message_reactions: [],
            reminders: [],
            sender_full_name: "Ava",
            sender_id: 7,
            sent_by_me: false,
            starred: false,
            unread: true,
            url: "#message-42",
        },
    });
    const template_source = ["single_message.hbs", "message_body.hbs", "message_avatar.hbs"]
        .map((file) => fs.readFileSync(path.join(__dirname, "../templates", file), "utf8"))
        .join("");
    const behavior_source = [
        "click_handlers.ts",
        "compose_reply.ts",
        "compose_validate.ts",
        "condense.ts",
        "copy_messages.ts",
        "echo.ts",
        "hotkey.ts",
        "message_actions_popover.ts",
        "message_list.ts",
        "message_list_hover.ts",
        "message_list_tooltips.ts",
        "message_list_view.ts",
        "message_lists.ts",
        "message_reminder.ts",
        "message_report.ts",
        "popover_menus_data.ts",
        "reactions.ts",
        "rows.ts",
        "user_card_popover.ts",
        "widgetize.ts",
    ]
        .map((file) => fs.readFileSync(path.join(__dirname, "../src", file), "utf8"))
        .join("");
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/message.css"),
        "utf8",
    );
    const action_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/message-actions.css"),
        "utf8",
    );
    const composition_css = fs.readFileSync(
        path.join(__dirname, "../styles/message_row.css"),
        "utf8",
    );
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_message_item.stories.ts"),
        "utf8",
    );
    const story_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");

    assert.match(html, /class="cf-message-item(?:\s|")/);
    assert.match(html, /cf-message-item--with-sender/);
    assert.match(html, /cf-message-item--unread/);
    assert.match(html, /<button type="button" class="cf-message-item__sender/);
    assert.match(html, /class="cf-message-item__sender-name/);
    assert.match(html, /class="cf-message-item__time(?:\s|")/);
    assert.match(html, /class="cf-message-item__content(?:\s|")/);
    assert.match(html, /class="cf-message-item__avatar(?:\s|")/);
    assert.match(html, /cf-message-item__bot/);
    assert.match(html, /cf-message-item__unread-label">translated: Unread message/);
    assert.match(html, /<rect x="4" y="7" width="16" height="12" rx="3">/);
    assert.match(component_css, /\.cf-message-item--preview/);
    assert.match(
        component_css,
        /\.cf-message-item--preview \.cf-message-item__time\s*{[^}]*color: var\(--cf-text-secondary\)/s,
    );
    assert.match(
        component_css,
        /\.cf-message-item--preview \.cf-message-item__body\s*{[^}]*display: block/s,
    );
    assert.match(
        component_css,
        /\.cf-message-item--preview \.cf-message-item__content\s*{[^}]*grid-area: auto/s,
    );
    assert.match(component_css, /\.cf-message-item:not\(\.cf-message-item--preview\)/);
    assert.match(component_css, /\.cf-message-item__unread-label\s*{[^}]*clip-path: inset\(50%\)/s);
    assert.match(
        component_css,
        /\.cf-message-item:not\(\.cf-message-item--preview\) \.cf-message-item__time\s*{[^}]*var\(--cf-text-secondary\)/s,
    );
    assert.match(
        component_css,
        /\.cf-message-item:not\(\.cf-message-item--preview\) \.cf-message-item__time\s*{[^}]*max-width: 14ch;[^}]*text-overflow: ellipsis/s,
    );
    assert.match(
        component_css,
        /\.cf-message-item--with-sender[\s\S]*\.cf-message-item__sender:focus-visible\s*{[^}]*outline: 2px solid var\(--cf-focus\)/,
    );
    assert.match(
        action_css,
        /\.cf-message-actions__button\s*{[^}]*opacity: 0;[^}]*pointer-events: none/s,
    );
    assert.match(
        action_css,
        /\.cf-message-actions__button:focus-visible\s*{[^}]*pointer-events: auto/s,
    );
    assert.match(template_source, /role="status" aria-label="{{t 'Message sending' }}"/);
    assert.match(story_source, /cf-message-actions__star-button--selected/);
    assert.match(story_source, /role="status" aria-live="polite"/);
    assert.match(story_source, /storybook-cf-message-item--active/);
    assert.match(story_source, /defaultViewport: "mobile1"/);
    assert.match(story_source, /≤ 390 px/);
    assert.match(
        story_css,
        /\.storybook-cf-message-item--active \.cf-message-actions__button\s*{[^}]*opacity: 1;[^}]*pointer-events: auto/s,
    );
    assert.match(story_css, /width: min\(100%, 390px\)/);
    assert.match(story_css, /color: var\(--cf-color-accent-hover\)/);
    assert.doesNotMatch(
        html,
        /\b(?:message_row|messagebox-content|messagebox|recipient_row|selectable_row|private-message|message_content|message-time|message_sender|sender_name|sender_name_text|message-avatar|inline_profile_picture|inline-profile-picture-wrapper|slow-send-spinner|message_length_controller)\b/,
    );
    assert.doesNotMatch(template_source, /zulip-icon|\bfa(?:\s|-")|<i(?:\s|>)/);
    assert.doesNotMatch(
        behavior_source,
        /["'](?:div)?\.(?:message_row|messagebox-content|messagebox|recipient_row|selectable_row|private-message)\b|(?:hasClass|classList\.contains)\(["'](?:message_row|recipient_row|selectable_row)["']\)/,
    );
    assert.doesNotMatch(
        behavior_source,
        /["']\.(?:message_content|message-time|message_sender|sender_name|inline-profile-picture-wrapper|slow-send-spinner|message_length_controller)\b/,
    );
    assert.doesNotMatch(
        composition_css,
        /\.(?:message_row|messagebox-content|messagebox|recipient_row|selectable_row|private-message|message_content|message-time|message_sender|sender_name|sender_name_text|message-avatar|inline_profile_picture|slow-send-spinner|message_length_controller)\b/,
    );
});

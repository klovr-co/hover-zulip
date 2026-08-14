"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_message_controls = require("../templates/message_controls.hbs");
const render_message_controls_failed = require("../templates/message_controls_failed_msg.hbs");
const render_message_reactions = require("../templates/message_reactions.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("message actions and reactions use standalone Cofounder contracts", () => {
    const actions_html = render_message_controls({
        is_archived: false,
        msg: {locally_echoed: false, sent_by_me: false, starred: true},
    });
    const reactions_html = render_message_reactions({
        is_archived: false,
        msg: {
            message_reactions: [
                {
                    emoji_alt_code: true,
                    emoji_name: "thumbs_up",
                    is_realm_emoji: false,
                    label: "You reacted with thumbs up",
                    local_id: "unicode_emoji,1f44d",
                    selected: true,
                    vote_text: "3",
                },
            ],
        },
    });
    const failed_html = render_message_controls_failed();
    const behavior_source = [
        "../src/click_handlers.ts",
        "../src/echo.ts",
        "../src/emoji_picker.ts",
        "../src/hotkey.ts",
        "../src/message_actions_popover.ts",
        "../src/message_list_hover.ts",
        "../src/message_list_tooltips.ts",
        "../src/message_live_update.ts",
        "../src/popover_menus_data.ts",
        "../src/reactions.ts",
        "../src/tippyjs.ts",
    ]
        .map((file) => fs.readFileSync(path.join(__dirname, file), "utf8"))
        .join("");
    const action_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/message-actions.css"),
        "utf8",
    );
    const reaction_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/message-reactions.css"),
        "utf8",
    );
    const legacy_message_css = fs.readFileSync(
        path.join(__dirname, "../styles/message_row.css"),
        "utf8",
    );
    const legacy_reaction_css = fs.readFileSync(
        path.join(__dirname, "../styles/reactions.css"),
        "utf8",
    );
    const reaction_type_source = fs.readFileSync(
        path.join(__dirname, "../src/message_store.ts"),
        "utf8",
    );
    const reaction_type = reaction_type_source.match(
        /export type MessageCleanReaction = \{([\s\S]*?)\};/,
    );
    assert.notEqual(reaction_type, null);

    assert.match(actions_html, /<button[^>]+cf-message-actions__reaction-button/);
    assert.match(actions_html, /cf-message-actions__more-button[^>]+aria-haspopup="menu"/);
    assert.match(actions_html, /cf-message-actions__star-button--selected/);
    assert.match(actions_html, /aria-pressed="true"/);
    assert.match(reactions_html, /class="cf-message-reactions"/);
    assert.match(reactions_html, /cf-message-reaction--selected/);
    assert.match(reactions_html, /class="cf-message-reaction__count">3/);
    assert.match(reactions_html, /<button[^>]+cf-message-reactions__add/);
    assert.match(failed_html, /cf-message-actions__failed-button refresh-failed-message/);
    assert.match(failed_html, /<path d="M20 11a8 8 0 1 0-2\.3 5\.7"/);
    assert.match(behavior_source, /\.cf-message-actions__star-button/);
    assert.match(behavior_source, /cf-message-reaction--selected/);
    assert.match(behavior_source, /\.cf-message-reactions__add/);
    assert.match(reaction_type[1], /selected: boolean/);
    assert.doesNotMatch(reaction_type[1], /class: string/);
    assert.match(action_css, /\.cf-message-actions__button:focus-visible/);
    assert.match(action_css, /\.cf-message-actions__star-button--selected/);
    assert.match(reaction_css, /\.cf-message-reaction:disabled/);
    assert.match(reaction_css, /@media \(hover: none\)/);
    assert.doesNotMatch(action_css + reaction_css, /var\(--ds-/);
    assert.doesNotMatch(legacy_message_css, /\.message_controls\b/);
    assert.doesNotMatch(legacy_reaction_css, /\.message_reactions\b/);
    assert.doesNotMatch(
        actions_html + reactions_html + failed_html,
        /zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)|message_control_button|reaction_button|message_reaction(?:_container|_count)?|star_container|actions_hover|empty-star/,
    );
    assert.doesNotMatch(
        behavior_source,
        /["']\.(?:message_controls|message_control_button|reaction_button|message_reaction|star_container|actions_hover|message-actions-menu-button|emoji-message-control-button-container)\b/,
    );
});
